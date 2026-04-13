"""
graph.py — LangGraph state machine for the content pipeline.

Flow:
  START → interviewer (loop) → writer → social → publisher → END
"""

import json
import os
from pathlib import Path
from typing import TypedDict, Annotated
from langgraph.graph import StateGraph, END
from langgraph.graph.message import add_messages
from langchain_anthropic import ChatAnthropic
from langchain_core.messages import HumanMessage, SystemMessage

# ---------------------------------------------------------------------------
# State
# ---------------------------------------------------------------------------

class PipelineState(TypedDict):
    messages: Annotated[list, add_messages]   # interview conversation history
    brief: dict                                # structured article brief
    interview_complete: bool                   # gate between interview and writing
    article: str                               # full article markdown
    linkedin: str                              # LinkedIn post
    publisher_package: str                     # Dev.to publishing package
    slug: str                                  # output folder name


# ---------------------------------------------------------------------------
# Load prompts
# ---------------------------------------------------------------------------

PROMPTS_DIR = Path(__file__).parent / "prompts"

def load_prompt(name: str) -> str:
    path = PROMPTS_DIR / f"{name}.md"
    if not path.exists():
        raise FileNotFoundError(f"Prompt file not found: {path}")
    return path.read_text()


def extract_text(content) -> str:
    """Normalize LLM response content to a plain string."""
    if isinstance(content, list):
        return " ".join(
            block.get("text", "") if isinstance(block, dict) else str(block)
            for block in content
        )
    return content


# ---------------------------------------------------------------------------
# LLM
# ---------------------------------------------------------------------------

llm = ChatAnthropic(
    model="claude-sonnet-4-20250514",
    api_key=os.environ.get("ANTHROPIC_API_KEY", ""),
    max_tokens=8096,
)


# ---------------------------------------------------------------------------
# Nodes
# ---------------------------------------------------------------------------

def interviewer_node(state: PipelineState) -> dict:
    """
    Runs one turn of the interview. Asks the next question or outputs
    the completed brief as JSON if enough information has been gathered.
    """
    system = load_prompt("interviewer")
    response = llm.invoke([
        SystemMessage(content=system),
        *state["messages"]
    ])

    content = extract_text(response.content)

    # Check if the interviewer has declared the brief complete
    # by attempting to parse the response as JSON (strip markdown fences if present)
    stripped = content.strip()
    if stripped.startswith("```"):
        stripped = stripped.split("\n", 1)[-1]
        stripped = stripped.rsplit("```", 1)[0].strip()
    try:
        brief = json.loads(stripped)
        return {
            "messages": [response],
            "brief": brief,
            "interview_complete": brief.get("interview_complete", False),
            "slug": brief.get("slug", "article"),
        }
    except json.JSONDecodeError:
        # Not done yet — still asking questions
        return {
            "messages": [response],
            "interview_complete": False,
        }


def should_continue_interview(state: PipelineState) -> str:
    """Conditional edge — continue interview or move to writing."""
    if state.get("interview_complete"):
        return "writer"
    return END


def writer_node(state: PipelineState) -> dict:
    """Takes the completed brief and writes the full article in one pass."""
    print("✍  Writing article...", flush=True)
    system = load_prompt("writer")
    brief_str = json.dumps(state["brief"], indent=2)

    response = llm.invoke([
        SystemMessage(content=system),
        HumanMessage(content=f"Here is the article brief:\n\n{brief_str}\n\nWrite the full article now.")
    ])

    return {"article": extract_text(response.content)}


def social_node(state: PipelineState) -> dict:
    """Takes the finished article and brief and produces a LinkedIn post."""
    print("📣  Writing LinkedIn post...", flush=True)
    system = load_prompt("social")
    brief_str = json.dumps(state["brief"], indent=2)

    response = llm.invoke([
        SystemMessage(content=system),
        HumanMessage(content=(
            f"Interview brief (Shane's actual words):\n\n{brief_str}\n\n"
            f"Finished article:\n\n{state['article']}\n\n"
            f"Write the LinkedIn post now."
        ))
    ])

    return {"linkedin": extract_text(response.content)}


def publisher_node(state: PipelineState) -> dict:
    """Produces the Dev.to publishing package and saves all output files."""
    print("📦  Building Dev.to package...", flush=True)
    system = load_prompt("publisher")
    brief_str = json.dumps(state["brief"], indent=2)

    response = llm.invoke([
        SystemMessage(content=system),
        HumanMessage(content=(
            f"Brief:\n\n{brief_str}\n\n"
            f"Article:\n\n{state['article']}\n\n"
            f"Produce the Dev.to publishing package now."
        ))
    ])

    package = extract_text(response.content)

    # Save all output files
    slug = state.get("slug", "article")
    output_dir = Path(__file__).parent / "output" / slug
    output_dir.mkdir(parents=True, exist_ok=True)

    (output_dir / "brief.json").write_text(json.dumps(state["brief"], indent=2))
    (output_dir / "article.md").write_text(state["article"])
    (output_dir / "linkedin.md").write_text(state["linkedin"])
    (output_dir / "devto.md").write_text(package)

    print(f"\n✓ Output saved to output/{slug}/")
    print(f"  - brief.json")
    print(f"  - article.md")
    print(f"  - linkedin.md")
    print(f"  - devto.md")

    return {"publisher_package": package}


# ---------------------------------------------------------------------------
# Build the graph
# ---------------------------------------------------------------------------

def build_graph() -> StateGraph:
    graph = StateGraph(PipelineState)

    graph.add_node("interviewer", interviewer_node)
    graph.add_node("writer", writer_node)
    graph.add_node("social", social_node)
    graph.add_node("publisher", publisher_node)

    graph.set_entry_point("interviewer")

    graph.add_conditional_edges(
        "interviewer",
        should_continue_interview,
        {
            END: END,
            "writer": "writer",
        }
    )

    graph.add_edge("writer", "social")
    graph.add_edge("social", "publisher")
    graph.add_edge("publisher", END)

    return graph.compile()
