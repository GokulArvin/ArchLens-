
from pathlib import Path
from typing import Any, Optional

from git import Repo, GitCommandError


class GitEvidenceExtractor:
    """
    Collects traceable Git and source-code evidence for an
    architecture conformance violation.
    """

    def __init__(self, repo_path: str):
        self.repo_path = Path(repo_path).resolve()
        self.repo: Optional[Repo] = None

        try:
            self.repo = Repo(self.repo_path, search_parent_directories=True)
            self.repo_path = Path(self.repo.working_tree_dir).resolve()
        except Exception as exc:
            print(f"Git repository initialization failed: {exc}")

    # ---------------------------------------------------------
    # PATH VALIDATION
    # ---------------------------------------------------------

    def _resolve_file_path(self, file_path: str) -> Optional[str]:
        """
        Resolve a file path relative to the repository root.
        Reject paths outside the repository.
        """

        if not file_path:
            return None

        try:
            supplied_path = Path(file_path)

            if supplied_path.is_absolute():
                resolved_path = supplied_path.resolve()
            else:
                resolved_path = (self.repo_path / supplied_path).resolve()

            resolved_path.relative_to(self.repo_path)

            if not resolved_path.is_file():
                return None

            return resolved_path.relative_to(self.repo_path).as_posix()

        except (ValueError, OSError):
            return None

    # ---------------------------------------------------------
    # EVIDENCE CREATION
    # ---------------------------------------------------------

    @staticmethod
    def _make_evidence(
        evidence_id: str,
        evidence_type: str,
        description: str,
        content: Any,
        source: Optional[str] = None
    ) -> dict:

        return {
            "evidence_id": evidence_id,
            "type": evidence_type,
            "description": description,
            "source": source,
            "content": content
        }

    # ---------------------------------------------------------
    # GIT BLAME
    # ---------------------------------------------------------

    def get_blame(
        self,
        file_path: str,
        line_numbers: Optional[list[int]] = None
    ) -> list[dict]:

        if self.repo is None:
            return []

        relative_path = self._resolve_file_path(file_path)

        if not relative_path:
            return []

        try:
            blame_data = self.repo.blame("HEAD", relative_path)
            results = []

            for commit, lines in blame_data:
                for line in lines:
                    if isinstance(line, bytes):
                        line = line.decode("utf-8", errors="replace")

                    results.append({
                        "commit_hash": commit.hexsha,
                        "author": str(commit.author),
                        "date": commit.committed_datetime.isoformat(),
                        "message": commit.message.strip(),
                        "line": line.strip()
                    })

            if line_numbers is not None:
                selected_lines = set(line_numbers)
                results = [
                    item
                    for index, item in enumerate(results, start=1)
                    if index in selected_lines
                ]

            return results

        except Exception as exc:
            print(f"Git blame failed: {exc}")
            return []

    # ---------------------------------------------------------
    # FILE COMMIT HISTORY
    # ---------------------------------------------------------

    def get_commits_for_file(
        self,
        file_path: str,
        max_commits: int = 10
    ) -> list[dict]:

        if self.repo is None:
            return []

        relative_path = self._resolve_file_path(file_path)

        if not relative_path:
            return []

        try:
            commits = self.repo.iter_commits(
                paths=relative_path,
                max_count=max_commits
            )

            return [
                {
                    "commit_hash": commit.hexsha,
                    "message": commit.message.strip(),
                    "author": str(commit.author),
                    "date": commit.committed_datetime.isoformat()
                }
                for commit in commits
            ]

        except Exception as exc:
            print(f"Commit history retrieval failed: {exc}")
            return []

    # ---------------------------------------------------------
    # COMMIT DIFF
    # ---------------------------------------------------------

    def get_diff(
        self,
        commit_hash: str,
        file_path: str
    ) -> str:

        if self.repo is None:
            return ""

        relative_path = self._resolve_file_path(file_path)

        if not relative_path:
            return ""

        try:
            commit = self.repo.commit(commit_hash)

            if commit.parents:
                parent = commit.parents[0]
                diff_index = parent.diff(
                    commit,
                    paths=relative_path,
                    create_patch=True
                )
            else:
                diff_index = commit.diff(
                    None,
                    paths=relative_path,
                    create_patch=True
                )

            diff_text = []

            for diff_item in diff_index:
                patch = diff_item.diff

                if isinstance(patch, bytes):
                    patch = patch.decode("utf-8", errors="replace")

                diff_text.append(patch)

            return "\n".join(diff_text)

        except Exception as exc:
            print(f"Git diff retrieval failed: {exc}")
            return ""

    # ---------------------------------------------------------
    # INTRODUCING COMMIT SEARCH
    # ---------------------------------------------------------

    def find_introducing_commit(
        self,
        file_path: str,
        target_import: str,
        max_commits: int = 100
    ) -> Optional[dict]:

        """
        Uses git log -S to locate commits that changed the
        occurrence count of the requested text.

        This deliberately uses git log rather than
        repo.iter_commits because -S is a git log option.
        """

        if self.repo is None:
            return None

        relative_path = self._resolve_file_path(file_path)

        if not relative_path or not target_import:
            return None

        try:
            commit_hashes = self.repo.git.log(
                f"-S{target_import}",
                "--format=%H",
                f"--max-count={max_commits}",
                "--",
                relative_path
            )

            if not commit_hashes.strip():
                return None

            for commit_hash in commit_hashes.splitlines():
                diff = self.get_diff(
                    commit_hash.strip(),
                    relative_path
                )

                if not diff:
                    continue

                # Look for the target text in added lines.
                added_lines = [
                    line[1:]
                    for line in diff.splitlines()
                    if line.startswith("+") and not line.startswith("+++")
                ]

                if any(target_import in line for line in added_lines):
                    commit = self.repo.commit(commit_hash.strip())

                    return {
                        "commit_hash": commit.hexsha,
                        "message": commit.message.strip(),
                        "author": str(commit.author),
                        "date": commit.committed_datetime.isoformat(),
                        "diff": diff[:10000]
                    }

            return None

        except GitCommandError as exc:
            print(f"Introducing commit search failed: {exc}")
            return None

        except Exception as exc:
            print(f"Introducing commit search failed: {exc}")
            return None

    # ---------------------------------------------------------
    # SOURCE CODE CONTEXT
    # ---------------------------------------------------------

    def get_code_context(
        self,
        file_path: str,
        target_symbol: Optional[str] = None,
        context_lines: int = 5
    ) -> dict:

        relative_path = self._resolve_file_path(file_path)

        if not relative_path:
            return {
                "file": file_path,
                "found": False,
                "content": "",
                "line_numbers": []
            }

        absolute_path = self.repo_path / relative_path

        try:
            content = absolute_path.read_text(
                encoding="utf-8",
                errors="replace"
            )

            lines = content.splitlines()

            if not target_symbol:
                return {
                    "file": relative_path,
                    "found": True,
                    "content": content[:12000],
                    "line_numbers": list(
                        range(1, min(len(lines), 200) + 1)
                    )
                }

            matching_lines = [
                index
                for index, line in enumerate(lines)
                if target_symbol in line
            ]

            if not matching_lines:
                return {
                    "file": relative_path,
                    "found": False,
                    "content": "",
                    "line_numbers": []
                }

            selected_lines = set()

            for index in matching_lines:
                start = max(0, index - context_lines)
                end = min(len(lines), index + context_lines + 1)

                selected_lines.update(range(start, end))

            ordered_lines = sorted(selected_lines)

            context = "\n".join(
                f"{index + 1}: {lines[index]}"
                for index in ordered_lines
            )

            return {
                "file": relative_path,
                "found": True,
                "content": context[:12000],
                "line_numbers": [
                    index + 1 for index in ordered_lines
                ]
            }

        except Exception as exc:
            print(f"Source context retrieval failed: {exc}")

            return {
                "file": relative_path,
                "found": False,
                "content": "",
                "line_numbers": []
            }

    # ---------------------------------------------------------
    # COMPLETE EVIDENCE PACKAGE
    # ---------------------------------------------------------

    def build_evidence_package(
        self,
        violation: dict,
        source_file: str,
        target_symbol: Optional[str] = None,
        line_numbers: Optional[list[int]] = None,
        max_commits: int = 10
    ) -> dict:

        evidence_items = []
        evidence_counter = 1

        def add_evidence(
            evidence_type: str,
            description: str,
            content: Any,
            source: Optional[str] = None
        ):
            nonlocal evidence_counter

            evidence_id = f"E{evidence_counter:03d}"
            evidence_counter += 1

            evidence_items.append(
                self._make_evidence(
                    evidence_id,
                    evidence_type,
                    description,
                    content,
                    source
                )
            )

        # 1. Conformance finding
        add_evidence(
            "conformance_finding",
            "Architecture conformance violation identified by the engine",
            violation
        )

        # 2. Source-code context
        code_context = self.get_code_context(
            source_file,
            target_symbol
        )

        if code_context["found"]:
            add_evidence(
                "source_code",
                "Source code context related to the violation",
                code_context,
                code_context["file"]
            )

        # 3. Git blame
        blame_data = self.get_blame(
            source_file,
            line_numbers
        )

        if blame_data:
            add_evidence(
                "git_blame",
                "Git blame information for the source file",
                blame_data,
                source_file
            )

        # 4. Introducing commit
        introducing_commit = None

        if target_symbol:
            introducing_commit = self.find_introducing_commit(
                source_file,
                target_symbol
            )

        if introducing_commit:
            add_evidence(
                "introducing_commit",
                "Candidate commit that introduced the target symbol",
                introducing_commit,
                source_file
            )

        # 5. Recent file history
        commit_history = self.get_commits_for_file(
            source_file,
            max_commits=max_commits
        )

        if commit_history:
            add_evidence(
                "git_history",
                "Recent Git commit history for the source file",
                commit_history,
                source_file
            )

        # 6. Dependency path
        dependency_path = [
            violation.get("source", ""),
            violation.get("target", "")
        ]

        dependency_path = [
            item for item in dependency_path if item
        ]

        return {
            "violation": violation,
            "architecture_rule": violation.get(
                "rule",
                violation.get("violation_type", "")
            ),
            "code_context": code_context,
            "dependency_path": dependency_path,
            "commit": introducing_commit,
            "diff": (
                introducing_commit.get("diff", "")[:10000]
                if introducing_commit else ""
            ),
            "recent_commits": commit_history,
            "evidence_items": evidence_items,
            "evidence_metadata": {
                "total_items": len(evidence_items),
                "git_available": self.repo is not None,
                "repository_path": str(self.repo_path),
                "source_file": source_file,
                "target_symbol": target_symbol
            }
        }
