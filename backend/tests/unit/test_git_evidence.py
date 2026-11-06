from git import Repo, Actor

from app.modules.git_evidence.extractor import GitEvidenceExtractor


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
