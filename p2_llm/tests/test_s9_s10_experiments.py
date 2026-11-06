"""Sprints 9–10: freeze guard, runner outputs, rubric round trip, service API for P4."""
import csv
import json
import shutil

import pytest

from archlens_llm.config import load_config
from archlens_llm.evaluation.rubric import aggregate, make_sheet
from archlens_llm.evaluation.runner import check_lock, freeze, run
from archlens_llm.service import analyze_violation, classify_dependency_role
from conftest import FIX, load


@pytest.fixture
def split(tmp_path):
    p = tmp_path / "split.json"
    p.write_text(json.dumps({"seed": 1, "prompt_dev": ["S01_shop"], "held_out_test": ["S02_layered"], "sha256": "abc"}))
    return p


def test_held_out_requires_matching_lock(tmp_path, split):
    cfg = load_config()
    cfg["gateway"]["cache"] = False
    lock = tmp_path / "lock.json"
    with pytest.raises(RuntimeError):
        run(FIX, split, "held_out_test", cfg, lock, out_root=tmp_path, experiments=("rca",))
    freeze(cfg, split, lock)
    assert check_lock(cfg, json.loads(split.read_text()), lock) == []
    cfg2 = json.loads(json.dumps(cfg)); cfg2["thresholds"]["rca_uncertain_below"] = 0.9
    assert "config_sha changed since freeze" in check_lock(cfg2, json.loads(split.read_text()), lock)
    res = run(FIX, split, "held_out_test", cfg, lock, out_root=tmp_path, experiments=("rca", "impact"))
    assert res["rca"]["grounded_full"]["mean"]["status_correct"] == 1.0
    assert "WARNING" in res  # mock results are labelled as non-research


def test_rubric_round_trip(tmp_path):
    rows = [{"variant": "grounded_full", "violation_id": "v1", "output": {"root_cause": "x", "evidence": []}},
            {"variant": "llm_only", "violation_id": "v1", "output": {"root_cause": "y", "evidence": []}}]
    sheet, key = make_sheet(rows, tmp_path / "sheet.csv", ["P2", "P1"])
    data = list(csv.DictReader(open(sheet)))
    assert "grounded_full" not in open(sheet).read()  # blinded
    for r in data:
        for c in ("architecture_correctness", "evidence_grounding", "root_cause_accuracy", "actionability", "hallucination_free"):
            r[c] = "5" if r["root_cause"] == "x" else ("2" if r["rater"] == "P2" else "3")
    with open(sheet, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(data[0])); w.writeheader(); w.writerows(data)
    agg = aggregate(sheet, key)
    assert agg["means_by_variant"]["grounded_full"]["evidence_grounding"] == 5.0
    assert agg["inter_rater"]["actionability"]["within_1"] == 1.0


def test_service_analyze_violation_contract(tmp_path):
    out = analyze_violation(load("S02_layered", "violation.json"), run_dir=str(tmp_path))
    assert out["root_cause"]["status"] == "SUPPORTED" and out["root_cause"]["introducing_commit"] == "abc12345"
    assert out["recommendation"]["status"] == "VALIDATED"
    assert ["Order Controller", "Order Repository"] in out["recommendation"]["remove_edges"]
    json.dumps(out)  # serialisable for FastAPI


def test_service_dependency_role(tmp_path):
    r = classify_dependency_role("OrderController", "OrderRepository", run_dir=str(tmp_path))
    assert r["ok"] and r["role"]["source_role"] == "Controller"
