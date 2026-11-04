"""
Sprint 6 / D30: render sample visual overlays linking diagram component
boxes to their matched real code module names (from D28's real, manually
verified alignment results).

Writes experiments/results/sprint6_alignment_overlay_<diagram_id>.png

Run from the backend/ directory: ../venv/Scripts/python.exe scripts/render_alignment_overlay.py
"""

import json
import sys
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND_DIR))

import matplotlib.patches as patches  # noqa: E402
import matplotlib.pyplot as plt  # noqa: E402
from PIL import Image  # noqa: E402

from app.modules.cv_pipeline.dataset_manifest import DIAGRAMS_DIR, load_manifest  # noqa: E402

REPO_ROOT = BACKEND_DIR.parent
ALIGNMENT_PATH = REPO_ROOT / "experiments" / "baselines" / "sprint6_graph_alignment.json"
OUT_DIR = REPO_ROOT / "experiments" / "results"


def render(diagram_id: str, alignment_by_component: dict[str, dict]):
    graphs = {g.id: g for g in load_manifest()}
    g = graphs[diagram_id]
    img_path = DIAGRAMS_DIR / Path(g.source).name

    fig, ax = plt.subplots(figsize=(14, 10))
    with Image.open(img_path) as im:
        ax.imshow(im)

    for c in g.components:
        if c.bbox is None:
            continue
        w, h = c.bbox.x2 - c.bbox.x1, c.bbox.y2 - c.bbox.y1
        alignment = alignment_by_component.get(c.id)
        if alignment and alignment["predicted"]:
            color = "limegreen" if alignment["correct"] else "orange"
            label = f"{alignment['predicted']} ({alignment['score']:.2f})"
        else:
            color = "red"
            label = "no match"
        ax.add_patch(patches.Rectangle((c.bbox.x1, c.bbox.y1), w, h, fill=False, edgecolor=color, linewidth=2))
        ax.text(
            c.bbox.x1, max(c.bbox.y1 - 6, 0), label, color=color, fontsize=7, weight="bold",
            bbox=dict(facecolor="white", alpha=0.85, edgecolor="none", pad=1),
        )

    ax.set_title(f"{diagram_id}: diagram node -> real code module alignment (Sprint 6)")
    ax.axis("off")

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    out_path = OUT_DIR / f"sprint6_alignment_overlay_{diagram_id}.png"
    fig.savefig(out_path, bbox_inches="tight", dpi=120)
    plt.close(fig)
    print(f"Wrote {out_path}")


def main():
    alignment_data = json.loads(ALIGNMENT_PATH.read_text(encoding="utf-8"))
    by_diagram: dict[str, dict[str, dict]] = {}
    for r in alignment_data["results"]:
        by_diagram.setdefault(r["diagram_id"], {})[r["component_id"]] = r

    for diagram_id, alignment_by_component in by_diagram.items():
        render(diagram_id, alignment_by_component)


if __name__ == "__main__":
    main()
