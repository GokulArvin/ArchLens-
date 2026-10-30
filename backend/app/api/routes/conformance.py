"""
API Routes - Conformance Checking
POST /api/v1/check-conformance
POST /api/v1/check-conformance/inline
"""

from fastapi import APIRouter, HTTPException
from app.modules.conformance_engine.engine import ConformanceEngine
from app.schemas.models import CheckConformanceRequest

router = APIRouter()
engine = ConformanceEngine()


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