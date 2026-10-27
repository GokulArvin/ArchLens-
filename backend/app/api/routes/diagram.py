"""
API Routes - Diagram Analysis
POST /api/v1/analyze-diagram
"""

from fastapi import APIRouter, UploadFile, File, HTTPException
from pathlib import Path
import shutil
import uuid

from app.modules.cv_pipeline.pipeline import CVPipeline
from app.schemas.models import AnalyzeDiagramRequest, ArchGraph

router = APIRouter()
cv_pipeline = CVPipeline()


@router.post("/analyze-diagram", response_model=dict)
async def analyze_diagram(file: UploadFile = File(...)):
    """
    Upload an architecture diagram image and extract the intended architecture graph (G_I).
    """
    # Save uploaded file
    upload_dir = Path("data/uploads")
    upload_dir.mkdir(parents=True, exist_ok=True)
    file_id = str(uuid.uuid4())
    file_path = upload_dir / f"{file_id}_{file.filename}"

    with open(file_path, "wb") as f:
        shutil.copyfileobj(file.file, f)

    try:
        result = cv_pipeline.analyze(str(file_path))
        result["diagram_id"] = file_id
        result["filename"] = file.filename
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"CV analysis failed: {str(e)}")
