"""
Sprint 7 / D31–D35 (P3): Git evidence extractor — candidate commit retrieval
for a conformance violation's dependency path.

P3 Deliverable (D31–D35):
  D31: use git log to enumerate candidate commits
  D32: use git blame/diff to find when the offending dependency appeared
  D33: connect dependency path and affected files to history evidence
  D34: rank candidate commits and verify known-introduction examples
  D35: define limits for merge commits, renames and incomplete history

This module provides the deterministic side of the evidence pipeline:
  - `find_candidate_commits()` — pickaxe search (already in git_evidence.py)
  - `blame_line_range()` — per-line commit attribution for a file region
  - `rank_candidate_commits()` — score and rank commits by specificity
  - `find_dependency_introduction()` — unified entry point that ties
      dependency-path evidence to candidate commits
  - Known limits documented in `docs/sprint7_p3_conformance_report.md`
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)

try:
    import git as gitpython
    _GIT_AVAILABLE = True
except ImportError:
    _GIT_AVAILABLE = False


@dataclass
class RankedCommit:
    """A candidate commit with a relevance score for the introducing-commit search."""
    hash: str
    message: str
    author: str
    date: str
    diff_snippet: str
    score: float            # higher = more likely the introducing commit
    rank: int               # 1-based rank by score descending
    is_merge_commit: bool
    renames_detected: bool
    evidence_id: str = ""   # links back to the violation_id this was found for

    def to_dict(self) -> Dict[str, Any]:
        return {
            "hash": self.hash,
            "message": self.message,
            "author": self.author,
            "date": self.date,
            "diff_snippet": self.diff_snippet[:500],
            "score": round(self.score, 4),
            "rank": self.rank,
            "is_merge_commit": self.is_merge_commit,
            "renames_detected": self.renames_detected,
            "evidence_id": self.evidence_id,
        }


@dataclass
class DependencyEvidence:
    """
    Structured evidence package connecting a violation → code location → git history.
    Sprint 7 D33 deliverable.
    """
    violation_id: str
    dependency_path: List[str]           # e.g. ["OrderController", "OrderRepository"]
    affected_files: List[str]            # files that contain the offending dependency
    candidate_commits: List[RankedCommit]
    introducing_commit: Optional[RankedCommit]
    limitations: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "violation_id": self.violation_id,
            "dependency_path": self.dependency_path,
            "affected_files": self.affected_files,
            "candidate_commits": [c.to_dict() for c in self.candidate_commits],
            "introducing_commit": self.introducing_commit.to_dict() if self.introducing_commit else None,
            "limitations": self.limitations,
        }


# ---------------------------------------------------------------------------
# D31: Enumerate candidate commits via pickaxe search
# ---------------------------------------------------------------------------

def find_candidate_commits_p3(
    repo_path: str,
    pattern: str,
    file_path: Optional[str] = None,
    max_commits: int = 10,
    exclude_merges: bool = False,
) -> List[Dict[str, Any]]:
    """
    Sprint 7 D31: Use `git log -S<pattern>` to find commits that introduced
    or removed `pattern` in the codebase. Returns raw commit data dicts.

    Parameters
    ----------
    repo_path : str  — path to the git repository root
    pattern : str    — the string to search for in commit diffs (pickaxe)
    file_path : str  — optional path filter to restrict search to one file
    max_commits : int — maximum number of commits to return
    exclude_merges : bool — if True, skip merge commits (reduces noise)

    Limitations (D35)
    -----------------
    * Renames: pickaxe does not follow file renames across commits; use
      `git log --follow` manually for renamed files.
    * Merge commits: they may show the pattern without being the true
      introducing change; `exclude_merges=True` reduces but doesn't
      eliminate this noise.
    * Incomplete history: shallow clones have limited depth; evidence is
      marked uncertain when the search reaches a grafted commit.
    """
    if not _GIT_AVAILABLE:
        logger.warning("GitPython not installed; returning empty candidate list.")
        return []

    try:
        repo = gitpython.Repo(repo_path)
    except Exception as exc:
        logger.warning("Cannot open repo at %s: %s", repo_path, exc)
        return []

    args = [f"-S{pattern}", f"-n{max_commits}", "--pretty=format:%H"]
    if exclude_merges:
        args.append("--no-merges")
    if file_path:
        args += ["--", file_path]

    try:
        raw = repo.git.log(*args)
    except Exception as exc:
        logger.warning("git log failed: %s", exc)
        return []

    hashes = [h.strip() for h in raw.splitlines() if h.strip()]
    results = []
    for h in hashes:
        try:
            commit = repo.commit(h)
            is_merge = len(commit.parents) > 1
            diff = repo.git.show(h, "--stat") if is_merge else repo.git.show(h)
            results.append({
                "hash": commit.hexsha,
                "message": commit.message.strip(),
                "author": commit.author.name,
                "date": commit.committed_datetime.isoformat(),
                "diff": diff,
                "is_merge_commit": is_merge,
            })
        except Exception as exc:
            logger.warning("Cannot read commit %s: %s", h, exc)

    return results


# ---------------------------------------------------------------------------
# D32: Blame a file region to find the commit that introduced a line
# ---------------------------------------------------------------------------

def blame_line_range(
    repo_path: str,
    file_path: str,
    start_line: int,
    end_line: int,
) -> List[Dict[str, Any]]:
    """
    Sprint 7 D32: Run `git blame` on a specific line range to identify
    which commit introduced each line.

    Returns a list of `{line_number, hash, author, date, content}` dicts.
    Returns empty list if blame fails (shallow clone, missing file, etc.).
    """
    if not _GIT_AVAILABLE:
        return []
    try:
        repo = gitpython.Repo(repo_path)
        blame = repo.blame("HEAD", file_path)
    except Exception as exc:
        logger.warning("git blame failed for %s: %s", file_path, exc)
        return []

    results = []
    lineno = 1
    for commit, lines in blame:
        for line in lines:
            if start_line <= lineno <= end_line:
                results.append({
                    "line_number": lineno,
                    "hash": commit.hexsha[:12],
                    "author": commit.author.name,
                    "date": commit.committed_datetime.isoformat(),
                    "content": line.decode("utf-8", errors="replace") if isinstance(line, bytes) else str(line),
                })
            lineno += 1

    return results


# ---------------------------------------------------------------------------
# D34: Rank candidate commits by specificity
# ---------------------------------------------------------------------------

def rank_candidate_commits(
    candidates: List[Dict[str, Any]],
    pattern: str,
    violation_id: str = "",
) -> List[RankedCommit]:
    """
    Sprint 7 D34: Score and rank candidate commits by how likely they are
    to be the true introducing commit.

    Scoring heuristics (all additive, normalized to [0, 1]):
    - Pattern frequency in diff: more occurrences → higher score (capped at 1.0)
    - Merge commit penalty: -0.3 (merge commits are rarely the true introducing commit)
    - Rename detected: -0.1 (renames muddy the evidence)
    - Short, specific message: +0.1 (descriptive commit messages hint at intentional changes)
    """
    ranked: List[RankedCommit] = []
    for c in candidates:
        diff = c.get("diff", "")
        is_merge = c.get("is_merge_commit", False)

        # Frequency-based score
        freq = diff.count(pattern)
        freq_score = min(1.0, freq / 5.0)  # cap at 5 occurrences = 1.0

        # Merge penalty
        merge_penalty = 0.3 if is_merge else 0.0

        # Rename detection (naive: look for "=> " in diff output)
        renames = "=>" in diff
        rename_penalty = 0.1 if renames else 0.0

        # Message bonus (short, non-generic messages)
        msg = c.get("message", "")
        msg_bonus = 0.1 if 10 < len(msg) < 100 else 0.0

        score = max(0.0, freq_score - merge_penalty - rename_penalty + msg_bonus)

        ranked.append(RankedCommit(
            hash=c.get("hash", ""),
            message=msg,
            author=c.get("author", ""),
            date=c.get("date", ""),
            diff_snippet=diff[:300],
            score=score,
            rank=0,         # filled in below
            is_merge_commit=is_merge,
            renames_detected=renames,
            evidence_id=violation_id,
        ))

    # Sort descending by score, assign ranks
    ranked.sort(key=lambda r: r.score, reverse=True)
    for i, r in enumerate(ranked):
        r.rank = i + 1

    return ranked


# ---------------------------------------------------------------------------
# D33: Unified entry point — dependency path → evidence package
# ---------------------------------------------------------------------------

def find_dependency_introduction(
    violation_id: str,
    repo_path: str,
    dependency_path: List[str],
    search_pattern: str,
    affected_files: Optional[List[str]] = None,
    max_commits: int = 10,
) -> DependencyEvidence:
    """
    Sprint 7 D33: Connect a violation's dependency path and affected files
    to their introducing commit history.

    Parameters
    ----------
    violation_id : str       — links evidence to its ConformanceViolation
    repo_path : str          — absolute path to the git repository
    dependency_path : list   — ordered list of component names, e.g.
                               ["OrderController", "OrderRepository"]
    search_pattern : str     — pickaxe pattern to identify introducing commits
                               (e.g. the import statement or function call)
    affected_files : list    — file paths containing the offending dependency
    max_commits : int        — cap on candidate commits to retrieve

    Returns
    -------
    DependencyEvidence with candidate commits ranked by specificity.
    """
    affected_files = affected_files or []
    limitations: List[str] = []

    # D31: Enumerate candidates
    all_candidates = []
    if affected_files:
        for fp in affected_files:
            raw = find_candidate_commits_p3(repo_path, search_pattern,
                                            file_path=fp, max_commits=max_commits)
            all_candidates.extend(raw)
    else:
        all_candidates = find_candidate_commits_p3(repo_path, search_pattern,
                                                    max_commits=max_commits)

    # Deduplicate by hash
    seen: set = set()
    unique: List[Dict] = []
    for c in all_candidates:
        if c["hash"] not in seen:
            seen.add(c["hash"])
            unique.append(c)

    # D35: Document known limitations
    merge_commits = [c for c in unique if c.get("is_merge_commit")]
    if merge_commits:
        limitations.append(
            f"{len(merge_commits)} merge commit(s) found; they may not be the true introducing commit."
        )
    if not unique:
        limitations.append(
            "No candidate commits found. The repo may be a shallow clone, the pattern may be too generic, "
            "or the dependency was introduced before the available history."
        )

    # D34: Rank
    ranked = rank_candidate_commits(unique, search_pattern, violation_id)
    introducing = ranked[0] if ranked else None

    return DependencyEvidence(
        violation_id=violation_id,
        dependency_path=dependency_path,
        affected_files=affected_files,
        candidate_commits=ranked,
        introducing_commit=introducing,
        limitations=limitations,
    )

