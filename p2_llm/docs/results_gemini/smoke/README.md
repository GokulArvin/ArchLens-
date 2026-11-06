# Real-model smoke test (Gemini Flash)

Real-model smoke test, config model gemini-3.5-flash (Google's quota error named gemini-3.6-flash, so it may be served as 3.6). 5/5 diagrams valid, 1 repair retry (S03), all finish_reason STOP, after the max_tokens fix (commit f345698). The full experiments are not run yet: the free tier allows 20 requests/day for this model.

## Files

- `smoke_output.txt`: console output of the final smoke run (`python -m archlens_llm.cli --config config/gemini.json smoke`).
- `llm_calls.jsonl`: every call logged in `runs/smoke` (28 lines), including the earlier failed attempts: HTTP 503 on gemini-3.8-flash, HTTP 404 on gemini-2.5-flash, and gemini-3.5-flash outputs truncated at the old 2048-token limit. The final run is the last 7 lines, the only ones with a `finish_reason` field.
