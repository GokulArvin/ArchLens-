"""
API Routes - Violations & RCA
POST /api/v1/analyze-violation
"""

from fastapi import APIRouter, HTTPException
from app.modules.git_evidence.extractor import GitEvidenceExtractor
from app.modules.llm_rca.analyzer import RCAAnalyzer
from app.schemas.models import AnalyzeViolationRequest

router = APIRouter()
rca_analyzer = RCAAnalyzer()


@router.post("/analyze-violation", response_model=dict)
async def analyze_violation(body: dict):
    """
    Given a violation + repo path, extract git evidence and run LLM RCA.
    """
    repo_path = body.get("repo_path", "")
    violation = body.get("violation", {})
    source_file = body.get("source_file", "")
    target_symbol = body.get("target_symbol", "")

    if not violation:
        raise HTTPException(status_code=400, detail="violation is required")

    # Extract git evidence
    evidence_package = {"violation": violation, "dependency_path": [
        violation.get("source", ""), violation.get("target", "")
    ]}

    if repo_path and source_file:
        try:
            git_extractor = GitEvidenceExtractor(repo_path)
            evidence_package = git_extractor.build_evidence_package(
                violation, source_file, target_symbol
            )
        except Exception as e:
            evidence_package["git_error"] = str(e)

    # Run LLM RCA
    try:
        rca_output = rca_analyzer.analyze(evidence_package)
        return {"evidence": evidence_package, "rca": rca_output}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
