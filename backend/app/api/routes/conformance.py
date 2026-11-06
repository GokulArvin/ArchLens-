
"""
API Routes - Conformance Checking and Graph Alignment

POST /api/v1/check-conformance
POST /api/v1/check-conformance/inline
POST /api/v1/check-conformance/repository
POST /api/v1/align-graphs
"""

from datetime import datetime, timezone
from typing import Any, Dict, Optional

from fastapi import APIRouter, HTTPException

from app.modules.conformance_engine.engine import ConformanceEngine
from app.modules.architecture_recovery.ast_parser import (
    ArchitectureRecoveryPipeline,
)
from app.modules.architecture_recovery.graph_alignment import (
    align_architecture_graphs,
)
from app.schemas.models import (
    CheckConformanceResponse,
    ConformanceReport,
)
from app.services.report_service import save_report


router = APIRouter()

engine = ConformanceEngine()
recovery_pipeline = ArchitectureRecoveryPipeline()


# ---------------------------------------------------------------------
# Response formatting
# ---------------------------------------------------------------------

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
    ruleset: Optional[Dict[str, Any]] = None,
) -> CheckConformanceResponse:
    """Run the deterministic conformance engine."""

    result = engine.check_conformance(intended, current, ruleset)

    return format_conformance_response(result)


# ---------------------------------------------------------------------
# Report persistence
# ---------------------------------------------------------------------

def persist_conformance_report(
    intended: Dict[str, Any],
    current: Dict[str, Any],
    response: CheckConformanceResponse,
    repository: str,
    diagram_path: Optional[str] = None,
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
    diagram_path: Optional[str] = None,
    comparison_current: Optional[Dict[str, Any]] = None,
    alignment: Optional[Dict[str, Any]] = None,
    ruleset: Optional[Dict[str, Any]] = None,
) -> CheckConformanceResponse:
    """
    Run conformance checking and persist the complete graphs.

    comparison_current may be a restricted graph containing only
    successfully aligned repository components. The full current
    repository graph is always retained in the report.
    """

    graph_for_comparison = (
        comparison_current
        if comparison_current is not None
        else current
    )

    response = run_conformance_check(
        intended,
        graph_for_comparison,
        ruleset,
    )

    response.alignment = alignment

    return persist_conformance_report(
        intended=intended,
        current=current,
        response=response,
        repository=repository,
        diagram_path=diagram_path,
    )


# ---------------------------------------------------------------------
# Existing conformance endpoints
# ---------------------------------------------------------------------

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
            ruleset=body.get("ruleset"),
        )

    except ValueError as error:
        raise HTTPException(status_code=400, detail=str(error))

    except Exception as error:
        raise HTTPException(
            status_code=500,
            detail=f"Conformance check failed: {str(error)}",
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
            ruleset=body.get("ruleset"),
        )

    except ValueError as error:
        raise HTTPException(status_code=400, detail=str(error))

    except Exception as error:
        raise HTTPException(
            status_code=500,
            detail=f"Conformance check failed: {str(error)}",
        )


# ---------------------------------------------------------------------
# Graph alignment preview
# ---------------------------------------------------------------------

@router.post("/align-graphs", response_model=dict)
async def align_graphs_endpoint(body: dict):
    """
    Preview alignment between an intended diagram graph and a
    current repository graph.

    Optional manual_mappings:
        {
            "diagram_component_id": "repository_component_id"
        }
    """

    intended = body.get("intended_graph")
    current = body.get("current_graph")
    manual_mappings = body.get("manual_mappings", {})

    if not isinstance(intended, dict):
        raise HTTPException(
            status_code=400,
            detail="intended_graph must be an object.",
        )

    if not isinstance(current, dict):
        raise HTTPException(
            status_code=400,
            detail="current_graph must be an object.",
        )

    if not isinstance(manual_mappings, dict):
        raise HTTPException(
            status_code=400,
            detail="manual_mappings must be an object.",
        )

    try:
        result = align_architecture_graphs(
            intended_graph=intended,
            current_graph=current,
            manual_mappings=manual_mappings,
        )

        return result

    except ValueError as error:
        raise HTTPException(status_code=400, detail=str(error))

    except Exception as error:
        raise HTTPException(
            status_code=500,
            detail=f"Graph alignment failed: {str(error)}",
        )


# ---------------------------------------------------------------------
# Repository conformance with graph alignment
# ---------------------------------------------------------------------

@router.post(
    "/check-conformance/repository",
    response_model=CheckConformanceResponse,
)
async def check_repository_conformance(body: dict):
    """
    Analyze a repository, align its modules with the intended diagram,
    and perform deterministic conformance checking.
    """

    intended = body.get("intended_graph")
    repo_path = body.get("repo_path")
    language = body.get("language", "python")
    manual_mappings = body.get("manual_mappings", {})

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

    if not isinstance(manual_mappings, dict):
        raise HTTPException(
            status_code=400,
            detail="manual_mappings must be an object.",
        )

    try:
        # 1. Recover the current architecture from source code.
        current = recovery_pipeline.analyze_repository(
            repo_path,
            language,
        )

        # 2. Align intended diagram components with repository modules.
        alignment_result = align_architecture_graphs(
            intended_graph=intended,
            current_graph=current,
            manual_mappings=manual_mappings,
        )

        aligned_intended = alignment_result["aligned_intended_graph"]

        mapping = alignment_result["mapping"]
        matched_repository_ids = set(mapping.values())

        # 3. Restrict deterministic comparison to successfully
        #    aligned repository components.
        comparison_current = dict(current)

        comparison_current["components"] = [
            component
            for component in current.get("components", [])
            if component.get("id") in matched_repository_ids
        ]

        comparison_current["relationships"] = [
            relationship
            for relationship in current.get("relationships", [])
            if (
                relationship.get("source") in matched_repository_ids
                and relationship.get("target") in matched_repository_ids
            )
        ]

        # 4. Preserve the original diagram and all alignment decisions
        #    inside the persisted intended graph.
        aligned_metadata = dict(aligned_intended.get("metadata") or {})
        alignment_metadata = dict(
            aligned_metadata.get("alignment") or {}
        )

        alignment_metadata.update({
            "unresolved_components": alignment_result[
                "unresolved_components"
            ],
            "unresolved_relationships": alignment_result[
                "unresolved_relationships"
            ],
            "original_diagram_graph": intended,
        })

        aligned_metadata["alignment"] = alignment_metadata
        aligned_intended["metadata"] = aligned_metadata

        # 5. Persist the complete repository graph, aligned intended
        #    graph, and alignment summary with the conformance report.
        return execute_and_persist(
            intended=aligned_intended,
            current=current,
            comparison_current=comparison_current,
            repository=repo_path,
            diagram_path=body.get("diagram_path"),
            ruleset=body.get("ruleset"),
            alignment={
                "mapping": alignment_result["mapping"],
                "mapping_details": alignment_result["mapping_details"],
                "unresolved_components": alignment_result[
                    "unresolved_components"
                ],
                "unresolved_relationships": alignment_result[
                    "unresolved_relationships"
                ],
                "summary": alignment_result["summary"],
            },
        )

    except ValueError as error:
        raise HTTPException(status_code=400, detail=str(error))

    except FileNotFoundError as error:
        raise HTTPException(status_code=404, detail=str(error))

    except NotImplementedError as error:
        raise HTTPException(status_code=400, detail=str(error))

    except Exception as error:
        raise HTTPException(
            status_code=500,
            detail=f"Repository conformance check failed: {str(error)}",
        )
