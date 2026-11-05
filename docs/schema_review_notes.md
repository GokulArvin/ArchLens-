# Schema Review Notes (Sprint 1 / D5)

Self-review of the manifest/annotation schema as the shared contract other
modules consume (P2/P3 aren't implemented in this P1-scoped track, so this
documents what they *would* need, based on the real `main` branch's module
breakdown).

## What P2 (semantic/LLM layer) would consume

- `ArchComponent.name` and `.type` - raw label + coarse type guess from the
  diagram, which P2's VLM/LLM layer would refine or validate semantically
  (e.g. disambiguating `"zuul"` -> `gateway` vs treating it as an unnamed
  service, per `docs/cv_failure_cases.md`).
- `ArchGraph.metadata["source_repository"]["diagram_provenance"]` - P2 should
  treat `"derived"` diagrams with more scrutiny/lower prior confidence than
  `"official"` ones, since the former encodes our own inference rather than
  an author-published diagram.

## What P3 (static analysis/graph layer) would consume

- `ArchGraph.metadata["source_repository"]["repo_url"]` and `"commit"` - the
  exact repository and commit P3 should clone and parse to build the current
  graph (`G_C`) for comparison against this diagram's intended graph (`G_I`).
- `ArchComponent.id`/`.name` - the names P3's alignment step (Sprint 6) needs
  to match against real module/class/service names in the cloned repo (e.g.
  matching `"frontend"` in `gcp_microservices_demo` to the real
  `src/frontend/` directory in that repo).
- `ArchRelationship.source`/`.target`/`.type` - the edges conformance checking
  (Sprint 6) would compare against P3's extracted dependency graph.

## Known schema gap for later sprints

`ArchGraph` currently has no explicit field for "which named directory/module
in the repo does this component correspond to" - for now that mapping is
implicit (component `name` ~ service directory name, which holds for 9 of
10 dataset entries where the diagram already uses the real service's actual
folder/service name). This should become an explicit field once P3's
alignment step (Sprint 6) is implemented, rather than relying on name
matching.

## Confirmation: no schema fork needed

Sprint 1 did **not** need to modify `backend/app/schemas/models.py` - the
diagram-repository pairing fits entirely inside the existing generic
`ArchGraph.metadata` field, keeping full compatibility with whatever P2/P3/P4
build against the same file on `main`.
