"""Config loader + one-line gateway construction."""
from __future__ import annotations

import json
from pathlib import Path

from .gateway import LLMGateway, build_provider

ROOT = Path(__file__).resolve().parent.parent
DEFAULT_CONFIG = ROOT / "config" / "llm_config.json"


def load_config(path: str | Path | None = None) -> dict:
    return json.loads(Path(path or DEFAULT_CONFIG).read_text())


def make_gateway(cfg: dict | None = None, run_dir: str | Path = "runs/default", provider_override: dict | None = None) -> LLMGateway:
    cfg = cfg or load_config()
    g = cfg.get("gateway", {})
    provider = build_provider(provider_override or cfg["provider"])
    return LLMGateway(provider, run_dir=run_dir, cache=g.get("cache", True), max_retries=g.get("max_retries", 3),
                      timeout_s=g.get("timeout_s", 60), temperature=g.get("temperature", 0.0),
                      max_tokens=g.get("max_tokens", 8192))
