
"""API routes for persisted conformance reports."""

from fastapi import APIRouter, HTTPException

from app.database.report_store import (
    get_report as get_stored_report,
    list_reports as list_stored_reports,
)

router = APIRouter()


@router.get("/report/{report_id}", response_model=dict)
async def get_report(report_id: str):
    """Retrieve a complete conformance report."""

    report = get_stored_report(report_id)

    if report is None:
        raise HTTPException(
            status_code=404,
            detail=f"Report {report_id} not found",
        )

    return report


@router.get("/reports", response_model=list)
async def list_reports():
    """List metadata for all saved conformance reports."""

    return list_stored_reports()
