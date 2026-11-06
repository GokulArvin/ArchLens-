"""Local (no-LLM) JSON extraction and repair. Sprint 1 D3: JSON validation strategy.

Strategy, cheapest first:
  1. parse as-is
  2. strip markdown fences / prose around the outermost {...} or [...]
  3. fix common LLM mistakes: trailing commas, smart quotes, Python literals
  4. give up -> caller sends a repair prompt (gateway) -> caller abstains
"""
from __future__ import annotations

import json
import re
from typing import Any

_FENCE = re.compile(r"```(?:json)?\s*(.*?)```", re.S | re.I)
_TRAILING_COMMA = re.compile(r",\s*([}\]])")


def _outermost(text: str) -> str | None:
    starts = [i for i in (text.find("{"), text.find("[")) if i != -1]
    if not starts:
        return None
    start = min(starts)
    open_ch = text[start]
    close_ch = "}" if open_ch == "{" else "]"
    depth, in_str, esc = 0, False, False
    for i in range(start, len(text)):
        ch = text[i]
        if in_str:
            if esc:
                esc = False
            elif ch == "\\":
                esc = True
            elif ch == '"':
                in_str = False
            continue
        if ch == '"':
            in_str = True
        elif ch == open_ch:
            depth += 1
        elif ch == close_ch:
            depth -= 1
            if depth == 0:
                return text[start:i + 1]
    return None  # truncated output


def _light_fix(s: str) -> str:
    s = s.replace("“", '"').replace("”", '"').replace("’", "'")
    s = _TRAILING_COMMA.sub(r"\1", s)
    s = re.sub(r"\bNone\b", "null", s)
    s = re.sub(r"\bTrue\b", "true", s)
    s = re.sub(r"\bFalse\b", "false", s)
    return s


def extract_json(text: str) -> tuple[Any | None, list[str]]:
    """Return (obj, repair_steps). obj is None if nothing parseable was found."""
    steps: list[str] = []
    if text is None:
        return None, ["empty"]
    try:
        return json.loads(text), steps
    except (json.JSONDecodeError, TypeError):
        pass
    m = _FENCE.search(text)
    candidate = m.group(1) if m else text
    if m:
        steps.append("strip_fence")
    inner = _outermost(candidate)
    if inner is None:
        return None, steps + ["no_json_object"]
    if inner != candidate.strip():
        steps.append("strip_prose")
    try:
        return json.loads(inner), steps
    except json.JSONDecodeError:
        pass
    fixed = _light_fix(inner)
    try:
        return json.loads(fixed), steps + ["light_fix"]
    except json.JSONDecodeError as e:
        return None, steps + [f"unparseable: {e.msg}"]
