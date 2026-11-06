"""
Graph module — Sprint 4–7 P3 deliverables.

Exports:
    ArchGraphBuilder       — JSON schema ↔ NetworkX DiGraph conversion
    PackageGraphAggregator — file/class-level → package-level aggregation
    GraphIntegrityChecker  — pre-conformance graph validation
"""

from app.modules.graph.builder import ArchGraphBuilder, PackageGraphAggregator
from app.modules.graph.integrity import GraphIntegrityChecker, IntegrityReport, IssueSeverity

__all__ = [
    "ArchGraphBuilder",
    "PackageGraphAggregator",
    "GraphIntegrityChecker",
    "IntegrityReport",
    "IssueSeverity",
]

