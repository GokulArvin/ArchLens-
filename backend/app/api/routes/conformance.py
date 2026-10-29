"""
API Routes - Conformance Checking
POST /api/v1/check-conformance
"""

from fastapi import APIRouter, HTTPException
from app.modules.conformance_engine.engine import ConformanceEngine
from app.schemas.models import CheckConformanceRequest

router = APIRouter()
engine = ConformanceEngine()


@router.post("/check-conformance", response_model=dict)
async def check_conformance(request: CheckConformanceRequest):
    """
    Compare the intended (G_I) and current (G_C) architecture graphs
    and return all detected violations and conformance verdicts.
    """
    try:
        if request.intended_graph and request.current_graph:
            result = engine.check_conformance(
                request.intended_graph, request.current_graph, request.ruleset
            )
            return result
        return {
            "message": "Conformance engine ready. Provide intended_graph and current_graph in request body.",
            "supported_verdicts": ["CONFORMANT", "VIOLATION", "MISSING", "UNEXPECTED", "UNCERTAIN"],
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/check-conformance/inline", response_model=dict)
async def check_conformance_inline(body: dict):
    """
    Check conformance with graphs and optional ruleset provided inline in the request body.
    """
    intended = body.get("intended_graph", {})
    current = body.get("current_graph", {})
    ruleset = body.get("ruleset")
    if not intended or not current:
        raise HTTPException(
            status_code=400, detail="Both intended_graph and current_graph are required."
        )

    try:
        result = engine.check_conformance(intended, current, ruleset)
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
