"""Provider-agnostic interface (Sprint 1 D4). The rest of ArchLens only sees these types."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Protocol


@dataclass
class LLMRequest:
    prompt: str
    system: str = ""
    images: list[str] = field(default_factory=list)   # file paths (PNG/JPEG)
    temperature: float = 0.0
    max_tokens: int = 2048
    json_mode: bool = True
    seed: int | None = 7


@dataclass
class LLMResponse:
    text: str
    provider: str
    model: str
    input_tokens: int = 0
    output_tokens: int = 0
    latency_s: float = 0.0
    cached: bool = False
    finish_reason: str = ""
    raw: dict = field(default_factory=dict)


class LLMProvider(Protocol):
    name: str
    model: str
    supports_images: bool

    def generate(self, req: LLMRequest, timeout_s: float) -> LLMResponse: ...


class ProviderError(RuntimeError):
    """Raised for transport/API failures; the gateway retries these."""

    def __init__(self, msg: str, retryable: bool = True):
        super().__init__(msg)
        self.retryable = retryable
