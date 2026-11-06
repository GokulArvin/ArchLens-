
from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def make_graph(components, relationships=None):
    return {
        "components": components,
        "relationships": relationships or [],
        "metadata": {},
    }


def test_align_graphs_endpoint_matches_components():
    intended = make_graph([
        {"id": "diagram-user", "name": "UserService"}
    ])

    current = make_graph([
        {"id": "app.services.user_service", "name": "UserService"}
    ])

    response = client.post(
        "/api/v1/align-graphs",
        json={
            "intended_graph": intended,
            "current_graph": current,
        },
    )

    assert response.status_code == 200

    data = response.json()

    assert data["mapping"]["diagram-user"] == "app.services.user_service"
    assert data["summary"]["matched_components"] == 1


def test_align_graphs_endpoint_accepts_manual_mapping():
    intended = make_graph([
        {"id": "diagram-user", "name": "User Service"}
    ])

    current = make_graph([
        {"id": "app.services.user", "name": "UserService"},
        {"id": "app.services.admin", "name": "AdminService"},
    ])

    response = client.post(
        "/api/v1/align-graphs",
        json={
            "intended_graph": intended,
            "current_graph": current,
            "manual_mappings": {
                "diagram-user": "app.services.admin"
            },
        },
    )

    assert response.status_code == 200
    assert (
        response.json()["mapping"]["diagram-user"]
        == "app.services.admin"
    )


def test_align_graphs_endpoint_rejects_invalid_mapping():
    intended = make_graph([
        {"id": "diagram-user", "name": "UserService"}
    ])

    current = make_graph([
        {"id": "app.services.user", "name": "UserService"}
    ])

    response = client.post(
        "/api/v1/align-graphs",
        json={
            "intended_graph": intended,
            "current_graph": current,
            "manual_mappings": {
                "diagram-user": "missing.module"
            },
        },
    )

    assert response.status_code == 400


def test_align_graphs_endpoint_requires_both_graphs():
    response = client.post(
        "/api/v1/align-graphs",
        json={
            "intended_graph": make_graph([]),
        },
    )

    assert response.status_code == 400
