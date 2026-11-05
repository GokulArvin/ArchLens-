"""
Sprint 1 / D4: manifest of sample architecture diagrams used to develop and
test the CV pipeline.

Each manifest entry is an `ArchGraph` (the shared schema from
`backend.app.schemas.models`, graph_type="intended") describing one real
diagram, plus a `source_repository` block recorded in `ArchGraph.metadata`
that pairs the diagram to the real repository it depicts:

    metadata["source_repository"] = {
        "repo_url": str,
        "commit": str,
        "license": str,
        "diagram_provenance": "official" | "derived",
        "evidence": list[str],   # only present when diagram_provenance == "derived"
    }

No synthetic/fabricated diagrams or annotations are used - every entry here
is a real architecture diagram of a real, publicly available repository,
manually annotated by inspecting the image (or, for "derived" entries,
rendered from evidence read directly out of the repository's real source).
"""

from __future__ import annotations

import json
from pathlib import Path

from app.schemas.models import ArchGraph

MANIFEST_PATH = Path(__file__).resolve().parents[4] / "data" / "annotations" / "manifest.json"
DIAGRAMS_DIR = Path(__file__).resolve().parents[4] / "data" / "diagrams" / "raw"


def load_manifest(path: Path = MANIFEST_PATH) -> list[ArchGraph]:
    """Load and validate every manifest entry as an ArchGraph."""
    raw = json.loads(path.read_text(encoding="utf-8"))
    return [ArchGraph.model_validate(entry) for entry in raw]


def validate_manifest(graphs: list[ArchGraph]) -> list[str]:
    """Return a list of human-readable problems found (empty if the manifest is clean)."""
    problems: list[str] = []
    for g in graphs:
        source_repo = g.metadata.get("source_repository")
        if not source_repo:
            problems.append(f"{g.name}: missing source_repository metadata")
            continue
        for required in ("repo_url", "commit", "license", "diagram_provenance"):
            if not source_repo.get(required):
                problems.append(f"{g.name}: source_repository missing '{required}'")
        if source_repo.get("diagram_provenance") == "derived" and not source_repo.get("evidence"):
            problems.append(f"{g.name}: derived diagram has no evidence citations")

        if not g.source:
            problems.append(f"{g.name}: missing diagram image path")
        else:
            img_path = DIAGRAMS_DIR / Path(g.source).name
            if not img_path.exists():
                problems.append(f"{g.name}: image file not found at {img_path}")

        component_ids = {c.id for c in g.components}
        if len(component_ids) != len(g.components):
            problems.append(f"{g.name}: duplicate component ids")

        for rel in g.relationships:
            if rel.source not in component_ids:
                problems.append(f"{g.name}: relationship source '{rel.source}' not a known component")
            if rel.target not in component_ids:
                problems.append(f"{g.name}: relationship target '{rel.target}' not a known component")

        for c in g.components:
            if c.bbox is None:
                continue
            if c.bbox.x1 < 0 or c.bbox.y1 < 0 or c.bbox.x2 <= c.bbox.x1 or c.bbox.y2 <= c.bbox.y1:
                problems.append(f"{g.name}: component '{c.id}' has an invalid bbox {c.bbox}")

    return problems


if __name__ == "__main__":
    graphs = load_manifest()
    problems = validate_manifest(graphs)
    print(f"Loaded {len(graphs)} manifest entries.")
    if problems:
        print(f"{len(problems)} problem(s) found:")
        for p in problems:
            print(f"  - {p}")
    else:
        print("Manifest is valid.")
