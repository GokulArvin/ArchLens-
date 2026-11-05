
"""
API Routes - Conformance Checking

POST /api/v1/check-conformance
POST /api/v1/check-conformance/inline
POST /api/v1/check-conformance/repository
"""

from typing import Any, Dict

from fastapi import APIRouter, HTTPException

from app.modules.conformance_engine.engine import ConformanceEngine
from app.modules.architecture_recovery.ast_parser import (
    ArchitectureRecoveryPipeline,
)
from app.schemas.models import CheckConformanceResponse


router = APIRouter()

engine = ConformanceEngine()
recovery_pipeline = ArchitectureRecoveryPipeline()


def format_conformance_response(
    result: Dict[str, Any],
) -> CheckConformanceResponse:
    """
    Normalize the conformance engine output into the shared
    Pydantic response schema.

    Ensures that every finding contains consistent fields
    required by the API and future RCA module.
    """

    normalized_result = dict(result)

    normalized_violations = []

    for finding in result.get("violations", []):
        violation = dict(finding)

        # Standardize source and target fields.
        violation["source"] = (
            violation.get("source")
            or violation.get("source_component")
        )

        violation["target"] = (
            violation.get("target")
            or violation.get("target_component")
        )

        # Preserve compatibility with older field names.
        violation.setdefault(
            "source_component",
            violation["source"],
        )
        violation.setdefault(
            "target_component",
            violation["target"],
        )

        # Use violation_type as the rule identifier if
        # the engine does not explicitly provide a rule.
        violation["rule"] = (
            violation.get("rule")
            or violation.get("violation_type")
        )

        # Ensure evidence is represented as a dictionary.
        evidence = violation.get("evidence", {})

        if evidence is None:
            evidence = {}
        elif not isinstance(evidence, dict):
            evidence = {"details": evidence}

        violation["evidence"] = evidence

        # Ensure confidence is available.
        if violation.get("confidence") is None:
            violation["confidence"] = 1.0

        # Ensure a description is available.
        violation.setdefault("description", "")

        normalized_violations.append(violation)

    normalized_result["violations"] = normalized_violations

    # Validate and construct the standardized response.
    return CheckConformanceResponse.model_validate(
        normalized_result
    )


def run_conformance_check(
    intended: Dict[str, Any],
    current: Dict[str, Any],
) -> CheckConformanceResponse:
    """
    Shared conformance-checking logic used by all endpoints.
    """

    result = engine.check_conformance(intended, current)

    return format_conformance_response(result)


@router.post(
    "/check-conformance",
    response_model=CheckConformanceResponse,
)
async def check_conformance(body: dict):
    """
    Compare intended and current architecture graphs.
    Both graphs must be provided in the request body.
    """

    intended = body.get("intended_graph")
    current = body.get("current_graph")

    if not intended or not current:
        raise HTTPException(
            status_code=400,
            detail="Both intended_graph and current_graph are required.",
        )

    try:
        return run_conformance_check(intended, current)

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
    """
    Check conformance with architecture graphs supplied
    directly in the request body.
    """

    intended = body.get("intended_graph")
    current = body.get("current_graph")

    if not intended or not current:
        raise HTTPException(
            status_code=400,
            detail="Both intended_graph and current_graph are required.",
        )

    try:
        return run_conformance_check(intended, current)

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
    """
    Automatically analyze a repository and check its
    architecture against the supplied intended graph.
    """

    intended = body.get("intended_graph")
    repo_path = body.get("repo_path")
    language = body.get("language", "python")

    if not intended:
        raise HTTPException(
            status_code=400,
            detail="intended_graph is required.",
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

        return run_conformance_check(
            intended,
            current,
        )

    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Repository conformance check failed: {str(e)}",
        )
