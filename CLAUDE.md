# CLAUDE.md

> AI context file. Claude reads this automatically at the start of every session.

---

## Project Overview

**content-pipeline** — A LangGraph-powered CLI that interviews Shane about an
upcoming article, then automatically writes the full draft, LinkedIn post, and
Dev.to publishing package in one pass.

---

## Stack

| Layer | Technology |
|---|---|
| Language | Python 3.11 |
| Framework | LangGraph |
| LLM | Claude via Anthropic API (claude-sonnet-4-20250514) |
| LLM Client | langchain-anthropic |
| Package Manager | pip |

---

## Architecture

Single LangGraph state machine defined in `graph.py`. Four nodes run sequentially:
interviewer (loop until brief complete) → writer → social → publisher.
All agent prompts live in `/prompts/` as markdown files loaded at runtime.
All output is saved to `/output/[slug]/` at the end of the pipeline.

---

## Directory Structure

```
content-pipeline/
├── main.py          — CLI entry point
├── graph.py         — LangGraph state machine and all node definitions
├── prompts/         — Agent prompt files (markdown)
├── output/          — Generated article output, organized by slug
└── templates/       — JSON schemas (brief.json)
```

---

## Conventions

- All agent logic lives in `graph.py` — do not split into separate agent files
- Prompts are markdown files in `/prompts/` — edit prompts there, not inline in code
- State is typed via `PipelineState` TypedDict — add new fields there if needed
- Output files are always: `brief.json`, `article.md`, `linkedin.md`, `devto.md`
- Slug is derived from the article brief — always lowercase, hyphenated

---

## Anti-Patterns

- Do not hardcode prompts inline in `graph.py` — they belong in `/prompts/`
- Do not split `graph.py` into multiple files unless the file exceeds 300 lines
- Do not add a web UI layer without explicit instruction — CLI only for now
- Do not change the output file names — downstream tooling depends on them

---

## Running the Project

```bash
# Install dependencies
pip install -r requirements.txt

# Set your API key
export ANTHROPIC_API_KEY=your_key_here

# Run the pipeline
python main.py
```

---

## Agent Instructions

- Work only within the scope of the assigned issue
- Do not modify prompt files unless the issue explicitly involves prompt changes
- A completed issue includes the pipeline running end-to-end without errors
- Do not add new dependencies without flagging them first
