
"""API routes for Git evidence collection and evidence-grounded RCA."""

import logging
from datetime import datetime, timezone
from typing import Any, Optional

from fastapi import APIRouter, HTTPException

from app.database.report_store import get_report, save_report
from app.modules.git_evidence.extractor import GitEvidenceExtractor
from app.modules.llm_rca.analyzer import RCAAnalyzer
from app.schemas.models import GitCommit, GitEvidence, RCAOutput

router = APIRouter()
logger = logging.getLogger(__name__)
rca_analyzer = RCAAnalyzer()


def _commit_model(data: Optional[dict]) -> Optional[GitCommit]:
    """Convert an extractor commit into the shared GitCommit schema."""
    if not isinstance(data, dict):
        return None

    commit_hash = data.get("hash") or data.get("commit_hash")
    if not commit_hash:
        return None

    return GitCommit(
        hash=str(commit_hash),
        message=str(data.get("message", "")),
        author=str(data.get("author", "")),
        date=str(data.get("date", "")),
        diff=data.get("diff"),
    )


def _structured_git_evidence(
    package: dict,
    violation: dict,
    source_file: str,
) -> GitEvidence:
    """Build the typed Git evidence representation."""
    commit = _commit_model(package.get("commit"))

    related_commits = []
    for item in package.get("recent_commits", []):
        converted = _commit_model(item)
        if converted:
            related_commits.append(converted)

    context = package.get("code_context", {})
    lines = context.get("content") if isinstance(context, dict) else None

    return GitEvidence(
        violation_id=str(violation.get("id", "unknown")),
        file=str(context.get("file") or source_file),
        lines=lines,
        dependency_path=package.get("dependency_path", []),
        introducing_commit=commit,
        related_commits=related_commits,
    )


def _structured_rca_output(
    rca_data: dict,
    violation: dict,
) -> RCAOutput:
    """Validate and convert RCA output to the shared report schema."""
    return RCAOutput(
        violation_id=str(
            rca_data.get("violation_id")
            or violation.get("id")
            or "unknown"
        ),
        violation_explanation=str(
            rca_data.get("violation_explanation", "")
        ),
        root_cause=str(rca_data.get("root_cause", "")),
        evidence=rca_data.get("evidence", []),
        affected_components=rca_data.get("affected_components", []),
        recommendation=str(rca_data.get("recommendation", "")),
        confidence=float(rca_data.get("confidence", 0.0)),
    )


@router.post("/analyze-violation", response_model=dict)
async def analyze_violation(body: dict):
    """
    Collect Git/source evidence, run RCA, and optionally attach
    both results to an existing conformance report.
    """

    repo_path = body.get("repo_path", "")
    violation = body.get("violation")
    source_file = body.get("source_file", "")
    target_symbol = body.get("target_symbol", "")
    report_id = body.get("report_id")

    if not isinstance(violation, dict) or not violation:
        raise HTTPException(
            status_code=400,
            detail="violation must be a non-empty object.",
        )

    report = None
    if report_id:
        report = get_report(report_id)
        if report is None:
            raise HTTPException(
                status_code=404,
                detail=f"Report {report_id} not found.",
            )

        # Prefer the canonical finding stored in the report

        report_violations = report.get("violations", [])
        requested_id = violation.get("id")

    if not requested_id:
        raise HTTPException(
        status_code=400,
        detail="A violation ID is required when report_id is supplied.",
        )

    matching = [
    item for item in report_violations
    if item.get("id") == requested_id
    ]

    if not matching:
        raise HTTPException(
        status_code=400,
        detail=(
            "The supplied violation ID does not belong "
            "to the specified report."
        ),
        )

    violation = matching[0]

    if repo_path and not source_file:
        raise HTTPException(
            status_code=400,
            detail="source_file is required when repo_path is supplied.",
        )

    # Start with a useful minimum evidence package.
    evidence_package: dict[str, Any] = {
        "violation": violation,
        "dependency_path": [
            item for item in (
                violation.get("source"),
                violation.get("target"),
            ) if item
        ],
        "evidence_items": [],
        "evidence_metadata": {
            "git_available": False,
            "source_file": source_file or None,
        },
    }

    # Add graph context from the same persisted report.
    if report:
        evidence_package["intended_architecture"] = (
            report.get("intended_graph") or {}
        )
        evidence_package["current_architecture"] = (
            report.get("current_graph") or {}
        )
        evidence_package["report_id"] = report_id
        evidence_package["run_id"] = report.get("run_id")

        graph_evidence = {
            "evidence_id": "E-GRAPH-001",
            "type": "architecture_graph",
            "description": (
                "Intended and current architecture graphs "
                "associated with this conformance report."
            ),
            "source": "conformance_report",
            "content": {
                "intended_graph": report.get("intended_graph") or {},
                "current_graph": report.get("current_graph") or {},
            },
        }
        evidence_package["evidence_items"].append(graph_evidence)

    # Collect repository evidence.
    if repo_path and source_file:
        try:
            extractor = GitEvidenceExtractor(repo_path)
            git_package = extractor.build_evidence_package(
                violation=violation,
                source_file=source_file,
                target_symbol=target_symbol or None,
            )

            # Preserve all extractor evidence and metadata.
            evidence_package.update(git_package)

            # Restore report context after merging the extractor package.
            if report:
                evidence_package["intended_architecture"] = (
                    report.get("intended_graph") or {}
                )
                evidence_package["current_architecture"] = (
                    report.get("current_graph") or {}
                )
                evidence_package["report_id"] = report_id
                evidence_package["run_id"] = report.get("run_id")

                # Keep the graph evidence item alongside Git evidence.
                evidence_package.setdefault("evidence_items", []).append(
                    graph_evidence
                )

        except Exception as exc:
            logger.exception("Git evidence extraction failed.")
            evidence_package["git_error"] = str(exc)

    # Perform RCA. The analyzer uses its safe fallback if no LLM
    # provider/API key is configured.
    try:
        rca_result = rca_analyzer.analyze(evidence_package)

        if hasattr(rca_result, "model_dump"):
            rca_data = rca_result.model_dump(mode="json")
        elif isinstance(rca_result, dict):
            rca_data = dict(rca_result)
        else:
            raise TypeError("RCA analyzer returned an unsupported result.")

        rca_data["report_id"] = report_id
        rca_data["run_id"] = report.get("run_id") if report else None

        # Attach both raw and structured representations to the same report.
        if report:
            git_evidence = _structured_git_evidence(
                evidence_package,
                violation,
                source_file,
            )
            structured_rca = _structured_rca_output(
                rca_data,
                violation,
            )

            report.setdefault("evidence_packages", []).append(
                evidence_package
            )
            report.setdefault("rca_results", []).append(rca_data)

            report.setdefault("git_evidence", []).append(
                git_evidence.model_dump(mode="json")
            )
            report.setdefault("rca_outputs", []).append(
                structured_rca.model_dump(mode="json")
            )

            report["updated_at"] = datetime.now(
                timezone.utc
            ).isoformat()

            save_report(report)

        return {
            "report_id": report_id,
            "run_id": report.get("run_id") if report else None,
            "violation_id": violation.get("id"),
            "evidence": evidence_package,
            "rca": rca_data,
            "persistence": {
                "attached_to_report": bool(report),
                "git_evidence_saved": bool(report),
                "rca_saved": bool(report),
            },
        }

    except HTTPException:
        raise
    except Exception as exc:
        logger.exception("Violation analysis failed.")
        raise HTTPException(
            status_code=500,
            detail=f"Violation analysis failed: {str(exc)}",
        ) from exc
