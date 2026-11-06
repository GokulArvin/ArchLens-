"""
API Routes - Diagram Analysis
POST /api/v1/analyze-diagram
"""

import json
from pathlib import Path
import shutil
import uuid
from typing import Optional

from fastapi import APIRouter, UploadFile, File, Form, HTTPException

from app.api.routes.conformance import check_repository_conformance
from app.core.config import settings
from app.modules.cv_pipeline.pipeline import CVPipeline
from app.schemas.models import CheckConformanceResponse

router = APIRouter()
cv_pipeline = CVPipeline({
    "yolo_model_path": settings.CV_YOLO_MODEL_PATH or None,
    "confidence": settings.CV_CONFIDENCE_THRESHOLD,
    "use_region_fallback": settings.CV_ENABLE_REGION_FALLBACK,
})


@router.post("/analyze-diagram", response_model=dict)
async def analyze_diagram(file: UploadFile = File(...)):
    """
    Upload an architecture diagram image and extract the intended architecture graph (G_I).
    """
    # Save uploaded file
    filename = Path(file.filename or "diagram").name
    if Path(filename).suffix.lower() not in {".png", ".jpg", ".jpeg"}:
        raise HTTPException(status_code=400, detail="Diagram must be a PNG or JPEG image.")

    upload_dir = Path(settings.UPLOAD_DIR)
    upload_dir.mkdir(parents=True, exist_ok=True)
    file_id = str(uuid.uuid4())
    file_path = upload_dir / f"{file_id}_{filename}"

    with open(file_path, "wb") as f:
        shutil.copyfileobj(file.file, f)

    try:
        result = cv_pipeline.analyze(str(file_path))
        result["diagram_id"] = file_id
        result["filename"] = filename
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"CV analysis failed: {str(e)}")


@router.post("/analyze-and-check", response_model=CheckConformanceResponse)
async def analyze_and_check(
    file: UploadFile = File(...),
    repo_path: str = Form(...),
    language: str = Form(default="python"),
    manual_mappings_json: str = Form(default="{}"),
    ruleset_json: Optional[str] = Form(default=None),
):
    """Run diagram extraction, repository recovery, alignment and conformance.

    Manual mappings use diagram component IDs as keys and recovered repository
    component IDs as values. They are especially useful for region-proposal
    components whose names are intentionally generic.
    """
    filename = Path(file.filename or "diagram").name
    if Path(filename).suffix.lower() not in {".png", ".jpg", ".jpeg"}:
        raise HTTPException(status_code=400, detail="Diagram must be a PNG or JPEG image.")

    try:
        manual_mappings = json.loads(manual_mappings_json or "{}")
        ruleset = json.loads(ruleset_json) if ruleset_json else None
    except json.JSONDecodeError as error:
        raise HTTPException(status_code=400, detail=f"Invalid JSON form field: {error.msg}")

    if not isinstance(manual_mappings, dict):
        raise HTTPException(status_code=400, detail="manual_mappings_json must be a JSON object.")
    if ruleset is not None and not isinstance(ruleset, dict):
        raise HTTPException(status_code=400, detail="ruleset_json must be a JSON object.")
    if not repo_path:
        raise HTTPException(status_code=400, detail="repo_path is required.")

    upload_dir = Path(settings.UPLOAD_DIR)
    upload_dir.mkdir(parents=True, exist_ok=True)
    diagram_id = str(uuid.uuid4())
    file_path = upload_dir / f"{diagram_id}_{filename}"

    try:
        with file_path.open("wb") as output:
            shutil.copyfileobj(file.file, output)

        intended_graph = cv_pipeline.analyze(str(file_path))
        if not intended_graph.get("components"):
            raise HTTPException(
                status_code=422,
                detail="Diagram extraction found no candidate components; no conformance report was created.",
            )

        intended_graph["diagram_id"] = diagram_id
        intended_graph["filename"] = filename
        return await check_repository_conformance({
            "intended_graph": intended_graph,
            "repo_path": repo_path,
            "language": language,
            "manual_mappings": manual_mappings,
            "ruleset": ruleset,
            "diagram_path": str(file_path),
        })
    except HTTPException:
        raise
    except FileNotFoundError as error:
        raise HTTPException(status_code=404, detail=str(error))
    except Exception as error:
        raise HTTPException(status_code=500, detail=f"End-to-end analysis failed: {str(error)}")
