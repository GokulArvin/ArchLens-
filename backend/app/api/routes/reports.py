"""
API Routes - Reports
GET /api/v1/report/{id}
"""

from fastapi import APIRouter, HTTPException

router = APIRouter()

# In-memory store (replace with DB in full implementation)
_reports: dict = {}


@router.get("/report/{report_id}", response_model=dict)
async def get_report(report_id: str):
    """Get a conformance report by ID."""
    if report_id not in _reports:
        raise HTTPException(status_code=404, detail=f"Report {report_id} not found")
    return _reports[report_id]


@router.get("/reports", response_model=list)
async def list_reports():
    """List all available reports."""
    return list(_reports.keys())
