"""
Sprint 6 / D28: test the name-matching module against real repository
directory listings - manually verified examples, not synthetic names.

Uses two of our real diagram<->repository pairs where the paired repo's
real service directory names were fetched via the GitHub API:

- GoogleCloudPlatform/microservices-demo: src/{adservice, cartservice,
  checkoutservice, currencyservice, emailservice, frontend, loadgenerator,
  paymentservice, productcatalogservice, recommendationservice,
  shippingservice, shoppingassistantservice}
- GoogleCloudPlatform/bank-of-anthos: src/accounts/{accounts-db, contacts,
  userservice}, src/ledger/{balancereader, ledger-db, ledgerwriter,
  transactionhistory}, src/frontend, src/loadgenerator

Each match below was manually checked against the real diagram and the
real repository tree (both linked in data/annotations/manifest.json's
source_repository block) before being counted correct/incorrect.

Run from the backend/ directory: ../venv/Scripts/python.exe scripts/test_graph_alignment.py
"""

import json
import sys
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND_DIR))

from app.modules.cv_pipeline.dataset_manifest import load_manifest  # noqa: E402
from app.modules.cv_pipeline.name_matching import best_match  # noqa: E402

REPO_ROOT = BACKEND_DIR.parent
OUT_PATH = REPO_ROOT / "experiments" / "baselines" / "sprint6_graph_alignment.json"

# Real directory listings, fetched via GitHub API (see docstring above).
REAL_CODE_IDENTIFIERS = {
    "gcp_microservices_demo": [
        "adservice", "cartservice", "checkoutservice", "currencyservice",
        "emailservice", "frontend", "loadgenerator", "paymentservice",
        "productcatalogservice", "recommendationservice", "shippingservice",
        "shoppingassistantservice",
    ],
    "gcp_bank_of_anthos": [
        "accounts-db", "contacts", "userservice", "balancereader", "ledger-db",
        "ledgerwriter", "transactionhistory", "frontend", "loadgenerator",
    ],
}

# Manually verified expected matches (diagram component id -> expected real
# code identifier, or None if there is genuinely no corresponding directory).
EXPECTED_MATCHES = {
    "gcp_microservices_demo": {
        "ad": "adservice", "cart": "cartservice", "checkout": "checkoutservice",
        "currency": "currencyservice", "email": "emailservice", "frontend": "frontend",
        "loadgenerator": "loadgenerator", "payment": "paymentservice",
        "productcatalog": "productcatalogservice", "recommendation": "recommendationservice",
        "shipping": "shippingservice",
        "rediscache": None,  # Redis is infra, not a service directory in src/
    },
    "gcp_bank_of_anthos": {
        "loadgen": "loadgenerator", "frontend": "frontend", "userservice": "userservice",
        "contacts": "contacts", "ledgerwriter": "ledgerwriter", "balancereader": "balancereader",
        "transactionhistory": "transactionhistory", "accountsdb": "accounts-db", "ledgerdb": "ledger-db",
    },
}


def main():
    graphs = {g.id: g for g in load_manifest()}
    results = []
    correct = 0
    total = 0

    for diagram_id, expected in EXPECTED_MATCHES.items():
        g = graphs[diagram_id]
        candidates = REAL_CODE_IDENTIFIERS[diagram_id]
        for c in g.components:
            if c.id not in expected:
                continue
            total += 1
            match = best_match(c.name, candidates, component_type=c.type.value)
            predicted = match.code_identifier if match else None
            is_correct = predicted == expected[c.id]
            correct += is_correct
            results.append({
                "diagram_id": diagram_id,
                "component_id": c.id,
                "component_name": c.name,
                "expected": expected[c.id],
                "predicted": predicted,
                "score": match.score if match else 0.0,
                "correct": is_correct,
            })
            marker = "OK" if is_correct else "WRONG"
            print(f"[{marker}] {diagram_id}/{c.id} ({c.name!r}) -> predicted={predicted!r} "
                  f"(score={match.score if match else 0.0:.2f}), expected={expected[c.id]!r}")

    accuracy = correct / total if total else 0.0
    OUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    OUT_PATH.write_text(json.dumps({
        "accuracy": round(accuracy, 4),
        "correct": correct,
        "total": total,
        "results": results,
    }, indent=2), encoding="utf-8")
    print(f"\nAccuracy on manually verified examples: {correct}/{total} = {accuracy:.4f}")
    print(f"Wrote {OUT_PATH}")


if __name__ == "__main__":
    main()
