"""
Sprint 7 / D34 (P3): Unit tests for Git evidence extractor (P3 side).

Tests the ranking, evidence-package structure, and limit-documentation
functions in git_evidence_p3.py WITHOUT requiring a real cloned repository.
"""

from __future__ import annotations


from app.modules.cv_pipeline.git_evidence_p3 import (
    DependencyEvidence,
    RankedCommit,
    find_dependency_introduction,
    rank_candidate_commits,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_commit(hash_: str, message: str, pattern: str, count: int = 1,
                 is_merge: bool = False, has_rename: bool = False) -> dict:
    diff = (pattern * count) + (" => " if has_rename else "")
    return {
        "hash": hash_,
        "message": message,
        "author": "Test Author",
        "date": "2024-01-01T00:00:00",
        "diff": diff,
        "is_merge_commit": is_merge,
    }


# ---------------------------------------------------------------------------
# D34: rank_candidate_commits
# ---------------------------------------------------------------------------

class TestRankCandidateCommits:

    def test_higher_frequency_scores_higher(self):
        """A commit with more pattern occurrences ranks higher."""
        candidates = [
            _make_commit("aaa", "minor fix", "import_x", count=1),
            _make_commit("bbb", "add import_x usage", "import_x", count=5),
        ]
        ranked = rank_candidate_commits(candidates, "import_x")
        assert ranked[0].hash == "bbb"
        assert ranked[0].rank == 1

    def test_merge_commit_penalised(self):
        """Merge commits receive a lower score than equivalent regular commits."""
        candidates = [
            _make_commit("ccc", "feat: add X", "X", count=3, is_merge=False),
            _make_commit("ddd", "Merge branch Y", "X", count=3, is_merge=True),
        ]
        ranked = rank_candidate_commits(candidates, "X")
        # Regular commit should rank higher
        assert ranked[0].hash == "ccc"

    def test_rename_detected_penalised(self):
        """Commits with renames in the diff receive a lower score."""
        candidates = [
            _make_commit("eee", "refactor", "dep", count=2, has_rename=True),
            _make_commit("fff", "add dep", "dep", count=2, has_rename=False),
        ]
        ranked = rank_candidate_commits(candidates, "dep")
        assert ranked[0].hash == "fff"

    def test_ranks_are_1_based_contiguous(self):
        """Ranks are 1-based and contiguous."""
        candidates = [
            _make_commit("g", "a", "p", count=1),
            _make_commit("h", "b", "p", count=2),
            _make_commit("i", "c", "p", count=3),
        ]
        ranked = rank_candidate_commits(candidates, "p")
        assert [r.rank for r in ranked] == [1, 2, 3]

    def test_empty_candidates_returns_empty(self):
        assert rank_candidate_commits([], "anything") == []

    def test_single_candidate_is_rank_1(self):
        candidates = [_make_commit("j", "sole commit", "token", count=2)]
        ranked = rank_candidate_commits(candidates, "token", violation_id="v42")
        assert len(ranked) == 1
        assert ranked[0].rank == 1
        assert ranked[0].evidence_id == "v42"

    def test_to_dict_has_expected_keys(self):
        candidates = [_make_commit("k", "msg", "pat", count=1)]
        ranked = rank_candidate_commits(candidates, "pat")
        d = ranked[0].to_dict()
        for key in ("hash", "message", "author", "date", "diff_snippet",
                    "score", "rank", "is_merge_commit", "renames_detected"):
            assert key in d, f"Missing key: {key}"


# ---------------------------------------------------------------------------
# D33: DependencyEvidence structure
# ---------------------------------------------------------------------------

class TestDependencyEvidenceStructure:

    def test_to_dict_structure(self):
        evidence = DependencyEvidence(
            violation_id="v1",
            dependency_path=["ControllerA", "RepositoryB"],
            affected_files=["src/controller.py"],
            candidate_commits=[],
            introducing_commit=None,
            limitations=["No candidates found."],
        )
        d = evidence.to_dict()
        for key in ("violation_id", "dependency_path", "affected_files",
                    "candidate_commits", "introducing_commit", "limitations"):
            assert key in d
        assert d["introducing_commit"] is None
        assert d["limitations"] == ["No candidates found."]

    def test_introducing_commit_in_dict(self):
        rc = RankedCommit(
            hash="abc123",
            message="add dep",
            author="Alice",
            date="2024-01-01",
            diff_snippet="import RepositoryB",
            score=0.9,
            rank=1,
            is_merge_commit=False,
            renames_detected=False,
            evidence_id="v1",
        )
        evidence = DependencyEvidence(
            violation_id="v1",
            dependency_path=["A", "B"],
            affected_files=[],
            candidate_commits=[rc],
            introducing_commit=rc,
        )
        d = evidence.to_dict()
        assert d["introducing_commit"]["hash"] == "abc123"
        assert d["introducing_commit"]["rank"] == 1


# ---------------------------------------------------------------------------
# D33 / D35: find_dependency_introduction without real repo (graceful degradation)
# ---------------------------------------------------------------------------

class TestFindDependencyIntroductionNoRepo:

    def test_nonexistent_repo_returns_empty_evidence(self):
        """When the repo path doesn't exist, evidence is returned with limitations."""
        evidence = find_dependency_introduction(
            violation_id="v99",
            repo_path="/nonexistent/path/to/repo",
            dependency_path=["A", "B"],
            search_pattern="import_B",
            affected_files=[],
        )
        assert isinstance(evidence, DependencyEvidence)
        assert evidence.introducing_commit is None
        assert evidence.candidate_commits == []
        # Limitations must document the failure
        assert len(evidence.limitations) >= 1

    def test_evidence_id_matches_violation_id(self):
        """The violation_id on the evidence package matches the input."""
        evidence = find_dependency_introduction(
            violation_id="violation-42",
            repo_path="/nonexistent",
            dependency_path=["Ctrl", "Repo"],
            search_pattern="from repo import Repo",
        )
        assert evidence.violation_id == "violation-42"

    def test_dependency_path_preserved(self):
        evidence = find_dependency_introduction(
            violation_id="v1",
            repo_path="/nonexistent",
            dependency_path=["ServiceA", "DatabaseB"],
            search_pattern="DatabaseB",
        )
        assert evidence.dependency_path == ["ServiceA", "DatabaseB"]

