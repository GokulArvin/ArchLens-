
"""API routes for persisted conformance reports and report exports."""

import html
import json

from fastapi import APIRouter, HTTPException
from fastapi.responses import HTMLResponse, Response

from app.services.report_service import (
    get_report as get_stored_report,
    list_reports as list_stored_reports,
)

router = APIRouter()


def _load_report(report_id: str) -> dict:
    """Load a report or raise a consistent 404 response."""
    report = get_stored_report(report_id)

    if report is None:
        raise HTTPException(
            status_code=404,
            detail=f"Report {report_id} not found.",
        )

    return report


def _safe(value) -> str:
    """Escape untrusted values before inserting them into HTML."""
    if value is None:
        return "Not available"
    if isinstance(value, (dict, list)):
        value = json.dumps(value, indent=2, default=str)
    return html.escape(str(value))


@router.get("/reports", response_model=list)
async def list_reports():
    """List report metadata, newest first."""
    return list_stored_reports()


@router.get("/report/{report_id}", response_model=dict)
async def get_report(report_id: str):
    """Retrieve a complete conformance report."""
    return _load_report(report_id)


@router.get("/report/{report_id}/export/json")
async def export_report_json(report_id: str):
    """Download the complete report as a JSON file."""
    report = _load_report(report_id)

    content = json.dumps(
        report,
        indent=2,
        ensure_ascii=False,
        default=str,
    )

    return Response(
        content=content,
        media_type="application/json",
        headers={
            "Content-Disposition": (
                f'attachment; filename="archlens-report-{report_id}.json"'
            )
        },
    )


@router.get("/report/{report_id}/export/html", response_class=HTMLResponse)
async def export_report_html(report_id: str):
    """Download a readable HTML version of the complete report."""
    report = _load_report(report_id)

    summary = report.get("summary") or {}
    violations = report.get("violations") or []
    git_evidence = report.get("git_evidence") or []
    rca_outputs = report.get("rca_outputs") or []

    violation_rows = []

    for item in violations:
        violation_rows.append(
            f"""
            <tr>
                <td>{_safe(item.get("verdict"))}</td>
                <td>{_safe(item.get("violation_type"))}</td>
                <td>{_safe(item.get("source"))}</td>
                <td>{_safe(item.get("target"))}</td>
                <td>{_safe(item.get("severity"))}</td>
                <td>{_safe(item.get("description"))}</td>
                <td>{_safe(item.get("confidence"))}</td>
            </tr>
            """
        )

    if not violation_rows:
        violation_rows.append(
            '<tr><td colspan="7">No violations recorded.</td></tr>'
        )

    evidence_sections = []

    for item in git_evidence:
        evidence_sections.append(
            f"""
            <section class="record">
                <h3>Git evidence — {_safe(item.get("violation_id"))}</h3>
                <p><strong>File:</strong> {_safe(item.get("file"))}</p>
                <p><strong>Lines:</strong> {_safe(item.get("lines"))}</p>
                <p><strong>Dependency path:</strong>
                    {_safe(item.get("dependency_path"))}</p>
                <p><strong>Introducing commit:</strong>
                    {_safe(item.get("introducing_commit"))}</p>
                <p><strong>Related commits:</strong>
                    {_safe(item.get("related_commits"))}</p>
            </section>
            """
        )

    if not evidence_sections:
        evidence_sections.append("<p>No Git evidence recorded.</p>")

    rca_sections = []

    for item in rca_outputs:
        rca_sections.append(
            f"""
            <section class="record">
                <h3>Root-cause analysis — {_safe(item.get("violation_id"))}</h3>
                <p><strong>Explanation:</strong>
                    {_safe(item.get("violation_explanation"))}</p>
                <p><strong>Root cause:</strong>
                    {_safe(item.get("root_cause"))}</p>
                <p><strong>Evidence IDs:</strong>
                    {_safe(item.get("evidence"))}</p>
                <p><strong>Affected components:</strong>
                    {_safe(item.get("affected_components"))}</p>
                <p><strong>Recommendation:</strong>
                    {_safe(item.get("recommendation"))}</p>
                <p><strong>Confidence:</strong>
                    {_safe(item.get("confidence"))}</p>
            </section>
            """
        )

    if not rca_sections:
        rca_sections.append("<p>No RCA results recorded.</p>")

    html_content = f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <title>ArchLens Conformance Report</title>
    <style>
        body {{
            font-family: Arial, sans-serif;
            max-width: 1100px;
            margin: 40px auto;
            padding: 0 24px;
            color: #1e293b;
            line-height: 1.6;
        }}
        h1, h2 {{ color: #0f172a; }}
        .metadata, .record {{
            background: #f8fafc;
            border: 1px solid #e2e8f0;
            border-radius: 8px;
            padding: 16px;
            margin: 16px 0;
        }}
        .verdict {{
            font-size: 1.3rem;
            font-weight: bold;
        }}
        table {{
            width: 100%;
            border-collapse: collapse;
            margin: 16px 0;
        }}
        th, td {{
            border: 1px solid #cbd5e1;
            padding: 10px;
            text-align: left;
            vertical-align: top;
        }}
        th {{ background: #e2e8f0; }}
        pre {{ white-space: pre-wrap; overflow-wrap: anywhere; }}
        @media print {{
            body {{ margin: 10px; }}
            .record, table {{ break-inside: avoid; }}
        }}
    </style>
</head>
<body>
    <h1>ArchLens Architecture Conformance Report</h1>

    <div class="metadata">
        <p><strong>Report ID:</strong> {_safe(report.get("id"))}</p>
        <p><strong>Run ID:</strong> {_safe(report.get("run_id"))}</p>
        <p><strong>Repository:</strong> {_safe(report.get("repository"))}</p>
        <p><strong>Status:</strong> {_safe(report.get("status"))}</p>
        <p><strong>Created:</strong> {_safe(report.get("created_at"))}</p>
        <p><strong>Updated:</strong> {_safe(report.get("updated_at"))}</p>
        <p class="verdict">
            Verdict: {_safe(summary.get("verdict", "Not available"))}
        </p>
        <p><strong>Total violations:</strong>
            {_safe(summary.get("total_violations", len(violations)))}</p>
    </div>

    <h2>Conformance Findings</h2>
    <table>
        <thead>
            <tr>
                <th>Verdict</th><th>Type</th><th>Source</th>
                <th>Target</th><th>Severity</th>
                <th>Description</th><th>Confidence</th>
            </tr>
        </thead>
        <tbody>
            {"".join(violation_rows)}
        </tbody>
    </table>

    <h2>Git Evidence</h2>
    {"".join(evidence_sections)}

    <h2>Root-Cause Analysis</h2>
    {"".join(rca_sections)}

    <h2>Intended Architecture Graph</h2>
    <pre>{_safe(report.get("intended_graph"))}</pre>

    <h2>Current Architecture Graph</h2>
    <pre>{_safe(report.get("current_graph"))}</pre>

    <footer>
        <p>Generated by ArchLens. Findings are based on the recorded
        conformance analysis and available evidence.</p>
    </footer>
</body>
</html>
"""

    return HTMLResponse(
        content=html_content,
        headers={
            "Content-Disposition": (
                f'attachment; filename="archlens-report-{report_id}.html"'
            )
        },
    )
