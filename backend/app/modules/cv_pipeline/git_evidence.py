"""
Sprint 7 / D33: Git evidence mining - candidate-commit retrieval for a
violation's dependency path.

This is P1's side of the input contract P3's RCA evidence pipeline needs:
given a real cloned repository and a search pattern describing the
dependency that was introduced (e.g. a URL, function name, or import), use
Git's pickaxe search (`git log -S<pattern>`) to find real candidate commits,
ranked newest-first. Populates the shared `GitCommit`/`GitEvidence` schemas
from app.schemas.models directly - no separate evidence schema invented.
"""

from __future__ import annotations

import git

from app.schemas.models import GitCommit, GitEvidence


def find_candidate_commits(repo_path: str, pattern: str, file_path: str | None = None, max_commits: int = 10) -> list[GitCommit]:
    """Pickaxe search: commits whose diff added/removed `pattern`, newest first."""
    repo = git.Repo(repo_path)
    # Options must precede the `--` pathspec separator, or git treats them as paths.
    args = ["-S", pattern, f"-n{max_commits}", "--pretty=format:%H"]
    if file_path:
        args += ["--", file_path]
    # GitPython's iter_commits() has no pickaxe (-S) support; use `git log` directly.
    raw = repo.git.log(*args)
    hashes = [h for h in raw.splitlines() if h.strip()]

    results = []
    for h in hashes:
        commit = repo.commit(h)
        diff = repo.git.show(h)
        results.append(GitCommit(
            hash=commit.hexsha,
            message=commit.message.strip(),
            author=commit.author.name,
            date=commit.committed_datetime.isoformat(),
            diff=diff,
        ))
    return results


def build_git_evidence(
    violation_id: str,
    repo_path: str,
    pattern: str,
    file_path: str,
    dependency_path: list[str],
    max_commits: int = 10,
) -> GitEvidence:
    """Find candidate commits and package the real evidence for one violation.

    `pattern` should be as specific as possible to the actual change (e.g. a
    new function/route name, not a generic string that may already exist
    elsewhere in the file) - pickaxe search can't otherwise tell "this
    commit re-touched an existing reference" from "this commit introduced
    the dependency". Empirically (see docs/sprint7_git_evidence_report.md):
    a specific pattern isolates exactly one commit, which is returned as
    `introducing_commit` with no ambiguity. If multiple commits match, the
    newest is returned as the best single guess (most likely cause of
    current behavior) and the rest as `related_commits` - but this is a
    heuristic, not a guarantee, for the ambiguous case.
    """
    candidates = find_candidate_commits(repo_path, pattern, file_path=file_path, max_commits=max_commits)
    introducing = candidates[0] if candidates else None  # newest match (find_candidate_commits returns newest-first)
    related = candidates[1:]
    return GitEvidence(
        violation_id=violation_id,
        file=file_path,
        dependency_path=dependency_path,
        introducing_commit=introducing,
        related_commits=related,
    )
