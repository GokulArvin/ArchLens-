"""
Pydantic schemas for ArchLens data models.
Shared across all modules for consistent JSON/graph schema.
"""

from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any, Literal
from enum import Enum
import uuid


# ─── Component / Node ────────────────────────────────────────────────────────

class ComponentType(str, Enum):
    SERVICE = "service"
    DATABASE = "database"
    QUEUE = "queue"
    GATEWAY = "gateway"
    FRONTEND = "frontend"
    CACHE = "cache"
    EXTERNAL = "external"
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


# ─── Relationship / Edge ─────────────────────────────────────────────────────

class RelationshipType(str, Enum):
    DEPENDS_ON = "depends_on"
    CALLS = "calls"
    INHERITS = "inherits"
    IMPLEMENTS = "implements"
    USES = "uses"
    CONTAINS = "contains"
    UNKNOWN = "unknown"


class ArchRelationship(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    source: str  # component id
    target: str  # component id
    type: RelationshipType = RelationshipType.DEPENDS_ON
    confidence: float = 1.0
    metadata: Dict[str, Any] = Field(default_factory=dict)


# ─── Architecture Graph ───────────────────────────────────────────────────────

class ArchGraph(BaseModel):
    """Unified graph model for both intended (G_I) and current (G_C) architectures."""
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    name: str
    graph_type: Literal["intended", "current"] = "intended"
    components: List[ArchComponent] = Field(default_factory=list)
    relationships: List[ArchRelationship] = Field(default_factory=list)
    source: Optional[str] = None  # e.g., diagram path or repo path
    metadata: Dict[str, Any] = Field(default_factory=dict)


# ─── Conformance / Violation ──────────────────────────────────────────────────

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


class ArchViolation(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    verdict: ViolationVerdict
    violation_type: Optional[ViolationType] = None
    source_component: str
    target_component: str
    expected: Optional[str] = None
    actual: Optional[str] = None
    severity: Literal["low", "medium", "high", "critical"] = "medium"
    description: str = ""


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
    intended_graph_id: str
    current_graph_id: str


class AnalyzeViolationRequest(BaseModel):
    violation_id: str
    include_git_evidence: bool = True
