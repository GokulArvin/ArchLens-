"""
API Routes - Repository Analysis
POST /api/v1/analyze-repository
"""

from fastapi import APIRouter, HTTPException
from app.modules.architecture_recovery.ast_parser import ArchitectureRecoveryPipeline
from app.schemas.models import AnalyzeRepositoryRequest

router = APIRouter()
recovery_pipeline = ArchitectureRecoveryPipeline()


@router.post("/analyze-repository", response_model=dict)
async def analyze_repository(request: AnalyzeRepositoryRequest):
    """
    Analyze a repository and extract the current architecture graph (G_C).
    """
    try:
        result = recovery_pipeline.analyze_repository(
            request.repo_path, request.language
        )
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Repository analysis failed: {str(e)}")
