
"""
Module E: Conformance Engine
Deterministic graph-based architecture conformance checking.

Compares:
    G_I = Intended architecture graph
    G_C = Current architecture graph

Supported verdicts:
    CONFORMANT | VIOLATION | MISSING | UNEXPECTED | UNCERTAIN
"""

import logging
from typing import Any, Dict, List, Tuple

import networkx as nx

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------
# Verdict constants
# ---------------------------------------------------------------------

CONFORMANT = "CONFORMANT"
VIOLATION = "VIOLATION"
MISSING = "MISSING"
UNEXPECTED = "UNEXPECTED"
UNCERTAIN = "UNCERTAIN"


# ---------------------------------------------------------------------
# Architectural rules
# ---------------------------------------------------------------------

class LayeredArchitectureRule:
    """Enforce layered architecture constraints."""

    FORBIDDEN_PATTERNS: List[Tuple[str, str]] = [
        ("controller", "repository"),
        ("frontend", "database"),
        ("gateway", "repository"),
        ("controller", "database"),
    ]

    def check(self, source_type: str, target_type: str) -> str:
        pair = (
            str(source_type).strip().lower(),
            str(target_type).strip().lower(),
        )

        if pair in self.FORBIDDEN_PATTERNS:
            return VIOLATION

        return CONFORMANT


class ConformanceRule:
    """Base class for conformance rules."""

    name = "base_rule"

    def apply(self, G_I, G_C, source, target):
        raise NotImplementedError


class ForbiddenDependencyRule(ConformanceRule):
    """Detect forbidden architectural dependencies."""

    name = "forbidden_dependency"

    def __init__(self, forbidden_pairs):
        self.forbidden_pairs = {
            (
                str(source).strip().lower(),
                str(target).strip().lower(),
            )
            for source, target in forbidden_pairs
        }

    def apply(self, G_I, G_C, source, target):
        """Check whether a dependency violates architectural layers."""

        source_data = G_C.nodes[source]
        target_data = G_C.nodes[target]

        # Extract architectural layers from metadata.
        # Fall back to component type for older graph formats.
        src_type = (
            source_data.get("metadata", {}).get("layer")
            or source_data.get("type", "")
        )

        tgt_type = (
            target_data.get("metadata", {}).get("layer")
            or target_data.get("type", "")
        )

        src_type = str(src_type).strip().lower()
        tgt_type = str(tgt_type).strip().lower()

        if (src_type, tgt_type) in self.forbidden_pairs:

            edge_data = G_C.get_edge_data(
                source,
                target,
                default={},
            )

            return {
                "verdict": VIOLATION,
                "rule": self.name,
                "violation_type": "forbidden_dependency",
                "source": source,
                "target": target,
                "source_component": source,
                "target_component": target,
                "severity": "high",
                "confidence": float(
                    edge_data.get("confidence", 1.0)
                ),
                "evidence": {
                    "source_layer": src_type,
                    "target_layer": tgt_type,
                    "relationship": edge_data,
                    "extraction_method": (
                        edge_data.get("metadata", {}).get(
                            "extraction_method"
                        )
                    ),
                },
                "description": (
                    f"Forbidden architectural dependency: "
                    f"{src_type} -> {tgt_type}."
                ),
            }

        return {"verdict": CONFORMANT}


class MissingDependencyRule(ConformanceRule):
    """Detect intended dependencies missing from the implementation."""

    name = "missing_dependency"

    def apply(self, G_I, G_C, source, target):

        if G_I.has_edge(source, target) and not G_C.has_edge(
            source, target
        ):
            edge_data = G_I.get_edge_data(
                source,
                target,
                default={},
            )

            return {
                "verdict": MISSING,
                "rule": self.name,
                "violation_type": "missing_dependency",
                "source": source,
                "target": target,
                "source_component": source,
                "target_component": target,
                "severity": "medium",
                "confidence": float(
                    edge_data.get("confidence", 1.0)
                ),
                "evidence": {
                    "expected_relationship": edge_data,
                    "found_in": "intended_graph",
                    "missing_from": "current_graph",
                },
                "description": (
                    f"Expected dependency {source} -> {target} "
                    "is missing from the implementation."
                ),
            }

        return {"verdict": CONFORMANT}


class UnexpectedDependencyRule(ConformanceRule):
    """Detect dependencies absent from the intended architecture."""

    name = "unexpected_dependency"

    def apply(self, G_I, G_C, source, target):

        if G_C.has_edge(source, target) and not G_I.has_edge(
            source, target
        ):
            edge_data = G_C.get_edge_data(
                source,
                target,
                default={},
            )

            return {
                "verdict": UNEXPECTED,
                "rule": self.name,
                "violation_type": "unexpected_dependency",
                "source": source,
                "target": target,
                "source_component": source,
                "target_component": target,
                "severity": "medium",
                "confidence": float(
                    edge_data.get("confidence", 1.0)
                ),
                "evidence": {
                    "actual_relationship": edge_data,
                    "found_in": "current_graph",
                    "missing_from": "intended_graph",
                },
                "description": (
                    f"Unexpected dependency {source} -> {target} "
                    "was found in the implementation."
                ),
            }

        return {"verdict": CONFORMANT}


class CycleDetectionRule(ConformanceRule):
    """Detect directed architectural cycles in the current graph."""

    name = "cycle_detection"

    def apply(self, G_I, G_C, source=None, target=None):
        results = []

        for cycle in nx.simple_cycles(G_C):

            cycle_edges = list(
                zip(cycle, cycle[1:] + cycle[:1])
            )

            edge_confidences = [
                float(
                    G_C.get_edge_data(
                        src,
                        tgt,
                        default={},
                    ).get("confidence", 1.0)
                )
                for src, tgt in cycle_edges
            ]

            confidence = min(edge_confidences, default=1.0)

            results.append({
                "verdict": VIOLATION,
                "rule": self.name,
                "violation_type": "cycle_violation",
                "source": cycle[0],
                "target": cycle[-1],
                "source_component": cycle[0],
                "target_component": cycle[-1],
                "severity": "high",
                "confidence": confidence,
                "evidence": {
                    "cycle_nodes": cycle,
                    "cycle_edges": [
                        {
                            "source": src,
                            "target": tgt,
                        }
                        for src, tgt in cycle_edges
                    ],
                },
                "description": (
                    "Architectural cycle detected: "
                    + " -> ".join(cycle + [cycle[0]])
                ),
                "cycle": cycle,
            })

        return results


# ---------------------------------------------------------------------
# Main Conformance Engine
# ---------------------------------------------------------------------

class ConformanceEngine:
    """Compare intended and current architecture graphs."""

    FORBIDDEN_PAIRS: List[Tuple[str, str]] = [
        ("controller", "repository"),
        ("frontend", "database"),
        ("gateway", "repository"),
        ("controller", "database"),
    ]

    UNCERTAINTY_THRESHOLD = 0.5

    def __init__(self):
        self.rules = [
            ForbiddenDependencyRule(self.FORBIDDEN_PAIRS),
            MissingDependencyRule(),
            UnexpectedDependencyRule(),
        ]

        self.cycle_rule = CycleDetectionRule()

    # -----------------------------------------------------------------
    # Graph construction and validation
    # -----------------------------------------------------------------

    def build_graph(self, graph_data: Dict[str, Any]) -> nx.DiGraph:
        """
        Convert an architecture graph dictionary into a validated
        NetworkX directed graph.
        """

        if not isinstance(graph_data, dict):
            raise ValueError("Graph data must be a dictionary.")

        components = graph_data.get("components", [])
        relationships = graph_data.get("relationships", [])

        if not isinstance(components, list):
            raise ValueError("'components' must be a list.")

        if not isinstance(relationships, list):
            raise ValueError("'relationships' must be a list.")

        G = nx.DiGraph()

        # Register all components before processing relationships.
        for comp in components:

            if not isinstance(comp, dict):
                raise ValueError(
                    "Each component must be a dictionary."
                )

            node_id = comp.get("id") or comp.get("name")

            if not node_id:
                raise ValueError(
                    "Every component must have an id or name."
                )

            if node_id in G:
                raise ValueError(
                    f"Duplicate component ID: {node_id}"
                )

            G.add_node(node_id, **comp)

        # Validate relationships against registered components.
        for rel in relationships:

            if not isinstance(rel, dict):
                raise ValueError(
                    "Each relationship must be a dictionary."
                )

            src = rel.get("source")
            tgt = rel.get("target")

            if not src or not tgt:
                raise ValueError(
                    "Every relationship must have source and target."
                )

            if src not in G:
                raise ValueError(
                    f"Relationship source '{src}' "
                    "is not a registered component."
                )

            if tgt not in G:
                raise ValueError(
                    f"Relationship target '{tgt}' "
                    "is not a registered component."
                )

            confidence = rel.get("confidence", 1.0)

            try:
                confidence = float(confidence)
            except (TypeError, ValueError):
                raise ValueError(
                    f"Invalid relationship confidence: {confidence}"
                )

            if not 0.0 <= confidence <= 1.0:
                raise ValueError(
                    "Relationship confidence must be between 0 and 1."
                )

            edge_data = dict(rel)
            edge_data["confidence"] = confidence

            G.add_edge(src, tgt, **edge_data)

        return G

    # -----------------------------------------------------------------
    # Uncertainty evaluation
    # -----------------------------------------------------------------

    def _has_uncertain_evidence(
        self,
        intended_graph: Dict[str, Any],
        current_graph: Dict[str, Any],
    ) -> bool:
        """
        Determine whether available graph evidence is insufficient
        for a confident conformance decision.

        Uncertainty conditions:
        - Component confidence below threshold.
        - Relationship confidence below threshold.
        - Explicitly unknown architectural layer.
        - Incomplete or uncertain graph alignment.

        Missing layer metadata alone does not imply uncertainty.
        """

        # IMPORTANT:
        # Graph-level checks must be inside this loop because the
        # variable 'graph' is assigned by the loop itself.
        for graph in (intended_graph, current_graph):

            # Check graph-level alignment uncertainty.
            graph_metadata = graph.get("metadata", {})

            if not isinstance(graph_metadata, dict):
                raise ValueError(
                    "Graph metadata must be a dictionary."
                )

            alignment = graph_metadata.get("alignment", {})

            if not isinstance(alignment, dict):
                raise ValueError(
                    "Graph alignment metadata must be a dictionary."
                )

            if alignment.get("has_uncertainty") is True:
                return True

            # Check component confidence and architectural layer.
            for component in graph.get("components", []):

                confidence = component.get("confidence", 1.0)

                try:
                    confidence = float(confidence)
                except (TypeError, ValueError):
                    raise ValueError(
                        f"Invalid component confidence: {confidence}"
                    )

                if not 0.0 <= confidence <= 1.0:
                    raise ValueError(
                        "Component confidence must be between 0 and 1."
                    )

                if confidence < self.UNCERTAINTY_THRESHOLD:
                    return True

                metadata = component.get("metadata", {})

                if not isinstance(metadata, dict):
                    raise ValueError(
                        "Component metadata must be a dictionary."
                    )

                # Missing layer alone does not trigger uncertainty.
                layer = metadata.get("layer")

                if (
                    layer is not None
                    and str(layer).strip().lower() == "unknown"
                ):
                    return True

            # Check relationship confidence.
            for relationship in graph.get("relationships", []):

                confidence = relationship.get("confidence", 1.0)

                try:
                    confidence = float(confidence)
                except (TypeError, ValueError):
                    raise ValueError(
                        f"Invalid relationship confidence: {confidence}"
                    )

                if not 0.0 <= confidence <= 1.0:
                    raise ValueError(
                        "Relationship confidence must be between 0 and 1."
                    )

                if confidence < self.UNCERTAINTY_THRESHOLD:
                    return True

                # An explicitly unverified relationship is uncertain.
                relationship_metadata = relationship.get(
                    "metadata", {}
                )

                if not isinstance(relationship_metadata, dict):
                    raise ValueError(
                        "Relationship metadata must be a dictionary."
                    )

                if (
                    relationship_metadata.get("direction_verified")
                    is False
                ):
                    return True

        return False

    # -----------------------------------------------------------------
    # Main conformance checking
    # -----------------------------------------------------------------

    def check_conformance(
        self,
        intended_graph: Dict[str, Any],
        current_graph: Dict[str, Any],
    ) -> Dict[str, Any]:
        """
        Compare intended and current architecture graphs
        and return a structured conformance report.
        """

        G_I = self.build_graph(intended_graph)
        G_C = self.build_graph(current_graph)

        violations = []

        # Check current dependencies for forbidden and unexpected edges.
        for src, tgt in G_C.edges():

            for rule in self.rules:

                if rule.name == "missing_dependency":
                    continue

                result = rule.apply(G_I, G_C, src, tgt)

                if result.get("verdict") not in (CONFORMANT, None):
                    violations.append(result)

        # Check for missing intended dependencies.
        missing_rule = MissingDependencyRule()

        for src, tgt in G_I.edges():

            result = missing_rule.apply(
                G_I,
                G_C,
                src,
                tgt,
            )

            if result.get("verdict") == MISSING:
                violations.append(result)

        # Check for architectural cycles.
        cycle_results = self.cycle_rule.apply(G_I, G_C)
        violations.extend(cycle_results)

        # Build summary.
        summary = {
            "total_violations": len(violations),
            "by_type": {},
            "severity_counts": {
                "low": 0,
                "medium": 0,
                "high": 0,
                "critical": 0,
            },
        }

        for violation in violations:

            violation_type = violation.get(
                "violation_type",
                "unknown",
            )

            summary["by_type"][violation_type] = (
                summary["by_type"].get(violation_type, 0) + 1
            )

            severity = violation.get("severity", "medium")

            if severity not in summary["severity_counts"]:
                severity = "medium"

            summary["severity_counts"][severity] += 1

        # Determine the overall verdict.
        has_uncertain_evidence = self._has_uncertain_evidence(
            intended_graph,
            current_graph,
        )

        # Definite violations take precedence over uncertainty.
        if violations:
            verdict = VIOLATION

        elif has_uncertain_evidence:
            verdict = UNCERTAIN

        else:
            verdict = CONFORMANT

        logger.info(
            "Conformance check complete: "
            "%s violations found; verdict=%s",
            len(violations),
            verdict,
        )

        return {
            "verdict": verdict,
            "violations": violations,
            "summary": summary,
        }
