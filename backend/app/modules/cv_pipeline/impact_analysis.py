"""
Sprint 8 / D36 + D37: connect diagram nodes to a NetworkX graph and the
offending edge, and compute which other nodes are affected (blast radius)
via real graph traversal - this is Module E's "Deterministic Rule Matching"
/ impact-analysis half, built on the real `ArchGraph` schema.
"""

from __future__ import annotations

from dataclasses import dataclass

import networkx as nx

from app.schemas.models import ArchGraph


def build_networkx_graph(graph: ArchGraph) -> nx.DiGraph:
    """Convert the shared ArchGraph schema into a NetworkX directed graph."""
    g = nx.DiGraph()
    for c in graph.components:
        g.add_node(c.id, name=c.name, type=c.type.value)
    for r in graph.relationships:
        g.add_edge(r.source, r.target, id=r.id, type=r.type.value)
    return g


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
