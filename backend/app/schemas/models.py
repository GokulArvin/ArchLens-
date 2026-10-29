"""
Pydantic schemas for ArchLens data models.
Shared across all modules for consistent JSON/graph schema.

Sprint 1 (P3 Deliverables):
- Versioned graph schema (ArchGraph, IntendedGraph G_I, CurrentGraph G_C)
- Node/Edge vocabulary specification
- ALLOW/FORBID/REQUIRE rule schema (ArchitectureRule, RuleSet)
- 5-verdict taxonomy (CONFORMANT, VIOLATION, MISSING, UNEXPECTED, UNCERTAIN)
"""

from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any, Literal
from enum import Enum
import uuid


# ─── Component / Node Vocabulary (Sprint 1 D1/D2) ────────────────────────────

class ComponentType(str, Enum):
    # Core types from Module C & architectural taxonomy
    COMPONENT = "component"
    SERVICE = "service"
    DATABASE = "database"
    QUEUE = "queue"
    GATEWAY = "gateway"
    FRONTEND = "frontend"
    CACHE = "cache"
    EXTERNAL = "external"
    EXTERNAL_SYSTEM = "external_system"
    MODULE = "module"
    INTERFACE = "interface"

    # Layered architecture roles (recovered from AST / static analysis)
    CONTROLLER = "controller"
    REPOSITORY = "repository"
    MODEL = "model"
    UTILITY = "utility"

    UNKNOWN = "unknown"


class BoundingBox(BaseModel):
    x1: float
    y1: float
    x2: float
    y2: float


class ArchComponent(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    name: str
    type: ComponentType = ComponentType.UNKNOWN
    bbox: Optional[BoundingBox] = None
    confidence: float = 1.0
    metadata: Dict[str, Any] = Field(default_factory=dict)


# ─── Relationship / Edge Vocabulary (Sprint 1 D1/D2) ─────────────────────────

class RelationshipType(str, Enum):
    DEPENDS_ON = "depends_on"
    CALLS = "calls"
    INHERITS = "inherits"
    IMPLEMENTS = "implements"
    USES = "uses"
    CONTAINS = "contains"
    PUBLISHES_TO = "publishes_to"
    READS_FROM = "reads_from"
    WRITES_TO = "writes_to"
    UNKNOWN = "unknown"


class ArchRelationship(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    source: str  # component id or component name
    target: str  # component id or component name
    type: RelationshipType = RelationshipType.DEPENDS_ON
    confidence: float = 1.0
    metadata: Dict[str, Any] = Field(default_factory=dict)


# ─── Architecture Graph Schemas (Sprint 1 D2) ────────────────────────────────

class ArchGraph(BaseModel):
    """Unified versioned graph model for both intended (G_I) and current (G_C) architectures."""
    schema_version: str = "1.0.0"
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    name: str
    graph_type: Literal["intended", "current"] = "intended"
    components: List[ArchComponent] = Field(default_factory=list)
    relationships: List[ArchRelationship] = Field(default_factory=list)
    source: Optional[str] = None  # e.g., diagram image path or repository directory
    metadata: Dict[str, Any] = Field(default_factory=dict)


class IntendedGraph(ArchGraph):
    """Intended architecture graph (G_I) extracted from diagrams."""
    graph_type: Literal["intended"] = "intended"


class CurrentGraph(ArchGraph):
    """Current architecture graph (G_C) extracted from source code."""
    graph_type: Literal["current"] = "current"


# ─── Rules Representation: ALLOW / FORBID / REQUIRE (Sprint 1 D3) ────────────

class RuleAction(str, Enum):
    ALLOW = "ALLOW"
    FORBID = "FORBID"
    REQUIRE = "REQUIRE"


class RuleCategory(str, Enum):
    LAYER_RULE = "layer_rule"
    DEPENDENCY_RULE = "dependency_rule"
    CYCLE_RULE = "cycle_rule"
    INTERFACE_RULE = "interface_rule"


class ArchitectureRule(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    name: str
    action: RuleAction = RuleAction.ALLOW  # ALLOW | FORBID | REQUIRE
    category: RuleCategory = RuleCategory.LAYER_RULE
    source: Optional[str] = None  # Name or type filter (e.g., 'controller', 'OrderController')
    target: Optional[str] = None  # Name or type filter (e.g., 'repository', 'OrderRepository')
    source_type: Optional[ComponentType] = None
    target_type: Optional[ComponentType] = None
    relation_type: Optional[RelationshipType] = None
    severity: Literal["low", "medium", "high", "critical"] = "medium"
    description: str = ""


class RuleSet(BaseModel):
    schema_version: str = "1.0.0"
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    name: str
    description: str = ""
    rules: List[ArchitectureRule] = Field(default_factory=list)
    confidence_threshold: float = 0.6  # below which verdicts are marked UNCERTAIN


# ─── Conformance / Verdict Taxonomy (Sprint 1 D1 / D3) ────────────────────────

class ViolationVerdict(str, Enum):
    CONFORMANT = "CONFORMANT"
    VIOLATION = "VIOLATION"
    MISSING = "MISSING"
    UNEXPECTED = "UNEXPECTED"
    UNCERTAIN = "UNCERTAIN"


class ViolationType(str, Enum):
    LAYER_VIOLATION = "layer_violation"
    FORBIDDEN_DEPENDENCY = "forbidden_dependency"
    MISSING_DEPENDENCY = "missing_dependency"
    UNEXPECTED_DEPENDENCY = "unexpected_dependency"
    CYCLE_VIOLATION = "cycle_violation"
    INTERFACE_VIOLATION = "interface_violation"
    UNCERTAIN_DEPENDENCY = "uncertain_dependency"


class ArchViolation(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    verdict: ViolationVerdict
    violation_type: Optional[ViolationType] = None
    source_component: str
    target_component: str
    expected: Optional[str] = None
    actual: Optional[str] = None
    severity: Literal["low", "medium", "high", "critical"] = "medium"
    confidence: float = 1.0
    description: str = ""
    rule_id: Optional[str] = None


# ─── Git Evidence ─────────────────────────────────────────────────────────────

class GitCommit(BaseModel):
    hash: str
    message: str
    author: str
    date: str
    diff: Optional[str] = None


class GitEvidence(BaseModel):
    violation_id: str
    file: str
    lines: Optional[str] = None
    dependency_path: List[str] = Field(default_factory=list)
    introducing_commit: Optional[GitCommit] = None
    related_commits: List[GitCommit] = Field(default_factory=list)


# ─── LLM RCA Output ───────────────────────────────────────────────────────────

class RCAOutput(BaseModel):
    violation_id: str
    violation_explanation: str
    root_cause: str
    evidence: List[str] = Field(default_factory=list)
    affected_components: List[str] = Field(default_factory=list)
    recommendation: str
    confidence: float = Field(ge=0.0, le=1.0)


# ─── Conformance Report ───────────────────────────────────────────────────────

class ConformanceReport(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    repository: str
    diagram_path: Optional[str] = None
    intended_graph: Optional[ArchGraph] = None
    current_graph: Optional[ArchGraph] = None
    ruleset: Optional[RuleSet] = None
    violations: List[ArchViolation] = Field(default_factory=list)
    git_evidence: List[GitEvidence] = Field(default_factory=list)
    rca_outputs: List[RCAOutput] = Field(default_factory=list)
    summary: Dict[str, Any] = Field(default_factory=dict)


# ─── API Request / Response Models ───────────────────────────────────────────

class AnalyzeDiagramRequest(BaseModel):
    diagram_path: str
    use_vlm: bool = True
    use_clip: bool = True


class AnalyzeRepositoryRequest(BaseModel):
    repo_path: str
    language: Literal["python", "java", "mixed"] = "python"


class CheckConformanceRequest(BaseModel):
    intended_graph_id: Optional[str] = None
    current_graph_id: Optional[str] = None
    intended_graph: Optional[ArchGraph] = None
    current_graph: Optional[ArchGraph] = None
    ruleset: Optional[RuleSet] = None


class AnalyzeViolationRequest(BaseModel):
    violation_id: str
    include_git_evidence: bool = True
