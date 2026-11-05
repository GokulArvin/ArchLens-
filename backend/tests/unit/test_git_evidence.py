"""
Sprint 7 / D34: RCA test case where the introducing commit is known - 100%
real, not synthetic. The known-good answer (commit d98872f) was verified by
manually reading `git show d98872f` against the real cloned repository
before writing this test (see docs/sprint7_git_evidence_report.md).

Requires the real clone from backend/scripts/clone_demo_repo.py; skipped
(not failed) if it hasn't been run, so the rest of the suite stays fast and
network-independent by default.
"""

from pathlib import Path

import pytest

from app.modules.cv_pipeline.code_retrieval import AffectedCodeNotFoundError, retrieve_file_content, retrieve_line_range
from app.modules.cv_pipeline.git_evidence import build_git_evidence, find_candidate_commits

REPO_ROOT = Path(__file__).resolve().parents[3]
CLONE_PATH = REPO_ROOT / "data" / "repositories" / "flask-microservice-demo"

KNOWN_INTRODUCING_COMMIT = "d98872fcde8ae00f9df3224c1d5d4f08eb312429"

requires_clone = pytest.mark.skipif(
    not CLONE_PATH.exists(), reason="run backend/scripts/clone_demo_repo.py to fetch the real test repo first"
)


@requires_clone
def test_specific_pattern_finds_exactly_the_known_commit():
    commits = find_candidate_commits(str(CLONE_PATH), "cust_search", file_path="backend/src/run.py")
    assert len(commits) == 1
    assert commits[0].hash == KNOWN_INTRODUCING_COMMIT


@requires_clone
def test_generic_pattern_finds_multiple_real_commits_honestly():
    """A less specific pattern genuinely matches more than one real commit -
    this is the real, demonstrated reason build_git_evidence can't just
    assume a single answer (see its docstring)."""
    commits = find_candidate_commits(str(CLONE_PATH), "demo_orders", file_path="backend/src/run.py")
    assert len(commits) >= 2
    assert KNOWN_INTRODUCING_COMMIT in [c.hash for c in commits]


@requires_clone
def test_build_git_evidence_identifies_the_real_introducing_commit():
    evidence = build_git_evidence(
        violation_id="v1",
        repo_path=str(CLONE_PATH),
        pattern="cust_search",
        file_path="backend/src/run.py",
        dependency_path=["backend", "orders"],
    )
    assert evidence.introducing_commit is not None
    assert evidence.introducing_commit.hash == KNOWN_INTRODUCING_COMMIT
    assert evidence.introducing_commit.author == "Michael Litherland"
    assert "custSearch" in evidence.introducing_commit.message or "search" in evidence.introducing_commit.message.lower()
    assert evidence.related_commits == []  # unambiguous - nothing else matched


@requires_clone
def test_retrieved_code_matches_the_real_route_handler():
    code = retrieve_line_range(str(CLONE_PATH), "backend/src/run.py", "25-29")
    assert "custSearch" in code
    assert "demo_orders" in code


@requires_clone
def test_retrieve_file_content_reads_a_real_file():
    content = retrieve_file_content(str(CLONE_PATH), "backend/src/run.py")
    assert "from flask import" in content


@requires_clone
def test_retrieve_file_content_raises_for_missing_file():
    with pytest.raises(AffectedCodeNotFoundError):
        retrieve_file_content(str(CLONE_PATH), "backend/src/does_not_exist.py")
