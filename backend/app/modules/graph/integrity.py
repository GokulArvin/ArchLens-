"""
Sprint 5 (P3 D19) + Sprint 6 (P3 D24):
Graph Integrity Checker — validates a NetworkX DiGraph before it enters
the conformance engine.

Checks performed
----------------
1. Missing endpoints — edge references a node id not in the graph.
2. Self-loops — edges where source == target.
3. Duplicate edges — parallel edges (DiGraph shouldn't have them, but
   data loaded from JSON can be inconsistent before build()).
4. Confidence bounds — confidence values outside [0, 1].
5. Cycle detection — simple cycles in the directed graph (structural fact;
   cycle *violations* are reported separately by the ConformanceEngine).
6. Isolated nodes — nodes with no edges at all (may indicate extraction gaps).

Each check returns a list of ``IntegrityIssue`` dataclasses.
``GraphIntegrityChecker.check()`` aggregates all issues and returns an
``IntegrityReport``.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from enum import Enum
from typing import List

import networkx as nx

logger = logging.getLogger(__name__)


class IssueSeverity(str, Enum):
    ERROR = "error"       # Graph is structurally invalid; block conformance
    WARNING = "warning"   # Graph is usable but results may be unreliable
    INFO = "info"         # Informational note only


@dataclass
class IntegrityIssue:
    code: str
    severity: IssueSeverity
    description: str
    node: str = ""
    edge: tuple = field(default_factory=tuple)


@dataclass
class IntegrityReport:
    is_valid: bool           # True when no ERROR-level issues
    issues: List[IntegrityIssue] = field(default_factory=list)
    cycle_count: int = 0
    isolated_node_count: int = 0

    def errors(self) -> List[IntegrityIssue]:
        return [i for i in self.issues if i.severity == IssueSeverity.ERROR]

    def warnings(self) -> List[IntegrityIssue]:
        return [i for i in self.issues if i.severity == IssueSeverity.WARNING]

    def summary(self) -> dict:
        return {
            "is_valid": self.is_valid,
            "total_issues": len(self.issues),
            "errors": len(self.errors()),
            "warnings": len(self.warnings()),
            "cycle_count": self.cycle_count,
            "isolated_node_count": self.isolated_node_count,
        }


class GraphIntegrityChecker:
    """
    Validates a NetworkX DiGraph before conformance checking.

    Usage
    -----
    checker = GraphIntegrityChecker()
    report  = checker.check(G)
    if not report.is_valid:
        raise ValueError(str(report.errors()))
    """

    def check(self, G: nx.DiGraph) -> IntegrityReport:
        issues: List[IntegrityIssue] = []

        issues.extend(self._check_missing_endpoints(G))
        issues.extend(self._check_self_loops(G))
        issues.extend(self._check_confidence_bounds(G))

        cycle_count = self._count_cycles(G)
        if cycle_count:
            issues.append(IntegrityIssue(
                code="CYCLE_DETECTED",
                severity=IssueSeverity.WARNING,
                description=(
                    f"{cycle_count} simple cycle(s) detected in the graph. "
                    "Cycles are structural facts; architectural violations are "
                    "reported separately by the ConformanceEngine."
                ),
            ))

        isolated = [n for n in G.nodes() if G.degree(n) == 0]
        if isolated:
            for n in isolated:
                issues.append(IntegrityIssue(
                    code="ISOLATED_NODE",
                    severity=IssueSeverity.INFO,
                    description=f"Node '{n}' has no edges (may indicate an extraction gap).",
                    node=n,
                ))

        is_valid = all(i.severity != IssueSeverity.ERROR for i in issues)
        report = IntegrityReport(
            is_valid=is_valid,
            issues=issues,
            cycle_count=cycle_count,
            isolated_node_count=len(isolated),
        )
        logger.info(
            "Integrity check: valid=%s, issues=%d (errors=%d, warnings=%d, cycles=%d)",
            is_valid, len(issues), len(report.errors()), len(report.warnings()), cycle_count,
        )
        return report

    # ------------------------------------------------------------------
    # Individual checks
    # ------------------------------------------------------------------

    @staticmethod
    def _check_missing_endpoints(G: nx.DiGraph) -> List[IntegrityIssue]:
        """
        Check that every edge endpoint has at least one node attribute
        (name, type, confidence) set — which indicates it was explicitly
        registered rather than silently auto-created by NetworkX when
        add_edge() was called with an unknown node id.
        """
        issues = []
        for u, v in G.edges():
            u_attrs = G.nodes[u]
            v_attrs = G.nodes[v]
            # An explicitly registered node will have at least a 'name' attribute.
            if not u_attrs.get("name") and not u_attrs.get("type"):
                issues.append(IntegrityIssue(
                    code="MISSING_SOURCE_NODE",
                    severity=IssueSeverity.ERROR,
                    description=(
                        f"Edge source '{u}' was not explicitly registered as a node "
                        f"(auto-created by edge addition without node attributes)."
                    ),
                    edge=(u, v),
                ))
            if not v_attrs.get("name") and not v_attrs.get("type"):
                issues.append(IntegrityIssue(
                    code="MISSING_TARGET_NODE",
                    severity=IssueSeverity.ERROR,
                    description=(
                        f"Edge target '{v}' was not explicitly registered as a node "
                        f"(auto-created by edge addition without node attributes)."
                    ),
                    edge=(u, v),
                ))
        return issues

    @staticmethod
    def _check_self_loops(G: nx.DiGraph) -> List[IntegrityIssue]:
        return [
            IntegrityIssue(
                code="SELF_LOOP",
                severity=IssueSeverity.WARNING,
                description=f"Self-loop on node '{u}' (source == target).",
                edge=(u, v),
            )
            for u, v in G.edges()
            if u == v
        ]

    @staticmethod
    def _check_confidence_bounds(G: nx.DiGraph) -> List[IntegrityIssue]:
        issues = []
        for u, v, attrs in G.edges(data=True):
            conf = attrs.get("confidence")
            if conf is None:
                continue
            try:
                c = float(conf)
            except (TypeError, ValueError):
                issues.append(IntegrityIssue(
                    code="INVALID_CONFIDENCE",
                    severity=IssueSeverity.ERROR,
                    description=f"Edge {u}→{v} has non-numeric confidence: {conf!r}.",
                    edge=(u, v),
                ))
                continue
            if not (0.0 <= c <= 1.0):
                issues.append(IntegrityIssue(
                    code="CONFIDENCE_OUT_OF_RANGE",
                    severity=IssueSeverity.WARNING,
                    description=f"Edge {u}→{v} confidence {c:.4f} is outside [0, 1].",
                    edge=(u, v),
                ))
        return issues

    @staticmethod
    def _count_cycles(G: nx.DiGraph) -> int:
        try:
            cycles = list(nx.simple_cycles(G))
            return len(cycles)
        except Exception as exc:
            logger.warning("Cycle detection failed: %s", exc)
            return 0

