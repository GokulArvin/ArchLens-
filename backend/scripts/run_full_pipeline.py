"""
Runs every P1 CV pipeline script end-to-end, in dependency order, so the
whole project's real artifacts (dataset, manifest, baselines, splits,
figures, reports) can be regenerated from scratch in one command - the
same sequence used for Sprint 10's clean-room reproducibility checks.

Each step is a real script already used throughout Sprints 1-9; this file
adds no new logic of its own beyond running them in the right order and
stopping on the first real failure.

Run from the backend/ directory: ../venv/Scripts/python.exe scripts/run_full_pipeline.py
"""

import subprocess
import sys
from pathlib import Path

SCRIPTS_DIR = Path(__file__).resolve().parent
BACKEND_DIR = SCRIPTS_DIR.parent

STEPS = [
    "dataset_fetch.py",
    "derive_bookinfo_diagram.py",
    "build_manifest.py",
    "batch_preprocess.py",
    "inspect_yolo_classes.py",
    "run_detection_baseline.py",
    "evaluate_detection_baseline.py",
    "test_segmentation_feasibility.py",
    "evaluate_segmentation_baseline.py",
    "compute_component_embeddings.py",
    "evaluate_geometry_relations.py",
    "clone_demo_repo.py",
    "test_graph_alignment.py",
    "render_alignment_overlay.py",
    "demo_violation_evidence_chain.py",
    "render_impact_visualization.py",
    "freeze_splits.py",
    "evaluate_on_frozen_test_split.py",
    "render_sprint9_summary_figure.py",
]


def main():
    for i, script in enumerate(STEPS, start=1):
        print(f"\n=== [{i}/{len(STEPS)}] {script} ===", flush=True)
        result = subprocess.run([sys.executable, str(SCRIPTS_DIR / script)], cwd=str(BACKEND_DIR))
        if result.returncode != 0:
            print(f"\nFAILED at step {i}: {script} (exit code {result.returncode})")
            sys.exit(result.returncode)
    print(f"\nAll {len(STEPS)} steps completed successfully.")


if __name__ == "__main__":
    main()
