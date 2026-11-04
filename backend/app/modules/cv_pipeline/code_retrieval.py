"""
Sprint 7 / D32: retrieve the real affected code entity for a violation.

P1's side of this handoff: given a violation's file path (and optionally a
line range from GitEvidence), fetch the real current file content from the
cloned repository. P3 would normally supply the affected entity's exact
location from its static-analysis graph; here, we demonstrate the retrieval
side against a real cloned repo (data/repositories/flask-microservice-demo).
"""

from __future__ import annotations

from pathlib import Path


class AffectedCodeNotFoundError(Exception):
    pass


def retrieve_file_content(repo_path: str, file_path: str) -> str:
    """Read the real current content of a file inside a cloned repository."""
    full_path = Path(repo_path) / file_path
    if not full_path.exists():
        raise AffectedCodeNotFoundError(f"{file_path} not found in {repo_path}")
    return full_path.read_text(encoding="utf-8")


def retrieve_line_range(repo_path: str, file_path: str, lines: str) -> str:
    """Read a specific "start-end" line range (1-indexed, inclusive) from a real file."""
    content = retrieve_file_content(repo_path, file_path)
    all_lines = content.splitlines()
    start_str, _, end_str = lines.partition("-")
    start, end = int(start_str), int(end_str or start_str)
    return "\n".join(all_lines[start - 1:end])
