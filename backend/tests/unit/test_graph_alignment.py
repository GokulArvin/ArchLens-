
import pytest

from app.modules.architecture_recovery.graph_alignment import (
    align_architecture_graphs,
)


def make_component(component_id, name, **extra):
    return {
        "id": component_id,
        "name": name,
        "type": "service",
        "metadata": extra,
    }


def make_graph(components, relationships=None):
    return {
        "components": components,
        "relationships": relationships or [],
        "metadata": {},
    }


def test_exact_name_match():
    intended = make_graph([
        make_component("diagram-1", "UserService")
    ])
    current = make_graph([
        make_component("app.services.user_service", "UserService")
    ])

    result = align_architecture_graphs(intended, current)

    assert result["mapping"]["diagram-1"] == "app.services.user_service"
    assert result["summary"]["matched_components"] == 1
    assert result["summary"]["unresolved_components"] == 0


def test_manual_mapping_overrides_automatic_matching():
    intended = make_graph([
        make_component("diagram-1", "User Service")
    ])
    current = make_graph([
        make_component("app.services.user", "UserService"),
        make_component("app.services.user_admin", "UserAdminService"),
    ])

    result = align_architecture_graphs(
        intended,
        current,
        manual_mappings={"diagram-1": "app.services.user_admin"},
    )

    assert result["mapping"]["diagram-1"] == "app.services.user_admin"
    assert result["mapping_details"][0]["method"] == "manual"


def test_ambiguous_match_is_not_guessed():
    intended = make_graph([
        make_component("diagram-1", "PaymentService")
    ])
    current = make_graph([
        make_component("app.one.payment_service", "PaymentService"),
        make_component("app.two.payment_service", "PaymentService"),
    ])

    result = align_architecture_graphs(intended, current)

    assert "diagram-1" not in result["mapping"]
    assert result["unresolved_components"][0]["reason"] == "ambiguous_match"


def test_unmatched_component_is_preserved_as_uncertainty():
    intended = make_graph([
        make_component("diagram-1", "Unknown External Platform")
    ])
    current = make_graph([
        make_component("app.services.user", "UserService")
    ])

    result = align_architecture_graphs(intended, current)

    assert result["summary"]["unresolved_components"] == 1
    assert result["aligned_intended_graph"]["metadata"]["alignment"]["has_uncertainty"]


def test_unverified_relationship_is_not_aligned():
    intended = make_graph(
        [
            make_component("diagram-a", "UserService"),
            make_component("diagram-b", "OrderService"),
        ],
        [{
            "id": "edge-1",
            "source": "diagram-a",
            "target": "diagram-b",
            "confidence": 0.9,
            "metadata": {"direction_verified": False},
        }],
    )
    current = make_graph([
        make_component("app.user", "UserService"),
        make_component("app.order", "OrderService"),
    ])

    result = align_architecture_graphs(intended, current)

    assert result["summary"]["aligned_relationships"] == 0
    assert result["unresolved_relationships"][0]["reason"] == "direction_unverified"


def test_low_confidence_relationship_is_not_aligned():
    intended = make_graph(
        [
            make_component("diagram-a", "UserService"),
            make_component("diagram-b", "OrderService"),
        ],
        [{
            "id": "edge-1",
            "source": "diagram-a",
            "target": "diagram-b",
            "confidence": 0.3,
            "metadata": {"direction_verified": True},
        }],
    )
    current = make_graph([
        make_component("app.user", "UserService"),
        make_component("app.order", "OrderService"),
    ])

    result = align_architecture_graphs(intended, current)

    assert result["summary"]["aligned_relationships"] == 0
    assert result["unresolved_relationships"][0]["reason"] == "low_confidence"


def test_invalid_manual_mapping_is_rejected():
    intended = make_graph([
        make_component("diagram-1", "UserService")
    ])
    current = make_graph([
        make_component("app.user", "UserService")
    ])

    with pytest.raises(ValueError):
        align_architecture_graphs(
            intended,
            current,
            manual_mappings={"diagram-1": "missing.module"},
        )
