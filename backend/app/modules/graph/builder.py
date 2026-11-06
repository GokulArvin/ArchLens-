"""
Sprint 4 (P3 D14) + Sprint 5 (P3 D17/D19) + Sprint 7 (P3 D26–D30):
Graph Builder — converts ArchGraph/CurrentGraph JSON schema dicts to NetworkX
DiGraphs for conformance checking and analysis.

Responsibilities
----------------
* D14: Build the first current architecture graph (G_C) with NetworkX from
        DependencyGraphBuilder output or from raw ArchGraph schema dicts.
* D17: Nodes carry `confidence` and `provenance` attributes; edges carry
        `type`, `confidence`, and `provenance`.
* D19/D24: Expose graph integrity metadata (endpoint presence, duplicates)
            so the ConformanceEngine can trust the graph structure.
* Sprint 7: Provides the graph-alignment helper used by the conformance engine.
"""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import networkx as nx

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# ArchGraphBuilder — JSON schema → NetworkX DiGraph
# ---------------------------------------------------------------------------

class ArchGraphBuilder:
    """
    Convert an ArchGraph-compatible dict (or Pydantic model) into a
    NetworkX DiGraph that ConformanceEngine can operate on.

    Node attributes stored per node:
        name        : str   — human-readable label
        type        : str   — ComponentType value (e.g. "service")
        confidence  : float — extraction confidence (default 1.0)
        provenance  : str   — origin tag (e.g. "cv_pipeline", "ast_parser")
        metadata    : dict  — any extra fields from the schema

    Edge attributes stored per directed edge (u → v):
        type        : str   — RelationshipType value (e.g. "depends_on")
        confidence  : float — extraction confidence (default 1.0)
        provenance  : str   — origin tag
        metadata    : dict  — any extra fields
    """

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    @staticmethod
    def build(graph_data: Any) -> nx.DiGraph:
        """
        Build a NetworkX DiGraph from an ArchGraph schema dict or Pydantic
        model instance.

        Parameters
        ----------
        graph_data : dict | ArchGraph
            Raw JSON-compatible dict or any object exposing .components
            and .relationships attributes (Pydantic model).

        Returns
        -------
        nx.DiGraph with node/edge attributes as described above.
        """
        # Accept Pydantic models by converting to dict first
        if hasattr(graph_data, "model_dump"):
            data = graph_data.model_dump(mode="json")
        elif hasattr(graph_data, "dict"):          # Pydantic v1 fallback
            data = graph_data.dict()
        elif isinstance(graph_data, dict):
            data = graph_data
        else:
            raise TypeError(f"Unsupported graph_data type: {type(graph_data)}")

        G = nx.DiGraph()
        G.graph["schema_version"] = data.get("schema_version", "1.0.0")
        G.graph["graph_type"] = data.get("graph_type", "unknown")
        G.graph["name"] = data.get("name", "")
        G.graph["source"] = data.get("source", "")

        # Add nodes
        for comp in data.get("components", []):
            node_id = comp.get("id") or comp.get("name", "")
            if not node_id:
                logger.warning("Component missing 'id' and 'name'; skipping: %s", comp)
                continue
            G.add_node(
                node_id,
                name=comp.get("name", node_id),
                type=_safe_str(comp.get("type", "unknown")),
                confidence=float(comp.get("confidence", 1.0)),
                provenance=comp.get("metadata", {}).get("provenance", "schema"),
                metadata=comp.get("metadata", {}),
            )

        # Add edges — deduplicate by keeping highest-confidence edge
        for rel in data.get("relationships", []):
            src = rel.get("source", "")
            tgt = rel.get("target", "")
            if not src or not tgt:
                logger.warning("Relationship missing source/target; skipping: %s", rel)
                continue
            # Auto-add nodes if they don't exist (defensive)
            if src not in G:
                G.add_node(src, name=src, type="unknown", confidence=1.0,
                           provenance="inferred", metadata={})
            if tgt not in G:
                G.add_node(tgt, name=tgt, type="unknown", confidence=1.0,
                           provenance="inferred", metadata={})

            confidence = float(rel.get("confidence", 1.0))
            existing = G.get_edge_data(src, tgt)
            if existing and existing.get("confidence", 0.0) >= confidence:
                continue  # keep the existing higher-confidence edge

            G.add_edge(
                src,
                tgt,
                type=_safe_str(rel.get("type", "depends_on")),
                confidence=confidence,
                provenance=rel.get("metadata", {}).get("provenance", "schema"),
                metadata=rel.get("metadata", {}),
            )

        logger.info(
            "Built DiGraph: %d nodes, %d edges (graph_type=%s)",
            G.number_of_nodes(),
            G.number_of_edges(),
            G.graph.get("graph_type"),
        )
        return G

    # ------------------------------------------------------------------
    # Serialization helpers (Sprint 5 D20 — round-trip)
    # ------------------------------------------------------------------

    @staticmethod
    def to_schema_dict(G: nx.DiGraph) -> Dict[str, Any]:
        """
        Serialize a NetworkX DiGraph back to an ArchGraph-compatible dict.
        Round-trip: build(to_schema_dict(G)) must return an isomorphic graph.
        """
        components = [
            {
                "id": n,
                "name": attrs.get("name", n),
                "type": attrs.get("type", "unknown"),
                "confidence": attrs.get("confidence", 1.0),
                "metadata": attrs.get("metadata", {}),
            }
            for n, attrs in G.nodes(data=True)
        ]
        relationships = [
            {
                "source": u,
                "target": v,
                "type": attrs.get("type", "depends_on"),
                "confidence": attrs.get("confidence", 1.0),
                "metadata": attrs.get("metadata", {}),
            }
            for u, v, attrs in G.edges(data=True)
        ]
        return {
            "schema_version": G.graph.get("schema_version", "1.0.0"),
            "name": G.graph.get("name", ""),
            "graph_type": G.graph.get("graph_type", "unknown"),
            "source": G.graph.get("source", ""),
            "components": components,
            "relationships": relationships,
        }

    @staticmethod
    def to_json(G: nx.DiGraph, path: Optional[str] = None) -> str:
        """Serialize DiGraph to JSON string; optionally write to `path`."""
        schema = ArchGraphBuilder.to_schema_dict(G)
        json_str = json.dumps(schema, indent=2)
        if path:
            Path(path).parent.mkdir(parents=True, exist_ok=True)
            Path(path).write_text(json_str, encoding="utf-8")
            logger.info("Graph written to %s", path)
        return json_str

    @staticmethod
    def to_adjacency_dict(G: nx.DiGraph) -> Dict[str, List[str]]:
        """Return a simple {node: [neighbours]} adjacency dict for quick inspection."""
        return {n: list(G.successors(n)) for n in G.nodes()}

    @staticmethod
    def to_dot(G: nx.DiGraph) -> str:
        """Return a minimal GraphViz DOT representation."""
        lines = ["digraph ArchLens {", '  rankdir="LR";']
        for n, attrs in G.nodes(data=True):
            label = attrs.get("name", n)
            ntype = attrs.get("type", "")
            conf = attrs.get("confidence", 1.0)
            lines.append(
                f'  "{n}" [label="{label}\\n[{ntype}]\\nconf={conf:.2f}"];'
            )
        for u, v, attrs in G.edges(data=True):
            etype = attrs.get("type", "")
            conf = attrs.get("confidence", 1.0)
            lines.append(f'  "{u}" -> "{v}" [label="{etype}\\n{conf:.2f}"];')
        lines.append("}")
        return "\n".join(lines)


# ---------------------------------------------------------------------------
# Sprint 4 D13 — Package-level graph aggregation
# ---------------------------------------------------------------------------

class PackageGraphAggregator:
    """
    Aggregate a file/class-level graph (G_C from DependencyGraphBuilder)
    into a coarser package/module-level graph.

    Rules applied
    -------------
    * Each node's `name` is split on the last '.' (or '/' for path-based IDs);
      everything before the last segment is the package.
    * Intra-package edges are dropped (self-loops at the package level).
    * Cross-package edges are kept; confidence is the max over all constituent
      file-level edges.
    """

    @staticmethod
    def aggregate(G: nx.DiGraph) -> nx.DiGraph:
        """Return a new DiGraph collapsed to package level."""

        def _package(node_id: str, attrs: dict) -> str:
            name = attrs.get("name", node_id)
            # Prefer dot-separated module path; fall back to slash-based path
            if "." in name:
                return ".".join(name.split(".")[:-1]) or name
            if "/" in name or "\\" in name:
                p = Path(name)
                return str(p.parent) if str(p.parent) != "." else name
            return name  # single-token: keep as-is

        P = nx.DiGraph()
        P.graph.update(G.graph)
        P.graph["aggregation"] = "package"

        # Assign package to each node
        node_to_pkg: Dict[str, str] = {}
        for n, attrs in G.nodes(data=True):
            pkg = _package(n, attrs)
            node_to_pkg[n] = pkg
            if pkg not in P:
                P.add_node(pkg, name=pkg, type="module", confidence=1.0,
                           provenance="aggregated", metadata={})

        # Aggregate edges
        edge_conf: Dict[Tuple[str, str], float] = {}
        for u, v, attrs in G.edges(data=True):
            src_pkg = node_to_pkg.get(u, u)
            tgt_pkg = node_to_pkg.get(v, v)
            if src_pkg == tgt_pkg:
                continue  # intra-package — drop
            key = (src_pkg, tgt_pkg)
            conf = float(attrs.get("confidence", 1.0))
            edge_conf[key] = max(edge_conf.get(key, 0.0), conf)

        for (src, tgt), conf in edge_conf.items():
            P.add_edge(src, tgt, type="depends_on", confidence=conf,
                       provenance="aggregated", metadata={})

        logger.info(
            "Package aggregation: %d → %d nodes, %d → %d edges",
            G.number_of_nodes(), P.number_of_nodes(),
            G.number_of_edges(), P.number_of_edges(),
        )
        return P


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _safe_str(value: Any) -> str:
    if hasattr(value, "value"):      # Enum
        return str(value.value)
    return str(value) if value is not None else "unknown"

