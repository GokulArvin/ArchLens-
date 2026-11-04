# Sprint 6: Graph Alignment & Conformance Uncertainty (D26-D30)

## D26 + D27: Mapping definition and matching features

`backend/app/modules/cv_pipeline/name_matching.py` defines the diagram-name
<-> code-identifier mapping: normalize both to a common token form
(camelCase/kebab-case/snake_case-aware), score token-set overlap (Jaccard),
suffix-stripped exact/substring matches (`cartservice` <-> `cart`), and a
component-`type` hint bonus (e.g. `database` + a `db`/`sql`/`repository`
token in the candidate). This is P1's half of the diagram-name <-> code-
module mapping (D26); P3 would supply the actual candidate identifier list
from static analysis of the real repo (file/directory names) - in this
solo-P1 track, D28 demonstrates that handoff concretely using real
repository listings fetched directly (see below).

## D28: Test on manually verified examples

Rather than invented test names, `backend/scripts/test_graph_alignment.py`
fetches the **real** `src/` directory listings (via the GitHub API) from two
of our diagram-paired repositories - `GoogleCloudPlatform/microservices-demo`
and `GoogleCloudPlatform/bank-of-anthos` - and matches our real manifest
component names against them. Every expected match was manually checked
against the actual diagram and the actual repository tree before being
recorded.

**Real result: 21/21 (100%) correct** on this set
(`experiments/baselines/sprint6_graph_alignment.json`).

This is a genuinely strong result, but an important caveat for honesty: both
chosen repos happen to use clean, diagram-matching directory naming
conventions (`cartservice`, `accounts-db`, etc.) - this is close to the
*easiest* case for name matching, not representative of harder diagrams in
our set like `dotnet_eshop` (nested service groups: "Identity Service" maps
to which of several real `src/Identity.API/`-style subpaths?) or
`spring_petclinic_microservices` ("UI + API Gateway" vs a real module
likely named something like `spring-petclinic-api-gateway`). Those cases
need the substring/Jaccard fallback this module provides (not just exact
suffix-stripped matches), but weren't empirically tested against real
repository listings this sprint due to time - flagged as follow-up for
Sprint 9's evaluation pass.

## D30: Visual overlays

`backend/scripts/render_alignment_overlay.py` renders each diagram with its
real component boxes labeled by their matched code module and score (green
= correct match, orange = matched but later found wrong, red = no match
above threshold). Output:
`experiments/results/sprint6_alignment_overlay_gcp_microservices_demo.png`
and `..._gcp_bank_of_anthos.png`. The one red ("no match") case -
`gcp_microservices_demo`'s "Redis cache" - is correct behavior, not a bug:
Redis is infrastructure, not a service directory in `src/`, so there is
genuinely no code module for it to align to.

## D29: Diagram-originated uncertainty and its effect on conformance

Three real sources of uncertainty compound as evidence flows from diagram
to conformance verdict, and the alignment `score` (D27) is the natural place
to carry that uncertainty forward rather than discarding it at a hard
threshold:

1. **Annotation/detection uncertainty** (Sprint 1 `docs/cv_failure_cases.md`,
   Sprint 3-4's near-zero pretrained-detector recall). If a diagram
   component's box/label itself is uncertain or wasn't reliably detected,
   any alignment built on it inherits that uncertainty - a conformance
   engine should propagate low upstream confidence into the final verdict's
   confidence, not treat a shaky detection as ground truth.
2. **Naming-convention mismatch** (this sprint's D28 caveat above). A
   diagram component whose name doesn't closely match any real code
   identifier isn't necessarily "missing" from the code - it may just use
   different vocabulary. A conformance engine should distinguish
   "no code module found" (alignment `score` is low/`None`) from "code
   module found, and a rule is violated" (alignment confident, rule
   actually broken) - collapsing these into one verdict would produce
   **UNCERTAIN** cases reported as hard **VIOLATION**s, a false-alarm risk.
3. **Many-to-one / one-to-many structure mismatches**. A single diagram box
   (e.g. `dotnet_eshop`'s "Identity Service") can correspond to several real
   code directories (API + worker + tests), or several diagram boxes could
   legitimately map to one shared code module. `best_match`'s current
   single-best-candidate design doesn't represent this; a future version
   should return ranked candidates above threshold, not just the top one,
   so a downstream conformance engine can represent **UNCERTAIN** instead
   of silently picking one.

**Recommendation for the (not-yet-built, P3/P4-owned) conformance engine**:
treat `MatchScore.score` as a first-class confidence value threaded through
to the final verdict, and reserve **UNCERTAIN** specifically for the
low-score/ambiguous-match cases above, rather than only for cases where no
candidate exists at all.
