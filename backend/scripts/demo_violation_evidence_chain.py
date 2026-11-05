"""
Sprint 7 / D31 + D32 + D33: an end-to-end demonstration linking a diagram's
components to a conformance-report-shaped violation, with real retrieved
code and real Git evidence attached.

Uses a real example from our dataset: `flask_microservice_demo`'s diagram
annotates `backend -> orders` as an intended edge (alongside `backend ->
aggregate -> orders`) - per our own ground truth, the real
`backend -> orders` call this sprint traces evidence for is CONFORMANT, not
a violation. To demonstrate the violation/evidence schema and chain end to
end, we apply a hypothetical, counterfactual stricter rule ("backend may
only reach orders through aggregate") that this real edge *would* break if
it were the actual rule - explicitly not a claim that the real project (or
our own diagram) considers this edge a problem. No conformance engine
exists yet in this P1-only track to evaluate real rules against, so the
*rule* here is illustrative, but every piece of *evidence* attached to the
resulting violation record is 100% real: the actual commit, diff, author,
date, and file content from the cloned repository.

Run from the backend/ directory: ../venv/Scripts/python.exe scripts/demo_violation_evidence_chain.py
"""

import sys
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND_DIR))

from app.modules.cv_pipeline.code_retrieval import retrieve_line_range  # noqa: E402
from app.modules.cv_pipeline.dataset_manifest import load_manifest  # noqa: E402
from app.modules.cv_pipeline.git_evidence import build_git_evidence  # noqa: E402
from app.schemas.models import ArchViolation, ConformanceReport  # noqa: E402

REPO_ROOT = BACKEND_DIR.parent
CLONE_PATH = REPO_ROOT / "data" / "repositories" / "flask-microservice-demo"
OUT_PATH = REPO_ROOT / "experiments" / "results" / "sprint7_violation_evidence_chain.json"


def main():
    if not CLONE_PATH.exists():
        raise FileNotFoundError(f"{CLONE_PATH} not found - run backend/scripts/clone_demo_repo.py first.")

    g = next(graph for graph in load_manifest() if graph.id == "flask_microservice_demo")

    # D31: the violation references the real diagram component ids directly -
    # this *is* the diagram-node <-> conformance-report link.
    violation = ArchViolation(
        id="v1",
        verdict="VIOLATION",
        violation_type="layer_violation",
        source_component="backend",  # real ArchComponent.id from the manifest
        target_component="orders",   # real ArchComponent.id from the manifest
        expected="backend -> aggregate -> orders",
        actual="backend -> orders (direct, via /custSearch/<name>)",
        severity="medium",
        description=(
            "Under a hypothetical stricter rule (backend may only reach orders through aggregate), "
            "backend's customer-search route would violate it by calling orders directly. Per our own "
            "diagram annotation this edge is actually intended/conformant - see script docstring."
        ),
    )

    # D32: retrieve the real affected code.
    affected_code = retrieve_line_range(str(CLONE_PATH), "backend/src/run.py", "25-29")

    # D33: real Git evidence, via pickaxe search with a pattern specific to this exact change.
    evidence = build_git_evidence(
        violation_id=violation.id,
        repo_path=str(CLONE_PATH),
        pattern="cust_search",
        file_path="backend/src/run.py",
        dependency_path=["backend", "orders"],
    )

    report = ConformanceReport(
        repository="https://github.com/mblitherland/flask-microservice-demo",
        diagram_path=g.source,
        intended_graph=g,
        violations=[violation],
        git_evidence=[evidence],
        summary={"violation_count": 1, "affected_code_lines": "backend/src/run.py:25-29"},
    )

    OUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    OUT_PATH.write_text(report.model_dump_json(indent=2), encoding="utf-8")

    print("Violation:", violation.description)
    print("\nAffected code (backend/src/run.py:25-29):\n" + affected_code)
    print(f"\nIntroducing commit: {evidence.introducing_commit.hash if evidence.introducing_commit else None}")
    print(f"Author: {evidence.introducing_commit.author if evidence.introducing_commit else None}")
    print(f"Date: {evidence.introducing_commit.date if evidence.introducing_commit else None}")
    print(f"Message: {evidence.introducing_commit.message if evidence.introducing_commit else None}")
    print(f"\nWrote {OUT_PATH}")


if __name__ == "__main__":
    main()
