
"""Application service for conformance report persistence.

API routers depend on this service rather than importing the database
implementation directly. This keeps HTTP concerns separate from storage.
"""

from typing import Any, Optional

from app.database import report_store


def save_report(report: dict[str, Any]) -> str:
    """Persist a complete report."""
    return report_store.save_report(report)


def get_report(report_id: str) -> Optional[dict[str, Any]]:
    """Retrieve a report by its identifier."""
    return report_store.get_report(report_id)


def list_reports() -> list[dict[str, Any]]:
    """List report metadata."""
    return report_store.list_reports()


def delete_report(report_id: str) -> bool:
    """Delete a report by its identifier."""
    return report_store.delete_report(report_id)
