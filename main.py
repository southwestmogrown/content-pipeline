"""
main.py — CLI entry point for the content pipeline.

Usage:
    python main.py

The pipeline will interview you, write the article, generate a LinkedIn post,
and produce the Dev.to publishing package. All output is saved to output/[slug]/.
"""

import itertools
import os
import readline  # noqa: F401 — enables arrow-key editing in input()
import sys
import threading
import time

from langchain_core.messages import HumanMessage
from graph import build_graph, PipelineState, writer_node, social_node, publisher_node


def _spinner(stop: threading.Event) -> None:
    for ch in itertools.cycle("⠋⠙⠹⠸⠼⠴⠦⠧⠇⠏"):
        if stop.is_set():
            break
        sys.stdout.write(f"\r{ch} Thinking...")
        sys.stdout.flush()
        time.sleep(0.08)
    sys.stdout.write("\r" + " " * 20 + "\r")
    sys.stdout.flush()


def main():
    # Verify API key is set
    if not os.environ.get("ANTHROPIC_API_KEY"):
        print("Error: ANTHROPIC_API_KEY environment variable not set.")
        print("Set it with: export ANTHROPIC_API_KEY=your_key_here")
        return

    print("=" * 60)
    print("  Content Pipeline — Building With AI Agents series")
    print("=" * 60)
    print("\nStarting interview. Type your answers and press Enter.")
    print("The pipeline will ask questions until it has enough to write.")
    print("Type 'quit' at any time to exit.\n")

    graph = build_graph()

    # Initial state
    state: PipelineState = {
        "messages": [],
        "brief": {},
        "interview_complete": False,
        "article": "",
        "linkedin": "",
        "publisher_package": "",
        "slug": "",
    }

    # Kick off the interview with an opening message
    state["messages"] = [
        HumanMessage(content="I'm ready to write the next article in the series. Let's start.")
    ]

    # Run the interview loop
    while not state.get("interview_complete"):
        # Run one turn of the graph (stops after interviewer node)
        stop = threading.Event()
        t = threading.Thread(target=_spinner, args=(stop,), daemon=True)
        t.start()
        try:
            state = graph.invoke(state, {"recursion_limit": 10})
        finally:
            stop.set()
            t.join()

        # Get the last message (interviewer's question)
        last_message = state["messages"][-1]

        # If interview is complete, the interviewer output JSON — skip printing
        if state.get("interview_complete"):
            print("\n✓ Interview complete. Writing article...\n")
            break

        # Print the interviewer's question
        print(f"\nInterviewer: {last_message.content}\n")

        # Get user input
        user_input = input("You: ").strip()
        if not user_input:
            continue
        if user_input.lower() == "quit":
            print("Exiting.")
            return

        # Add user response to messages
        state["messages"].append(HumanMessage(content=user_input))

    # Run the rest of the pipeline (writer → social → publisher)
    state = {**state, **writer_node(state)}
    state = {**state, **social_node(state)}
    state = {**state, **publisher_node(state)}

    print("\n" + "=" * 60)
    print("  Pipeline complete.")
    print("=" * 60)
    print(f"\nSlug: {state['slug']}")
    print(f"Output: output/{state['slug']}/")
    print("\nNext steps:")
    print("  1. Review and edit article.md")
    print("  2. Review linkedin.md")
    print("  3. Follow the checklist in devto.md before publishing")


if __name__ == "__main__":
    main()
