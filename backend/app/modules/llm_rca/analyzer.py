
"""
Module F: Evidence-Grounded LLM Root Cause Analysis.

The LLM explains architecture violations using supplied evidence.
The deterministic ConformanceEngine remains the sole authority
for determining conformance verdicts.

Features:
- OpenAI, Gemini, Anthropic and local Ollama support
- Configurable timeout and retry handling
- In-memory response caching with TTL
- Evidence ID validation
- Structured RCA output validation
- Provider/model/prompt metadata
- Safe fallback when evidence or LLM services are unavailable
"""

import hashlib
import json
import logging
import time

from typing import Any, Dict, Optional

from tenacity import (
    Retrying,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)

from app.core.config import settings


logger = logging.getLogger(__name__)

PROMPT_VERSION = "1.0.0"


# ---------------------------------------------------------
# PROMPTS
# ---------------------------------------------------------

SYSTEM_PROMPT = """
You are an expert software architecture root cause analysis assistant.

Your responsibility is to explain architecture violations using
ONLY the evidence supplied to you.

IMPORTANT RULES:

1. The deterministic ConformanceEngine has already determined
   the architecture violation. You must not change its verdict.

2. Do not invent files, dependencies, commits, architectural
   rules, code changes, or relationships.

3. Do not claim that a commit caused a violation unless the
   supplied evidence supports that conclusion.

4. Every factual claim in your explanation and root cause must
   be supported by supplied evidence IDs.

5. The evidence field MUST contain only valid evidence IDs
   provided in the evidence package.

6. If evidence is insufficient, explicitly state that the
   root cause cannot be determined from the available evidence.

7. Distinguish confirmed facts from possible explanations.

8. Return valid JSON only. Do not include Markdown or code fences.
"""


RCA_USER_PROMPT_TEMPLATE = """
# ArchLens Root Cause Analysis

## Intended Architecture
{intended_architecture}

## Current Architecture
{current_architecture}

## Detected Violation
{violation}

## Dependency Path
{dependency_path}

## Architecture Rule
{architecture_rule}

## Git Commit
{git_commit}

## Relevant Diff
{diff}

## Source Code Context
{code_context}

## Available Evidence

The following evidence items are the ONLY sources you may cite:

{evidence_items}

## Your Tasks

1. Explain the detected architecture violation.
2. Identify the most likely root cause, if supported by evidence.
3. Identify affected architectural components.
4. Cite evidence IDs supporting your claims.
5. Recommend a corrective action consistent with the intended architecture.
6. If the evidence is insufficient, clearly say so rather than guessing.

Return ONLY valid JSON matching this schema:

{{
    "violation_explanation": "string",
    "root_cause": "string",
    "evidence": ["E001", "E002"],
    "affected_components": ["component_name"],
    "recommendation": "string",
    "confidence": 0.0
}}

IMPORTANT:
- Evidence must contain only supplied evidence IDs.
- Do not invent evidence IDs.
- Confidence must be a number between 0.0 and 1.0.
- Use an empty evidence list if no evidence supports the analysis.
"""


# ---------------------------------------------------------
# LLM GATEWAY
# ---------------------------------------------------------

class LLMGateway:
    """
    Gateway for supported LLM providers.

    Supports:
    - OpenAI
    - Google Gemini
    - Anthropic
    - Ollama through its OpenAI-compatible local API

    Includes timeout, retry and in-memory caching.
    """

    def __init__(
        self,
        provider: Optional[str] = None,
        model: Optional[str] = None,
        api_key: Optional[str] = None,
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None,
        timeout: Optional[int] = None,
        max_retries: Optional[int] = None,
        cache_enabled: Optional[bool] = None,
        cache_ttl: Optional[int] = None,
    ):

        self.provider = (
            provider or settings.LLM_PROVIDER
        ).lower()

        self.model = model or settings.LLM_MODEL

        self.api_key = (
            api_key or self._get_configured_api_key()
        )

        self.temperature = (
            settings.LLM_TEMPERATURE
            if temperature is None
            else temperature
        )

        self.max_tokens = (
            settings.LLM_MAX_TOKENS
            if max_tokens is None
            else max_tokens
        )

        self.timeout = (
            settings.LLM_TIMEOUT_SECONDS
            if timeout is None
            else timeout
        )

        self.max_retries = (
            settings.LLM_MAX_RETRIES
            if max_retries is None
            else max_retries
        )

        self.cache_enabled = (
            settings.LLM_CACHE_ENABLED
            if cache_enabled is None
            else cache_enabled
        )

        self.cache_ttl = (
            settings.LLM_CACHE_TTL_SECONDS
            if cache_ttl is None
            else cache_ttl
        )

        self._client = None

        # Cache format:
        # {request_hash: (creation_timestamp, response)}
        self._cache: Dict[str, tuple] = {}

        self.last_cache_hit = False

    def _get_configured_api_key(self) -> Optional[str]:
        """Read the API key for the selected provider."""

        if self.provider == "openai":
            return settings.OPENAI_API_KEY or None

        if self.provider == "gemini":
            return settings.GOOGLE_API_KEY or None

        if self.provider == "anthropic":
            return settings.ANTHROPIC_API_KEY or None

        if self.provider == "ollama":
            # Ollama serves locally and does not require an API key.
            return "ollama"

        raise ValueError(
            f"Unsupported LLM provider: {self.provider}"
        )

    def _get_client(self):
        """Initialize the provider client only when needed."""

        if self._client is not None:
            return self._client

        if not self.api_key and self.provider != "ollama":
            raise RuntimeError(
                f"No API key configured for provider: {self.provider}"
            )

        if self.provider in {"openai", "ollama"}:
            from openai import OpenAI

            client_options = {
                "api_key": self.api_key,
                "timeout": self.timeout,
                "max_retries": 0,
            }
            if self.provider == "ollama":
                client_options["base_url"] = settings.OLLAMA_BASE_URL

            self._client = OpenAI(**client_options)

        elif self.provider == "gemini":
            import google.generativeai as genai

            genai.configure(api_key=self.api_key)

            self._client = genai.GenerativeModel(
                self.model,
                generation_config={
                    "temperature": self.temperature,
                    "max_output_tokens": self.max_tokens,
                    "response_mime_type": "application/json",
                },
            )

        elif self.provider == "anthropic":
            import anthropic

            self._client = anthropic.Anthropic(
                api_key=self.api_key,
                timeout=self.timeout,
                max_retries=0,
            )

        else:
            raise ValueError(
                f"Unknown LLM provider: {self.provider}"
            )

        return self._client

    def _get_cache_key(
        self,
        system_prompt: str,
        user_prompt: str
    ) -> str:

        request_content = json.dumps(
            {
                "provider": self.provider,
                "model": self.model,
                "temperature": self.temperature,
                "max_tokens": self.max_tokens,
                "system_prompt": system_prompt,
                "user_prompt": user_prompt,
                "prompt_version": PROMPT_VERSION,
            },
            sort_keys=True,
        )

        return hashlib.sha256(
            request_content.encode("utf-8")
        ).hexdigest()

    def _get_cached_response(
        self,
        cache_key: str
    ) -> Optional[str]:

        if not self.cache_enabled:
            return None

        cached = self._cache.get(cache_key)

        if cached is None:
            return None

        created_at, response = cached

        if time.time() - created_at > self.cache_ttl:
            del self._cache[cache_key]
            return None

        return response

    def _save_cached_response(
        self,
        cache_key: str,
        response: str
    ) -> None:

        if not self.cache_enabled:
            return

        self._cache[cache_key] = (
            time.time(),
            response
        )

    def _call_once(
        self,
        system_prompt: str,
        user_prompt: str
    ) -> str:
        """Perform one provider API request."""

        client = self._get_client()

        if self.provider in {"openai", "ollama"}:

            response = client.chat.completions.create(
                model=self.model,
                messages=[
                    {
                        "role": "system",
                        "content": system_prompt,
                    },
                    {
                        "role": "user",
                        "content": user_prompt,
                    },
                ],
                temperature=self.temperature,
                max_tokens=self.max_tokens,
                response_format={
                    "type": "json_object"
                },
            )

            content = response.choices[0].message.content

            if not content:
                raise ValueError(
                    f"{self.provider.capitalize()} returned an empty response."
                )

            return content

        elif self.provider == "gemini":

            full_prompt = (
                system_prompt + "\n\n" + user_prompt
            )

            response = client.generate_content(
                full_prompt,
                request_options={
                    "timeout": self.timeout
                },
            )

            if not response.text:
                raise ValueError(
                    "Gemini returned an empty response."
                )

            return response.text

        elif self.provider == "anthropic":

            response = client.messages.create(
                model=self.model,
                max_tokens=self.max_tokens,
                temperature=self.temperature,
                system=system_prompt,
                messages=[
                    {
                        "role": "user",
                        "content": user_prompt,
                    }
                ],
            )

            if not response.content:
                raise ValueError(
                    "Anthropic returned an empty response."
                )

            return response.content[0].text

        raise ValueError(
            f"Unsupported provider: {self.provider}"
        )

    def call(
        self,
        system_prompt: str,
        user_prompt: str
    ) -> str:
        """Call the LLM with caching and retry handling."""

        cache_key = self._get_cache_key(
            system_prompt,
            user_prompt
        )

        self.last_cache_hit = False

        cached_response = self._get_cached_response(
            cache_key
        )

        if cached_response is not None:
            self.last_cache_hit = True
            logger.info("LLM cache hit")
            return cached_response

        retry_count = max(1, int(self.max_retries))

        retryer = Retrying(
            stop=stop_after_attempt(retry_count),
            wait=wait_exponential(
                multiplier=1,
                min=2,
                max=10,
            ),
            retry=retry_if_exception_type(Exception),
            reraise=True,
        )

        response = retryer(
            lambda: self._call_once(
                system_prompt,
                user_prompt
            )
        )

        self._save_cached_response(
            cache_key,
            response
        )

        return response


# ---------------------------------------------------------
# RCA ANALYZER
# ---------------------------------------------------------

class RCAAnalyzer:
    """
    Evidence-grounded root cause analysis.

    If no explicit gateway is supplied, a configured gateway
    is created automatically when provider credentials exist, or
    when the selected provider is local Ollama.
    """

    def __init__(
        self,
        llm_gateway: Optional[LLMGateway] = None
    ):

        self.llm = llm_gateway

        if self.llm is None:
            try:
                configured_key = (
                    settings.OPENAI_API_KEY
                    if settings.LLM_PROVIDER.lower() == "openai"
                    else settings.GOOGLE_API_KEY
                    if settings.LLM_PROVIDER.lower() == "gemini"
                    else settings.ANTHROPIC_API_KEY
                    if settings.LLM_PROVIDER.lower() == "anthropic"
                    else "ollama"
                    if settings.LLM_PROVIDER.lower() == "ollama"
                    else None
                )

                if configured_key:
                    self.llm = LLMGateway()

            except Exception as exc:
                logger.warning(
                    "Could not initialize LLM gateway: %s",
                    exc
                )

    # -----------------------------------------------------
    # PROMPT CONSTRUCTION
    # -----------------------------------------------------

    def _build_prompt(
        self,
        evidence_package: Dict[str, Any]
    ) -> str:

        violation = evidence_package.get(
            "violation", {}
        )

        evidence_items = evidence_package.get(
            "evidence_items", []
        )

        code_context = evidence_package.get(
            "code_context",
            evidence_package.get("code", {})
        )

        return RCA_USER_PROMPT_TEMPLATE.format(
            intended_architecture=json.dumps(
                evidence_package.get(
                    "intended_architecture",
                    evidence_package.get(
                        "architecture_rule", {}
                    )
                ),
                indent=2,
                default=str
            ),

            current_architecture=json.dumps(
                evidence_package.get(
                    "current_architecture",
                    {}
                ),
                indent=2,
                default=str
            ),

            violation=json.dumps(
                violation,
                indent=2,
                default=str
            ),

            dependency_path=" -> ".join(
                evidence_package.get(
                    "dependency_path", []
                )
            ),

            architecture_rule=json.dumps(
                evidence_package.get(
                    "architecture_rule", {}
                ),
                indent=2,
                default=str
            ),

            git_commit=json.dumps(
                evidence_package.get(
                    "commit", {}
                ),
                indent=2,
                default=str
            ),

            diff=evidence_package.get(
                "diff",
                "No diff available"
            ),

            code_context=json.dumps(
                code_context,
                indent=2,
                default=str
            ),

            evidence_items=json.dumps(
                evidence_items,
                indent=2,
                default=str
            ),
        )

    # -----------------------------------------------------
    # EVIDENCE VALIDATION
    # -----------------------------------------------------

    @staticmethod
    def _validate_evidence_references(
        rca: Dict[str, Any],
        evidence_package: Dict[str, Any]
    ) -> None:
        """
        Ensure every evidence ID cited by the LLM exists
        in the supplied evidence package.
        """

        evidence_items = evidence_package.get(
            "evidence_items", []
        )

        valid_ids = {
            item.get("evidence_id")
            for item in evidence_items
            if isinstance(item, dict)
            and item.get("evidence_id")
        }

        cited_evidence = rca.get("evidence")

        if not isinstance(cited_evidence, list):
            raise ValueError(
                "RCA evidence must be a list of evidence IDs."
            )

        invalid_ids = [
            evidence_id
            for evidence_id in cited_evidence
            if not isinstance(evidence_id, str)
            or evidence_id not in valid_ids
        ]

        if invalid_ids:
            raise ValueError(
                f"LLM referenced invalid evidence IDs: {invalid_ids}"
            )

    # -----------------------------------------------------
    # RCA OUTPUT VALIDATION
    # -----------------------------------------------------

    @staticmethod
    def _validate_rca(
        rca: Dict[str, Any]
    ) -> None:

        required = [
            "violation_explanation",
            "root_cause",
            "evidence",
            "affected_components",
            "recommendation",
            "confidence",
        ]

        for field in required:
            if field not in rca:
                raise ValueError(
                    f"Missing required RCA field: {field}"
                )

        string_fields = [
            "violation_explanation",
            "root_cause",
            "recommendation",
        ]

        for field in string_fields:
            if not isinstance(rca[field], str):
                raise ValueError(
                    f"RCA field '{field}' must be a string."
                )

        if not isinstance(rca["evidence"], list):
            raise ValueError(
                "RCA evidence must be a list."
            )

        if not isinstance(
            rca["affected_components"], list
        ):
            raise ValueError(
                "Affected components must be a list."
            )

        confidence = rca["confidence"]

        if (
            isinstance(confidence, bool)
            or not isinstance(confidence, (int, float))
            or not 0.0 <= confidence <= 1.0
        ):
            raise ValueError(
                "RCA confidence must be a number between 0 and 1."
            )

    # -----------------------------------------------------
    # MAIN ANALYSIS
    # -----------------------------------------------------

    def analyze(
        self,
        evidence_package: Dict[str, Any]
    ) -> Dict[str, Any]:

        violation = evidence_package.get(
            "violation", {}
        )

        evidence_items = evidence_package.get(
            "evidence_items", []
        )

        violation_id = violation.get(
            "id", "unknown"
        )

        # No evidence means no factual RCA should be generated.
        if not evidence_items:
            logger.warning(
                "No evidence available for RCA."
            )

            return self._placeholder_rca(
                evidence_package,
                status="insufficient_evidence",
                error="No evidence items were supplied."
            )

        if self.llm is None:
            logger.warning(
                "No configured LLM gateway. Using placeholder RCA."
            )

            return self._placeholder_rca(
                evidence_package,
                status="llm_unavailable",
                error="No configured LLM API key or gateway."
            )

        try:
            user_prompt = self._build_prompt(
                evidence_package
            )

            raw_response = self.llm.call(
                SYSTEM_PROMPT,
                user_prompt
            )

            rca_output = json.loads(raw_response)

            if not isinstance(rca_output, dict):
                raise ValueError(
                    "LLM response must be a JSON object."
                )

            self._validate_rca(rca_output)

            self._validate_evidence_references(
                rca_output,
                evidence_package
            )

            # Do not permit unsupported root-cause claims.
            if not rca_output["evidence"]:
                rca_output["root_cause"] = (
                    "Insufficient evidence to determine the root cause."
                )

                rca_output["confidence"] = 0.0

                rca_output["recommendation"] = (
                    "Collect additional source-code, dependency, "
                    "and Git evidence before determining a corrective action."
                )

                status = "insufficient_evidence"

            else:
                status = "success"

            rca_output.update({
                "violation_id": violation_id,
                "analysis_status": status,
                "provider": self.llm.provider,
                "model": self.llm.model,
                "prompt_version": PROMPT_VERSION,
                "cache_hit": self.llm.last_cache_hit,
            })

            logger.info(
                "LLM RCA completed with status: %s",
                status
            )

            return rca_output

        except json.JSONDecodeError as exc:
            logger.error(
                "LLM returned invalid JSON: %s",
                exc
            )

            return self._placeholder_rca(
                evidence_package,
                status="invalid_response",
                error=str(exc)
            )

        except Exception as exc:
            logger.exception(
                "LLM RCA analysis failed."
            )

            return self._placeholder_rca(
                evidence_package,
                status="failed",
                error=str(exc)
            )

    # -----------------------------------------------------
    # SAFE FALLBACK
    # -----------------------------------------------------

    def _placeholder_rca(
        self,
        evidence_package: Dict[str, Any],
        error: Optional[str] = None,
        status: str = "llm_unavailable"
    ) -> Dict[str, Any]:

        violation = evidence_package.get(
            "violation", {}
        )

        source = violation.get(
            "source", "unknown"
        )

        target = violation.get(
            "target", "unknown"
        )

        return {
            "violation_id": violation.get(
                "id", "unknown"
            ),

            "violation_explanation": (
                f"The Conformance Engine reported an architectural "
                f"violation involving {source} -> {target}. "
                f"Violation type: "
                f"{violation.get('violation_type', 'unknown')}."
            ),

            "root_cause": (
                "The root cause could not be established automatically. "
                "Manual review of the supplied evidence is required."
            ),

            "evidence": [],

            "affected_components": [
                component
                for component in [source, target]
                if component
            ],

            "recommendation": (
                "Review the detected dependency against the intended "
                "architecture and collect additional evidence before "
                "implementing a corrective change."
            ),

            "confidence": 0.0,

            "analysis_status": status,

            "provider": (
                self.llm.provider if self.llm else None
            ),

            "model": (
                self.llm.model if self.llm else None
            ),

            "prompt_version": PROMPT_VERSION,

            "cache_hit": False,

            "error": error,
        }
