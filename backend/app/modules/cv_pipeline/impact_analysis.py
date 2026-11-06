"""
Sprint 8 / D36 + D37: connect diagram nodes to a NetworkX graph and the
offending edge, and compute which other nodes are affected (blast radius)
via real graph traversal - this is Module E's "Deterministic Rule Matching"
/ impact-analysis half, built on the real `ArchGraph` schema.

Sprint 8 / D38 + D40: validate proposed corrections against forbidden-edge
rules and produce machine-readable impact summaries.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import List, Set

import networkx as nx

from app.schemas.models import ArchGraph, ViolationType
from app.schemas.vocabulary import DEFAULT_FORBIDDEN_DEPENDENCIES


# ─── Helpers ─────────────────────────────────────────────────────────────────

def _normalize(val: object) -> str:
    """Lowercase string from a plain str or an Enum value."""
    if hasattr(val, "value"):
        return str(val.value).lower().strip()
    return str(val).lower().strip()


# Normalised forbidden pairs cached at import time
_FORBIDDEN_PAIRS: list[tuple[str, str]] = [
    (_normalize(s), _normalize(t)) for s, t in DEFAULT_FORBIDDEN_DEPENDENCIES
]


def build_networkx_graph(graph: ArchGraph) -> nx.DiGraph:
    """Convert the shared ArchGraph schema into a NetworkX directed graph."""
    g = nx.DiGraph()
    for c in graph.components:
        g.add_node(c.id, name=c.name, type=c.type.value)
    for r in graph.relationships:
        g.add_edge(r.source, r.target, id=r.id, type=r.type.value)
    return g


# ─── Dataclasses ─────────────────────────────────────────────────────────────

@dataclass
class ImpactAnalysis:
    source: str
    target: str
    upstream_affected: list[str]  # nodes that depend on `source` (indirectly coupled to the bad edge)
    downstream_affected: list[str]  # nodes reachable from `target` (what `source` is now indirectly coupled to)

    def to_dict(self) -> dict:
        return {
            "source": self.source,
            "target": self.target,
            "upstream_affected": self.upstream_affected,
            "downstream_affected": self.downstream_affected,
        }


@dataclass
class PathValidation:
    valid: bool
    reasons: list[str]

    def to_dict(self) -> dict:
        return {"valid": self.valid, "reasons": self.reasons}


@dataclass
class CorrectionValidation:
    """D38: result of checking whether proposed correction edges are safe."""
    valid: bool
    violations: List[str]
    safe_edges: List[tuple]

    def to_dict(self) -> dict:
        return {
            "valid": self.valid,
            "violations": self.violations,
            "safe_edges": [list(e) for e in self.safe_edges],
        }


# ─── Core traversal functions ─────────────────────────────────────────────────

def validate_recommended_path(g: nx.DiGraph, source: str, target: str, proposed_path: list[str]) -> PathValidation:
    """Sprint 8 / D39: does a proposed fix preserve the intended diagram's paths/layers?

    A recommended fix is only valid if every edge it relies on already
    exists in the intended graph (no new/invented dependency), it actually
    connects `source` to `target`, and it does not simply reuse the
    offending direct edge.
    """
    reasons: list[str] = []

    if len(proposed_path) < 2 or proposed_path[0] != source or proposed_path[-1] != target:
        reasons.append(f"proposed path must start at {source!r} and end at {target!r}")
        return PathValidation(valid=False, reasons=reasons)

    if len(proposed_path) == 2:
        reasons.append("proposed path is just the original direct edge - not a different route")
        return PathValidation(valid=False, reasons=reasons)

    for a, b in zip(proposed_path, proposed_path[1:]):
        if not g.has_edge(a, b):
            reasons.append(f"edge {a!r} -> {b!r} is not part of the intended architecture graph")

    return PathValidation(valid=not reasons, reasons=reasons)


def compute_affected_nodes(g: nx.DiGraph, source: str, target: str) -> ImpactAnalysis:
    """Real graph traversal: who is affected by the (source -> target) edge?

    Upstream: every node that can reach `source` - if the edge is removed or
    changed, anything that depends on `source` is indirectly affected.
    Downstream: every node reachable from `target` - `source` is now
    transitively coupled to all of it through this one edge.
    """
    if source not in g or target not in g:
        raise ValueError(f"source={source!r} / target={target!r} must both be real nodes in the graph")

    upstream = sorted(nx.ancestors(g, source))
    downstream = sorted(nx.descendants(g, target))
    return ImpactAnalysis(source=source, target=target, upstream_affected=upstream, downstream_affected=downstream)


# ─── D38: Correction-edge validation ─────────────────────────────────────────

def validate_correction_edges(
    G_I: nx.DiGraph,
    G_C: nx.DiGraph,
    source: str,
    target: str,
    proposed_edges: List[tuple],
) -> CorrectionValidation:
    """D38: Check that adding *proposed_edges* to G_C does NOT create new FORBIDDEN edges.

    For every proposed (src, tgt) edge, the component types are resolved from
    whichever graph (G_C, then G_I) has the node metadata.  If the resulting
    type pair appears in DEFAULT_FORBIDDEN_DEPENDENCIES the edge is rejected.

    Returns a CorrectionValidation with:
    - valid        – True only when *all* proposed edges are safe.
    - violations   – Human-readable descriptions of each offending edge.
    - safe_edges   – Subset of proposed_edges that passed the check.
    """
    violations: List[str] = []
    safe_edges: List[tuple] = []

    def _node_type(graph_primary: nx.DiGraph, graph_fallback: nx.DiGraph, node_id: str) -> str:
        for g in (graph_primary, graph_fallback):
            if node_id in g and g.nodes[node_id].get("type"):
                return _normalize(g.nodes[node_id]["type"])
        return ""

    for edge in proposed_edges:
        src, tgt = edge[0], edge[1]
        src_type = _node_type(G_C, G_I, src)
        tgt_type = _node_type(G_C, G_I, tgt)

        if (src_type, tgt_type) in _FORBIDDEN_PAIRS:
            violations.append(
                f"Proposed edge {src!r} -> {tgt!r} creates a forbidden dependency: "
                f"{src_type} -> {tgt_type}"
            )
        else:
            safe_edges.append(tuple(edge))

    return CorrectionValidation(
        valid=len(violations) == 0,
        violations=violations,
        safe_edges=safe_edges,
    )


# ─── D37 (extended): Transitive impact across multiple sources ────────────────

def transitive_impact(g: nx.DiGraph, sources: Set[str]) -> Set[str]:
    """D37 (extended): Return all nodes transitively reachable downstream from *sources*.

    Uses BFS/DFS-safe traversal that handles cycles without hanging.
    The source nodes themselves are **not** included in the result unless
    another source can reach them.
    """
    visited: Set[str] = set()
    queue = list(sources)

    while queue:
        node = queue.pop()
        for successor in g.successors(node):
            if successor not in visited:
                visited.add(successor)
                queue.append(successor)

    return visited


# ─── D40: Machine-readable impact summary ────────────────────────────────────

def compute_impact_summary(
    G: nx.DiGraph,
    source: str,
    target: str,
    violation_type: str,
) -> dict:
    """D40: Produce a machine-readable impact summary for the (source -> target) violation.

    Keys returned:
    - violation_edge          – (source, target) tuple
    - upstream_count          – number of ancestors of `source`
    - downstream_count        – number of descendants of `target`
    - upstream_affected       – sorted list of upstream node ids
    - downstream_affected     – sorted list of downstream node ids
    - blast_radius_fraction   – (upstream + downstream unique nodes) / total nodes
    - impact_severity         – "low" / "medium" / "high" / "critical"
      thresholds: <0.1 → low, <0.3 → medium, <0.6 → high, else → critical
    """
    if source not in G or target not in G:
        raise ValueError(f"source={source!r} / target={target!r} must both be real nodes in the graph")

    total_nodes = G.number_of_nodes()
    upstream_affected = sorted(nx.ancestors(G, source))
    downstream_affected = sorted(nx.descendants(G, target))

    # Unique affected nodes (union, excluding source/target themselves)
    all_affected = set(upstream_affected) | set(downstream_affected)
    blast_radius_fraction = len(all_affected) / total_nodes if total_nodes > 0 else 0.0

    if blast_radius_fraction < 0.1:
        impact_severity = "low"
    elif blast_radius_fraction < 0.3:
        impact_severity = "medium"
    elif blast_radius_fraction < 0.6:
        impact_severity = "high"
    else:
        impact_severity = "critical"

    return {
        "violation_edge": (source, target),
        "upstream_count": len(upstream_affected),
        "downstream_count": len(downstream_affected),
        "upstream_affected": upstream_affected,
        "downstream_affected": downstream_affected,
        "blast_radius_fraction": blast_radius_fraction,
        "impact_severity": impact_severity,
        "violation_type": violation_type,
    }
