"""
Sprint 8 / D36-D37, D39-D40: tests for impact analysis and recommendation-
path validation, including controlled violations against the real
`gcp_microservices_demo` graph topology.

The two controlled violations below (`shipping -> frontend`,
`recommendation -> cart`) are deliberately inserted test fixtures - edges
that do not exist in the real manifest - used to verify affected-node
computation localizes correctly, per the source plan's own exit-gate
requirement ("a controlled violation inserted into a test fixture is
detected and localized correctly"). This is standard fault-injection
testing, not fabricated project data.
"""

import pytest

from app.modules.cv_pipeline.dataset_manifest import load_manifest
from app.modules.cv_pipeline.impact_analysis import build_networkx_graph, compute_affected_nodes, validate_recommended_path


@pytest.fixture(scope="module")
def microservices_demo_graph():
    g = next(x for x in load_manifest() if x.id == "gcp_microservices_demo")
    return build_networkx_graph(g)


def test_build_networkx_graph_has_real_nodes_and_edges(microservices_demo_graph):
    assert "frontend" in microservices_demo_graph.nodes
    assert microservices_demo_graph.has_edge("checkout", "payment")


def test_controlled_violation_backward_edge_has_large_blast_radius(microservices_demo_graph):
    """shipping -> frontend is a controlled (inserted) backward-dependency
    violation: frontend is the real hub node, so this should affect almost
    every other real component downstream."""
    impact = compute_affected_nodes(microservices_demo_graph, "shipping", "frontend")
    assert set(impact.upstream_affected) == {"checkout", "frontend", "loadgenerator"}
    # frontend reaches nearly the whole real graph - including shipping itself, since the
    # inserted backward edge creates a real cycle.
    assert "shipping" in impact.downstream_affected
    assert len(impact.downstream_affected) >= 8


def test_controlled_violation_leaf_target_has_small_blast_radius(microservices_demo_graph):
    """recommendation -> cart is a controlled (inserted) direct-bypass
    violation with a small, precisely known blast radius."""
    impact = compute_affected_nodes(microservices_demo_graph, "recommendation", "cart")
    assert set(impact.upstream_affected) == {"frontend", "loadgenerator"}
    assert set(impact.downstream_affected) == {"rediscache"}


def test_compute_affected_nodes_rejects_unknown_node(microservices_demo_graph):
    with pytest.raises(ValueError, match="must both be real nodes"):
        compute_affected_nodes(microservices_demo_graph, "not-a-real-node", "frontend")


def test_validate_recommended_path_accepts_a_real_intended_route():
    """flask_microservice_demo really has both a direct backend->orders edge
    and a genuine alternate real route through aggregate - use that for a
    true multi-hop acceptance case (Sprint 7's demo scenario)."""
    g = next(x for x in load_manifest() if x.id == "flask_microservice_demo")
    nx_g = build_networkx_graph(g)
    result = validate_recommended_path(nx_g, "backend", "orders", ["backend", "aggregate", "orders"])
    assert result.valid is True


def test_validate_recommended_path_rejects_a_direct_edge_reuse(microservices_demo_graph):
    result = validate_recommended_path(microservices_demo_graph, "checkout", "productcatalog", ["checkout", "productcatalog"])
    assert result.valid is False
    assert "direct edge" in result.reasons[0]


def test_validate_recommended_path_rejects_invented_edges(microservices_demo_graph):
    result = validate_recommended_path(microservices_demo_graph, "ad", "frontend", ["ad", "payment", "frontend"])
    assert result.valid is False
    assert any("not part of the intended" in r for r in result.reasons)

    result = validate_recommended_path(microservices_demo_graph, "shipping", "frontend", ["shipping", "cart", "frontend"])
    assert result.valid is False  # "cart -> frontend" doesn't exist in the real graph
