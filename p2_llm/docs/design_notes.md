# P2 design notes (Sprints 1–5)

## 1. Which tasks need an LLM/VLM and which don't (S1 D1)

| Question | Authority | LLM involved? |
|---|---|---|
| Is this box a component? Where is it? | P1 detector | No |
| What text is written in the box? | OCR (Tesseract) first | VLM only to fix or confirm unreadable text |
| What *type* is it (service/db/queue…)? | Label dictionary baseline → **VLM** | Yes (semantic) |
| Is there an arrow A→B? | Geometry (P1/P3) | VLM confirms or rejects candidates and reads direction |
| Does A import B in code? | Static analysis (P3) | **Never** |
| Is A→B forbidden? | Conformance engine (P3) | **Never** |
| Which code module is diagram box "Order Svc"? | Exact → normalized → alias → token match | **LLM only for unresolved nodes**, picking from a shortlist |
| What role does this dependency play (Controller→Infrastructure)? | **LLM** (`dependency_role`) | Yes |
| Why was the violation introduced? | **LLM**, from the evidence package | Yes |
| Which commit introduced it? | Git ranking (P3) → **LLM** picks only from the supplied commits | Constrained |
| What is affected? | Graph traversal (P3 / `impact.compute_affected`) | LLM explains impact only for the computed set |
| How do we fix it? | **LLM**, then a deterministic rule check | Yes, and always validated |

## 2. Prompt + validation spec (S1 D2–D3)
- **Every prompt** has a SYSTEM block with the grounding rules and a USER block that contains `TASK:` and an `INPUT_JSON:` block. It must ask for exactly one JSON object.
- **Versions** are `declared+sha8(file)`. If anyone edits a prompt, the freeze lock breaks.
- **Validation ladder:**
  1. Local JSON repair: strip fences/prose, remove trailing commas, convert Python literals.
  2. Pydantic schema check (`extra="forbid"`, confidence in [0,1], enum vocabularies).
  3. Task validator (IDs exist, no invented components/commits, rule checks).
  4. Repair prompt with the exact errors, up to `max_repairs=2`.
  5. Abstain.
- **What abstention means:** a component gets `abstain=true`, a relation `status="uncertain"`, an alignment `UNCERTAIN`, RCA `UNCERTAIN`, and impact `UNCERTAIN`. A failed extraction falls back to `cv_only` with provenance `fallback:cv_only`.
- **Logging:** every attempt writes the raw output, parsed output, errors, repair steps, prompt version, provider/model, temperature, tokens, latency and cache flag to `runs/<run>/llm_calls.jsonl`.

## 3. Provider choice (S1 D4)
The gateway is provider-agnostic. Switching providers changes one block in `config/llm_config.json`.

| Option | Use for | Notes |
|---|---|---|
| Gemini (`kind: gemini`) | Main runs. Takes image input and has a JSON response mode. | Needs `GEMINI_API_KEY`. [Likely] Free-tier rate limits will throttle batch runs. The gateway retries 429s with backoff and caches responses. |
| Ollama / vLLM (`kind: openai_compatible`) | An open-weights baseline that runs offline and reproducibly | Use a vision model for extraction and any instruct model for RCA. Set `supports_images:false` for text-only models. |
| OpenAI / Groq | A second-model sensitivity check | Same OpenAI-compatible provider class. |
| Mock (`kind: mock`) | Tests and CI only | Deterministic heuristics. **Not a model, and its numbers are not results.** |

Model IDs live only in the config. Check your provider's current model list before you freeze. Pin one model for the main table and one for the sensitivity check (S9 D45).

## 4. CV → semantic handoff requirements (S3 D15, S4 D16)
For each detected box, P1 supplies `{id, bbox, class, confidence}`. P2 adds `ocr_text`, `ocr_conf` and `issues` (`no_text`, `low_ocr_conf`, `outside_box:*`, `ambiguous_text:*`) before calling the VLM. Semantic classification is still needed when:
- the OCR text has no dictionary hit (e.g. "Catalog API" could be an interface or a service);
- the name contains another type word ("User Service" vs "User"). The dictionary handles this with a head-noun rule, but icons still need the VLM;
- the type is shown by **shape or icon**, not text (cylinder = database, person = user, cloud = external);
- the OCR read is partial or misspelled (noisy scans);
- the edge type is `publishes_to`/`reads_from`/`contains`, which can only be told from dashed lines, labels or nesting.

## 5. Findings on the synthetic pilot (S2 D7, S3 D13). These are not research claims.
- **Page-level OCR misses most labels**, because box borders and arrows break Tesseract's layout analysis. **Per-component crop OCR**, trying 3 binarisation variants × PSM 6/7 and keeping the best, read 31/34 names exactly. All 3 misses are on the noisy S02 diagram, where the reads were partial ("Web", "Order", "Repository"). [Certain on these fixtures]
- **Preprocessing before crop OCR hurt label reading** (`runs/preprocess_compare/comparison.md`, mean exact-name rate): original 0.917 > gaussian 0.875 > median 0.870 > bilateral 0.847 > CLAHE 0.722 > adaptive threshold 0.553. [Certain on these fixtures] [Guessing] Real scanned diagrams may reverse this. Re-run `preprocess_compare` on the real pilot set before telling P1 to drop any of these steps.
- The dictionary baseline typed 13 of 15 prompt-dev components correctly. It missed two:
  - "Search Index" is drawn as a cylinder, so only the shape says it's a database.
  - "Catalog API" could be an interface or a service from the name alone.

  Both are cases where the VLM has to look at the image. [Certain on these fixtures]

## 6. Hard-case set (S3 D14)
Tag real diagrams with these categories. Keep at least 2 per category in `prompt_dev` and 2 in `held_out_test`.

| Tag | Example | Expected behaviour |
|---|---|---|
| `low_contrast_noise` | S02 (grey on grey + speckle) | partial OCR → VLM corrects, or the component abstains |
| `abbreviations` | S03 ("Pmt Svc", "Inv DB") | normalised names; alignment via ABBREVIATIONS |
| `icon_only` | person/cylinder/cloud icons with no text | type from shape; name from the nearby label (rule A2) |
| `overlapping_boxes` | nested containers | `contains` edges; text goes to the smallest box (rule A1) |
| `double_headed_or_undirected` | ↔ or plain lines | relation `uncertain` (R5) |
| `crossing_arrows` | arrows crossing other arrows | geometry candidates conflict → VLM decides or UNCERTAIN |
| `legend_present` | colour/line-style legends | few-shot conventions; don't treat the legend as components |
