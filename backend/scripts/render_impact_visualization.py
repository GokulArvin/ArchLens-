"""
Sprint 8 / D37 + D40: render affected-node highlighting on the real
architecture graph for the two controlled violations tested in
backend/tests/unit/test_impact_analysis.py.

Writes experiments/results/sprint8_impact_<source>_<target>.png

Run from the backend/ directory: ../venv/Scripts/python.exe scripts/render_impact_visualization.py
"""

import sys
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND_DIR))

import matplotlib.pyplot as plt  # noqa: E402
import networkx as nx  # noqa: E402

from app.modules.cv_pipeline.dataset_manifest import load_manifest  # noqa: E402
from app.modules.cv_pipeline.impact_analysis import build_networkx_graph, compute_affected_nodes  # noqa: E402

REPO_ROOT = BACKEND_DIR.parent
OUT_DIR = REPO_ROOT / "experiments" / "results"

CONTROLLED_VIOLATIONS = [
    ("shipping", "frontend"),       # backward-dependency violation, large blast radius
    ("recommendation", "cart"),     # direct-bypass violation, small blast radius
]


def render(g: nx.DiGraph, source: str, target: str):
    impact = compute_affected_nodes(g, source, target)
    affected = set(impact.upstream_affected) | set(impact.downstream_affected)

    render_graph = g.copy()
    render_graph.add_edge(source, target)  # the controlled (inserted) violating edge

    pos = nx.spring_layout(render_graph, seed=42)
    fig, ax = plt.subplots(figsize=(10, 8))

    node_colors = []
    for n in render_graph.nodes:
        if n in (source, target):
            node_colors.append("red")
        elif n in affected:
            node_colors.append("orange")
        else:
            node_colors.append("lightgray")

    edge_colors = ["red" if (u, v) == (source, target) else "gray" for u, v in render_graph.edges]
    edge_widths = [3 if (u, v) == (source, target) else 1 for u, v in render_graph.edges]

    nx.draw(
        render_graph, pos, ax=ax, with_labels=True, node_color=node_colors,
        edge_color=edge_colors, width=edge_widths, node_size=1400, font_size=8, arrows=True,
    )
    ax.set_title(
        f"Impact of controlled violation {source} -> {target}\n"
        f"red = violation endpoints, orange = affected ({len(affected)} nodes), gray = unaffected"
    )

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    out_path = OUT_DIR / f"sprint8_impact_{source}_{target}.png"
    fig.savefig(out_path, bbox_inches="tight", dpi=120)
    plt.close(fig)
    print(f"{source} -> {target}: {len(affected)} affected nodes -> {out_path}")


def main():
    g = next(x for x in load_manifest() if x.id == "gcp_microservices_demo")
    nx_graph = build_networkx_graph(g)
    for source, target in CONTROLLED_VIOLATIONS:
        render(nx_graph, source, target)


if __name__ == "__main__":
    main()
