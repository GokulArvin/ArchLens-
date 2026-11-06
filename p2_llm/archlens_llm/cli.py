"""Command line for P2.

  python -m archlens_llm.cli smoke                      # S1 D5 smoke test (logs failures)
  python -m archlens_llm.cli audit                      # S3 D11 annotation audit
  python -m archlens_llm.cli split                      # S2 D10 create (once) the prompt-dev / held-out split
  python -m archlens_llm.cli demo  [SYSTEM]             # one violation end to end
  python -m archlens_llm.cli experiment [--split prompt_dev|held_out_test]
  python -m archlens_llm.cli freeze                     # S9 D41 freeze prompts/config/split
  python -m archlens_llm.cli rubric RUN_DIR --raters P2 P1
Add --config path/to/llm_config.json to use a real provider.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from .config import ROOT, load_config

FIX = ROOT / "fixtures" / "synthetic"
SPLIT = ROOT / "config" / "split.json"
LOCK = ROOT / "config" / "experiment.lock.json"


def _systems():
    return sorted(p.name for p in FIX.iterdir() if (p / "violation.json").exists())


def cmd_smoke(cfg, args):
    from .config import make_gateway
    from .ocr import ocr_components
    from .vlm_extraction import VLMExtractor
    from .service import classify_dependency_role
    run_dir = ROOT / "runs" / "smoke"
    gw = make_gateway(cfg, run_dir=run_dir)
    fails = []
    for s in _systems()[:5]:
        d = FIX / s
        comps = ocr_components(str(d / "diagram.png"), json.loads((d / "detections.json").read_text()))
        r = VLMExtractor(gw, mode="cv_vlm", fewshot=True).extract(s, str(d / "diagram.png"), comps)
        status = "FALLBACK" if r.fallback else "ok"
        print(f"{s:16s} {status:8s} " + ", ".join(f"{c.name or '?'}:{c.type}" for c in r.extraction.components))
        if r.fallback:
            fails.append({"system": s, "errors": r.model_errors})
    role = classify_dependency_role("OrderController", "OrderRepository", "imports", cfg=cfg, run_dir=str(run_dir))
    print("dependency_role:", role["role"])
    (run_dir / "smoke_failures.json").write_text(json.dumps(fails, indent=1))
    print(f"\nlog: {run_dir / 'llm_calls.jsonl'}   failures: {len(fails)}")


def cmd_audit(cfg, args):
    from .annotation import audit_annotations
    anns = [json.loads((FIX / s / "annotation.json").read_text()) for s in _systems()]
    print(json.dumps(audit_annotations(anns), indent=1))


def cmd_split(cfg, args):
    from .annotation import make_split
    print(json.dumps(make_split(_systems(), SPLIT), indent=1))


def cmd_demo(cfg, args):
    from .service import analyze_violation
    s = args.system or "S02_layered"
    pkg = json.loads((FIX / s / "violation.json").read_text())
    out = analyze_violation(pkg, cfg=cfg, run_dir=str(ROOT / "runs" / "demo"))
    print(json.dumps(out, indent=1))


def cmd_experiment(cfg, args):
    from .evaluation.runner import run
    if not SPLIT.exists():
        cmd_split(cfg, args)
    res = run(FIX, SPLIT, args.split, cfg, LOCK)
    print((ROOT / "runs" / res["exp_id"] / "results.md").read_text())


def cmd_freeze(cfg, args):
    from .evaluation.runner import freeze
    print(json.dumps(freeze(cfg, SPLIT, LOCK), indent=1))


def cmd_rubric(cfg, args):
    from .evaluation.rubric import make_sheet
    run_dir = Path(args.run_dir)
    sheet, key = make_sheet(json.loads((run_dir / "rca_all.json").read_text()), run_dir / "rubric_sheet.csv", args.raters)
    print(f"sheet: {sheet}\nkey (keep private until scoring is done): {key}")


def main(argv=None):
    ap = argparse.ArgumentParser(prog="archlens_llm")
    ap.add_argument("--config", default=None)
    sub = ap.add_subparsers(dest="cmd", required=True)
    for n in ("smoke", "audit", "split", "freeze"):
        sub.add_parser(n)
    p = sub.add_parser("demo"); p.add_argument("system", nargs="?")
    p = sub.add_parser("experiment"); p.add_argument("--split", default="prompt_dev", choices=["prompt_dev", "held_out_test"])
    p = sub.add_parser("rubric"); p.add_argument("run_dir"); p.add_argument("--raters", nargs="+", default=["P2", "P1"])
    args = ap.parse_args(argv)
    cfg = load_config(args.config)
    globals()[f"cmd_{args.cmd}"](cfg, args)


if __name__ == "__main__":
    sys.exit(main())
