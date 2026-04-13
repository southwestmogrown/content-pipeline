# GitHub Issues

Findings from code review session 2026-03-14. Organized by channel with GitHub-ready issue bodies and a sequenced fix plan.

---

## Channels

- **Correctness** — bugs that cause wrong behavior or wrong data flowing through the pipeline
- **Reliability** — crashes, unhandled errors, and missing guards
- **Configuration** — settings that are wrong or missing

---

## Channel: Correctness

---

### Issue 1 — Brief is always empty; output always saves to `output/article/`

**Labels:** `bug` `correctness` `priority: high`

**Description**

The `interviewer_node` extracts the brief using `brief.get("article", {})`, expecting the LLM to return a JSON object with a nested `"article"` key. In practice, the LLM always returns a flat JSON object — there is no `"article"` wrapper. As a result, `state["brief"]` is always set to `{}` and `state["slug"]` always falls back to `"article"`.

Every downstream node (`writer`, `social`, `publisher`) operates on an empty brief. All output is written to `output/article/` regardless of the actual article topic.

**Location:** `graph.py:81, 83`

```python
"brief": brief.get("article", {}),   # always returns {}
"slug": brief.get("article", {}).get("slug", "article"),  # always returns "article"
```

**Steps to reproduce**
1. Run the pipeline end to end
2. Check `state["brief"]` after the interview — it will be `{}`
3. Check `output/` — directory will be named `article/`

**Expected behavior**
`state["brief"]` contains the full article brief. Output is saved to a slug derived from the article title.

**Fix**
Remove the `.get("article", {})` indirection. Use the top-level JSON object directly as the brief. Add a `slug` field to the interviewer prompt's required JSON schema and derive it with `brief.get("slug", "article")`.

```python
"brief": brief,
"interview_complete": brief.get("interview_complete", False),
"slug": brief.get("slug", "article"),
```

---

### Issue 2 — Second `graph.invoke` re-runs the interviewer node, wasting an API call and risking failure

**Labels:** `bug` `correctness` `priority: high`

**Description**

After the interview loop exits, `main.py` calls `graph.invoke(state)` to run the writing phase. Because the graph entry point is `"interviewer"`, this invoke always executes the interviewer node first — making a full LLM API call — before the conditional edge routes to `"writer"`. This wastes one API call per run and has already caused a production failure when the LLM returned a conversational response instead of JSON on that re-entry, silently breaking the pipeline.

**Location:** `main.py:74`, `graph.py:175`

```python
# main.py
state = graph.invoke(state)  # starts at interviewer, not writer

# graph.py
graph.set_entry_point("interviewer")  # always the entry point, no way to override
```

**Steps to reproduce**
1. Add logging to `interviewer_node`
2. Run the full pipeline
3. Observe that `interviewer_node` is called one extra time after the interview is complete

**Expected behavior**
The writing phase invokes `writer_node` directly — the interviewer is not called again.

**Fix**
Replace the second `graph.invoke` with direct sequential function calls for the three writing nodes, since they are pure functions with no branching logic:

```python
state = writer_node(state)
state = social_node(state)
state = publisher_node(state)
```

Alternatively, compile a second graph with `"writer"` as the entry point and invoke that for the writing phase.

> **Note:** Fix Issue 1 (empty brief) before validating this fix, so the writer receives correct data when testing.

---

## Channel: Reliability

---

### Issue 3 — `ANTHROPIC_API_KEY` guard in `main.py` is unreachable; import crashes first

**Labels:** `bug` `reliability` `priority: high`

**Description**

`main.py` checks for `ANTHROPIC_API_KEY` at line 18 and prints a clean error message if it's missing. However, line 13 imports `build_graph` from `graph`, which instantiates the `ChatAnthropic` client at module level using `os.environ["ANTHROPIC_API_KEY"]`. If the key is not set, this raises a `KeyError` during import — before `main()` is ever called. The user-facing guard never runs.

**Location:** `main.py:13`, `graph.py:47`

```python
# main.py:13 — import triggers module-level code in graph.py
from graph import build_graph, PipelineState

# graph.py:47 — crashes here with KeyError if key not set
api_key=os.environ["ANTHROPIC_API_KEY"],
```

**Steps to reproduce**
1. Unset `ANTHROPIC_API_KEY`
2. Run `python main.py`
3. Observe `KeyError` traceback instead of the clean error message

**Expected behavior**
```
Error: ANTHROPIC_API_KEY environment variable not set.
Set it with: export ANTHROPIC_API_KEY=your_key_here
```

**Fix**
Move the `llm` instantiation inside `build_graph()` so it doesn't execute at import time:

```python
def build_graph() -> StateGraph:
    llm = ChatAnthropic(
        model="claude-sonnet-4-20250514",
        api_key=os.environ["ANTHROPIC_API_KEY"],
        max_tokens=8096,
    )
    # pass llm into node closures or bind it here
    ...
```

---

### Issue 4 — Missing prompt file produces an unreadable LangGraph traceback

**Labels:** `bug` `reliability` `priority: medium`

**Description**

`load_prompt` reads a file from `/prompts/` with no existence check. If a prompt file is missing or misnamed, Python raises `FileNotFoundError` inside a node invocation. The user sees a deep LangGraph traceback with no clear indication that a missing file is the cause.

**Location:** `graph.py:37-38`

```python
def load_prompt(name: str) -> str:
    return (PROMPTS_DIR / f"{name}.md").read_text()
```

**Steps to reproduce**
1. Rename `prompts/writer.md` to `prompts/writer.md.bak`
2. Run the pipeline through the interview
3. Observe the traceback — the root cause is buried

**Expected behavior**
```
FileNotFoundError: Prompt file not found: /path/to/prompts/writer.md
```

**Fix**
```python
def load_prompt(name: str) -> str:
    path = PROMPTS_DIR / f"{name}.md"
    if not path.exists():
        raise FileNotFoundError(f"Prompt file not found: {path}")
    return path.read_text()
```

---

### Issue 5 — `response.content` type not normalized in writer, social, and publisher nodes

**Labels:** `bug` `reliability` `priority: medium`

**Description**

`interviewer_node` handles the case where `response.content` is a list of content blocks (lines 68-69). The other three nodes (`writer_node`, `social_node`, `publisher_node`) do not. If the Anthropic API returns a list of blocks for any of these — which can happen under certain token/tool-use configurations — `state["article"]`, `state["linkedin"]`, or `state["publisher_package"]` will be a Python list. This causes one of two silent failures:

- f-string interpolation in the next node will render as `[{'type': 'text', ...}]`
- `write_text()` in `publisher_node` will raise `TypeError: expected str, not list`

**Location:** `graph.py:111, 124, 142`

```python
return {"article": response.content}       # writer_node — not normalized
return {"linkedin": response.content}      # social_node — not normalized
package = response.content                 # publisher_node — not normalized
```

**Fix**
Extract the existing normalization logic from `interviewer_node` into a shared helper and call it in all nodes:

```python
def extract_text(content) -> str:
    if isinstance(content, list):
        return " ".join(
            block.get("text", "") if isinstance(block, dict) else str(block)
            for block in content
        )
    return content
```

---

## Channel: Configuration

---

### Issue 6 — Final `graph.invoke` has no recursion limit

**Labels:** `bug` `configuration` `priority: low`

**Description**

The interview loop invoke sets `recursion_limit: 10`. The final pipeline invoke that runs writer → social → publisher passes no config at all, falling back to LangGraph's default of 25. If a node fails silently and the graph loops unexpectedly, it will burn through 25 iterations before raising an error. The limit should be explicit and tight.

**Location:** `main.py:74`

```python
state = graph.invoke(state)  # no recursion_limit
```

**Fix**
```python
state = graph.invoke(state, {"recursion_limit": 5})
```

Writer + social + publisher is 3 nodes. A limit of 5 gives one retry margin and fails fast if something goes wrong. Note: if Issue 2 is fixed by replacing this invoke with direct function calls, this issue is resolved automatically.

---

## Fix Sequence

### Wave 1 — Run in parallel (no interdependencies)

All four can be worked simultaneously. Each touches a different function or file with no shared state.

| Issue | File | Scope |
|---|---|---|
| Issue 3 — Unreachable API key guard | `graph.py:45-49` | Move `llm` into `build_graph()` |
| Issue 4 — Missing prompt file traceback | `graph.py:37-38` | Add existence check to `load_prompt` |
| Issue 5 — `response.content` not normalized | `graph.py:111, 124, 142` | Extract helper, apply to 3 nodes |
| Issue 6 — No recursion limit on final invoke | `main.py:74` | Add `{"recursion_limit": 5}` |

---

### Wave 2 — After Wave 1 completes

Fix the brief data structure. This must come before Issue 2 because the correct brief content is needed to validate that the writing phase works end-to-end.

| Issue | File | Scope |
|---|---|---|
| Issue 1 — Brief always empty | `graph.py:81-83` + `prompts/interviewer.md` | Remove `article` wrapper, add `slug` field to JSON schema |

---

### Wave 3 — After Wave 2 completes

Fix the double-invoke architecture. Depends on Issue 1 being resolved so the writer receives real brief data during testing.

| Issue | File | Scope |
|---|---|---|
| Issue 2 — Interviewer re-runs on second invoke | `main.py:73-74` + `graph.py:175` | Replace second `graph.invoke` with direct node calls |

> **Note:** If Issue 2 is fixed via direct function calls (recommended), Issue 6 is automatically resolved and can be skipped.

---

## Summary

| # | Issue | Channel | Priority | Wave |
|---|---|---|---|---|
| 1 | Brief always empty | Correctness | High | 2 |
| 2 | Interviewer re-runs on second invoke | Correctness | High | 3 |
| 3 | API key guard unreachable | Reliability | High | 1 |
| 4 | Missing prompt file gives bad traceback | Reliability | Medium | 1 |
| 5 | `response.content` not normalized | Reliability | Medium | 1 |
| 6 | No recursion limit on final invoke | Configuration | Low | 1 (or skip if #2 fixed) |
