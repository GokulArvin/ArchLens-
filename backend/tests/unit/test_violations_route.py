
import asyncio

import pytest
from fastapi import HTTPException

from app.api.routes import violations


class FakeRCA:
    def analyze(self, evidence):
        return {
            "violation_id": evidence["violation"].get("id", "standalone"),
            "violation_explanation": "Test finding",
            "root_cause": "Insufficient evidence for a deeper cause.",
            "evidence": [],
            "affected_components": [],
            "recommendation": "Review the dependency.",
            "confidence": 0.0,
            "analysis_status": "insufficient_evidence",
        }


def test_analyze_violation_without_report_id_does_not_reference_undefined_values(monkeypatch):
    monkeypatch.setattr(violations, "rca_analyzer", FakeRCA())

    response = asyncio.run(
        violations.analyze_violation({
            "violation": {
                "id": "v-1",
                "source": "controller",
                "target": "repository",
            }
        })
    )

    assert response["violation_id"] == "v-1"
    assert response["report_id"] is None
    assert response["persistence"]["attached_to_report"] is False


def test_analyze_violation_uses_canonical_report_finding(monkeypatch):
    stored_report = {
        "id": "r-1",
        "run_id": "run-1",
        "violations": [{
            "id": "v-1",
            "source": "controller",
            "target": "repository",
            "description": "Canonical finding",
        }],
        "intended_graph": {"components": [], "relationships": []},
        "current_graph": {"components": [], "relationships": []},
    }
    saved = {}

    monkeypatch.setattr(violations, "get_report", lambda report_id: stored_report)
    monkeypatch.setattr(violations, "save_report", lambda report: saved.update(report))
    monkeypatch.setattr(violations, "rca_analyzer", FakeRCA())

    response = asyncio.run(
        violations.analyze_violation({
            "report_id": "r-1",
            "violation": {"id": "v-1", "description": "Client altered this"},
        })
    )

    assert response["violation_id"] == "v-1"
    assert response["run_id"] == "run-1"
    assert saved["rca_results"][0]["root_cause"]
    assert saved["rca_outputs"][0]["violation_id"] == "v-1"
    assert len(saved["evidence_packages"]) == 1


def test_analyze_violation_rejects_unknown_finding_for_report(monkeypatch):
    monkeypatch.setattr(
        violations,
        "get_report",
        lambda report_id: {"id": report_id, "violations": []},
    )

    with pytest.raises(HTTPException) as exc:
        asyncio.run(
            violations.analyze_violation({
                "report_id": "r-1",
                "violation": {"id": "not-in-report"},
            })
        )

    assert exc.value.status_code == 400


def test_analyze_violation_requires_source_file_with_repository(monkeypatch):
    monkeypatch.setattr(violations, "rca_analyzer", FakeRCA())

    with pytest.raises(HTTPException) as exc:
        asyncio.run(
            violations.analyze_violation({
                "repo_path": "/tmp/repo",
                "violation": {"id": "v-1"},
            })
        )

    assert exc.value.status_code == 400
