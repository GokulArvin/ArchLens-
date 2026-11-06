
import asyncio
import json

import pytest
from fastapi import HTTPException
from fastapi.responses import HTMLResponse, Response

from app.api.routes import reports


SAMPLE_REPORT = {
    "id": "test-report-001",
    "run_id": "test-run-001",
    "repository": "sample-repository",
    "status": "completed",
    "created_at": "2026-11-06T10:00:00Z",
    "updated_at": "2026-11-06T10:00:00Z",
    "summary": {
        "verdict": "VIOLATION",
        "total_violations": 1,
    },
    "violations": [
        {
            "id": "v1",
            "verdict": "VIOLATION",
            "violation_type": "forbidden_dependency",
            "source": "controller",
            "target": "repository",
            "severity": "high",
            "description": "Forbidden dependency detected.",
            "confidence": 1.0,
        }
    ],
    "git_evidence": [],
    "rca_outputs": [],
    "intended_graph": {"components": []},
    "current_graph": {"components": []},
}


def test_json_export_returns_complete_report(monkeypatch):
    monkeypatch.setattr(
        reports,
        "get_stored_report",
        lambda report_id: SAMPLE_REPORT,
    )

    response = asyncio.run(
        reports.export_report_json("test-report-001")
    )

    assert isinstance(response, Response)
    assert response.media_type == "application/json"

    exported = json.loads(response.body)

    assert exported["id"] == "test-report-001"
    assert exported["violations"][0]["source"] == "controller"
    assert "attachment" in response.headers["content-disposition"]


def test_html_export_contains_report_data_and_escapes_html(monkeypatch):
    malicious_report = {
        **SAMPLE_REPORT,
        "repository": "<script>alert('xss')</script>",
    }

    monkeypatch.setattr(
        reports,
        "get_stored_report",
        lambda report_id: malicious_report,
    )

    response = asyncio.run(
        reports.export_report_html("test-report-001")
    )

    assert isinstance(response, HTMLResponse)

    content = response.body.decode("utf-8")

    assert "ArchLens Architecture Conformance Report" in content
    assert "VIOLATION" in content
    assert "&lt;script&gt;" in content
    assert "<script>alert('xss')</script>" not in content
    assert "attachment" in response.headers["content-disposition"]


def test_export_returns_404_for_unknown_report(monkeypatch):
    monkeypatch.setattr(
        reports,
        "get_stored_report",
        lambda report_id: None,
    )

    with pytest.raises(HTTPException) as exc:
        asyncio.run(
            reports.export_report_json("missing-report")
        )

    assert exc.value.status_code == 404
