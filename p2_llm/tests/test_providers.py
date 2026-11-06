"""Provider payloads/usage parsing (no network): guards the real-API code paths we cannot hit in CI."""
import pytest

from archlens_llm.gateway import LLMRequest, ProviderError
from archlens_llm.gateway import providers as P
from conftest import FIX


def test_gemini_payload_and_usage(monkeypatch):
    monkeypatch.setenv("GEMINI_API_KEY", "k")
    seen = {}

    def fake_post(url, payload, headers, timeout_s):
        seen.update(url=url, payload=payload, headers=headers)
        return {"candidates": [{"content": {"parts": [{"text": '{"a":1}'}]}}],
                "usageMetadata": {"promptTokenCount": 11, "candidatesTokenCount": 3}}
    monkeypatch.setattr(P, "_post", fake_post)
    pr = P.GeminiProvider(model="m-test")
    r = pr.generate(LLMRequest(prompt="hi", system="sys", images=[str(FIX / "S01_shop" / "diagram.png")]), 5)
    assert r.text == '{"a":1}' and r.input_tokens == 11 and r.output_tokens == 3
    assert seen["url"].endswith("/models/m-test:generateContent") and seen["headers"]["x-goog-api-key"] == "k"
    parts = seen["payload"]["contents"][0]["parts"]
    assert parts[1]["inline_data"]["mime_type"] == "image/png"
    assert seen["payload"]["generationConfig"]["responseMimeType"] == "application/json"
    assert seen["payload"]["systemInstruction"]["parts"][0]["text"] == "sys"


def test_gateway_max_tokens_and_finish_reason(monkeypatch, tmp_path):
    import json
    from archlens_llm.gateway import LLMGateway
    from archlens_llm.schemas import DependencyRole
    monkeypatch.setenv("GEMINI_API_KEY", "k")
    seen = {}
    answer = {"source_role": "Controller", "target_role": "Repository",
              "architectural_meaning": "layer skip", "confidence": 0.9}

    def fake_post(url, payload, headers, timeout_s):
        seen.update(payload=payload)
        return {"candidates": [{"content": {"parts": [{"text": json.dumps(answer)}]}, "finishReason": "STOP"}],
                "usageMetadata": {"promptTokenCount": 11, "candidatesTokenCount": 3}}
    monkeypatch.setattr(P, "_post", fake_post)
    gw = LLMGateway(P.GeminiProvider(model="m-test"), run_dir=tmp_path, cache=False, max_tokens=8192)
    r = gw.structured("dependency_role", {"input_json": {"source": "a", "target": "b"}}, DependencyRole)
    assert r.ok
    assert seen["payload"]["generationConfig"]["maxOutputTokens"] == 8192
    rec = json.loads((tmp_path / "llm_calls.jsonl").read_text().splitlines()[-1])
    assert rec["finish_reason"] == "STOP"


def test_gemini_requires_key(monkeypatch):
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    with pytest.raises(ProviderError):
        P.GeminiProvider(model="m")


def test_openai_compatible_payload(monkeypatch):
    seen = {}

    def fake_post(url, payload, headers, timeout_s):
        seen.update(url=url, payload=payload)
        return {"choices": [{"message": {"content": "{}"}}], "usage": {"prompt_tokens": 5, "completion_tokens": 1}}
    monkeypatch.setattr(P, "_post", fake_post)
    pr = P.OpenAICompatibleProvider(model="qwen", base_url="http://localhost:11434/v1")
    r = pr.generate(LLMRequest(prompt="hi", images=[str(FIX / "S01_shop" / "diagram.png")]), 5)
    assert seen["url"] == "http://localhost:11434/v1/chat/completions" and r.input_tokens == 5
    content = seen["payload"]["messages"][-1]["content"]
    assert content[1]["image_url"]["url"].startswith("data:image/png;base64,")
    assert seen["payload"]["response_format"] == {"type": "json_object"}


def test_text_only_provider_rejects_images(tmp_path):
    from archlens_llm.gateway import LLMGateway
    gw = LLMGateway(P.OpenAICompatibleProvider(model="x", supports_images=False), run_dir=tmp_path)
    with pytest.raises(ProviderError):
        gw.generate(LLMRequest(prompt="p", images=[str(FIX / "S01_shop" / "diagram.png")]))
