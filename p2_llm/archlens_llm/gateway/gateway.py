"""LLM Gateway: retries, timeouts, caching, logging and structured (schema-validated) calls.

Rule from the sprint plan: "Keep every model output structured and validated.
Store raw output, parsed output, prompt/model version and evaluation result."

Every attempt is appended to runs/<run_id>/llm_calls.jsonl.
"""
from __future__ import annotations

import hashlib
import json
import time
import uuid
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Optional, Type

from pydantic import BaseModel, ValidationError

from ..jsonutil import extract_json
from ..prompts import render
from .base import LLMRequest, LLMResponse, ProviderError

Validator = Callable[[BaseModel], list[str]]  # returns list of semantic errors


@dataclass
class StructuredResult:
    ok: bool
    parsed: Optional[BaseModel]
    abstained: bool
    attempts: int
    errors: list[str] = field(default_factory=list)
    raw_outputs: list[str] = field(default_factory=list)
    prompt_name: str = ""
    prompt_version: str = ""
    model: str = ""
    input_tokens: int = 0
    output_tokens: int = 0


class LLMGateway:
    def __init__(self, provider, run_dir: str | Path = "runs/default", cache: bool = True,
                 max_retries: int = 3, timeout_s: float = 60.0, temperature: float = 0.0,
                 backoff_s: float = 1.5, max_tokens: int = 8192):
        self.provider = provider
        self.max_tokens = max_tokens
        self.run_dir = Path(run_dir)
        self.run_dir.mkdir(parents=True, exist_ok=True)
        self.log_path = self.run_dir / "llm_calls.jsonl"
        self.cache_dir = self.run_dir / "cache" if cache else None
        if self.cache_dir:
            self.cache_dir.mkdir(exist_ok=True)
        self.max_retries = max_retries
        self.timeout_s = timeout_s
        self.temperature = temperature
        self.backoff_s = backoff_s
        self.totals = {"calls": 0, "input_tokens": 0, "output_tokens": 0, "cache_hits": 0}

    # ------------------------------------------------------------------ raw
    def _cache_key(self, req: LLMRequest) -> str:
        h = hashlib.sha256()
        h.update(f"{self.provider.name}|{self.provider.model}|{req.temperature}|{req.system}|{req.prompt}".encode())
        for p in req.images:
            h.update(Path(p).read_bytes())
        return h.hexdigest()[:32]

    def generate(self, req: LLMRequest) -> LLMResponse:
        if req.images and not getattr(self.provider, "supports_images", False):
            raise ProviderError(f"provider {self.provider.name}/{self.provider.model} has no image input",
                                retryable=False)
        key = self._cache_key(req)
        if self.cache_dir and (self.cache_dir / f"{key}.json").exists():
            d = json.loads((self.cache_dir / f"{key}.json").read_text())
            self.totals["cache_hits"] += 1
            return LLMResponse(**{**d, "cached": True, "raw": {}})
        last: Exception | None = None
        for attempt in range(self.max_retries):
            try:
                resp = self.provider.generate(req, self.timeout_s)
                self.totals["calls"] += 1
                self.totals["input_tokens"] += resp.input_tokens
                self.totals["output_tokens"] += resp.output_tokens
                if self.cache_dir:
                    d = {k: v for k, v in resp.__dict__.items() if k not in ("raw", "cached")}
                    (self.cache_dir / f"{key}.json").write_text(json.dumps(d))
                return resp
            except ProviderError as e:
                last = e
                if not e.retryable:
                    break
                time.sleep(self.backoff_s * (2 ** attempt))
        raise ProviderError(f"provider failed after retries: {last}", retryable=False)

    # ----------------------------------------------------------- structured
    def structured(self, prompt_name: str, variables: dict[str, Any], schema: Type[BaseModel],
                   validator: Validator | None = None, images: list[str] | None = None,
                   max_repairs: int = 2, task: str = "", meta: dict | None = None) -> StructuredResult:
        """Render prompt -> call -> parse -> schema-validate -> semantic-validate.

        On failure, send a repair prompt containing the exact errors (max_repairs times),
        then abstain. Abstention is a first-class outcome: callers map it to UNCERTAIN.
        """
        system, prompt, version = render(prompt_name, variables)
        res = StructuredResult(ok=False, parsed=None, abstained=False, attempts=0,
                               prompt_name=prompt_name, prompt_version=version,
                               model=f"{self.provider.name}/{self.provider.model}")
        current_prompt = prompt
        for attempt in range(max_repairs + 1):
            res.attempts += 1
            req = LLMRequest(prompt=current_prompt, system=system, images=images or [],
                             temperature=self.temperature, max_tokens=self.max_tokens)
            try:
                resp = self.generate(req)
            except ProviderError as e:
                res.errors.append(f"provider: {e}")
                self._log(task, prompt_name, version, None, None, [str(e)], attempt, meta)
                break
            res.raw_outputs.append(resp.text)
            res.input_tokens += resp.input_tokens
            res.output_tokens += resp.output_tokens
            errors: list[str] = []
            obj, steps = extract_json(resp.text)
            parsed = None
            if obj is None:
                errors.append("output is not valid JSON (" + ", ".join(steps) + ")")
            else:
                try:
                    parsed = schema.model_validate(obj)
                except ValidationError as e:
                    errors += [f"schema: {'.'.join(map(str, er['loc']))}: {er['msg']}" for er in e.errors()[:12]]
            if parsed is not None and validator is not None:
                errors += validator(parsed)
            self._log(task, prompt_name, version, resp, parsed, errors, attempt, meta, steps)
            if not errors:
                res.ok, res.parsed = True, parsed
                return res
            res.errors = errors
            _, current_prompt, _ = render("repair", {
                "original_prompt": prompt, "previous_output": resp.text[:6000],
                "errors": "\n".join(f"- {e}" for e in errors),
                "schema": json.dumps(schema.model_json_schema(), indent=1)[:6000],
            })
        res.abstained = True
        return res

    def _log(self, task, prompt_name, version, resp, parsed, errors, attempt, meta, steps=None):
        rec = {
            "ts": time.strftime("%Y-%m-%dT%H:%M:%S"), "call_id": uuid.uuid4().hex[:12], "task": task,
            "prompt": prompt_name, "prompt_version": version, "attempt": attempt,
            "provider": getattr(self.provider, "name", "?"), "model": getattr(self.provider, "model", "?"),
            "temperature": self.temperature,
            "raw_output": resp.text if resp else None,
            "parsed_output": parsed.model_dump() if parsed is not None else None,
            "json_repair_steps": steps or [], "errors": errors, "valid": not errors,
            "input_tokens": resp.input_tokens if resp else 0,
            "output_tokens": resp.output_tokens if resp else 0,
            "latency_s": round(resp.latency_s, 3) if resp else 0, "cached": resp.cached if resp else False,
            "finish_reason": resp.finish_reason if resp else "",
            "meta": meta or {},
        }
        with self.log_path.open("a") as f:
            f.write(json.dumps(rec) + "\n")
