"""The multipart endpoint exercises the joined diagram-to-report workflow."""

from pathlib import Path

from fastapi.testclient import TestClient

from app.api.routes import diagram as diagram_route
from app.core.config import settings
from app.database import report_store
from app.main import app


client = TestClient(app)


def test_analyze_and_check_persists_aligned_conformance_report(tmp_path, monkeypatch):
    sample_repo = Path(__file__).resolve().parents[1] / "fixtures" / "sample_repo"
    uploads = tmp_path / "uploads"
    reports = tmp_path / "report-data"
    monkeypatch.setattr(settings, "UPLOAD_DIR", str(uploads))
    monkeypatch.setattr(report_store, "DATA_DIR", reports)
    monkeypatch.setattr(report_store, "DB_PATH", reports / "reports.db")

    intended_graph = {
        "graph_type": "intended",
        "components": [
            {"id": "controllers.order_controller", "name": "OrderController", "type": "controller"},
            {"id": "services.order_service", "name": "OrderService", "type": "service"},
            {"id": "repositories.order_repository", "name": "OrderRepository", "type": "repository"},
        ],
        "relationships": [
            {"source": "controllers.order_controller", "target": "services.order_service", "type": "depends_on", "confidence": 1.0},
            {"source": "services.order_service", "target": "repositories.order_repository", "type": "depends_on", "confidence": 1.0},
            {"source": "controllers.order_controller", "target": "repositories.order_repository", "type": "depends_on", "confidence": 1.0},
        ],
    }
    monkeypatch.setattr(diagram_route.cv_pipeline, "analyze", lambda path: {**intended_graph, "source": path})

    response = client.post(
        "/api/v1/analyze-and-check",
        data={
            "repo_path": str(sample_repo),
            "language": "python",
            "manual_mappings_json": "{}",
            "ruleset_json": (
                '{"name":"smoke","confidence_threshold":0.6,"rules":['
                '{"name":"forbid-controller-repository","action":"FORBID",'
                '"category":"layer_rule","source":"controller",'
                '"target":"repository","severity":"high"}]}'
            ),
        },
        files={"file": ("architecture.png", b"synthetic image payload", "image/png")},
    )

    assert response.status_code == 200, response.text
    result = response.json()
    assert result["verdict"] == "VIOLATION"
    assert result["report_id"]
    assert result["alignment"]["summary"]["matched_components"] == 3

    stored = client.get(f"/api/v1/report/{result['report_id']}")
    assert stored.status_code == 200
    assert stored.json()["diagram_path"].endswith("architecture.png")
    assert len(stored.json()["current_graph"]["components"]) >= 4


def test_analyze_and_check_uses_real_region_fallback(tmp_path, monkeypatch):
    sample_repo = Path(__file__).resolve().parents[1] / "fixtures" / "sample_repo"
    repository_root = Path(__file__).resolve().parents[3]
    diagram_path = repository_root / "data" / "diagrams" / "raw" / "gcp_microservices_demo.png"
    uploads = tmp_path / "uploads"
    reports = tmp_path / "report-data"
    monkeypatch.setattr(settings, "UPLOAD_DIR", str(uploads))
    monkeypatch.setattr(report_store, "DATA_DIR", reports)
    monkeypatch.setattr(report_store, "DB_PATH", reports / "reports.db")
    monkeypatch.setattr(diagram_route.cv_pipeline.component_detector, "detect", lambda _: [])
    monkeypatch.setattr(
        diagram_route.cv_pipeline.clip_classifier,
        "classify",
        lambda _: {"database": 0.0, "service": 0.0},
    )

    response = client.post(
        "/api/v1/analyze-and-check",
        data={
            "repo_path": str(sample_repo),
            "language": "python",
            "manual_mappings_json": '{"0":"controllers.order_controller"}',
        },
        files={"file": (diagram_path.name, diagram_path.read_bytes(), "image/png")},
    )

    assert response.status_code == 200, response.text
    result = response.json()
    assert result["report_id"]
    assert result["alignment"]["mapping"]["0"] == "controllers.order_controller"
    stored = client.get(f"/api/v1/report/{result['report_id']}")
    assert stored.status_code == 200
    assert stored.json()["intended_graph"]["metadata"]["component_detection_method"] == "region_proposal"
