
"""Conservative alignment of diagram components with repository modules.

Exact component/module matches take priority over fuzzy alias matches.
Ambiguous and unmatched components remain unresolved.

Unverified or low-confidence diagram relationships are excluded from
the deterministic conformance graph and recorded as uncertainty.
"""

import re
from typing import Any, Dict, Optional


DEFAULT_CONFIDENCE_THRESHOLD = 0.5
DEFAULT_MATCH_THRESHOLD = 0.80


def _normalize(value: Any) -> str:
    """Normalize a label for conservative name comparison."""
    return re.sub(r"[^a-z0-9]", "", str(value).lower())


def _normalize_module_path(value: Any) -> str:
    """Normalize a Python module/file path without losing its full identity."""
    value = str(value).strip().replace("\\", "/")

    if value.endswith(".py"):
        value = value[:-3]

    value = value.strip("/")
    value = value.replace("/", ".")

    if value.endswith(".__init__"):
        value = value[:-9]
    elif value == "__init__":
        value = ""

    return _normalize(value)


def _tokens(value: Any) -> set[str]:
    """Extract normalized name tokens, including simple plurals."""
    raw = re.findall(r"[a-z0-9]+", str(value).lower())
    result = set()

    for token in raw:
        if len(token) > 3 and token.endswith("s"):
            token = token[:-1]
        result.add(token)

    return result


def _primary_aliases(component: Dict[str, Any]) -> set[str]:
    """Return aliases suitable for exact component/module matching."""
    aliases = set()
    metadata = component.get("metadata") or {}

    for key in ("id", "name"):
        value = component.get(key)
        if value:
            aliases.add(str(value))

    if isinstance(metadata, dict):
        for key in ("file", "module", "qualified_name"):
            value = metadata.get(key)
            if value:
                aliases.add(str(value))

    return {item for item in aliases if item.strip()}


def _component_aliases(component: Dict[str, Any]) -> set[str]:
    """Collect broader aliases for fuzzy matching."""
    aliases = _primary_aliases(component)
    metadata = component.get("metadata") or {}

    if isinstance(metadata, dict):
        for item in metadata.get("ocr_labels", []):
            if isinstance(item, dict) and item.get("text"):
                aliases.add(str(item["text"]))

        for key in ("classes", "functions"):
            for item in metadata.get(key, []):
                if isinstance(item, dict) and item.get("name"):
                    aliases.add(str(item["name"]))
                elif isinstance(item, str):
                    aliases.add(item)

    expanded = set(aliases)

    for alias in aliases:
        parts = re.split(r"[./\\]+", alias)
        if parts and parts[-1]:
            expanded.add(parts[-1])

    return {item for item in expanded if item.strip()}


def _exact_match(
    diagram_component: Dict[str, Any],
    repository_component: Dict[str, Any],
) -> bool:
    """Check full normalized identity, not partial package overlap."""
    diagram_aliases = {
        _normalize_module_path(value)
        for value in _primary_aliases(diagram_component)
    }

    repository_aliases = {
        _normalize_module_path(value)
        for value in _primary_aliases(repository_component)
    }

    diagram_aliases.discard("")
    repository_aliases.discard("")

    return bool(diagram_aliases & repository_aliases)


def _match_score(
    diagram_component: Dict[str, Any],
    repository_component: Dict[str, Any],
) -> float:
    """Return the strongest fuzzy alias similarity between components."""
    diagram_aliases = _component_aliases(diagram_component)
    repository_aliases = _component_aliases(repository_component)

    best = 0.0

    for left in diagram_aliases:
        left_normalized = _normalize(left)
        left_tokens = _tokens(left)

        if not left_normalized or not left_tokens:
            continue

        for right in repository_aliases:
            right_normalized = _normalize(right)
            right_tokens = _tokens(right)

            if not right_normalized or not right_tokens:
                continue

            if left_normalized == right_normalized:
                best = max(best, 1.0)
                continue

            # Jaccard similarity avoids treating a generic parent package
            # such as "app" as a perfect match for every app.* module.
            union = left_tokens | right_tokens
            overlap = left_tokens & right_tokens

            if union:
                score = len(overlap) / len(union)
                best = max(best, score)

    return best


def align_architecture_graphs(
    intended_graph: Dict[str, Any],
    current_graph: Dict[str, Any],
    manual_mappings: Optional[Dict[str, str]] = None,
    match_threshold: float = DEFAULT_MATCH_THRESHOLD,
    relationship_threshold: float = DEFAULT_CONFIDENCE_THRESHOLD,
) -> Dict[str, Any]:
    """Align intended diagram nodes to current repository modules.

    Args:
        intended_graph: CV-extracted intended architecture graph.
        current_graph: AST-extracted repository architecture graph.
        manual_mappings: Optional diagram component ID to repository ID map.
        match_threshold: Minimum automatic fuzzy alias similarity.
        relationship_threshold: Minimum relationship confidence.

    Returns:
        Aligned graph, mapping decisions, and unresolved elements.
    """
    if not isinstance(intended_graph, dict) or not isinstance(current_graph, dict):
        raise ValueError("Both architecture graphs must be dictionaries.")

    intended_components = intended_graph.get("components", [])
    current_components = current_graph.get("components", [])
    intended_relationships = intended_graph.get("relationships", [])

    if not isinstance(intended_components, list):
        raise ValueError("Intended graph components must be a list.")

    if not isinstance(current_components, list):
        raise ValueError("Current graph components must be a list.")

    if not isinstance(intended_relationships, list):
        raise ValueError("Intended graph relationships must be a list.")

    manual_mappings = manual_mappings or {}

    if not isinstance(manual_mappings, dict):
        raise ValueError("Manual mappings must be a dictionary.")

    current_by_id = {
        component.get("id"): component
        for component in current_components
        if isinstance(component, dict) and component.get("id")
    }

    intended_by_id = {
        component.get("id"): component
        for component in intended_components
        if isinstance(component, dict) and component.get("id")
    }

    if len(intended_by_id) != len(intended_components):
        raise ValueError("Every intended component must have a unique ID.")

    if len(current_by_id) != len(current_components):
        raise ValueError("Every current component must have a unique ID.")

    mapping = {}
    mapping_details = []
    unresolved_components = []
    used_targets = set()

    # Validate and apply explicit mappings first.
    for source_id, target_id in manual_mappings.items():
        if source_id not in intended_by_id:
            raise ValueError(
                f"Manual mapping references unknown diagram component: {source_id}"
            )

        if target_id not in current_by_id:
            raise ValueError(
                f"Manual mapping references unknown repository component: {target_id}"
            )

        if target_id in used_targets:
            raise ValueError(
                f"Repository component is mapped more than once: {target_id}"
            )

        mapping[source_id] = target_id
        used_targets.add(target_id)

        mapping_details.append({
            "diagram_component_id": source_id,
            "repository_component_id": target_id,
            "method": "manual",
            "confidence": 1.0,
            "status": "matched",
        })

    # Automatic matching: exact identity first, fuzzy matching second.
    for component in intended_components:
        source_id = component["id"]

        if source_id in mapping:
            continue

        available_targets = {
            target_id: target_component
            for target_id, target_component in current_by_id.items()
            if target_id not in used_targets
        }

        # Stage 1: exact full ID/module/name match.
        exact_candidates = [
            target_id
            for target_id, target_component in available_targets.items()
            if _exact_match(component, target_component)
        ]

        if len(exact_candidates) == 1:
            best_target = exact_candidates[0]

            mapping[source_id] = best_target
            used_targets.add(best_target)

            mapping_details.append({
                "diagram_component_id": source_id,
                "repository_component_id": best_target,
                "method": "exact_module_match",
                "confidence": 1.0,
                "status": "matched",
            })
            continue

        if len(exact_candidates) > 1:
            unresolved_components.append({
                "diagram_component_id": source_id,
                "diagram_component_name": component.get("name"),
                "reason": "ambiguous_match",
                "candidates": [
                    {"component_id": target_id, "confidence": 1.0}
                    for target_id in exact_candidates
                ],
            })
            continue

        # Stage 2: conservative fuzzy alias matching.
        candidates = []

        for target_id, target_component in available_targets.items():
            score = _match_score(component, target_component)

            if score >= match_threshold:
                candidates.append((score, target_id))

        candidates.sort(key=lambda item: (-item[0], item[1]))

        if not candidates:
            unresolved_components.append({
                "diagram_component_id": source_id,
                "diagram_component_name": component.get("name"),
                "reason": "no_confident_match",
                "candidates": [],
            })
            continue

        best_score, best_target = candidates[0]

        tied = (
            len(candidates) > 1
            and abs(candidates[0][0] - candidates[1][0]) < 0.05
        )

        if tied:
            unresolved_components.append({
                "diagram_component_id": source_id,
                "diagram_component_name": component.get("name"),
                "reason": "ambiguous_match",
                "candidates": [
                    {"component_id": target_id, "confidence": score}
                    for score, target_id in candidates
                ],
            })
            continue

        mapping[source_id] = best_target
        used_targets.add(best_target)

        mapping_details.append({
            "diagram_component_id": source_id,
            "repository_component_id": best_target,
            "method": "automatic_alias_match",
            "confidence": best_score,
            "status": "matched",
        })

    # Only mapped diagram components enter the aligned graph.
    aligned_components = []

    for component in intended_components:
        source_id = component["id"]
        target_id = mapping.get(source_id)

        if target_id is None:
            continue

        aligned_component = dict(component)
        aligned_component["id"] = target_id

        metadata = dict(aligned_component.get("metadata") or {})
        metadata["alignment"] = {
            "original_diagram_component_id": source_id,
            "repository_component_id": target_id,
        }
        aligned_component["metadata"] = metadata

        aligned_components.append(aligned_component)

    # Exclude uncertain relationships from deterministic comparison.
    aligned_relationships = []
    unresolved_relationships = []

    for relationship in intended_relationships:
        if not isinstance(relationship, dict):
            raise ValueError("Every intended relationship must be an object.")

        source_id = relationship.get("source")
        target_id = relationship.get("target")

        try:
            confidence = float(relationship.get("confidence", 1.0))
        except (TypeError, ValueError):
            raise ValueError("Relationship confidence must be numeric.")

        metadata = relationship.get("metadata") or {}

        if not 0.0 <= confidence <= 1.0:
            raise ValueError("Relationship confidence must be between 0 and 1.")

        if not isinstance(metadata, dict):
            raise ValueError("Relationship metadata must be an object.")

        reason = None

        if source_id not in mapping or target_id not in mapping:
            reason = "unmapped_endpoint"
        elif confidence < relationship_threshold:
            reason = "low_confidence"
        elif metadata.get("direction_verified") is False:
            reason = "direction_unverified"

        if reason:
            unresolved_relationships.append({
                "relationship_id": relationship.get("id"),
                "source": source_id,
                "target": target_id,
                "confidence": confidence,
                "reason": reason,
                "metadata": metadata,
            })
            continue

        aligned = dict(relationship)
        aligned["source"] = mapping[source_id]
        aligned["target"] = mapping[target_id]

        relationship_metadata = dict(metadata)
        relationship_metadata["alignment"] = {
            "original_source": source_id,
            "original_target": target_id,
        }
        aligned["metadata"] = relationship_metadata

        aligned_relationships.append(aligned)

    aligned_graph = dict(intended_graph)
    graph_metadata = dict(intended_graph.get("metadata") or {})

    graph_metadata["alignment"] = {
        "mapping": mapping_details,
        "unresolved_component_count": len(unresolved_components),
        "unresolved_relationship_count": len(unresolved_relationships),
        "has_uncertainty": bool(
            unresolved_components or unresolved_relationships
        ),
    }

    aligned_graph.update({
        "graph_type": "intended",
        "components": aligned_components,
        "relationships": aligned_relationships,
        "metadata": graph_metadata,
    })

    return {
        "aligned_intended_graph": aligned_graph,
        "mapping": mapping,
        "mapping_details": mapping_details,
        "unresolved_components": unresolved_components,
        "unresolved_relationships": unresolved_relationships,
        "summary": {
            "intended_components": len(intended_components),
            "matched_components": len(mapping),
            "unresolved_components": len(unresolved_components),
            "intended_relationships": len(intended_relationships),
            "aligned_relationships": len(aligned_relationships),
            "unresolved_relationships": len(unresolved_relationships),
        },
    }
