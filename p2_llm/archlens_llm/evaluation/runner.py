"""Sprint 9: frozen-config experiment runner for every P2 comparison.

  E1 extraction   cv_only | vlm_only | cv_vlm | cv_vlm_geometry   (+ fewshot on/off sensitivity)
  E2 alignment    deterministic-only | deterministic + LLM
  E3 rca          llm_only | grounded_no_git | grounded_git_no_graph | grounded_full   (ablations 2 & 4)
  E4 impact       impact/recommendation validity, fix correctness, rule-check pass

Freeze rule (sprint plan §2): the held-out test split can only be run with a lock file whose
prompt versions, config and split hash match the current ones. Edit a prompt -> lock breaks.
"""
from __future__ import annotations

import hashlib
import json
import platform
import time
from pathlib import Path

from .. import __version__
from ..alignment import Aligner, score_alignment
from ..config import ROOT, load_config, make_gateway
from ..grounding import EVIDENCE_GROUPS
from ..impact import ImpactRecommender
from ..prompts import all_prompt_versions
from ..rca import RCAAnalyzer
from ..vlm_extraction import FEWSHOT_PATH, MODES, VLMExtractor
from .metrics import extraction_metrics, impact_metrics, mean_table, rca_metrics


def _sha(obj) -> str:
    return hashlib.sha256(json.dumps(obj, sort_keys=True).encode()).hexdigest()[:16]


def current_fingerprint(cfg: dict, split: dict) -> dict:
    return {"prompt_versions": all_prompt_versions(),
            "fewshot_sha": hashlib.sha256(FEWSHOT_PATH.read_bytes()).hexdigest()[:16],
            "config_sha": _sha({k: cfg[k] for k in ("provider", "gateway", "thresholds", "extraction", "rca") if k in cfg}),
            "split_sha": split.get("sha256"), "provider": cfg["provider"], "temperature": cfg["gateway"]["temperature"],
            "package_version": __version__}


def freeze(cfg: dict, split_path: str | Path, lock_path: str | Path) -> dict:
    split = json.loads(Path(split_path).read_text())
    lock = {**current_fingerprint(cfg, split), "frozen_at": time.strftime("%Y-%m-%dT%H:%M:%S"),
            "python": platform.python_version()}
    Path(lock_path).write_text(json.dumps(lock, indent=1))
    return lock


def check_lock(cfg: dict, split: dict, lock_path: str | Path) -> list[str]:
    p = Path(lock_path)
    if not p.exists():
        return [f"no lock file at {p}; run `freeze` first"]
    lock = json.loads(p.read_text())
    cur = current_fingerprint(cfg, split)
    return [f"{k} changed since freeze" for k in ("prompt_versions", "fewshot_sha", "config_sha", "split_sha")
            if lock.get(k) != cur.get(k)]


def _ocr_cached(sysdir: Path, cache_dir: Path) -> list[dict]:
    from ..ocr import ocr_components
    cache_dir.mkdir(parents=True, exist_ok=True)
    f = cache_dir / f"{sysdir.name}_ocr.json"
    if f.exists():
        return json.loads(f.read_text())
    comps = ocr_components(str(sysdir / "diagram.png"), json.loads((sysdir / "detections.json").read_text()))
    f.write_text(json.dumps(comps))
    return comps


def run(fixture_root: str | Path, split_path: str | Path, split_name: str = "prompt_dev", cfg: dict | None = None,
        lock_path: str | Path | None = None, out_root: str | Path | None = None,
        experiments: tuple[str, ...] = ("extraction", "alignment", "rca", "impact")) -> dict:
    cfg = cfg or load_config()
    split = json.loads(Path(split_path).read_text())
    if split_name == "held_out_test":
        problems = check_lock(cfg, split, lock_path or ROOT / "config" / "experiment.lock.json")
        if problems:
            raise RuntimeError("refusing to run on held_out_test: " + "; ".join(problems))
    exp_id = f"{time.strftime('%Y%m%d-%H%M%S')}_{split_name}_{cfg['provider']['kind']}"
    out = Path(out_root or ROOT / "runs") / exp_id
    (out / "outputs").mkdir(parents=True, exist_ok=True)
    gw = make_gateway(cfg, run_dir=out)
    th = cfg["thresholds"]
    root = Path(fixture_root)
    systems = [root / s for s in split[split_name]]
    results: dict = {"exp_id": exp_id, "split": split_name, "systems": split[split_name],
                     "fingerprint": current_fingerprint(cfg, split)}
    if cfg["provider"]["kind"] == "mock":
        results["WARNING"] = "mock provider: pipeline smoke test only, NOT research results"

    if "extraction" in experiments:
        rows = {}
        settings = [(m, True) for m in MODES] + [("cv_vlm_geometry", False)]
        for mode, fs in settings:
            name = f"{mode}{'' if fs or mode == 'cv_only' else '_no_fewshot'}"
            if mode == "cv_only" and not fs:
                continue
            per = []
            for sd in systems:
                comps = _ocr_cached(sd, out.parent / "_ocr_cache")
                geo = json.loads((sd / "geometry_candidates.json").read_text())
                ex = VLMExtractor(gw if mode != "cv_only" else None, mode=mode, fewshot=fs,
                                  relation_uncertain_below=th["relation_uncertain_below"],
                                  component_abstain_below=th["component_abstain_below"])
                r = ex.extract(sd.name, str(sd / "diagram.png"), comps, geo)
                (out / "outputs" / f"extraction_{name}_{sd.name}.json").write_text(json.dumps(r.to_graph(), indent=1))
                m = extraction_metrics(r, json.loads((sd / "annotation.json").read_text()))
                per.append({"system": sd.name, **m})
            rows[name] = {"mean": mean_table(per), "per_system": per}
        results["extraction"] = rows

    if "alignment" in experiments:
        rows = {}
        for name, use_llm in (("deterministic_only", False), ("deterministic_plus_llm", True)):
            per = []
            for sd in systems:
                ann = json.loads((sd / "annotation.json").read_text())
                nodes = [{"id": c["id"], "name": c["name"], "type": c["type"]} for c in ann["components"]]
                al = Aligner(gw, use_llm=use_llm, accept_at=th["alignment_accept_at"],
                             token_accept=th["alignment_token_accept"], token_margin=th["alignment_token_margin"])
                pred = al.align(nodes, json.loads((sd / "code_entities.json").read_text()))
                sc = score_alignment(pred, json.loads((sd / "alignment_gold.json").read_text()))
                (out / "outputs" / f"alignment_{name}_{sd.name}.json").write_text(
                    json.dumps({"pred": [p.model_dump() for p in pred], "score": sc}, indent=1))
                per.append({"system": sd.name, **{k: v for k, v in sc.items() if k != "rows"}})
            rows[name] = {"mean": mean_table(per), "per_system": per}
        results["alignment"] = rows

    if "rca" in experiments:
        rows, all_rca = {}, []
        for variant in EVIDENCE_GROUPS:
            per = []
            for sd in systems:
                pkg = json.loads((sd / "violation.json").read_text())
                r = RCAAnalyzer(gw, variant=variant, uncertain_below=th["rca_uncertain_below"]).analyze(pkg)
                d = r.to_dict()
                all_rca.append(d)
                (out / "outputs" / f"rca_{variant}_{sd.name}.json").write_text(json.dumps(d, indent=1))
                per.append({"system": sd.name, **rca_metrics(r, pkg["ground_truth"])})
            rows[variant] = {"mean": mean_table(per), "per_system": per}
        results["rca"] = rows
        (out / "rca_all.json").write_text(json.dumps(all_rca, indent=1))

    if "impact" in experiments:
        per = []
        for sd in systems:
            pkg = json.loads((sd / "violation.json").read_text())
            r = ImpactRecommender(gw, abstain_below=th["impact_abstain_below"]).recommend(pkg)
            (out / "outputs" / f"impact_{sd.name}.json").write_text(json.dumps(r.to_dict(), indent=1))
            per.append({"system": sd.name, **impact_metrics(r, pkg["ground_truth"])})
        results["impact"] = {"mean": mean_table(per), "per_system": per}

    results["usage"] = gw.totals
    (out / "results.json").write_text(json.dumps(results, indent=1))
    (out / "results.md").write_text(to_markdown(results))
    return results


def to_markdown(res: dict) -> str:
    L = [f"# P2 experiment {res['exp_id']}", ""]
    if "WARNING" in res:
        L += [f"> **{res['WARNING']}**", ""]
    L += [f"Split: `{res['split']}` ({len(res['systems'])} systems). Provider: `{res['fingerprint']['provider']}`.", ""]
    def table(title, block, cols):
        L.extend([f"## {title}", "", "| setting | " + " | ".join(cols) + " | n |", "|---|" + "---|" * (len(cols) + 1)])
        for name, b in block.items():
            m = b["mean"]
            L.append(f"| {name} | " + " | ".join("–" if m.get(c) is None else str(m.get(c)) for c in cols) + f" | {m['n']} |")
        L.append("")
    if "extraction" in res:
        table("E1 Diagram extraction", res["extraction"], ["name_accuracy", "type_accuracy", "relation_precision",
              "relation_recall", "relation_f1", "valid_structured_output"])
    if "alignment" in res:
        table("E2 Component alignment", res["alignment"], ["precision", "recall", "f1", "wrong_matches", "uncertain"])
    if "rca" in res:
        table("E3 Root-cause analysis (ablations)", res["rca"], ["valid_structured_output", "status_correct", "overclaim",
              "introducing_commit_correct", "top1", "top3", "grounding_score", "unsupported_claims", "root_cause_keyword_recall"])
    if "impact" in res:
        table("E4 Impact + recommendation", {"impact_recommendation": res["impact"]},
              ["valid_structured_output", "fix_correct", "forbidden_edges_proposed", "abstained"])
    L += [f"Usage: {res['usage']}", ""]
    return "\n".join(L)
