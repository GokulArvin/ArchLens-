"""Versioned JSON contracts for every P2 (LLM/VLM) output.

Sprint 1 D2: structured outputs for component label, relation candidate,
explanation and recommendation. Every model output in ArchLens is parsed into
one of these models; anything that fails validation is repaired, retried or
abstained on (see gateway/gateway.py).

The vocabularies mirror the Implementation Design:
  * Module C node types / edge types
  * Section 7.1 verdict taxonomy
  * Section 9.2 forced structured output for RCA
"""
from __future__ import annotations

from typing import Annotated, Literal, Optional

from pydantic import BaseModel, ConfigDict, Field, field_validator

SCHEMA_VERSION = "p2-schemas/1.0.0"

COMPONENT_TYPES = (
    "service", "database", "queue", "external_system", "user", "gateway",
    "frontend", "cache", "storage", "module", "interface", "component", "unknown",
)
RELATION_TYPES = (
    "depends_on", "calls", "contains", "implements", "publishes_to",
    "reads_from", "writes_to",
)
VERDICTS = ("CONFORMANT", "VIOLATION", "MISSING", "UNEXPECTED", "UNCERTAIN")
VIOLATION_TYPES = (
    "forbidden_dependency",   # V1
    "layer_violation",        # V2
    "unexpected_coupling",    # V3
    "boundary_violation",     # V4
    "circular_dependency",    # V5
    "missing_dependency",     # V6
)

ComponentType = Literal[COMPONENT_TYPES]  # type: ignore[valid-type]
RelationType = Literal[RELATION_TYPES]    # type: ignore[valid-type]


class _Strict(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)


Confidence = Annotated[float, Field(ge=0.0, le=1.0)]


# --------------------------------------------------------------------------
# Diagram semantics (Sprint 4–5)
# --------------------------------------------------------------------------
class ComponentLabel(_Strict):
    id: str
    name: str
    type: ComponentType
    confidence: Confidence
    evidence: list[str] = Field(default_factory=list,
                                description="e.g. 'ocr:Order Service', 'visual:cylinder'")
    bbox: Optional[list[float]] = None
    abstain: bool = False

    @field_validator("bbox")
    @classmethod
    def _bbox(cls, v):
        if v is None:
            return v
        if len(v) != 4 or v[2] <= v[0] or v[3] <= v[1]:
            raise ValueError("bbox must be [x1, y1, x2, y2] with x2>x1, y2>y1")
        return v


class RelationCandidate(_Strict):
    source: str
    target: str
    type: RelationType = "depends_on"
    confidence: Confidence
    evidence: list[str] = Field(default_factory=list,
                                description="e.g. 'arrowhead near c2', 'geometry:edge#3'")
    status: Literal["candidate", "uncertain", "rejected"] = "candidate"


class DiagramExtraction(_Strict):
    components: list[ComponentLabel]
    relationships: list[RelationCandidate] = Field(default_factory=list)
    notes: str = ""


# --------------------------------------------------------------------------
# Dependency role (Design §6.3: static analysis gives the edge, LLM the role)
# --------------------------------------------------------------------------
class DependencyRole(_Strict):
    source_role: str
    target_role: str
    architectural_meaning: str
    confidence: Confidence


# --------------------------------------------------------------------------
# Semantic alignment (Sprint 6)
# --------------------------------------------------------------------------
class AlignmentLLMAnswer(_Strict):
    diagram_node_id: str
    code_entity_id: Optional[str]
    confidence: Confidence
    evidence: list[str] = Field(default_factory=list)
    reason: str = ""


class AlignmentSuggestion(_Strict):
    diagram_node_id: str
    code_entity_id: Optional[str]
    method: Literal["exact", "normalized", "alias", "token", "llm", "none"]
    confidence: Confidence
    evidence: list[str] = Field(default_factory=list)
    verdict: Literal["MATCHED", "UNCERTAIN", "NO_MATCH"]


# --------------------------------------------------------------------------
# Evidence package (produced by P3/P4, consumed by P2) — Design §8.1
# --------------------------------------------------------------------------
class Commit(BaseModel):
    hash: str
    message: str = ""
    author: str = ""
    date: str = ""
    files: list[str] = Field(default_factory=list)
    diff: str = ""


class EvidencePackage(BaseModel):
    """Loose on purpose (extra allowed): P4 owns the contract, we read what we need."""
    model_config = ConfigDict(extra="allow")

    violation_id: str = "v0"
    violation: dict                      # {type, source, target, verdict?}
    architecture_rule: dict = Field(default_factory=dict)  # {allowed, forbidden, required}
    code: dict = Field(default_factory=dict)               # {file, lines, snippet}
    dependency_path: list[str] = Field(default_factory=list)
    commit: Optional[Commit] = None                        # most likely introducing commit
    candidate_commits: list[Commit] = Field(default_factory=list)
    diff: str = ""
    intended_edges: list[list[str]] = Field(default_factory=list)
    current_edges: list[list[str]] = Field(default_factory=list)
    layer_of: dict[str, str] = Field(default_factory=dict)  # component -> layer
    affected_components: list[dict] = Field(default_factory=list)  # from P3 impact fn


# --------------------------------------------------------------------------
# RCA (Sprint 7) — Design §9.2 plus evidence IDs
# --------------------------------------------------------------------------
class EvidenceCitation(_Strict):
    evidence_id: str
    claim: str


class RCAOutput(_Strict):
    violation_explanation: str
    root_cause: str
    evidence: list[EvidenceCitation]
    affected_components: list[str]
    recommendation: str
    introducing_commit: Optional[str] = None
    candidate_commit_ranking: list[str] = Field(default_factory=list)
    root_cause_status: Literal["SUPPORTED", "UNCERTAIN"] = "SUPPORTED"
    confidence: Confidence


# --------------------------------------------------------------------------
# Impact + recommendation (Sprint 8)
# --------------------------------------------------------------------------
class ImpactItem(_Strict):
    component: str
    impact: str
    evidence_ids: list[str]


class Recommendation(_Strict):
    summary: str
    steps: list[str]
    remove_edges: list[list[str]] = Field(default_factory=list)
    add_edges: list[list[str]] = Field(default_factory=list)
    rationale: str
    evidence_ids: list[str]

    @field_validator("remove_edges", "add_edges")
    @classmethod
    def _pairs(cls, v):
        for e in v:
            if len(e) != 2:
                raise ValueError("edges must be [source, target] pairs")
        return v


class ImpactRecommendation(_Strict):
    impacts: list[ImpactItem]
    recommendation: Recommendation
    confidence: Confidence
    abstain: bool = False
    abstain_reason: str = ""
