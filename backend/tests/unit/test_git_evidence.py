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
from git import Repo

from app.modules.cv_pipeline.code_retrieval import AffectedCodeNotFoundError, retrieve_file_content, retrieve_line_range
from app.modules.cv_pipeline.git_evidence import build_git_evidence, find_candidate_commits
from app.modules.git_evidence.extractor import GitEvidenceExtractor

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

def create_repo(tmp_path):
    repo = Repo.init(tmp_path)
    repo.config_writer().set_value("user", "name", "Test User").release()
    repo.config_writer().set_value("user", "email", "test@example.com").release()

    source = tmp_path / "sample.py"
    source.write_text("import os\n\ndef hello():\n    return 'hello'\n", encoding="utf-8")
    repo.index.add(["sample.py"])
    repo.index.commit("Initial commit")

    source.write_text(
        "import os\nimport json\n\ndef hello():\n    return 'hello'\n",
        encoding="utf-8",
    )
    repo.index.add(["sample.py"])
    repo.index.commit("Add json import")

    return repo, source


def test_initializes_valid_git_repository(tmp_path):
    repo, _ = create_repo(tmp_path)
    extractor = GitEvidenceExtractor(str(tmp_path))
    assert extractor.repo is not None
    assert extractor.repo.working_tree_dir == repo.working_tree_dir


def test_handles_invalid_repository(tmp_path):
    extractor = GitEvidenceExtractor(str(tmp_path / "missing"))
    assert extractor.repo is None
    assert extractor.get_blame("sample.py") == []


def test_rejects_path_outside_repository(tmp_path):
    create_repo(tmp_path)
    extractor = GitEvidenceExtractor(str(tmp_path))
    outside = tmp_path.parent / "outside.py"
    outside.write_text("print('outside')", encoding="utf-8")
    assert extractor._resolve_file_path(str(outside)) is None


def test_resolves_existing_repository_file(tmp_path):
    create_repo(tmp_path)
    extractor = GitEvidenceExtractor(str(tmp_path))
    assert extractor._resolve_file_path("sample.py") == "sample.py"


def test_get_blame_returns_commit_information(tmp_path):
    create_repo(tmp_path)
    extractor = GitEvidenceExtractor(str(tmp_path))
    blame = extractor.get_blame("sample.py")
    assert blame
    assert all("commit_hash" in item and "line" in item for item in blame)


def test_get_blame_filters_requested_lines(tmp_path):
    create_repo(tmp_path)
    extractor = GitEvidenceExtractor(str(tmp_path))
    blame = extractor.get_blame("sample.py", line_numbers=[1])
    assert len(blame) == 1
    assert blame[0]["line"] == "import os"


def test_get_commits_for_file(tmp_path):
    create_repo(tmp_path)
    extractor = GitEvidenceExtractor(str(tmp_path))
    commits = extractor.get_commits_for_file("sample.py")
    assert len(commits) == 2
    assert commits[0]["message"] == "Add json import"


def test_get_diff_contains_added_import(tmp_path):
    repo, _ = create_repo(tmp_path)
    extractor = GitEvidenceExtractor(str(tmp_path))
    latest_commit = repo.head.commit.hexsha
    diff = extractor.get_diff(latest_commit, "sample.py")
    assert "import json" in diff


def test_find_introducing_commit(tmp_path):
    create_repo(tmp_path)
    extractor = GitEvidenceExtractor(str(tmp_path))
    result = extractor.find_introducing_commit("sample.py", "import json")
    assert result is not None
    assert "import json" in result["diff"]
    assert result["message"] == "Add json import"


def test_get_code_context_finds_symbol(tmp_path):
    create_repo(tmp_path)
    extractor = GitEvidenceExtractor(str(tmp_path))
    result = extractor.get_code_context("sample.py", target_symbol="hello")
    assert result["found"] is True
    assert "def hello():" in result["content"]
    assert result["line_numbers"]


def test_get_code_context_handles_missing_symbol(tmp_path):
    create_repo(tmp_path)
    extractor = GitEvidenceExtractor(str(tmp_path))
    result = extractor.get_code_context("sample.py", target_symbol="missing_symbol")
    assert result["found"] is False
    assert result["content"] == ""


def test_build_evidence_package(tmp_path):
    create_repo(tmp_path)
    extractor = GitEvidenceExtractor(str(tmp_path))
    violation = {
        "source": "frontend",
        "target": "database",
        "rule": "forbidden_dependency",
    }
    package = extractor.build_evidence_package(
        violation,
        "sample.py",
        target_symbol="import json",
    )
    assert package["violation"] == violation
    assert package["dependency_path"] == ["frontend", "database"]
    assert package["evidence_metadata"]["git_available"] is True
    assert package["evidence_metadata"]["total_items"] > 0
    assert package["evidence_items"][0]["evidence_id"] == "E001"

