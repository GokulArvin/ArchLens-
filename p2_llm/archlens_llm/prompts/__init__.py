"""Versioned prompt templates (Sprint 1 D3).

Each template file has a header, a SYSTEM block and a USER block. The effective
version is "<declared version>+<sha256[:8] of file>", so editing a prompt
without bumping the version is still detectable by the experiment freeze check.
"""
from __future__ import annotations

import hashlib
import json
from functools import lru_cache
from pathlib import Path
from string import Template
from typing import Any

PROMPT_DIR = Path(__file__).parent


@lru_cache(maxsize=None)
def _load(name: str) -> tuple[str, str, str]:
    path = PROMPT_DIR / f"{name}.txt"
    text = path.read_text()
    declared = "0"
    for line in text.splitlines():
        if line.startswith("# version:"):
            declared = line.split(":", 1)[1].strip()
    sha = hashlib.sha256(text.encode()).hexdigest()[:8]
    system = text.split("=== SYSTEM ===", 1)[1].split("=== USER ===", 1)[0].strip() if "=== SYSTEM ===" in text else ""
    user = text.split("=== USER ===", 1)[1].strip()
    return system, user, f"{declared}+{sha}"


def render(name: str, variables: dict[str, Any]) -> tuple[str, str, str]:
    system, user, version = _load(name)
    vals = {k: (json.dumps(v, indent=1) if isinstance(v, (dict, list)) else str(v)) for k, v in variables.items()}
    return Template(system).substitute(vals), Template(user).substitute(vals), version


def all_prompt_versions() -> dict[str, str]:
    return {p.stem: _load(p.stem)[2] for p in sorted(PROMPT_DIR.glob("*.txt"))}
