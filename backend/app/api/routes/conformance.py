
"""
API Routes - Conformance Checking

POST /api/v1/check-conformance
POST /api/v1/check-conformance/inline
POST /api/v1/check-conformance/repository
"""

from fastapi import APIRouter, HTTPException

from app.modules.conformance_engine.engine import ConformanceEngine
from app.modules.architecture_recovery.ast_parser import (
    ArchitectureRecoveryPipeline,
)

router = APIRouter()

engine = ConformanceEngine()
recovery_pipeline = ArchitectureRecoveryPipeline()


@router.post("/check-conformance", response_model=dict)
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
        return engine.check_conformance(intended, current)
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Conformance check failed: {str(e)}",
        )


@router.post("/check-conformance/inline", response_model=dict)
async def check_conformance_inline(body: dict):
    """
    Check conformance with graphs provided inline in the request body.
    """
    intended = body.get("intended_graph")
    current = body.get("current_graph")

    if not intended or not current:
        raise HTTPException(
            status_code=400,
            detail="Both intended_graph and current_graph are required.",
        )

    try:
        return engine.check_conformance(intended, current)
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Conformance check failed: {str(e)}",
        )


@router.post("/check-conformance/repository", response_model=dict)
async def check_repository_conformance(body: dict):
    """
    Automatically analyze a repository and check its architecture
    against the supplied intended architecture graph.
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

        result = engine.check_conformance(
            intended,
            current,
        )

        return result

    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Repository conformance check failed: {str(e)}",
        )
