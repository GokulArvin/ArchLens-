
"""
API Routes - Conformance Checking

POST /api/v1/check-conformance
POST /api/v1/check-conformance/inline
POST /api/v1/check-conformance/repository
"""

from datetime import datetime, timezone
from typing import Any, Dict

from fastapi import APIRouter, HTTPException

from app.modules.conformance_engine.engine import ConformanceEngine
from app.modules.architecture_recovery.ast_parser import (
    ArchitectureRecoveryPipeline,
)

from app.schemas.models import (
    CheckConformanceResponse,
    ConformanceReport,
)

from app.database.report_store import save_report


router = APIRouter()

engine = ConformanceEngine()
recovery_pipeline = ArchitectureRecoveryPipeline()


def format_conformance_response(
    result: Dict[str, Any],
) -> CheckConformanceResponse:
    """Normalize engine output into the shared response schema."""

    normalized_result = dict(result)
    normalized_violations = []

    for finding in result.get("violations", []):
        violation = dict(finding)

        violation["source"] = (
            violation.get("source")
            or violation.get("source_component")
        )

        violation["target"] = (
            violation.get("target")
            or violation.get("target_component")
        )

        violation.setdefault("source_component", violation["source"])
        violation.setdefault("target_component", violation["target"])

        violation["rule"] = (
            violation.get("rule")
            or violation.get("violation_type")
        )

        evidence = violation.get("evidence", {})

        if evidence is None:
            evidence = {}
        elif not isinstance(evidence, dict):
            evidence = {"details": evidence}

        violation["evidence"] = evidence

        if violation.get("confidence") is None:
            violation["confidence"] = 1.0

        violation.setdefault("description", "")

        normalized_violations.append(violation)

    normalized_result["violations"] = normalized_violations

    return CheckConformanceResponse.model_validate(normalized_result)


def run_conformance_check(
    intended: Dict[str, Any],
    current: Dict[str, Any],
) -> CheckConformanceResponse:
    """Run the deterministic conformance engine."""

    result = engine.check_conformance(intended, current)

    return format_conformance_response(result)


def persist_conformance_report(
    intended: Dict[str, Any],
    current: Dict[str, Any],
    response: CheckConformanceResponse,
    repository: str,
    diagram_path: str | None = None,
) -> CheckConformanceResponse:
    """Create and persist a report for a conformance run."""

    report = ConformanceReport(
        repository=repository,
        diagram_path=diagram_path,
        intended_graph=intended,
        current_graph=current,
        violations=response.violations,
        summary={
            "verdict": response.verdict.value,
            **response.summary.model_dump(mode="json"),
        },
        status="completed",
    )

    report.updated_at = datetime.now(timezone.utc)

    report_data = report.model_dump(mode="json")
    report_id = save_report(report_data)

    response.report_id = report_id
    response.run_id = report.run_id

    return response


def execute_and_persist(
    intended: Dict[str, Any],
    current: Dict[str, Any],
    repository: str,
    diagram_path: str | None = None,
) -> CheckConformanceResponse:
    """Run conformance checking and save the resulting report."""

    response = run_conformance_check(intended, current)

    return persist_conformance_report(
        intended=intended,
        current=current,
        response=response,
        repository=repository,
        diagram_path=diagram_path,
    )


@router.post(
    "/check-conformance",
    response_model=CheckConformanceResponse,
)
async def check_conformance(body: dict):
    """Compare intended and current architecture graphs."""

    intended = body.get("intended_graph")
    current = body.get("current_graph")

    if not isinstance(intended, dict) or not isinstance(current, dict):
        raise HTTPException(
            status_code=400,
            detail="Both intended_graph and current_graph must be objects.",
        )

    try:
        return execute_and_persist(
            intended=intended,
            current=current,
            repository=body.get("repository", "inline"),
            diagram_path=body.get("diagram_path"),
        )

    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Conformance check failed: {str(e)}",
        )


@router.post(
    "/check-conformance/inline",
    response_model=CheckConformanceResponse,
)
async def check_conformance_inline(body: dict):
    """Check conformance using graphs supplied in the request."""

    intended = body.get("intended_graph")
    current = body.get("current_graph")

    if not isinstance(intended, dict) or not isinstance(current, dict):
        raise HTTPException(
            status_code=400,
            detail="Both intended_graph and current_graph must be objects.",
        )

    try:
        return execute_and_persist(
            intended=intended,
            current=current,
            repository=body.get("repository", "inline"),
            diagram_path=body.get("diagram_path"),
        )

    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Conformance check failed: {str(e)}",
        )


@router.post(
    "/check-conformance/repository",
    response_model=CheckConformanceResponse,
)
async def check_repository_conformance(body: dict):
    """Analyze a repository and compare it with the intended graph."""

    intended = body.get("intended_graph")
    repo_path = body.get("repo_path")
    language = body.get("language", "python")

    if not isinstance(intended, dict):
        raise HTTPException(
            status_code=400,
            detail="intended_graph must be an object.",
        )

    if not repo_path:
        raise HTTPException(
            status_code=400,
            detail="repo_path is required.",
        )

    try:
        current = recovery_pipeline.analyze_repository(
            repo_path,
            language,
        )

        return execute_and_persist(
            intended=intended,
            current=current,
            repository=repo_path,
            diagram_path=body.get("diagram_path"),
        )

    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Repository conformance check failed: {str(e)}",
        )
