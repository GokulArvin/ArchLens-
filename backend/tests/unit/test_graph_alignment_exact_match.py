
from app.modules.architecture_recovery.graph_alignment import (
    align_architecture_graphs,
)


def test_exact_module_match_beats_parent_package_alias():
    intended = {
        "components": [
            {"id": "app.main", "name": "app.main"},
            {
                "id": "app.api.routes.repository",
                "name": "app.api.routes.repository",
            },
        ],
        "relationships": [],
    }

    current = {
        "components": [
            {"id": "app.main", "name": "app.main"},
            {"id": "app", "name": "app"},
            {
                "id": "app.api.routes.repository",
                "name": "app.api.routes.repository",
            },
            {"id": "app.api.routes", "name": "app.api.routes"},
        ],
        "relationships": [],
    }

    result = align_architecture_graphs(intended, current)

    assert result["mapping"] == {
        "app.main": "app.main",
        "app.api.routes.repository": "app.api.routes.repository",
    }
    assert result["summary"]["matched_components"] == 2
    assert result["summary"]["unresolved_components"] == 0

    methods = {
        item["diagram_component_id"]: item["method"]
        for item in result["mapping_details"]
    }

    assert methods["app.main"] == "exact_module_match"
    assert methods["app.api.routes.repository"] == "exact_module_match"


def test_genuine_ambiguous_fuzzy_match_remains_unresolved():
    intended = {
        "components": [
            {"id": "user-service", "name": "User Service"},
        ],
        "relationships": [],
    }

    current = {
        "components": [
            {"id": "service-one", "name": "User Service"},
            {"id": "service-two", "name": "User Service"},
        ],
        "relationships": [],
    }

    result = align_architecture_graphs(intended, current)

    assert result["summary"]["matched_components"] == 0
    assert result["unresolved_components"][0]["reason"] == "ambiguous_match"
