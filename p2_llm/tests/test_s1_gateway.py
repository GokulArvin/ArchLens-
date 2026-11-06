"""Sprint 1: schemas, JSON validation strategy, gateway retry/repair/abstain, logging."""
import json

import pytest
from pydantic import ValidationError

from archlens_llm.jsonutil import extract_json
from archlens_llm.prompts import all_prompt_versions, render
from archlens_llm.schemas import ComponentLabel, DependencyRole, RCAOutput, RelationCandidate
from conftest import make_gw


def test_schema_rejects_bad_values():
    with pytest.raises(ValidationError):
        ComponentLabel(id="c1", name="x", type="spaceship", confidence=0.5)
    with pytest.raises(ValidationError):
        RelationCandidate(source="a", target="b", confidence=1.2)
    with pytest.raises(ValidationError):
        ComponentLabel(id="c1", name="x", type="service", confidence=0.5, bbox=[10, 10, 5, 20])
    with pytest.raises(ValidationError):  # extra fields forbidden
        DependencyRole(source_role="a", target_role="b", architectural_meaning="m", confidence=0.5, extra=1)


@pytest.mark.parametrize("text,ok", [
    ('{"a": 1}', True),
    ('```json\n{"a": 1}\n```', True),
    ('Sure! Here it is: {"a": [1, 2,], "b": None} hope this helps', True),
    ('{"a": 1', False),
    ("no json here", False),
])
def test_extract_json(text, ok):
    obj, steps = extract_json(text)
    assert (obj is not None) == ok


def test_prompt_versions_have_hash():
    v = all_prompt_versions()
    assert {"vlm_extraction", "rca_grounded", "impact_recommendation", "semantic_alignment", "repair"} <= set(v)
    assert all("+" in x for x in v.values())
    with pytest.raises(KeyError):
        render("rca_grounded", {})  # missing variable is an error, not a silent blank


def test_structured_ok_and_logged(gw):
    r = gw.structured("dependency_role", {"input_json": {"source": "OrderController", "target": "OrderRepository"}},
                      DependencyRole)
    assert r.ok and r.parsed.source_role == "Controller" and r.parsed.target_role == "Repository"
    rec = json.loads((gw.run_dir / "llm_calls.jsonl").read_text().splitlines()[-1])
    for k in ("raw_output", "parsed_output", "prompt_version", "model", "input_tokens", "valid"):
        assert k in rec


def test_malformed_output_is_repaired(tmp_path):
    gw = make_gw(tmp_path, ["malformed_once"])
    r = gw.structured("vlm_extraction", {"mode": "cv_vlm", "component_types": "", "relation_types": "",
                                         "fewshot_block": "", "input_json": {"components": [{"id": "c1", "ocr_text": "Orders DB"}]}},
                      __import__("archlens_llm.schemas", fromlist=["DiagramExtraction"]).DiagramExtraction)
    assert r.ok and r.attempts == 2


def test_always_invalid_abstains(tmp_path):
    gw = make_gw(tmp_path, ["always_invalid"])
    r = gw.structured("dependency_role", {"input_json": {"source": "a", "target": "b"}}, DependencyRole, max_repairs=2)
    assert not r.ok and r.abstained and r.attempts == 3 and r.parsed is None


def test_transient_network_error_is_retried(tmp_path):
    gw = make_gw(tmp_path, ["network_once"])
    r = gw.structured("dependency_role", {"input_json": {"source": "a", "target": "b"}}, DependencyRole)
    assert r.ok


def test_cache_hit(tmp_path):
    from archlens_llm.gateway import LLMGateway
    from archlens_llm.gateway.mock_provider import MockProvider
    gw = LLMGateway(MockProvider(), run_dir=tmp_path, cache=True)
    for _ in range(2):
        gw.structured("dependency_role", {"input_json": {"source": "a", "target": "b"}}, DependencyRole)
    assert gw.totals["cache_hits"] == 1 and gw.totals["calls"] == 1


def test_rca_schema_matches_design_9_2():
    fields = set(RCAOutput.model_fields)
    assert {"violation_explanation", "root_cause", "evidence", "affected_components", "recommendation", "confidence"} <= fields
