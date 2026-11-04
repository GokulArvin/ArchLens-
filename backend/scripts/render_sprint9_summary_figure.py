"""
Sprint 9 / D45: a final summary figure comparing all three CV baselines'
F1 scores, both on the full 10-diagram dataset (Sprints 3-5) and on the
frozen held-out test split (this sprint).

Run from the backend/ directory: ../venv/Scripts/python.exe scripts/render_sprint9_summary_figure.py
"""

import json
import sys
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND_DIR))

import matplotlib.pyplot as plt  # noqa: E402

REPO_ROOT = BACKEND_DIR.parent
BASELINES_DIR = REPO_ROOT / "experiments" / "baselines"
RESULTS_DIR = REPO_ROOT / "experiments" / "results"


def main():
    full_dataset_f1 = {
        "Detector (YOLO/COCO)": json.loads((BASELINES_DIR / "sprint3_yolo_coco_baseline_eval.json").read_text())["aggregate"]["f1"],
        "Segmentation (region-crop)": None,  # Sprint 4 only evaluated a 3-diagram subset, not the full 10 - not directly comparable
        "Geometry relations": json.loads((BASELINES_DIR / "sprint5_geometry_relations.json").read_text())["aggregate"]["f1"],
    }

    test_split = json.loads((RESULTS_DIR / "sprint9_test_split_evaluation.json").read_text())["summary"]
    test_split_f1 = {
        "Detector (YOLO/COCO)": test_split["detector_yolo_coco"]["f1"] if test_split["detector_yolo_coco"] else 0.0,
        "Segmentation (region-crop)": test_split["segmentation_region_cropping"]["f1"],
        "Geometry relations": test_split["geometry_relations"]["f1"],
    }

    labels = list(test_split_f1.keys())
    full_values = [full_dataset_f1[k] for k in labels]  # None where not evaluated (kept out of the chart honestly)
    test_values = [test_split_f1[k] for k in labels]

    x = range(len(labels))
    width = 0.35
    fig, ax = plt.subplots(figsize=(9, 5))
    full_bars = ax.bar(
        [i - width / 2 for i in x], [v if v is not None else 0.0 for v in full_values], width,
        label="Full dataset (10 diagrams, Sprints 3-5)",
    )
    test_bars = ax.bar([i + width / 2 for i in x], test_values, width, label="Frozen test split (2 diagrams, Sprint 9)")
    ax.set_xticks(list(x))
    ax.set_xticklabels(labels)
    ax.set_ylabel("F1 score")
    ax.set_title("CV Baseline Comparison (real, measured results)")
    ax.legend()
    full_labels = [f"{v:.3f}" if v is not None else "N/A" for v in full_values]
    ax.bar_label(full_bars, labels=full_labels)
    ax.bar_label(test_bars, fmt="%.3f")

    out_path = RESULTS_DIR / "sprint9_baseline_comparison.png"
    fig.savefig(out_path, bbox_inches="tight", dpi=120)
    plt.close(fig)
    print(f"Wrote {out_path}")


if __name__ == "__main__":
    main()
