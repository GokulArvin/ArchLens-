"""Sprints 2–4: annotation validation/audit/agreement, splits, label normalization, OCR association, relation rules."""
import copy

import pytest

from archlens_llm.annotation import agreement, audit_annotations, make_split, validate_annotation
from archlens_llm.labels import alignment_key, infer_type, normalize_name, normalize_type_label
from archlens_llm.ocr import Word, associate_text
from archlens_llm.relations import validate_relations
from archlens_llm.schemas import ComponentLabel
from conftest import load


def test_fixture_annotations_valid():
    for s in ("S01_shop", "S02_layered", "S06_missing"):
        assert validate_annotation(load(s, "annotation.json")) == []


def test_annotation_errors_detected():
    a = copy.deepcopy(load("S01_shop", "annotation.json"))
    a["components"][0]["type"] = "DB"
    a["relationships"].append({"source": "c1", "target": "c99", "type": "depends_on"})
    errs = validate_annotation(a)
    assert any("vocabulary" in e for e in errs) and any("unknown endpoint" in e for e in errs)


def test_audit_finds_inconsistent_types():
    a, b = copy.deepcopy(load("S01_shop", "annotation.json")), copy.deepcopy(load("S06_missing", "annotation.json"))
    for c in b["components"]:
        if c["name"] == "Orders DB":
            c["type"] = "storage"
    rep = audit_annotations([a, b])
    assert "order database" in rep["inconsistent_names"]


def test_agreement_identical_is_perfect_and_disagreement_logged():
    a = load("S02_layered", "annotation.json")
    r = agreement(a, a)
    assert r["type_kappa"] == 1.0 and r["relation_f1"] == 1.0 and r["disagreements"] == []
    b = copy.deepcopy(a)
    b["components"][3]["type"] = "module"
    b["relationships"].pop()
    r2 = agreement(a, b)
    kinds = {d["kind"] for d in r2["disagreements"]}
    assert "type" in kinds and "relation" in kinds and r2["relation_f1"] < 1.0


def test_split_is_frozen(tmp_path):
    p = tmp_path / "split.json"
    s1 = make_split(["a", "b", "c", "d"], p)
    s2 = make_split(["x", "y"], p)  # second call must NOT overwrite
    assert s1 == s2 and set(s1["prompt_dev"]).isdisjoint(s1["held_out_test"])


@pytest.mark.parametrize("name,typ", [("Orders DB", "database"), ("User Service", "service"), ("Kafka", "queue"),
                                      ("API Gateway", "gateway"), ("Customer", "user"), ("Stripe", "external_system"),
                                      ("Redis cache", "cache"), ("Web Frontend", "frontend")])
def test_label_dictionary(name, typ):
    assert infer_type(name)[0] == typ


def test_name_normalization():
    assert normalize_name("OrderSvc") == normalize_name("order-service") == normalize_name("Order Service")
    assert alignment_key("Pmt Svc") == alignment_key("PaymentService") == "payment"
    assert normalize_type_label("DB") == "database" and normalize_type_label("Message Queue") == "queue"


def test_text_association_rules():
    comps = [{"id": "c1", "bbox": [0, 0, 100, 50]}, {"id": "c2", "bbox": [200, 0, 300, 50]},
             {"id": "c3", "bbox": [400, 0, 500, 50]}]
    words = [Word("Order", (10, 10, 40, 20), 90), Word("Service", (45, 10, 90, 20), 90),   # A1 inside c1
             Word("Kafka", (210, 55, 250, 70), 90),                                         # A2 just below c2
             Word("Far", (700, 300, 720, 310), 90)]                                         # dropped
    out = {c["id"]: c for c in associate_text(comps, words)}
    assert out["c1"]["ocr_text"] == "Order Service"
    assert out["c2"]["ocr_text"] == "Kafka" and any(i.startswith("outside_box") for i in out["c2"]["issues"])
    assert out["c3"]["ocr_text"] == "" and "no_text" in out["c3"]["issues"]


def test_relation_rules():
    comps = [ComponentLabel(id="c1", name="A", type="service", confidence=0.9),
             ComponentLabel(id="c2", name="B", type="service", confidence=0.9),
             ComponentLabel(id="c3", name="", type="unknown", confidence=0.2, abstain=True)]
    rels = [{"source": "c1", "target": "c9", "confidence": 0.9, "evidence": ["x"]},           # R1
            {"source": "c1", "target": "c1", "confidence": 0.9, "evidence": ["x"]},           # R2
            {"source": "c1", "target": "c2", "type": "talks_to", "confidence": 0.8, "evidence": ["x"]},  # R3
            {"source": "c1", "target": "c2", "confidence": 0.6, "evidence": ["y"]},           # R4 dup
            {"source": "c2", "target": "c1", "confidence": 0.75, "evidence": ["z"]},          # R5 reverse
            {"source": "c2", "target": "c3", "confidence": 0.9, "evidence": ["w"]},           # R8 shaky endpoint
            {"source": "c3", "target": "c1", "confidence": 0.3, "evidence": []}]              # R6+R7
    out, issues = validate_relations(rels, comps, 0.5)
    by = {(r.source, r.target): r for r in out}
    assert ("c1", "c9") not in by and ("c1", "c1") not in by
    assert by[("c1", "c2")].type == "depends_on" and set(by[("c1", "c2")].evidence) == {"x", "y"}
    assert by[("c1", "c2")].status == "uncertain" and by[("c2", "c1")].status == "uncertain"
    assert by[("c2", "c3")].status == "uncertain" and by[("c3", "c1")].status == "uncertain"
    rules = {i["rule"] for i in issues}
    assert {"R1", "R2", "R3", "R4", "R5"} <= rules
