"""Adapters for teammates' formats. Inputs are small literals in the exact shapes found on the
P1 (Gokul), P3 (Bhumika) and P4 (Bhuvana) branches; no teammate files are read."""
from archlens_llm import adapters as A
from archlens_llm.impact import ImpactRecommender
from archlens_llm.rca import RCAAnalyzer
from archlens_llm.schemas import EvidencePackage
from archlens_llm.vlm_extraction import cv_only_baseline

# --- P1 shapes (detection_mapping.MappedDetection, schemas.ArchComponent, geometry_relations.RelationCandidate)
P1_MAPPED = {"bbox": [768.8, 251.2, 930.4, 392.4], "confidence": 0.5388,
             "mapped_class": "architecture_component", "raw_coco_class": "umbrella", "raw_coco_class_id": 25}
P1_COMPONENT = {"id": "backend", "name": "Backend", "type": "gateway",
                "bbox": {"x1": 68.0, "y1": 75.0, "x2": 470.0, "y2": 240.0}, "confidence": 1.0, "metadata": {}}
P1_RELATION = {"source": "backend", "target": "orders", "confidence": 0.7324}
# --- P4 shapes (cv_pipeline.ComponentDetector.detect, CVPipeline relationships)
P4_DETECTION = {"bbox": [10, 20, 110, 80], "confidence": 0.5, "class_name": "architecture_component"}
P4_RELATION = {"id": "3f2c-uuid", "source": "c1", "target": "c2", "type": "depends_on", "confidence": 0.3,
               "metadata": {"extraction_method": "hough_line_candidate", "direction_verified": False}}

# --- P3 shapes (DependencyGraphBuilder nodes, example_ruleset.json rules, ConformanceEngine verdicts)
P3_COMPONENTS = [
    {"id": "frontend", "name": "WebFrontend", "type": "frontend", "confidence": 1.0},
    {"id": "app.controllers.order_controller", "name": "OrderController", "type": "controller",
     "file": "app/controllers/order_controller.py", "classes": ["OrderController"],
     "inference_confidence": 1.0, "metadata": {"functions": [], "classes_full": []}},
    {"id": "app.services.order_service", "name": "OrderService", "type": "service",
     "file": "app/services/order_service.py", "classes": ["OrderService"], "inference_confidence": 1.0, "metadata": {}},
    {"id": "app.repositories.order_repository", "name": "OrderRepository", "type": "repository",
     "file": "app/repositories/order_repository.py", "classes": ["OrderRepository"],
     "inference_confidence": 1.0, "metadata": {}},
    {"id": "database", "name": "OrderDatabase", "type": "database", "confidence": 1.0},
]
P3_RELATIONSHIPS = [
    {"id": "rel-1", "source": "frontend", "target": "app.controllers.order_controller", "type": "calls", "confidence": 1.0},
    {"id": "rel-2", "source": "app.controllers.order_controller", "target": "app.services.order_service",
     "type": "depends_on", "confidence": 1.0},
    {"id": "rel-3", "source": "app.services.order_service", "target": "app.repositories.order_repository",
     "type": "depends_on", "confidence": 1.0},
    {"id": "rel-4", "source": "app.repositories.order_repository", "target": "database", "type": "reads_from", "confidence": 1.0},
    {"id": "rel-v", "source": "app.controllers.order_controller", "target": "app.repositories.order_repository",
     "type": "depends_on", "confidence": 1.0},
]
P3_RULES = [
    {"id": "rule-allow-fe-ctrl", "name": "Allow Frontend to Controller", "action": "ALLOW", "category": "layer_rule",
     "source": "frontend", "target": "controller", "severity": "low", "description": "Frontend may invoke controllers"},
    {"id": "r2", "name": "a", "action": "ALLOW", "category": "layer_rule", "source": "controller", "target": "service"},
    {"id": "r3", "name": "b", "action": "ALLOW", "category": "layer_rule", "source": "service", "target": "repository"},
    {"id": "r4", "name": "c", "action": "ALLOW", "category": "layer_rule", "source": "repository", "target": "database"},
    {"id": "r5", "name": "d", "action": "FORBID", "category": "layer_rule", "source": "controller", "target": "repository",
     "severity": "high"},
    {"id": "r6", "name": "e", "action": "REQUIRE", "category": "layer_rule", "source": "service", "target": "repository"},
]
P3_VERDICT = {"verdict": "VIOLATION", "violation_type": "forbidden_dependency",
              "source": "app.controllers.order_controller", "target": "app.repositories.order_repository",
              "severity": "high", "confidence": 1.0, "description": "Forbidden dependency: controller → repository."}

# --- P4 commit shapes (GitEvidenceExtractor.find_introducing_commit / get_commits_for_file)
INTRO = {"hash": "abc12345deadbeef", "short_hash": "abc12345", "message": "Refactor order processing",
         "author": "Dev <dev@example.com>", "date": "2025-01-10T10:00:00+00:00",
         "diff": "+from app.repositories.order_repository import OrderRepository\n+repo.find(id)"}
RECENT = [{"hash": "abc12345deadbeef", "short_hash": "abc12345", "message": "Refactor order processing",
           "author": "Dev <dev@example.com>", "date": "2025-01-10T10:00:00+00:00"},
          {"hash": "def67890cafebabe", "short_hash": "def67890", "message": "Add request logging",
           "author": "Dev <dev@example.com>", "date": "2025-01-09T10:00:00+00:00"}]


def _id_to_name():
    return {c["id"]: c["name"] for c in P3_COMPONENTS}


def _p4_package(violation):
    """Exactly the key layout of P4 build_evidence_package()."""
    return {"violation": violation, "architecture_rule": {},
            "code": {"file": "app/controllers/order_controller.py", "target_symbol": "OrderRepository"},
            "dependency_path": [violation.get("source", ""), violation.get("target", "")],
            "commit": INTRO, "diff": INTRO["diff"][:2000], "recent_commits": RECENT[:5]}


# ------------------------------------------------------------------------------- P1 / P4
def test_detections_from_p1_and_p4():
    out = A.from_p1_detections([P1_MAPPED, P4_DETECTION, {"id": "x9", "bbox": {"x1": 1, "y1": 2, "x2": 3, "y2": 4},
                                                          "class": "service", "confidence": 0.7}])
    assert [d["id"] for d in out] == ["d1", "d2", "x9"]
    assert out[0] == {"id": "d1", "bbox": [768.8, 251.2, 930.4, 392.4], "class": "architecture_component",
                      "confidence": 0.5388}
    assert out[1]["class"] == "architecture_component" and out[1]["bbox"] == [10.0, 20.0, 110.0, 80.0]
    assert out[2]["bbox"] == [1.0, 2.0, 3.0, 4.0] and out[2]["class"] == "service"


def test_components_from_p1_keep_id_and_convert_bbox():
    out = A.from_p1_components([P1_COMPONENT, {**P1_COMPONENT, "id": "nobox", "bbox": None}])
    assert out == [{"id": "backend", "bbox": [68.0, 75.0, 470.0, 240.0], "class": "gateway", "confidence": 1.0}]


def test_relations_undirected_are_capped_and_become_uncertain():
    out = A.from_p1_relations([P1_RELATION, P4_RELATION])
    assert out[0] == {"id": "g1", "source": "backend", "target": "orders", "confidence": 0.49}
    assert out[1]["id"] == "3f2c-uuid" and out[1]["confidence"] == 0.3
    assert A.from_p1_relations([P1_RELATION], directed=True)[0]["confidence"] == 0.7324
    # P2's own rule then marks it uncertain (threshold 0.5), with no model in the loop
    comps = [{"id": "backend", "ocr_text": "Backend"}, {"id": "orders", "ocr_text": "Orders Service"}]
    ex = cv_only_baseline(comps, out[:1], uncertain_below=0.5)
    assert ex.relationships[0].status == "uncertain"


# ------------------------------------------------------------------------------------ P3
def test_p3_entities_and_layers():
    ents = A.from_p3_entities(P3_COMPONENTS)
    assert ents[1] == {"id": "app.controllers.order_controller", "name": "OrderController", "kind": "controller",
                       "path": "app/controllers/order_controller.py"}
    assert ents[0]["path"] == "frontend"          # no file in G_C example -> id
    lay = A.layer_of_from_p3(P3_COMPONENTS)
    assert lay["OrderController"] == "Controller" and lay["OrderDatabase"] == "Database"


def test_p3_rules():
    r = A.from_p3_rules(P3_RULES)
    assert r["allowed"] == ["Frontend->Controller", "Controller->Service", "Service->Repository", "Repository->Database"]
    assert r["forbidden"] == ["Controller->Repository"] and r["required"] == ["Service->Repository"]
    assert A.from_p3_rules({"id": "rs", "rules": P3_RULES}) == r          # whole RuleSet dict
    named = A.from_p3_rules([{"action": "FORBID", "source": "order_controller", "target": None,
                              "target_type": "database"}])
    assert named["forbidden"] == ["order_controller->Database"]          # names kept, missing type side -> layer


def test_p3_verdict_and_edges():
    v = A.from_p3_verdict(P3_VERDICT, _id_to_name())
    assert v == {"type": "forbidden_dependency", "source": "OrderController", "target": "OrderRepository",
                 "verdict": "VIOLATION"}
    edges = A.edges_from_p3(P3_RELATIONSHIPS, _id_to_name())
    assert ["OrderController", "OrderRepository"] in edges and len(edges) == 5


# ------------------------------------------------------------------------------------ P4
def test_p4_evidence_validates_and_dedups_commits():
    pkg = A.from_p4_evidence(_p4_package(P3_VERDICT), current_edges=[("a", "b")])
    ep = EvidencePackage.model_validate(pkg)
    assert [c.hash for c in ep.candidate_commits] == ["abc12345deadbeef", "def67890cafebabe"]
    assert ep.commit.hash == "abc12345deadbeef" and ep.commit.diff.startswith("+from")
    assert ep.code == {"file": "app/controllers/order_controller.py", "target_symbol": "OrderRepository"}
    assert ep.violation["type"] == "forbidden_dependency"                # P3 violation_type -> type
    assert ep.current_edges == [["a", "b"]] and "recent_commits" not in pkg


def test_p4_evidence_without_commit_and_with_lines():
    raw = {**_p4_package({"source": "A", "target": "B"}), "commit": None, "recent_commits": [],
           "code": {"file": "f.py", "target_symbol": "B", "lines": "3-5", "snippet": "import B"},
           "architecture_rule": P3_RULES}
    ep = EvidencePackage.model_validate(A.from_p4_evidence(raw))
    assert ep.commit is None and ep.candidate_commits == []
    assert ep.code["lines"] == "3-5" and ep.code["snippet"] == "import B"
    assert ep.architecture_rule["forbidden"] == ["Controller->Repository"]   # rule list converted


# ----------------------------------------------------------------------------- end to end
def test_end_to_end_p3_p4_into_rca_and_impact(gw):
    ids = _id_to_name()
    violation = A.from_p3_verdict(P3_VERDICT, ids)                       # P3 verdict -> P2 violation
    raw = _p4_package(violation)                                         # what P4 builds today
    raw["architecture_rule"] = P3_RULES                                  # P3 rules, passed through by P4
    pkg = A.from_p4_evidence(raw, current_edges=A.edges_from_p3(P3_RELATIONSHIPS, ids),
                             intended_edges=A.edges_from_p3(P3_RELATIONSHIPS[:4], ids),
                             layer_of=A.layer_of_from_p3(P3_COMPONENTS))
    rca = RCAAnalyzer(gw, "grounded_full").analyze(pkg)
    # Today's P4 package has no code.snippet and no commit "files", so nothing ties the commit to the
    # offending line: grounded RCA correctly abstains instead of guessing.
    assert rca.output is not None and rca.status == "UNCERTAIN" and rca.output.introducing_commit is None
    imp = ImpactRecommender(gw).recommend(pkg)
    assert imp.status == "VALIDATED", imp.reasons
    assert imp.output.recommendation.remove_edges == [["OrderController", "OrderRepository"]]
    names = {a["component"] for a in imp.affected}                       # computed from adapted current_edges
    assert {"OrderController", "OrderRepository", "WebFrontend", "OrderDatabase"} <= names


def test_end_to_end_rca_supported_once_p4_sends_snippet_and_files(gw):
    """The two fields to ask P4 for: code.lines/snippet and the files each commit touched."""
    ids = _id_to_name()
    raw = _p4_package(A.from_p3_verdict(P3_VERDICT, ids))
    raw["commit"] = {**INTRO, "files": ["app/controllers/order_controller.py"]}
    raw["code"] = {**raw["code"], "lines": "12-14",
                   "snippet": "from app.repositories.order_repository import OrderRepository\nrepo.find(id)"}
    pkg = A.from_p4_evidence(raw, current_edges=A.edges_from_p3(P3_RELATIONSHIPS, ids),
                             layer_of=A.layer_of_from_p3(P3_COMPONENTS))
    rca = RCAAnalyzer(gw, "grounded_full").analyze(pkg)
    assert rca.status == "SUPPORTED" and rca.output.introducing_commit == "abc12345deadbeef"
