"""Evidence indexing and grounding checks shared by RCA (Sprint 7) and impact/recommendation (Sprint 8).

Every piece of evidence handed to the LLM gets a stable ID. Anything the LLM asserts — a cited ID,
a component, a commit hash, a file name — is checked against that index. "Hard" problems go back to
the model as a repair prompt; whatever is still unsupported afterwards is logged as a hallucination
and pushes the result to UNCERTAIN.
"""
from __future__ import annotations

import json
import re
import time
from dataclasses import dataclass, field
from pathlib import Path

from .schemas import EvidencePackage

FILE_RE = re.compile(r"\b[\w./-]+\.(?:java|py|ts|tsx|js|go|kt|cs|rb|php|scala|xml|sql|ya?ml|json|gradle|md)\b")
HASH_RE = re.compile(r"\b(?=[0-9a-f]*\d)(?=[0-9a-f]*[a-f])[0-9a-f]{7,40}\b")

EVIDENCE_GROUPS = {
    # which evidence each RCA variant receives (ablations, Design §10.2)
    "llm_only": set(),
    "grounded_no_git": {"rule", "code", "path", "graph", "impact"},
    "grounded_git_no_graph": {"rule", "code", "git"},
    "grounded_full": {"rule", "code", "path", "graph", "impact", "git"},
}


@dataclass
class EvidenceIndex:
    items: list[dict]
    components: set[str] = field(default_factory=set)
    files: set[str] = field(default_factory=set)
    commits: set[str] = field(default_factory=set)
    text_blob: str = ""

    @property
    def ids(self) -> set[str]:
        return {i["id"] for i in self.items}


def index_evidence(pkg: EvidencePackage, groups: set[str]) -> EvidenceIndex:
    items: list[dict] = []
    v = pkg.violation
    comps = {v.get("source"), v.get("target")}
    files: set[str] = set()
    commits: set[str] = set()
    if "rule" in groups and pkg.architecture_rule:
        items.append({"id": "E-RULE", "kind": "rule", "content": pkg.architecture_rule})
        if pkg.layer_of:
            items.append({"id": "E-LAYERS", "kind": "layers", "content": pkg.layer_of})
            comps |= set(pkg.layer_of)
    if "code" in groups and pkg.code:
        items.append({"id": "E-CODE", "kind": "code", **pkg.code})
        files.add(pkg.code.get("file", ""))
    if "path" in groups and pkg.dependency_path:
        items.append({"id": "E-PATH", "kind": "dependency_path", "content": pkg.dependency_path})
        comps |= set(pkg.dependency_path)
    if "graph" in groups:
        if pkg.intended_edges:
            items.append({"id": "E-GRAPH-I", "kind": "intended_graph", "content": pkg.intended_edges})
        if pkg.current_edges:
            items.append({"id": "E-GRAPH-C", "kind": "current_graph", "content": pkg.current_edges})
        for e in pkg.intended_edges + pkg.current_edges:
            comps |= set(e)
    if "impact" in groups and pkg.affected_components:
        items.append({"id": "E-IMPACT", "kind": "affected_components", "content": pkg.affected_components})
        comps |= {a["component"] for a in pkg.affected_components}
    if "git" in groups:
        cands = list(pkg.candidate_commits) or ([pkg.commit] if pkg.commit else [])
        for c in cands:
            items.append({"id": f"E-COMMIT-{c.hash}", "kind": "commit", "commit": c.hash, "content": c.message,
                          "files": c.files, "author": c.author, "date": c.date})
            diff = c.diff or (pkg.diff if pkg.commit and c.hash == pkg.commit.hash else "")
            if diff:
                items.append({"id": f"E-DIFF-{c.hash}", "kind": "diff", "commit": c.hash, "content": diff})
            commits.add(c.hash)
            files |= set(c.files)
    comps.discard(None)
    blob = json.dumps(items)
    return EvidenceIndex(items=items, components=comps, files={f for f in files if f}, commits=commits, text_blob=blob)


def _file_supported(fname: str, idx: EvidenceIndex) -> bool:
    base = fname.rsplit("/", 1)[-1]
    stem = base.rsplit(".", 1)[0]
    return any(f.endswith(base) for f in idx.files) or (len(stem) > 3 and stem in idx.text_blob)


def text_mentions(text: str, idx: EvidenceIndex) -> list[dict]:
    """Soft checks on free text: file names and commit hashes that do not appear in the evidence."""
    out = []
    for f in set(FILE_RE.findall(text)):
        if not _file_supported(f, idx):
            out.append({"type": "unknown_file", "value": f})
    for h in set(HASH_RE.findall(text)):
        if not any(c.startswith(h) or h.startswith(c) for c in idx.commits):
            out.append({"type": "unknown_commit_in_text", "value": h})
    return out


def check_ids(cited: list[str], idx: EvidenceIndex) -> list[str]:
    return [c for c in cited if c not in idx.ids]


def check_components(names: list[str], idx: EvidenceIndex) -> list[str]:
    known = {n.lower() for n in idx.components}
    return [n for n in names if n.lower() not in known]


class HallucinationLog:
    def __init__(self, path: str | Path):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)

    def write(self, violation_id: str, stage: str, variant: str, model: str, issues: list[dict]):
        if not issues:
            return
        with self.path.open("a") as f:
            for i in issues:
                f.write(json.dumps({"ts": time.strftime("%Y-%m-%dT%H:%M:%S"), "violation_id": violation_id,
                                    "stage": stage, "variant": variant, "model": model, **i}) + "\n")
