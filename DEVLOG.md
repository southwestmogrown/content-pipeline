# DEVLOG

## 2026-03-14 — Pipeline debugging session

### Bug: Pipeline silently exited after interview completed

**Symptom:** After the interviewer said "I'll get started," nothing happened.

**Root cause:** The LLM responded conversationally instead of outputting JSON. `json.loads()` failed, `interview_complete` stayed `False`, and `should_continue_interview` returned `END` — killing the graph silently.

**Fixes:**
- `graph.py`: `should_continue_interview` now returns `"interviewer"` (loop) instead of `END` when interview is incomplete — then reverted (see below).
- `prompts/interviewer.md`: Added explicit instruction not to send conversational sign-offs when the interview is done.

---

### Bug: `GraphRecursionError` — limit of 3 reached

**Symptom:** `langgraph.errors.GraphRecursionError: Recursion limit of 3 reached without hitting a stop condition.`

**Root cause:** After fixing the loop edge, the graph now looped internally. The recursion limit of 3 in `main.py` was hit immediately. Also revealed an architectural conflict: `main.py` already owns the interview loop externally via a `while` loop, so the graph should not loop internally.

**Fixes:**
- `graph.py`: Reverted internal loop edge — `should_continue_interview` returns `END` for incomplete interviews, matching the original intent.
- `main.py`: Increased `recursion_limit` from `3` to `10` to give each graph invoke adequate headroom.

---

### Bug: Interview complete but pipeline hung at `You:` prompt

**Symptom:** Interviewer printed a JSON block, but the pipeline printed `Interviewer: ```json...` and waited for user input.

**Root cause:** The LLM wrapped the JSON in markdown code fences (` ```json ``` `), causing `json.loads()` to fail. `interview_complete` stayed `False`, so the while loop continued and printed the JSON as a question.

**Fixes:**
- `graph.py`: Added fence-stripping logic in `interviewer_node` before attempting `json.loads()`. Strips the opening ` ``` ` or ` ```json ` line and closing ` ``` ` before parsing.
- `prompts/interviewer.md`: Added explicit instruction: raw JSON only, first character must be `{`, no markdown fences.

---

### Bug: Second hang — `interview_complete` never set to `True`

**Symptom:** Even with fence-stripping working, the pipeline still hung after the interviewer output valid JSON.

**Root cause:** The LLM omitted `"interview_complete": true` from the JSON output. `brief.get("interview_complete", False)` returned `False`, so the while loop never exited.

**Fix:**
- `prompts/interviewer.md`: Added explicit instruction that the JSON must include `"interview_complete": true` as a top-level field, and that without it the pipeline cannot proceed.

---

### Enhancement: No visibility into writing phase

**Symptom:** After the interview completed and writing began, the terminal went silent. No way to tell if the pipeline was running or frozen.

**Fix:**
- `graph.py`: Added `print(..., flush=True)` status lines at the start of `writer_node`, `social_node`, and `publisher_node`.
- `main.py`: Removed the now-redundant `print("Writing article...")` line since the node itself prints status.

---

## 2026-03-14 — Code review and systematic fix pass

Formal code review conducted using the `code-review` skill. Six issues identified across three channels (Correctness, Reliability, Configuration). Fixes executed in three sequential waves using parallel sub-agents where file overlap allowed.

### Bug: Brief always empty; output always saved to `output/article/`

**Root cause:** `interviewer_node` extracted the brief with `brief.get("article", {})`, expecting a nested `"article"` key. The LLM never produces one — the JSON is always flat. Every run wrote an empty brief to state and saved output to `output/article/`.

**Fix:**
- `graph.py`: Removed `.get("article", {})` indirection. Brief is now stored as the full parsed JSON object. Slug derived from `brief.get("slug", "article")`.
- `prompts/interviewer.md`: Added `slug` as a required top-level field in the output JSON schema.

---

### Bug: Interviewer re-ran on every writing phase invoke

**Root cause:** After the interview loop, `main.py` called `graph.invoke(state)` to run writer → social → publisher. Because `"interviewer"` is the graph entry point, this always executed one extra interviewer LLM call before the conditional edge routed to `"writer"`. Wasted an API call per run and had already caused a failure when the LLM returned conversational text on re-entry.

**Fix:**
- `main.py`: Replaced `graph.invoke(state)` with direct sequential calls to `writer_node`, `social_node`, and `publisher_node`. Updated import to include the three node functions.
- This also resolved the configuration issue (no recursion limit on the final invoke) as a side effect — the invoke no longer exists.

---

### Bug: `ANTHROPIC_API_KEY` guard was unreachable

**Root cause:** `graph.py` instantiated `llm` at module level using `os.environ["ANTHROPIC_API_KEY"]`. Importing `graph` crashed with `KeyError` before `main()` ever ran, making the clean error message in `main.py` unreachable.

**Fix:**
- `graph.py`: Changed to `os.environ.get("ANTHROPIC_API_KEY", "")` so the module imports cleanly and the guard in `main.py` runs first.

---

### Enhancement: `load_prompt` now raises a descriptive error on missing files

**Previous behavior:** Missing prompt file raised a generic `FileNotFoundError` buried in a LangGraph traceback.

**Fix:**
- `graph.py`: `load_prompt` now checks `path.exists()` and raises `FileNotFoundError(f"Prompt file not found: {path}")` with the full path before attempting to read.

---

### Enhancement: `response.content` normalized in all nodes

**Previous behavior:** `interviewer_node` normalized list-type content blocks to a string. `writer_node`, `social_node`, and `publisher_node` did not — a list response would corrupt state or crash `write_text()`.

**Fix:**
- `graph.py`: Extracted normalization into a shared `extract_text()` helper. Applied to all four nodes.
