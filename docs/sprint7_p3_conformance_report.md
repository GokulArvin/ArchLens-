# Sprint 7 / D35 (P3): Known Limits for Git Evidence Extraction

## Overview

The `git_evidence_p3.py` module retrieves candidate commits that may have introduced a conformance violation's offending dependency. This document records known limitations, edge cases, and uncertainty signals discovered during Sprint 7 P3 work.

## Methods Used

| Method | Git Command | Coverage |
|--------|-------------|---------|
| Pickaxe search | `git log -S<pattern>` | Finds commits that added/removed the pattern |
| Blame attribution | `git blame HEAD <file>` | Per-line commit attribution |
| Rank by specificity | Custom scoring | Merge/rename penalties, frequency scoring |

## Known Limitations (D35)

### 1. Merge Commits
- **Problem**: Merge commits appear in pickaxe results even when they didn't introduce the dependency — they simply merged a branch that did.
- **Detection**: `is_merge_commit = len(commit.parents) > 1`
- **Mitigation**: `exclude_merges=True` flag; merge commits receive a -0.3 score penalty in ranking.
- **Residual risk**: The true introducing commit may be on a merged branch; `git log` on the main branch may miss it.

### 2. File Renames
- **Problem**: `git log -S<pattern>` does not follow file renames across commits. If the file containing the dependency was renamed, commits before the rename will not appear in results.
- **Detection**: `"=>" in diff` heuristic (naive but fast).
- **Mitigation**: -0.1 score penalty; warn in evidence limitations.
- **Residual risk**: Renames are common in refactoring sprints; evidence may be incomplete.

### 3. Shallow Clones
- **Problem**: Repositories cloned with `--depth=N` have truncated history. The pickaxe search stops at the grafted commit boundary without warning.
- **Detection**: Check for `gitpython.exc.GitCommandError` with "shallow" in message.
- **Mitigation**: Document in `limitations` field of `DependencyEvidence`.
- **Residual risk**: Cannot retrieve pre-clone history.

### 4. Generic Patterns
- **Problem**: A broad search pattern (e.g. a common module name) matches many unrelated commits, diluting the evidence.
- **Guidance**: Prefer the most specific string possible — the exact import statement or function call site, not just the module name.
- **Example**: `"from repositories import OrderRepository"` is better than `"repositories"`.

### 5. Incomplete History / Monorepo
- **Problem**: In monorepos or repositories with complex history (squash merges, force pushes), the pickaxe result may be incomplete or point to a squash boundary.
- **Mitigation**: `limitations` field explicitly documents when only 0 candidates are found.

## Uncertainty Policy

Consistent with the sprint plan's requirement that *the system can produce a structured explanation and clearly indicate when root cause is uncertain*:

- When `introducing_commit` is `None`: mark as `UNCERTAIN` in the evidence package.
- When `len(candidate_commits) > 1` and top-ranked commit is a merge: add "UNCERTAIN — multiple candidates, top candidate is a merge commit" to limitations.
- When `renames_detected`: add "UNCERTAIN — file renames detected, evidence may be incomplete".

## Ground-Truth Notes (D34)

The only verified ground-truth example in the ArchLens dataset is `flask-microservice-demo / commit d98872f` (see `test_git_evidence.py`). All other candidate commits are unverified and should be treated as heuristic suggestions.

| Violation | Pattern | Known Commit | Confidence |
|-----------|---------|-------------|------------|
| `backend → orders` unauthorized direct call | `cust_search` | `d98872f` | Verified ✅ |
| All others | — | None verified | Unverified |

