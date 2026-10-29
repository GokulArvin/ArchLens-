"""
Module E: Conformance Engine
Fully deterministic graph-based conformance checking.

Given G_I (intended) and G_C (current), applies architectural rules
(ALLOW, FORBID, REQUIRE) and produces verdicts:
CONFORMANT | VIOLATION | MISSING | UNEXPECTED | UNCERTAIN
"""

import networkx as nx
from typing import List, Dict, Any, Optional, Set, Tuple, Union
import logging

from app.schemas.models import (
    ViolationVerdict,
    ViolationType,
    RuleAction,
    RuleCategory,
    ArchitectureRule,
    RuleSet,
)
from app.schemas.vocabulary import DEFAULT_FORBIDDEN_DEPENDENCIES, DEFAULT_ALLOWED_DEPENDENCIES

logger = logging.getLogger(__name__)

# ─── Verdict string constants ─────────────────────────────────────────────────
CONFORMANT = ViolationVerdict.CONFORMANT.value
VIOLATION = ViolationVerdict.VIOLATION.value
MISSING = ViolationVerdict.MISSING.value
UNEXPECTED = ViolationVerdict.UNEXPECTED.value
UNCERTAIN = ViolationVerdict.UNCERTAIN.value


def _normalize_str(val: Any) -> str:
    """Safely convert value or Enum to lowercase string."""
    if val is None:
        return ""
    if hasattr(val, "value"):
        return str(val.value).lower().strip()
    return str(val).lower().strip()


class LayeredArchitectureRule:
    """Enforce layered architecture constraints."""

    def __init__(self, forbidden_patterns: Optional[List[Tuple[str, str]]] = None):
        self.FORBIDDEN_PATTERNS = [
            (_normalize_str(s), _normalize_str(t))
            for s, t in (forbidden_patterns or DEFAULT_FORBIDDEN_DEPENDENCIES)
        ]

    def check(self, source_type: str, target_type: str) -> str:
        """Return verdict for a dependency from source_type → target_type."""
        pair = (_normalize_str(source_type), _normalize_str(target_type))
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
        edge_data: Dict[str, Any],
    ) -> Dict[str, Any]:
        raise NotImplementedError


class ForbiddenDependencyRule(ConformanceRule):
    """Detect dependencies present in G_C that match forbidden rules."""

    name = "forbidden_dependency"

    def __init__(self, forbidden_pairs: Optional[List[Tuple[str, str]]] = None):
        self.forbidden_pairs = [
            (_normalize_str(s), _normalize_str(t))
            for s, t in (forbidden_pairs or DEFAULT_FORBIDDEN_DEPENDENCIES)
        ]

    def apply(self, G_I, G_C, source, target, edge_data):
        src_type = _normalize_str(G_C.nodes[source].get("type", ""))
        tgt_type = _normalize_str(G_C.nodes[target].get("type", ""))
        src_name = _normalize_str(G_C.nodes[source].get("name", source))
        tgt_name = _normalize_str(G_C.nodes[target].get("name", target))

        # Check by type or by exact name
        if (src_type, tgt_type) in self.forbidden_pairs or (src_name, tgt_name) in self.forbidden_pairs:
            return {
                "verdict": VIOLATION,
                "violation_type": ViolationType.FORBIDDEN_DEPENDENCY.value,
                "source": source,
                "target": target,
                "severity": "high",
                "confidence": edge_data.get("confidence", 1.0),
                "description": (
                    f"Forbidden dependency: {src_type or src_name} → {tgt_type or tgt_name}. "
                    f"Architectural constraint violation detected."
                ),
            }
        return {"verdict": CONFORMANT, "source": source, "target": target}


class MissingDependencyRule(ConformanceRule):
    """Detect dependencies present in G_I but missing in G_C."""

    name = "missing_dependency"

    def apply(self, G_I, G_C, source, target, edge_data):
        if G_I.has_edge(source, target) and not G_C.has_edge(source, target):
            return {
                "verdict": MISSING,
                "violation_type": ViolationType.MISSING_DEPENDENCY.value,
                "source": source,
                "target": target,
                "severity": "medium",
                "confidence": 1.0,
                "description": (
                    f"Expected dependency {source} → {target} is missing in the implementation."
                ),
            }
        return {"verdict": CONFORMANT, "source": source, "target": target}


class UnexpectedDependencyRule(ConformanceRule):
    """Detect dependencies in G_C not present in G_I and not covered by an ALLOW rule."""

    name = "unexpected_dependency"

    def __init__(self, allowed_pairs: Optional[List[Tuple[str, str]]] = None):
        self.allowed_pairs = [
            (_normalize_str(s), _normalize_str(t))
            for s, t in (allowed_pairs or DEFAULT_ALLOWED_DEPENDENCIES)
        ]

    def apply(self, G_I, G_C, source, target, edge_data):
        if G_C.has_edge(source, target) and not G_I.has_edge(source, target):
            src_type = _normalize_str(G_C.nodes[source].get("type", ""))
            tgt_type = _normalize_str(G_C.nodes[target].get("type", ""))
            src_name = _normalize_str(G_C.nodes[source].get("name", source))
            tgt_name = _normalize_str(G_C.nodes[target].get("name", target))

            # If it matches an explicit ALLOW pair, it's allowed
            if (src_type, tgt_type) in self.allowed_pairs or (src_name, tgt_name) in self.allowed_pairs:
                return {"verdict": CONFORMANT, "source": source, "target": target}

            return {
                "verdict": UNEXPECTED,
                "violation_type": ViolationType.UNEXPECTED_DEPENDENCY.value,
                "source": source,
                "target": target,
                "severity": "medium",
                "confidence": edge_data.get("confidence", 1.0),
                "description": (
                    f"Unexpected dependency {source} → {target} found in implementation "
                    f"but not in intended architecture."
                ),
            }
        return {"verdict": CONFORMANT, "source": source, "target": target}


class CycleDetectionRule(ConformanceRule):
    """Detect architectural cycles in G_C."""

    name = "cycle_detection"

    def apply(self, G_I, G_C, source=None, target=None, edge_data=None):
        cycles = list(nx.simple_cycles(G_C))
        results = []
        for cycle in cycles:
            results.append({
                "verdict": VIOLATION,
                "violation_type": ViolationType.CYCLE_VIOLATION.value,
                "source": cycle[0],
                "target": cycle[-1],
                "severity": "high",
                "confidence": 1.0,
                "description": f"Architectural cycle detected: {' → '.join(cycle)}",
                "cycle": cycle,
            })
        return results


class ConformanceEngine:
    """
    Main deterministic conformance engine.
    Compares G_I and G_C with ALLOW/FORBID/REQUIRE rules and produces
    structured violation reports across the 5-verdict taxonomy.
    """

    def __init__(
        self,
        ruleset: Optional[Union[RuleSet, Dict[str, Any], List[ArchitectureRule]]] = None,
        confidence_threshold: float = 0.6,
    ):
        self.confidence_threshold = confidence_threshold
        self.ruleset = self._parse_ruleset(ruleset)
        self._init_rules()

    def _parse_ruleset(
        self, ruleset: Optional[Union[RuleSet, Dict[str, Any], List[ArchitectureRule]]]
    ) -> RuleSet:
        if isinstance(ruleset, RuleSet):
            if ruleset.confidence_threshold:
                self.confidence_threshold = ruleset.confidence_threshold
            return ruleset
        elif isinstance(ruleset, dict):
            rs = RuleSet(**ruleset)
            if rs.confidence_threshold:
                self.confidence_threshold = rs.confidence_threshold
            return rs
        elif isinstance(ruleset, list):
            return RuleSet(name="CustomRules", rules=ruleset, confidence_threshold=self.confidence_threshold)
        else:
            rules = []
            for src, tgt in DEFAULT_FORBIDDEN_DEPENDENCIES:
                rules.append(
                    ArchitectureRule(
                        name=f"Forbid {src}->{tgt}",
                        action=RuleAction.FORBID,
                        category=RuleCategory.LAYER_RULE,
                        source=src,
                        target=tgt,
                        severity="high",
                        description=f"Forbidden cross-layer dependency: {src} -> {tgt}",
                    )
                )
            for src, tgt in DEFAULT_ALLOWED_DEPENDENCIES:
                rules.append(
                    ArchitectureRule(
                        name=f"Allow {src}->{tgt}",
                        action=RuleAction.ALLOW,
                        category=RuleCategory.LAYER_RULE,
                        source=src,
                        target=tgt,
                        severity="low",
                        description=f"Allowed layer dependency: {src} -> {tgt}",
                    )
                )
            return RuleSet(
                name="DefaultLayeredArchitectureRules",
                description="Default 3-tier and microservice layered rules",
                rules=rules,
                confidence_threshold=self.confidence_threshold,
            )

    def _init_rules(self):
        forbidden_pairs = []
        allowed_pairs = []

        for rule in self.ruleset.rules:
            src = _normalize_str(rule.source or (rule.source_type.value if rule.source_type else ""))
            tgt = _normalize_str(rule.target or (rule.target_type.value if rule.target_type else ""))
            if not src or not tgt:
                continue

            if rule.action == RuleAction.FORBID:
                forbidden_pairs.append((src, tgt))
            elif rule.action == RuleAction.ALLOW:
                allowed_pairs.append((src, tgt))

        self.forbidden_rule = ForbiddenDependencyRule(forbidden_pairs)
        self.missing_rule = MissingDependencyRule()
        self.unexpected_rule = UnexpectedDependencyRule(allowed_pairs)
        self.cycle_rule = CycleDetectionRule()

    def build_graph(self, graph_data: Union[Dict[str, Any], Any]) -> nx.DiGraph:
        """Convert ArchGraph dict or model → NetworkX DiGraph."""
        if hasattr(graph_data, "model_dump"):
            graph_data = graph_data.model_dump(mode="json")
        elif hasattr(graph_data, "dict"):
            graph_data = graph_data.dict()

        G = nx.DiGraph()
        for comp in graph_data.get("components", []):
            node_id = comp.get("id") or comp.get("name")
            # Store normalized attributes for robust matching
            comp_copy = dict(comp)
            comp_copy["type"] = _normalize_str(comp.get("type", ""))
            comp_copy["name"] = _normalize_str(comp.get("name", node_id))
            G.add_node(node_id, **comp_copy)

        for rel in graph_data.get("relationships", []):
            src = rel.get("source")
            tgt = rel.get("target")
            if src and tgt:
                G.add_edge(src, tgt, **rel)
        return G

    def check_conformance(
        self,
        intended_graph: Union[Dict[str, Any], Any],
        current_graph: Union[Dict[str, Any], Any],
        custom_ruleset: Optional[Union[RuleSet, Dict[str, Any]]] = None,
    ) -> Dict[str, Any]:
        """
        Main entry point: compare G_I vs G_C and evaluate against rules.
        Returns verdicts across the 5-verdict taxonomy:
        CONFORMANT | VIOLATION | MISSING | UNEXPECTED | UNCERTAIN
        """
        if custom_ruleset:
            self.ruleset = self._parse_ruleset(custom_ruleset)
            self._init_rules()

        G_I = self.build_graph(intended_graph)
        G_C = self.build_graph(current_graph)

        violations: List[Dict[str, Any]] = []
        conformant_count = 0

        # 1. Check REQUIRE rules from RuleSet
        for rule in self.ruleset.rules:
            if rule.action == RuleAction.REQUIRE:
                req_src = _normalize_str(rule.source or (rule.source_type.value if rule.source_type else ""))
                req_tgt = _normalize_str(rule.target or (rule.target_type.value if rule.target_type else ""))

                # Find if any matching edge exists in G_C
                found = False
                for src, tgt in G_C.edges():
                    s_type = _normalize_str(G_C.nodes[src].get("type", ""))
                    t_type = _normalize_str(G_C.nodes[tgt].get("type", ""))
                    s_name = _normalize_str(G_C.nodes[src].get("name", src))
                    t_name = _normalize_str(G_C.nodes[tgt].get("name", tgt))

                    if (s_type == req_src or s_name == req_src) and (t_type == req_tgt or t_name == req_tgt):
                        found = True
                        break

                if not found:
                    violations.append({
                        "verdict": MISSING,
                        "violation_type": ViolationType.MISSING_DEPENDENCY.value,
                        "source": rule.source or (rule.source_type.value if rule.source_type else "unknown"),
                        "target": rule.target or (rule.target_type.value if rule.target_type else "unknown"),
                        "severity": rule.severity,
                        "confidence": 1.0,
                        "rule_id": rule.id,
                        "description": f"Required architectural relationship {rule.source} → {rule.target} is absent.",
                    })

        # 2. Check edges in G_C
        for src, tgt, edge_data in G_C.edges(data=True):
            confidence = edge_data.get("confidence", 1.0)

            # Check for UNCERTAIN verdict (confidence below threshold)
            if confidence < self.confidence_threshold:
                violations.append({
                    "verdict": UNCERTAIN,
                    "violation_type": ViolationType.UNCERTAIN_DEPENDENCY.value,
                    "source": src,
                    "target": tgt,
                    "severity": "low",
                    "confidence": confidence,
                    "description": (
                        f"Relationship {src} → {tgt} has low extraction confidence "
                        f"({confidence:.2f} < threshold {self.confidence_threshold:.2f})."
                    ),
                })
                continue

            # Check for FORBIDDEN dependencies (VIOLATION)
            forbidden_res = self.forbidden_rule.apply(G_I, G_C, src, tgt, edge_data)
            if forbidden_res.get("verdict") == VIOLATION:
                violations.append(forbidden_res)
                continue

            # Check for UNEXPECTED dependencies
            unexpected_res = self.unexpected_rule.apply(G_I, G_C, src, tgt, edge_data)
            if unexpected_res.get("verdict") == UNEXPECTED:
                violations.append(unexpected_res)
                continue

            # If edge exists in G_I or is explicitly allowed
            if G_I.has_edge(src, tgt) or unexpected_res.get("verdict") == CONFORMANT:
                conformant_count += 1

        # 3. Check for MISSING dependencies (edges in G_I absent in G_C)
        for src, tgt, edge_data in G_I.edges(data=True):
            missing_res = self.missing_rule.apply(G_I, G_C, src, tgt, edge_data)
            if missing_res.get("verdict") == MISSING:
                already_reported = any(
                    v["verdict"] == MISSING and v["source"] == src and v["target"] == tgt
                    for v in violations
                )
                if not already_reported:
                    violations.append(missing_res)

        # 4. Check for architectural cycles in G_C
        cycle_results = self.cycle_rule.apply(G_I, G_C)
        violations.extend(cycle_results)

        # 5. Compute summary across 5-verdict taxonomy
        summary = {
            "total_violations": len(violations),
            "verdicts": {
                CONFORMANT: conformant_count,
                VIOLATION: sum(1 for v in violations if v.get("verdict") == VIOLATION),
                MISSING: sum(1 for v in violations if v.get("verdict") == MISSING),
                UNEXPECTED: sum(1 for v in violations if v.get("verdict") == UNEXPECTED),
                UNCERTAIN: sum(1 for v in violations if v.get("verdict") == UNCERTAIN),
            },
            "by_type": {},
            "severity_counts": {"low": 0, "medium": 0, "high": 0, "critical": 0},
        }

        for v in violations:
            vtype = v.get("violation_type", "unknown")
            summary["by_type"][vtype] = summary["by_type"].get(vtype, 0) + 1
            severity = v.get("severity", "medium")
            if severity in summary["severity_counts"]:
                summary["severity_counts"][severity] += 1

        # Overall verdict determination
        if summary["verdicts"][VIOLATION] > 0:
            overall_verdict = VIOLATION
        elif summary["verdicts"][MISSING] > 0:
            overall_verdict = MISSING
        elif summary["verdicts"][UNCERTAIN] > 0:
            overall_verdict = UNCERTAIN
        elif summary["verdicts"][UNEXPECTED] > 0:
            overall_verdict = UNEXPECTED
        else:
            overall_verdict = CONFORMANT

        logger.info(
            f"Conformance check complete. Overall: {overall_verdict}, "
            f"Violations: {len(violations)}, Conformant edges: {conformant_count}"
        )

        return {
            "verdict": overall_verdict,
            "violations": violations,
            "summary": summary,
            "ruleset": self.ruleset.model_dump(mode="json") if hasattr(self.ruleset, "model_dump") else None,
        }
