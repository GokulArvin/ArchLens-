"""
Vocabulary and Taxonomy Definitions for ArchLens (Sprint 1 D1).

Defines:
1. Node Vocabulary (Components, Services, Databases, Controllers, Repositories, etc.)
2. Edge Vocabulary (depends_on, calls, inherits, implements, publishes_to, reads_from, writes_to, etc.)
3. Conformance Verdict Taxonomy (CONFORMANT, VIOLATION, MISSING, UNEXPECTED, UNCERTAIN)
4. Violation Categories (layer_violation, forbidden_dependency, missing_dependency, unexpected_dependency, cycle_violation, interface_violation, uncertain_dependency)
5. Architectural Rule Actions (ALLOW, FORBID, REQUIRE)
"""

from app.schemas.models import (
    ComponentType,
    RelationshipType,
    ViolationVerdict,
    ViolationType,
    RuleAction,
    RuleCategory,
)

# ─── Verdict Descriptions (Sprint 1 D1 / D3) ─────────────────────────────────

VERDICT_DESCRIPTIONS = {
    ViolationVerdict.CONFORMANT: "Expected edge exists and is explicitly permitted by architectural intent.",
    ViolationVerdict.VIOLATION: "A forbidden dependency exists in the implementation violating architectural constraints.",
    ViolationVerdict.MISSING: "A required architectural relationship defined in G_I is absent in G_C.",
    ViolationVerdict.UNEXPECTED: "Implementation contains a relationship not represented in G_I and not covered by an ALLOW rule.",
    ViolationVerdict.UNCERTAIN: "Evidence is insufficient, conflicting, or below confidence threshold.",
}

# ─── Standard Architectural Layer Hierarchy ──────────────────────────────────

LAYER_HIERARCHY = [
    ComponentType.FRONTEND,
    ComponentType.GATEWAY,
    ComponentType.CONTROLLER,
    ComponentType.SERVICE,
    ComponentType.REPOSITORY,
    ComponentType.DATABASE,
]

# Standard forbidden layer dependencies (skipping layers or reverse dependencies)
DEFAULT_FORBIDDEN_DEPENDENCIES = [
    (ComponentType.CONTROLLER.value, ComponentType.REPOSITORY.value),
    (ComponentType.CONTROLLER.value, ComponentType.DATABASE.value),
    (ComponentType.FRONTEND.value, ComponentType.DATABASE.value),
    (ComponentType.GATEWAY.value, ComponentType.REPOSITORY.value),
    (ComponentType.REPOSITORY.value, ComponentType.CONTROLLER.value),
    (ComponentType.DATABASE.value, ComponentType.SERVICE.value),
]

# Standard allowed layer dependencies
DEFAULT_ALLOWED_DEPENDENCIES = [
    (ComponentType.FRONTEND.value, ComponentType.GATEWAY.value),
    (ComponentType.GATEWAY.value, ComponentType.CONTROLLER.value),
    (ComponentType.CONTROLLER.value, ComponentType.SERVICE.value),
    (ComponentType.SERVICE.value, ComponentType.REPOSITORY.value),
    (ComponentType.REPOSITORY.value, ComponentType.DATABASE.value),
    (ComponentType.SERVICE.value, ComponentType.QUEUE.value),
    (ComponentType.SERVICE.value, ComponentType.CACHE.value),
]
