"""Concrete providers. Pure stdlib HTTP so nothing extra has to be installed.

* GeminiProvider            -> Google Generative Language REST API (key: GEMINI_API_KEY)
* OpenAICompatibleProvider  -> anything speaking /v1/chat/completions:
                               Ollama (local), vLLM, LM Studio, OpenAI, Groq, Together...
* MockProvider              -> deterministic offline provider (see mock_provider.py)

Model names change often: they live in config/llm_config.json, never in code.
"""
from __future__ import annotations

import base64
import json
import mimetypes
import os
import time
import urllib.error
import urllib.request

from .base import LLMRequest, LLMResponse, ProviderError


def _b64(path: str) -> tuple[str, str]:
    mime = mimetypes.guess_type(path)[0] or "image/png"
    with open(path, "rb") as f:
        return mime, base64.b64encode(f.read()).decode()


def _post(url: str, payload: dict, headers: dict, timeout_s: float) -> dict:
    data = json.dumps(payload).encode()
    req = urllib.request.Request(url, data=data, headers={"Content-Type": "application/json", **headers})
    try:
        with urllib.request.urlopen(req, timeout=timeout_s) as r:
            return json.loads(r.read().decode())
    except urllib.error.HTTPError as e:
        body = e.read().decode(errors="replace")[:500]
        retryable = e.code in (408, 429, 500, 502, 503, 504)
        raise ProviderError(f"HTTP {e.code}: {body}", retryable=retryable) from e
    except (urllib.error.URLError, TimeoutError) as e:
        raise ProviderError(f"network: {e}", retryable=True) from e


class GeminiProvider:
    name = "gemini"
    supports_images = True

    def __init__(self, model: str, api_key_env: str = "GEMINI_API_KEY",
                 base_url: str = "https://generativelanguage.googleapis.com/v1beta"):
        self.model = model
        self.base_url = base_url.rstrip("/")
        self.api_key = os.environ.get(api_key_env, "")
        if not self.api_key:
            raise ProviderError(f"{api_key_env} is not set", retryable=False)

    def generate(self, req: LLMRequest, timeout_s: float) -> LLMResponse:
        parts: list[dict] = [{"text": req.prompt}]
        for p in req.images:
            mime, data = _b64(p)
            parts.append({"inline_data": {"mime_type": mime, "data": data}})
        gen_cfg = {"temperature": req.temperature, "maxOutputTokens": req.max_tokens}
        if req.json_mode:
            gen_cfg["responseMimeType"] = "application/json"
        payload = {"contents": [{"role": "user", "parts": parts}], "generationConfig": gen_cfg}
        if req.system:
            payload["systemInstruction"] = {"parts": [{"text": req.system}]}
        t0 = time.time()
        out = _post(f"{self.base_url}/models/{self.model}:generateContent",
                    payload, {"x-goog-api-key": self.api_key}, timeout_s)
        try:
            text = "".join(p.get("text", "") for p in out["candidates"][0]["content"]["parts"])
        except (KeyError, IndexError) as e:
            raise ProviderError(f"unexpected Gemini response: {str(out)[:300]}", retryable=True) from e
        usage = out.get("usageMetadata", {})
        return LLMResponse(text=text, provider=self.name, model=self.model,
                           input_tokens=usage.get("promptTokenCount", 0),
                           output_tokens=usage.get("candidatesTokenCount", 0),
                           latency_s=time.time() - t0,
                           finish_reason=out["candidates"][0].get("finishReason", ""), raw=out)


class OpenAICompatibleProvider:
    name = "openai_compatible"

    def __init__(self, model: str, base_url: str = "http://localhost:11434/v1",
                 api_key_env: str = "OPENAI_API_KEY", supports_images: bool = True,
                 json_response_format: bool = True):
        self.model = model
        self.base_url = base_url.rstrip("/")
        self.api_key = os.environ.get(api_key_env, "ollama")
        self.supports_images = supports_images
        self.json_response_format = json_response_format

    def generate(self, req: LLMRequest, timeout_s: float) -> LLMResponse:
        content: list[dict] | str
        if req.images:
            content = [{"type": "text", "text": req.prompt}]
            for p in req.images:
                mime, data = _b64(p)
                content.append({"type": "image_url", "image_url": {"url": f"data:{mime};base64,{data}"}})
        else:
            content = req.prompt
        messages = ([{"role": "system", "content": req.system}] if req.system else []) + \
                   [{"role": "user", "content": content}]
        payload = {"model": self.model, "messages": messages,
                   "temperature": req.temperature, "max_tokens": req.max_tokens}
        if req.seed is not None:
            payload["seed"] = req.seed
        if req.json_mode and self.json_response_format:
            payload["response_format"] = {"type": "json_object"}
        t0 = time.time()
        out = _post(f"{self.base_url}/chat/completions", payload,
                    {"Authorization": f"Bearer {self.api_key}"}, timeout_s)
        try:
            text = out["choices"][0]["message"]["content"] or ""
        except (KeyError, IndexError) as e:
            raise ProviderError(f"unexpected response: {str(out)[:300]}", retryable=True) from e
        usage = out.get("usage", {})
        return LLMResponse(text=text, provider=self.name, model=self.model,
                           input_tokens=usage.get("prompt_tokens", 0),
                           output_tokens=usage.get("completion_tokens", 0),
                           latency_s=time.time() - t0,
                           finish_reason=out["choices"][0].get("finish_reason", "") or "", raw=out)


def build_provider(cfg: dict):
    """cfg = config['provider'] block from config/llm_config.json."""
    kind = cfg.get("kind", "mock")
    if kind == "gemini":
        return GeminiProvider(model=cfg["model"], api_key_env=cfg.get("api_key_env", "GEMINI_API_KEY"))
    if kind == "openai_compatible":
        return OpenAICompatibleProvider(model=cfg["model"], base_url=cfg.get("base_url", "http://localhost:11434/v1"),
                                        api_key_env=cfg.get("api_key_env", "OPENAI_API_KEY"),
                                        supports_images=cfg.get("supports_images", True),
                                        json_response_format=cfg.get("json_response_format", True))
    if kind == "mock":
        from .mock_provider import MockProvider
        return MockProvider(faults=cfg.get("faults", []))
    raise ValueError(f"unknown provider kind: {kind}")
