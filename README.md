# content-pipeline

> A LangGraph-powered CLI that interviews you about an article, then writes the full draft, LinkedIn post, and Dev.to publishing package in one pass.

Built for the "Building With AI Agents" series on Dev.to. Instead of manually outlining, drafting section by section, and assembling a publishing package, you answer a few targeted interview questions and the pipeline handles the rest.

---

## Features

- **Conversational interview** — Claude asks targeted questions one or two at a time until it has everything it needs to write
- **Full article generation** — produces a complete, publish-ready markdown draft written in your voice
- **LinkedIn post** — tailored social copy extracted from the finished article
- **Dev.to publishing package** — formatted output with tags, excerpt, cover image prompt, and a pre-publish checklist
- **Organized output** — all files saved to `output/[slug]/` automatically

---

## Tech Stack

| Layer | Technology |
|---|---|
| Language | Python 3.11 |
| Framework | LangGraph |
| LLM | Claude (`claude-sonnet-4-20250514`) |
| LLM Client | langchain-anthropic |
| Package Manager | pip |

---

## Getting Started

### Prerequisites

- Python 3.11+
- An Anthropic API key

### Installation

```bash
# Clone the repo
git clone https://github.com/southwestmogrown/content-pipeline
cd content-pipeline

# Install dependencies
pip install -r requirements.txt

# Set your API key
export ANTHROPIC_API_KEY=your_key_here

# Run the pipeline
python main.py
```

---

## Usage

Run `python main.py` and answer the interviewer's questions. The pipeline asks one or two questions at a time until it has enough to write. When the interview is complete, it transitions automatically — no input needed.

```
$ python main.py

============================================================
  Content Pipeline — Building With AI Agents series
============================================================

Starting interview. Type your answers and press Enter.
The pipeline will ask questions until it has enough to write.
Type 'quit' at any time to exit.

Interviewer: Which article in the series are we working on today?
You: Article 4 — the full GitHub issue to PR workflow...

[interview continues until brief is complete]

✓ Interview complete. Writing article...

✍  Writing article...
📣  Writing LinkedIn post...
📦  Building Dev.to package...

✓ Output saved to output/github-issue-to-pr/
  - brief.json
  - article.md
  - linkedin.md
  - devto.md
```

Type `quit` at any `You:` prompt to exit without saving.

---

## Output Structure

```
output/
└── [article-slug]/
    ├── brief.json    — structured interview brief
    ├── article.md    — full article draft
    ├── linkedin.md   — standalone LinkedIn post
    └── devto.md      — Dev.to publishing package and checklist
```

---

## Architecture

Single LangGraph state machine (`graph.py`) with four nodes running sequentially:

```
START → interviewer → writer → social → publisher → END
```

The interviewer runs once per turn via an external loop in `main.py`, gating on a structured JSON brief. When the brief is complete, the graph transitions to the writer and runs through to the publisher in one pass. All prompts live in `/prompts/` as markdown files loaded at runtime.

| File | Purpose |
|---|---|
| `main.py` | CLI entry point and interview loop |
| `graph.py` | LangGraph state machine and all node definitions |
| `prompts/` | Agent prompt files (markdown) |
| `output/` | Generated output, organized by slug |
| `templates/` | JSON schemas |
| `skills/` | Reusable Claude skill definitions |

---

## Customizing for Your Own Use

The prompts in `/prompts/` are where all voice and convention logic lives. To adapt this pipeline for your own content:

| Prompt | What to change |
|---|---|
| `interviewer.md` | Series context, roadmap, and interview questions |
| `writer.md` | Voice, formatting rules, and series conventions |
| `social.md` | LinkedIn post format and tone |
| `publisher.md` | Dev.to package format and checklist |

The graph itself (`graph.py`) doesn't need to change.

---

## Roadmap

- [ ] Streaming output during LLM generation steps
- [ ] Resume interrupted sessions from a saved brief
- [ ] Multi-article batch mode
- [ ] Draft revision pass via follow-up prompt


hello world
---

## License

MIT
