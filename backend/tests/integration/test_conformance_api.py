"""
Integration tests for FastAPI endpoints (Sprint 1 P3 Integration).
Tests end-to-end flow from repository analysis to conformance checking.
"""

import json
from pathlib import Path
import pytest
from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)


@pytest.fixture
def example_data():
    examples_dir = Path(__file__).resolve().parent.parent.parent / "app" / "schemas" / "examples"
    with open(examples_dir / "example_GI.json", "r", encoding="utf-8") as f:
        gi = json.load(f)
    with open(examples_dir / "example_GC_conformant.json", "r", encoding="utf-8") as f:
        gc_conf = json.load(f)
    with open(examples_dir / "example_GC_violations.json", "r", encoding="utf-8") as f:
        gc_viol = json.load(f)
    with open(examples_dir / "example_ruleset.json", "r", encoding="utf-8") as f:
        ruleset = json.load(f)
    return {"gi": gi, "gc_conf": gc_conf, "gc_viol": gc_viol, "ruleset": ruleset}


@pytest.fixture
def sample_repo_path():
    base_dir = Path(__file__).resolve().parent.parent / "fixtures" / "sample_repo"
    return str(base_dir)


def test_api_check_conformance_conformant(example_data):
    """Test POST /api/v1/check-conformance/inline with conformant graphs."""
    payload = {
        "intended_graph": example_data["gi"],
        "current_graph": example_data["gc_conf"],
        "ruleset": example_data["ruleset"],
    }
    response = client.post("/api/v1/check-conformance/inline", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert data["verdict"] == "CONFORMANT"
    assert len(data["violations"]) == 0
    assert data["summary"]["verdicts"]["CONFORMANT"] >= 1


def test_api_check_conformance_violations(example_data):
    """Test POST /api/v1/check-conformance/inline with violations graph."""
    payload = {
        "intended_graph": example_data["gi"],
        "current_graph": example_data["gc_viol"],
        "ruleset": example_data["ruleset"],
    }
    response = client.post("/api/v1/check-conformance/inline", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert data["verdict"] == "VIOLATION"
    verdicts = [v["verdict"] for v in data["violations"]]
    assert "VIOLATION" in verdicts
    assert "MISSING" in verdicts
    assert "UNCERTAIN" in verdicts


def test_api_analyze_repository(sample_repo_path):
    """Test POST /api/v1/analyze-repository on sample repository fixture."""
    payload = {
        "repo_path": sample_repo_path,
        "language": "python",
    }
    response = client.post("/api/v1/analyze-repository", json=payload)
    assert response.status_code == 200
    graph = response.json()
    assert graph["graph_type"] == "current"
    assert len(graph["components"]) >= 4
    assert len(graph["relationships"]) >= 4


def test_api_end_to_end_pipeline(sample_repo_path, example_data):
    """End-to-end test: analyze repo -> check conformance against intended graph."""
    # 1. Recover current architecture
    repo_resp = client.post(
        "/api/v1/analyze-repository",
        json={"repo_path": sample_repo_path, "language": "python"},
    )
    assert repo_resp.status_code == 200
    current_graph = repo_resp.json()

    # 2. Check conformance against intended graph
    conf_resp = client.post(
        "/api/v1/check-conformance/inline",
        json={
            "intended_graph": example_data["gi"],
            "current_graph": current_graph,
            "ruleset": example_data["ruleset"],
        },
    )
    assert conf_resp.status_code == 200
    result = conf_resp.json()
    assert "verdict" in result
    assert "violations" in result
    assert "summary" in result
