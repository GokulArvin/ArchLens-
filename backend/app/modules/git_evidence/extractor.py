"""
Git Evidence Extraction
Determines which commits introduced architecture violations.
Uses GitPython for programmatic git access.
"""

from git import Repo, GitCommandError
from pathlib import Path
from typing import List, Dict, Any, Optional
import logging

logger = logging.getLogger(__name__)


class GitEvidenceExtractor:
    """
    Extracts git evidence for architecture violations.
    Uses git log, blame, and diff to identify introducing commits.
    """

    def __init__(self, repo_path: str):
        try:
            self.repo = Repo(repo_path)
            self.repo_path = Path(repo_path)
            logger.info(f"Git repo initialized: {repo_path}")
        except Exception as e:
            logger.error(f"Failed to initialize git repo at {repo_path}: {e}")
            self.repo = None

    def get_blame(self, file_path: str, line_numbers: Optional[List[int]] = None) -> List[Dict]:
        """Run git blame on a file to identify introducing commits per line."""
        if not self.repo:
            return []

        try:
            blame = self.repo.blame("HEAD", file_path)
            results = []
            for commit, lines in blame:
                results.append({
                    "commit_hash": commit.hexsha,
                    "commit_message": commit.message.strip(),
                    "author": str(commit.author),
                    "date": commit.committed_datetime.isoformat(),
                    "lines": [l.decode("utf-8", errors="ignore") if isinstance(l, bytes) else l
                              for l in lines],
                })
            return results
        except Exception as e:
            logger.warning(f"git blame failed for {file_path}: {e}")
            return []

    def get_commits_for_file(
        self, file_path: str, max_commits: int = 50
    ) -> List[Dict]:
        """Get commit history for a specific file."""
        if not self.repo:
            return []

        try:
            commits = list(self.repo.iter_commits(paths=file_path, max_count=max_commits))
            return [
                {
                    "hash": c.hexsha,
                    "short_hash": c.hexsha[:8],
                    "message": c.message.strip(),
                    "author": str(c.author),
                    "date": c.committed_datetime.isoformat(),
                }
                for c in commits
            ]
        except Exception as e:
            logger.warning(f"git log failed for {file_path}: {e}")
            return []

    def get_diff(self, commit_hash: str, file_path: Optional[str] = None) -> str:
        """Get the diff for a specific commit."""
        if not self.repo:
            return ""

        try:
            commit = self.repo.commit(commit_hash)
            if commit.parents:
                parent = commit.parents[0]
                diffs = parent.diff(commit, paths=file_path)
                result = []
                for diff in diffs:
                    result.append(f"--- {diff.a_path}\n+++ {diff.b_path}\n")
                    if diff.diff:
                        result.append(
                            diff.diff.decode("utf-8", errors="ignore")
                        )
                return "\n".join(result)
            return ""
        except Exception as e:
            logger.warning(f"git diff failed for commit {commit_hash}: {e}")
            return ""

    def find_introducing_commit(
        self,
        source_file: str,
        target_import: str,
        max_commits: int = 100,
    ) -> Optional[Dict]:
        """
        Find the commit that introduced a specific import/dependency.
        Uses git log -S (pickaxe) to find the introducing commit.
        """
        if not self.repo:
            return None

        try:
            commits = list(
                self.repo.iter_commits(
                    paths=source_file,
                    max_count=max_commits,
                    S=target_import,
                )
            )
            if commits:
                c = commits[-1]  # oldest commit that added this string
                return {
                    "hash": c.hexsha,
                    "short_hash": c.hexsha[:8],
                    "message": c.message.strip(),
                    "author": str(c.author),
                    "date": c.committed_datetime.isoformat(),
                    "diff": self.get_diff(c.hexsha, source_file),
                }
        except Exception as e:
            logger.warning(f"git pickaxe failed: {e}")

        return None

    def build_evidence_package(
        self,
        violation: Dict[str, Any],
        source_file: str,
        target_symbol: str,
        architecture_rule: Optional[Dict] = None,
    ) -> Dict[str, Any]:
        """
        Build the structured evidence package that will be sent to the LLM.
        """
        introducing_commit = self.find_introducing_commit(source_file, target_symbol)
        file_commits = self.get_commits_for_file(source_file, max_commits=10)

        diff = ""
        if introducing_commit:
            diff = introducing_commit.get("diff", "")

        evidence = {
            "violation": violation,
            "architecture_rule": architecture_rule or {},
            "code": {
                "file": source_file,
                "target_symbol": target_symbol,
            },
            "dependency_path": [violation.get("source", ""), violation.get("target", "")],
            "commit": introducing_commit,
            "diff": diff[:2000] if diff else "",  # truncate for LLM context
            "recent_commits": file_commits[:5],
        }

        logger.info(
            f"Evidence package built for violation: "
            f"{violation.get('source')} → {violation.get('target')}"
        )
        return evidence
