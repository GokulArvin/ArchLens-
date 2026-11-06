"""Sprints 5–6: VLM extraction guarantees and semantic alignment with abstention."""
from archlens_llm.alignment import Aligner, score_alignment
from archlens_llm.vlm_extraction import VLMExtractor, cv_only_baseline
from conftest import FIX, load, make_gw


def _comps(system):
    # Use gold names as OCR so the test does not depend on Tesseract
    gold = {c["id"]: c["name"] for c in load(system, "annotation.json")["components"]}
    return [{**d, "ocr_text": gold[d["id"]], "ocr_conf": 0.95} for d in load(system, "detections.json")]


def test_cv_vlm_geometry_labels_every_box(gw):
    s = "S01_shop"
    r = VLMExtractor(gw, mode="cv_vlm_geometry").extract(s, str(FIX / s / "diagram.png"), _comps(s),
                                                          load(s, "geometry_candidates.json"))
    ids = {c.id for c in r.extraction.components}
    assert not r.fallback and ids == {d["id"] for d in load(s, "detections.json")}
    assert all(x.source in ids and x.target in ids for x in r.extraction.relationships)
    weak = [x for x in r.extraction.relationships if x.confidence < 0.5]
    assert weak and all(x.status == "uncertain" for x in weak)
    g = r.to_graph()
    assert all("provenance" in c for c in g["components"]) and all("provenance" in e for e in g["relationships"])


def test_hallucinated_id_is_repaired(tmp_path):
    gw = make_gw(tmp_path, ["hallucinate_once"])
    s = "S02_layered"
    r = VLMExtractor(gw, mode="cv_vlm_geometry").extract(s, str(FIX / s / "diagram.png"), _comps(s),
                                                          load(s, "geometry_candidates.json"))
    assert not r.fallback and r.provenance["attempts"] == 2
    assert all(x.source != "c99" for x in r.extraction.relationships)


def test_model_failure_falls_back_to_cv_only(tmp_path):
    gw = make_gw(tmp_path, ["always_invalid"])
    s = "S03_logistics"
    r = VLMExtractor(gw, mode="cv_vlm").extract(s, str(FIX / s / "diagram.png"), _comps(s))
    assert r.fallback and r.model_errors and len(r.extraction.components) == 6
    assert r.to_graph()["components"][0]["provenance"] == "fallback:cv_only"


def test_unreadable_box_abstains():
    ex = cv_only_baseline([{"id": "c1", "bbox": [0, 0, 10, 10], "ocr_text": ""}], [])
    assert ex.components[0].abstain and ex.components[0].type == "unknown"


def test_alignment_cascade_and_llm_only_for_unresolved(gw):
    s = "S01_shop"
    nodes = [{"id": c["id"], "name": c["name"], "type": c["type"]} for c in load(s, "annotation.json")["components"]]
    pred = Aligner(gw).align(nodes, load(s, "code_entities.json"))
    by = {p.diagram_node_id: p for p in pred}
    assert by["c4"].method in ("exact", "normalized") and by["c4"].verdict == "MATCHED"   # Order Service
    assert by["c8"].method == "llm"                                                        # Kafka -> needs semantics
    sc = score_alignment(pred, load(s, "alignment_gold.json"))
    assert sc["wrong_matches"] == 0


def test_alignment_semantic_beats_exact():
    from archlens_llm.gateway import LLMGateway
    from archlens_llm.gateway.mock_provider import MockProvider
    import tempfile
    gw = LLMGateway(MockProvider(), run_dir=tempfile.mkdtemp(), cache=False)
    f_det, f_llm = [], []
    for s in ("S01_shop", "S03_logistics", "S04_modular"):
        nodes = [{"id": c["id"], "name": c["name"], "type": c["type"]} for c in load(s, "annotation.json")["components"]]
        gold, ents = load(s, "alignment_gold.json"), load(s, "code_entities.json")
        f_det.append(score_alignment(Aligner(None, use_llm=False).align(nodes, ents), gold)["recall"])
        f_llm.append(score_alignment(Aligner(gw).align(nodes, ents), gold)["recall"])
    assert sum(f_llm) >= sum(f_det)


def test_alignment_low_confidence_and_bad_candidate_become_uncertain(tmp_path):
    node = [{"id": "c1", "name": "Kafka", "type": "queue"}]
    ents = [{"id": "messaging/kafka/EventBusProducer", "name": "EventBusProducer", "path": "messaging/kafka"},
            {"id": "x/Other", "name": "Other", "path": "x"}]
    low = Aligner(make_gw(tmp_path / "a", ["low_confidence"])).align(node, ents)[0]
    assert low.verdict == "UNCERTAIN" and low.code_entity_id is not None
    bad = Aligner(make_gw(tmp_path / "b", ["hallucinate_once"])).align(node, ents)[0]
    assert bad.code_entity_id in (None, "messaging/kafka/EventBusProducer")  # repaired, never the invented id


def test_alignment_conflict_rule():
    nodes = [{"id": "c1", "name": "Notification", "type": "service"}, {"id": "c2", "name": "Notifications", "type": "service"}]
    ents = [{"id": "n/NotificationService", "name": "NotificationService", "path": "n"}]
    pred = Aligner(None, use_llm=False, token_accept=0.5).align(nodes, ents)
    assert sum(p.verdict == "MATCHED" for p in pred) <= 1
