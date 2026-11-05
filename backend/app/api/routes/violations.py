
"""API Routes - Violation analysis and evidence-grounded RCA."""

from datetime import datetime, timezone

from fastapi import APIRouter, HTTPException

from app.modules.git_evidence.extractor import GitEvidenceExtractor
from app.modules.llm_rca.analyzer import RCAAnalyzer

from app.database.report_store import (
    get_report,
    save_report,
)


router = APIRouter()

rca_analyzer = RCAAnalyzer()


@router.post("/analyze-violation", response_model=dict)
async def analyze_violation(body: dict):
    """Collect Git evidence and perform root-cause analysis."""

    repo_path = body.get("repo_path", "")
    violation = body.get("violation", {})
    source_file = body.get("source_file", "")
    target_symbol = body.get("target_symbol", "")
    report_id = body.get("report_id")

    if not violation:
        raise HTTPException(
            status_code=400,
            detail="violation is required",
        )

    if report_id:
        existing_report = get_report(report_id)

        if existing_report is None:
            raise HTTPException(
                status_code=404,
                detail=f"Report {report_id} not found",
            )

    evidence_package = {
        "violation": violation,
        "dependency_path": [
            violation.get("source", ""),
            violation.get("target", ""),
        ],
    }

    if repo_path and source_file:
        try:
            git_extractor = GitEvidenceExtractor(repo_path)

            evidence_package = git_extractor.build_evidence_package(
                violation,
                source_file,
                target_symbol,
            )

        except Exception as e:
            evidence_package["git_error"] = str(e)

    try:
        rca_output = rca_analyzer.analyze(evidence_package)

        # Normalize model output for JSON storage.
        if hasattr(rca_output, "model_dump"):
            rca_data = rca_output.model_dump(mode="json")
        elif isinstance(rca_output, dict):
            rca_data = rca_output
        else:
            rca_data = {"result": str(rca_output)}

        # Attach evidence and RCA to the existing report.
        if report_id:
            report = get_report(report_id)

            report.setdefault("evidence_packages", []).append(
                evidence_package
            )

            report.setdefault("rca_results", []).append(
                rca_data
            )

            report["updated_at"] = datetime.now(
                timezone.utc
            ).isoformat()

            save_report(report)

        return {
            "report_id": report_id,
            "evidence": evidence_package,
            "rca": rca_data,
        }

    except HTTPException:
        raise

    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Violation analysis failed: {str(e)}",
        )
