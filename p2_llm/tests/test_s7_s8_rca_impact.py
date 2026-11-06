"""Sprints 7–8: evidence-grounded RCA, hallucination checks, impact/recommendation rule validation."""
import copy
import json

import pytest

from archlens_llm.grounding import EVIDENCE_GROUPS, index_evidence, text_mentions
from archlens_llm.impact import ImpactRecommender, compute_affected, edge_verdict
from archlens_llm.rca import RCAAnalyzer
from archlens_llm.schemas import EvidencePackage
from conftest import load, make_gw

ALL = ["S01_shop", "S02_layered", "S03_logistics", "S04_modular", "S05_cycle", "S06_missing"]


def test_evidence_index_respects_variant():
    pkg = EvidencePackage.model_validate(load("S02_layered", "violation.json"))
    full = index_evidence(pkg, EVIDENCE_GROUPS["grounded_full"]).ids
    nogit = index_evidence(pkg, EVIDENCE_GROUPS["grounded_no_git"]).ids
    assert "E-COMMIT-abc12345" in full and not any(i.startswith("E-COMMIT") for i in nogit)
    assert index_evidence(pkg, EVIDENCE_GROUPS["llm_only"]).ids == set()


def test_text_mentions_flags_invented_files_and_hashes():
    pkg = EvidencePackage.model_validate(load("S02_layered", "violation.json"))
    idx = index_evidence(pkg, EVIDENCE_GROUPS["grounded_full"])
    found = {m["value"] for m in text_mentions("See LegacyAdapter.java and commit deadbeef1; OrderController.java is fine", idx)}
    assert found == {"LegacyAdapter.java", "deadbeef1"}


@pytest.mark.parametrize("system", ALL)
def test_grounded_rca_matches_ground_truth(gw, system):
    pkg = load(system, "violation.json")
    r = RCAAnalyzer(gw, "grounded_full").analyze(pkg)
    gt = pkg["ground_truth"]
    assert r.status == gt["expected_status"]
    assert r.output.introducing_commit == gt["introducing_commit"] or gt["introducing_commit"] is None
    ids = set(r.evidence_ids)
    assert all(c.evidence_id in ids for c in r.output.evidence)


def test_uncertain_when_history_missing(gw):
    r = RCAAnalyzer(gw, "grounded_full").analyze(load("S05_cycle", "violation.json"))
    assert r.status == "UNCERTAIN" and r.output.introducing_commit is None and r.reasons


def test_no_git_variant_cannot_claim_commit(gw):
    r = RCAAnalyzer(gw, "grounded_no_git").analyze(load("S01_shop", "violation.json"))
    assert r.output.introducing_commit is None and r.status == "UNCERTAIN"


def test_llm_only_is_never_supported(gw):
    r = RCAAnalyzer(gw, "llm_only").analyze(load("S01_shop", "violation.json"))
    assert r.status == "UNCERTAIN" and r.grounding_score == 0.0


def test_hallucinated_rca_is_repaired_and_logged(tmp_path):
    gw = make_gw(tmp_path, ["hallucinate_once"])
    r = RCAAnalyzer(gw, "grounded_full").analyze(load("S02_layered", "violation.json"))
    assert r.provenance["attempts"] == 2 and r.output.introducing_commit == "abc12345"
    assert "BillingService" not in r.output.affected_components


def test_persistent_hallucination_ends_uncertain_and_logged(tmp_path):
    from archlens_llm.gateway import LLMGateway
    from archlens_llm.gateway.mock_provider import MockProvider

    class Liar(MockProvider):
        def generate(self, req, timeout_s):
            resp = super().generate(req, timeout_s)
            o = json.loads(resp.text)
            o["introducing_commit"] = "deadbeef"
            resp.text = json.dumps(o)
            return resp

    gw = LLMGateway(Liar(), run_dir=tmp_path, cache=False)
    r = RCAAnalyzer(gw, "grounded_full").analyze(load("S02_layered", "violation.json"))
    assert r.status == "UNCERTAIN"
    log = (tmp_path / "hallucinations.jsonl").read_text()
    assert "unknown_introducing_commit" in log


def test_edge_verdict_layers():
    pkg = load("S02_layered", "violation.json")
    r, L, I = pkg["architecture_rule"], pkg["layer_of"], pkg["intended_edges"]
    assert edge_verdict("Order Controller", "Order Repository", r, L, I) == "FORBIDDEN"
    assert edge_verdict("Order Controller", "Order Service", r, L, I) == "ALLOWED"


def test_compute_affected_fallback():
    pkg = load("S01_shop", "violation.json")
    aff = {a["component"]: a for a in compute_affected(pkg["current_edges"], "Web Frontend", "Orders DB")}
    assert aff["Web Frontend"]["direction"] == "source" and aff["User"]["direction"] == "upstream"
    assert "Orders DB" in aff


@pytest.mark.parametrize("system", ALL)
def test_impact_recommendation_validated(gw, system):
    pkg = load(system, "violation.json")
    r = ImpactRecommender(gw).recommend(pkg)
    assert r.status == "VALIDATED", r.reasons
    fix = pkg["ground_truth"]["expected_fix"]
    assert all(e in r.output.recommendation.remove_edges for e in fix["remove"])
    assert all(e in r.output.recommendation.add_edges for e in fix["add"])
    assert not any(x["verdict"] == "FORBIDDEN" for x in r.rule_check)


def test_forbidden_fix_is_rejected(tmp_path):
    from archlens_llm.gateway import LLMGateway
    from archlens_llm.gateway.mock_provider import MockProvider

    class BadFix(MockProvider):
        def generate(self, req, timeout_s):
            resp = super().generate(req, timeout_s)
            o = json.loads(resp.text)
            o["recommendation"]["add_edges"] = [["Order Controller", "Database"]]  # Controller->Data is forbidden
            resp.text = json.dumps(o)
            return resp

    gw = LLMGateway(BadFix(), run_dir=tmp_path, cache=False)
    r = ImpactRecommender(gw).recommend(load("S02_layered", "violation.json"))
    assert r.status == "UNCERTAIN" and r.output is None
    assert any("FORBIDDEN" in x for x in r.reasons)


def test_invented_component_in_impact_is_repaired(tmp_path):
    gw = make_gw(tmp_path, ["hallucinate_once"])
    r = ImpactRecommender(gw).recommend(load("S01_shop", "violation.json"))
    assert r.status == "VALIDATED" and all(i.component != "GhostService" for i in r.output.impacts)
