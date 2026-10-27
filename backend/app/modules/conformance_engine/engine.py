"""
Module E: Conformance Engine
Fully deterministic graph-based conformance checking.

Given G_I (intended) and G_C (current), applies architectural rules
and produces verdicts: CONFORMANT | VIOLATION | MISSING | UNEXPECTED | UNCERTAIN
"""

import networkx as nx
from typing import List, Dict, Any, Optional, Set, Tuple
import logging

logger = logging.getLogger(__name__)


# ─── Verdict constants ────────────────────────────────────────────────────────
CONFORMANT = "CONFORMANT"
VIOLATION = "VIOLATION"
MISSING = "MISSING"
UNEXPECTED = "UNEXPECTED"
UNCERTAIN = "UNCERTAIN"


class LayeredArchitectureRule:
    """Enforce layered architecture constraints."""

    # Forbidden cross-layer dependencies
    FORBIDDEN_PATTERNS: List[Tuple[str, str]] = [
        ("controller", "repository"),
        ("frontend", "database"),
        ("gateway", "repository"),
    ]

    def check(self, source_type: str, target_type: str) -> str:
        """Return verdict for a dependency from source_type → target_type."""
        pair = (source_type.lower(), target_type.lower())
        if pair in self.FORBIDDEN_PATTERNS:
            return VIOLATION
        return CONFORMANT


class ConformanceRule:
    """Base class for conformance rules."""

    name: str = "base_rule"

    def apply(
        self,
        G_I: nx.DiGraph,
        G_C: nx.DiGraph,
        source: str,
        target: str,
    ) -> Dict[str, Any]:
        raise NotImplementedError


class ForbiddenDependencyRule(ConformanceRule):
    """Detect dependencies that are present in G_C but forbidden by G_I rules."""

    name = "forbidden_dependency"

    def __init__(self, forbidden_pairs: List[Tuple[str, str]]):
        self.forbidden_pairs = forbidden_pairs

    def apply(self, G_I, G_C, source, target):
        src_type = G_C.nodes[source].get("type", "")
        tgt_type = G_C.nodes[target].get("type", "")

        if (src_type, tgt_type) in self.forbidden_pairs:
            return {
                "verdict": VIOLATION,
                "violation_type": "forbidden_dependency",
                "source": source,
                "target": target,
                "severity": "high",
                "description": (
                    f"Forbidden dependency: {src_type} → {tgt_type}. "
                    f"Layer violation detected."
                ),
            }
        return {"verdict": CONFORMANT, "source": source, "target": target}


class MissingDependencyRule(ConformanceRule):
    """Detect dependencies present in G_I but missing in G_C."""

    name = "missing_dependency"

    def apply(self, G_I, G_C, source, target):
        if G_I.has_edge(source, target) and not G_C.has_edge(source, target):
            return {
                "verdict": MISSING,
                "violation_type": "missing_dependency",
                "source": source,
                "target": target,
                "severity": "medium",
                "description": (
                    f"Expected dependency {source} → {target} is missing "
                    f"in the implementation."
                ),
            }
        return {"verdict": CONFORMANT, "source": source, "target": target}


class UnexpectedDependencyRule(ConformanceRule):
    """Detect dependencies in G_C not present in G_I."""

    name = "unexpected_dependency"

    def apply(self, G_I, G_C, source, target):
        if G_C.has_edge(source, target) and not G_I.has_edge(source, target):
            return {
                "verdict": UNEXPECTED,
                "violation_type": "unexpected_dependency",
                "source": source,
                "target": target,
                "severity": "medium",
                "description": (
                    f"Unexpected dependency {source} → {target} found "
                    f"in implementation but not in intended architecture."
                ),
            }
        return {"verdict": CONFORMANT, "source": source, "target": target}


class CycleDetectionRule(ConformanceRule):
    """Detect architectural cycles in G_C."""

    name = "cycle_detection"

    def apply(self, G_I, G_C, source=None, target=None):
        cycles = list(nx.simple_cycles(G_C))
        results = []
        for cycle in cycles:
            results.append({
                "verdict": VIOLATION,
                "violation_type": "cycle_violation",
                "source": cycle[0],
                "target": cycle[-1],
                "severity": "high",
                "description": f"Architectural cycle detected: {' → '.join(cycle)}",
                "cycle": cycle,
            })
        return results


class ConformanceEngine:
    """
    Main conformance engine.
    Compares G_I and G_C and produces structured violation reports.
    """

    FORBIDDEN_PAIRS: List[Tuple[str, str]] = [
        ("controller", "repository"),
        ("frontend", "database"),
        ("gateway", "repository"),
        ("controller", "database"),
    ]

    def __init__(self):
        self.rules: List[ConformanceRule] = [
            ForbiddenDependencyRule(self.FORBIDDEN_PAIRS),
            MissingDependencyRule(),
            UnexpectedDependencyRule(),
        ]
        self.cycle_rule = CycleDetectionRule()

    def build_graph(self, graph_data: Dict[str, Any]) -> nx.DiGraph:
        """Convert ArchGraph dict → NetworkX DiGraph."""
        G = nx.DiGraph()
        for comp in graph_data.get("components", []):
            node_id = comp.get("id") or comp.get("name")
            G.add_node(node_id, **comp)

        for rel in graph_data.get("relationships", []):
            src = rel.get("source")
            tgt = rel.get("target")
            if src and tgt:
                G.add_edge(src, tgt, **rel)
        return G

    def check_conformance(
        self,
        intended_graph: Dict[str, Any],
        current_graph: Dict[str, Any],
    ) -> Dict[str, Any]:
        """
        Main entry point: compare G_I vs G_C and return all violations.
        """
        G_I = self.build_graph(intended_graph)
        G_C = self.build_graph(current_graph)

        violations = []

        # Check all edges in G_C for violations
        for src, tgt in G_C.edges():
            for rule in self.rules:
                if rule.name == "missing_dependency":
                    continue  # handled separately
                result = rule.apply(G_I, G_C, src, tgt)
                if result.get("verdict") not in (CONFORMANT, None):
                    violations.append(result)

        # Check missing dependencies (edges in G_I not in G_C)
        missing_rule = MissingDependencyRule()
        for src, tgt in G_I.edges():
            result = missing_rule.apply(G_I, G_C, src, tgt)
            if result.get("verdict") == MISSING:
                violations.append(result)

        # Check for cycles
        cycle_results = self.cycle_rule.apply(G_I, G_C)
        violations.extend(cycle_results)

        summary = {
            "total_violations": len(violations),
            "by_type": {},
            "severity_counts": {"low": 0, "medium": 0, "high": 0, "critical": 0},
        }
        for v in violations:
            vtype = v.get("violation_type", "unknown")
            summary["by_type"][vtype] = summary["by_type"].get(vtype, 0) + 1
            severity = v.get("severity", "medium")
            summary["severity_counts"][severity] += 1

        logger.info(f"Conformance check complete: {len(violations)} violations found")
        return {
            "verdict": VIOLATION if violations else CONFORMANT,
            "violations": violations,
            "summary": summary,
        }
