"""Human rubric (Design §10.3) for RCA / recommendation quality — Sprint 8 D40, Sprint 9 D44.

make_sheet()  -> CSV with one row per (output, rater), criteria blank, scored 1–5.
aggregate()   -> per-variant means + inter-rater agreement (exact, within-1, quadratic weighted kappa).
Raters must not see the variant name (column is hashed) to avoid bias.
"""
from __future__ import annotations

import csv
import hashlib
from collections import defaultdict
from pathlib import Path

CRITERIA = ["architecture_correctness", "evidence_grounding", "root_cause_accuracy", "actionability",
            "hallucination_free"]  # 5 = no hallucination


def _blind(variant: str, vid: str) -> str:
    return hashlib.sha256(f"{variant}|{vid}".encode()).hexdigest()[:10]


def make_sheet(rca_results: list[dict], out_csv: str | Path, raters: list[str], key_csv: str | Path | None = None):
    out_csv = Path(out_csv)
    key = []
    with out_csv.open("w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["item", "violation_id", "rater", "violation_explanation", "root_cause", "recommendation",
                    "cited_evidence"] + CRITERIA + ["comment"])
        for r in rca_results:
            o = r.get("output") or {}
            item = _blind(r["variant"], r["violation_id"])
            key.append((item, r["variant"], r["violation_id"]))
            for rater in raters:
                w.writerow([item, r["violation_id"], rater, o.get("violation_explanation", ""), o.get("root_cause", ""),
                            o.get("recommendation", ""), "; ".join(e["evidence_id"] for e in o.get("evidence", []))]
                           + [""] * len(CRITERIA) + [""])
    key_csv = Path(key_csv or out_csv.with_name(out_csv.stem + "_KEY_do_not_share.csv"))
    with key_csv.open("w", newline="") as f:
        csv.writer(f).writerows([("item", "variant", "violation_id")] + key)
    return out_csv, key_csv


def _qwk(a: list[int], b: list[int], lo=1, hi=5) -> float:
    n = hi - lo + 1
    if not a:
        return float("nan")
    O = [[0] * n for _ in range(n)]
    for x, y in zip(a, b):
        O[x - lo][y - lo] += 1
    ha = [sum(r) for r in O]
    hb = [sum(O[i][j] for i in range(n)) for j in range(n)]
    N = len(a)
    num = den = 0.0
    for i in range(n):
        for j in range(n):
            wgt = (i - j) ** 2 / (n - 1) ** 2
            num += wgt * O[i][j]
            den += wgt * ha[i] * hb[j] / N
    return 1.0 if den == 0 else round(1 - num / den, 3)


def aggregate(filled_csv: str | Path, key_csv: str | Path) -> dict:
    key = {row["item"]: row["variant"] for row in csv.DictReader(open(key_csv))}
    by_variant = defaultdict(lambda: defaultdict(list))
    by_item = defaultdict(dict)
    for row in csv.DictReader(open(filled_csv)):
        v = key[row["item"]]
        for c in CRITERIA:
            if row[c].strip():
                s = int(row[c])
                by_variant[v][c].append(s)
                by_item[(row["item"], c)][row["rater"]] = s
    means = {v: {c: round(sum(x) / len(x), 2) for c, x in cs.items()} for v, cs in by_variant.items()}
    raters = sorted({r for d in by_item.values() for r in d})
    agree = {}
    if len(raters) >= 2:
        r1, r2 = raters[:2]
        for c in CRITERIA:
            pairs = [(d[r1], d[r2]) for (it, cc), d in by_item.items() if cc == c and r1 in d and r2 in d]
            if pairs:
                agree[c] = {"exact": round(sum(a == b for a, b in pairs) / len(pairs), 2),
                            "within_1": round(sum(abs(a - b) <= 1 for a, b in pairs) / len(pairs), 2),
                            "qwk": _qwk([a for a, _ in pairs], [b for _, b in pairs]), "n": len(pairs)}
    return {"means_by_variant": means, "inter_rater": agree, "raters": raters}
