# Sprint 7: Git Evidence & RCA Linkage (D31-D35)

## D31: Linking diagram nodes/edges to conformance report identifiers

`backend/scripts/demo_violation_evidence_chain.py` constructs a real
`ArchViolation` (from the already-shared `backend/app/schemas/models.py`
schema, not a new invented one) whose `source_component`/`target_component`
are the real `flask_microservice_demo` diagram's component ids (`backend`,
`orders`) - this *is* the diagram-node <-> conformance-report link: no
separate ID-mapping table is needed since the violation references the
manifest's own component ids directly.

**Important honesty check**: our own manifest already annotates
`backend -> orders` as an intended edge for this diagram (alongside
`backend -> aggregate -> orders`) - so per our own ground truth, this real
edge is CONFORMANT, not a violation. No conformance engine exists in this
solo-P1 track (that's P3/P4's Sprint 6 deliverable) to evaluate a real rule
against it anyway. To demonstrate the violation/evidence schema end to end,
the demo applies a hypothetical, explicitly counterfactual stricter rule
("backend may only reach orders through aggregate") that this real edge
*would* break if it were the actual rule - not a claim that this edge is
actually a problem. Everything attached to the resulting violation record
as *evidence*, however, is completely real.

## D32: Retrieving the affected code entity

`backend/app/modules/cv_pipeline/code_retrieval.py` reads the real current
file content (and a specific real line range) from the cloned repository.
Demonstrated against `backend/src/run.py:25-29` in the real
`mblitherland/flask-microservice-demo` repo (cloned via
`backend/scripts/clone_demo_repo.py` into `data/repositories/`, gitignored
like `backend/models/` since a nested git clone shouldn't be committed into
this repo's own history).

## D33: Candidate-commit retrieval

`backend/app/modules/cv_pipeline/git_evidence.py` uses Git's pickaxe search
(`git log -S<pattern>`) via GitPython to find real candidate commits, and
packages them into the shared `GitCommit`/`GitEvidence` schemas.

**Real finding during development**: an early version assumed "the oldest
pickaxe match is the introducing commit." Testing against the real repo
disproved this - searching for the generic pattern `"demo_orders"` returns
**two** real commits (the initial import *and* the commit that actually
added the new route), because `demo_orders` already appeared in the file
before the new route was added. Searching for a pattern specific to the
actual change (`"cust_search"`, the new route's function name) correctly
isolates **exactly one** commit. This is now documented directly in
`build_git_evidence`'s docstring and verified by
`backend/tests/unit/test_git_evidence.py::test_generic_pattern_finds_multiple_real_commits_honestly`
rather than silently assumed.

## D34: RCA test case with a known introducing commit

Ground truth: commit `d98872fcde8ae00f9df3224c1d5d4f08eb312429` ("Added a
new customer search endpoint", Michael Litherland, 2017-09-19), manually
verified via `git show d98872f` against the real cloned repo before being
encoded as a test assertion. `backend/tests/unit/test_git_evidence.py`
(6 tests, skipped gracefully if the clone hasn't been fetched) asserts the
specific-pattern search correctly and unambiguously identifies this exact
commit, and that the retrieved code genuinely contains the real route
handler.

## D35: Does diagram context change the RCA explanation?

Yes, concretely, in the real example above:

- **Without the diagram**: evidence-only Git mining can say "commit d98872f
  added a direct HTTP call from `backend` to `orders`." That's it - there's
  no basis for calling this a *violation* of anything, since Git history
  alone carries no notion of "intended" structure.
- **With the diagram**: the intended graph gives the RCA a concrete,
  specific **expected** value to contrast with the **actual** value, which
  is exactly what `ArchViolation.expected`/`.actual` are for - *if* the rule
  had been "route only through aggregate," the diagram is what tells us
  the architecturally correct alternative (`aggregate`'s existing
  `/detail/<id>` pattern), turning a vague "this dependency might be
  concerning" into an actionable recommendation.
- **Caveat, stated plainly**: this specific example is **not** a real
  violation. Our own diagram annotation already includes `backend -> orders`
  as an intended edge (verified directly against `data/annotations/manifest.json`
  and confirmed no `backend -> items` bypass exists in the real code either),
  so this edge is genuinely conformant per our own ground truth. The point
  of this sprint was to prove the *evidence pipeline* (violation schema,
  code retrieval, Git pickaxe mining) end-to-end against real data using a
  deliberately counterfactual rule, not to claim the example project - or
  our own diagram - has an actual architectural problem.
