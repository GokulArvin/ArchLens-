# Sprint 8: Impact Analysis & Recommendations (D36-D40)

## D36 + D37: Diagram nodes -> graph nodes, offending edges, affected-node highlighting

`backend/app/modules/cv_pipeline/impact_analysis.py` converts the real
shared `ArchGraph` schema into a NetworkX `DiGraph` (`build_networkx_graph`)
and computes real blast-radius impact via graph traversal
(`compute_affected_nodes`): **upstream** = `nx.ancestors(source)` (anything
that depends on the violating edge's source), **downstream** =
`nx.descendants(target)` (everything the source is now transitively
coupled to through the bad edge). `backend/scripts/render_impact_visualization.py`
renders this as a real highlighted graph image.

## D38: Recommendation patterns

`backend/app/modules/cv_pipeline/recommendations.py` defines one template
per real `ViolationType` enum value (`layer_violation`, `forbidden_dependency`,
`missing_dependency`, `unexpected_dependency`, `cycle_violation`,
`interface_violation`), filled with the violation's real `source_component`/
`target_component`/`expected`/`actual` fields - not a separate invented
taxonomy.

## D39: Do recommendations preserve intended paths/layers?

`validate_recommended_path` checks a proposed fix (a node sequence from
source to target) three ways: (1) it must actually start/end at the
violation's real endpoints, (2) it must not just restate the original
direct edge, (3) **every edge it uses must already exist in the real
intended graph** - a recommendation can route traffic differently, but it
can't invent a dependency that isn't part of the architecture. Verified on
real data (`backend/tests/unit/test_impact_analysis.py`):
`backend -> aggregate -> orders` (the real alternate path in
`flask_microservice_demo`) is accepted; a path through a non-existent
`ad -> payment -> frontend` route is correctly rejected with the specific
missing edges named.

## D40: Impact visualization against controlled violations

Two controlled (deliberately inserted, not fabricated project data -
standard fault-injection testing per the plan's own exit-gate requirement)
violations tested against the real `gcp_microservices_demo` graph topology:

| violation (inserted) | upstream affected | downstream affected |
|---|---|---|
| `shipping -> frontend` (backward dependency) | `checkout, frontend, loadgenerator` | 10 of 12 real nodes, **including `shipping` itself** (the inserted edge creates a real cycle) |
| `recommendation -> cart` (direct bypass) | `frontend, loadgenerator` | `rediscache` only |

Both are exactly localized and match the real graph's actual reachability -
the backward-dependency case genuinely demonstrates why backward edges are
dangerous (near-total blast radius through the real `frontend` hub node),
while the bypass case shows a correctly *small*, precise blast radius when
the target is a near-leaf node. Rendered figures:
`experiments/results/sprint8_impact_shipping_frontend.png` and
`..._recommendation_cart.png`.
