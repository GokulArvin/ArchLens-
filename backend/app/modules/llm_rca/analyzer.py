"""
Module F: LLM-based Root Cause Analysis
Evidence-grounded semantic reasoning about architecture violations.

The LLM receives the structured evidence package and returns:
- Violation explanation
- Root cause identification
- Affected components
- Recommendation

IMPORTANT: The LLM is the semantic reasoner, NOT the conformance authority.
The violation verdict itself is always produced by the deterministic ConformanceEngine.
"""

import json
import logging
from typing import Dict, Any, Optional, List
from tenacity import retry, stop_after_attempt, wait_exponential

logger = logging.getLogger(__name__)

# ─── Prompt Templates ──────────────────────────────────────────────────────────

SYSTEM_PROMPT = """You are an expert software architecture analysis assistant.
You must reason ONLY from the supplied evidence.
Do NOT invent files, dependencies, commits, or architectural rules.
Do NOT guess beyond what the evidence supports.
Always return valid JSON matching the specified schema."""

RCA_USER_PROMPT_TEMPLATE = """
## Intended Architecture
{intended_architecture}

## Current Architecture (Implemented)
{current_architecture}

## Detected Violation
{violation}

## Dependency Path
{dependency_path}

## Git Commit (Introducing Change)
{git_commit}

## Relevant Diff
```diff
{diff}
```

## Code Context
File: {code_file}
Symbol: {code_symbol}

## Architecture Rule Violated
{architecture_rule}

## Your Task
1. Explain the architecture violation clearly.
2. Identify the most likely root cause based on the evidence.
3. List all affected architectural components.
4. Cite specific evidence from the diff/commit.
5. Recommend an architecture-compliant corrective action.

Return ONLY valid JSON matching this exact schema:
{{
  "violation_explanation": "string",
  "root_cause": "string",
  "evidence": ["string"],
  "affected_components": ["string"],
  "recommendation": "string",
  "confidence": 0.0
}}
"""


class LLMGateway:
    """
    LLM API gateway with retry logic, caching and structured output validation.
    Supports OpenAI, Gemini, and Anthropic.
    """

    def __init__(
        self,
        provider: str = "openai",
        model: str = "gpt-4o",
        api_key: Optional[str] = None,
        temperature: float = 0.1,
        max_tokens: int = 4096,
    ):
        self.provider = provider
        self.model = model
        self.api_key = api_key
        self.temperature = temperature
        self.max_tokens = max_tokens
        self._client = None

    def _get_client(self):
        if self._client:
            return self._client

        if self.provider == "openai":
            import openai
            self._client = openai.OpenAI(api_key=self.api_key)
        elif self.provider == "gemini":
            import google.generativeai as genai
            genai.configure(api_key=self.api_key)
            self._client = genai.GenerativeModel(self.model)
        elif self.provider == "anthropic":
            import anthropic
            self._client = anthropic.Anthropic(api_key=self.api_key)
        else:
            raise ValueError(f"Unknown LLM provider: {self.provider}")

        return self._client

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=10),
    )
    def call(self, system_prompt: str, user_prompt: str) -> str:
        """Make an LLM API call with retry logic."""
        client = self._get_client()

        if self.provider == "openai":
            response = client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                ],
                temperature=self.temperature,
                max_tokens=self.max_tokens,
                response_format={"type": "json_object"},
            )
            return response.choices[0].message.content

        elif self.provider == "gemini":
            full_prompt = f"{system_prompt}\n\n{user_prompt}"
            response = client.generate_content(full_prompt)
            return response.text

        elif self.provider == "anthropic":
            response = client.messages.create(
                model=self.model,
                max_tokens=self.max_tokens,
                system=system_prompt,
                messages=[{"role": "user", "content": user_prompt}],
            )
            return response.content[0].text

        raise ValueError(f"Unsupported provider: {self.provider}")


class RCAAnalyzer:
    """
    Root Cause Analysis using LLM with evidence-grounded reasoning.
    """

    def __init__(self, llm_gateway: Optional[LLMGateway] = None):
        self.llm = llm_gateway

    def analyze(self, evidence_package: Dict[str, Any]) -> Dict[str, Any]:
        """
        Perform LLM-based RCA on a violation evidence package.
        Returns structured RCA output.
        """
        if not self.llm:
            logger.warning("No LLM gateway configured. Returning placeholder RCA.")
            return self._placeholder_rca(evidence_package)

        user_prompt = RCA_USER_PROMPT_TEMPLATE.format(
            intended_architecture=json.dumps(
                evidence_package.get("architecture_rule", {}), indent=2
            ),
            current_architecture="(See violation and dependency path)",
            violation=json.dumps(evidence_package.get("violation", {}), indent=2),
            dependency_path=" → ".join(
                evidence_package.get("dependency_path", [])
            ),
            git_commit=json.dumps(evidence_package.get("commit", {}), indent=2),
            diff=evidence_package.get("diff", "No diff available"),
            code_file=evidence_package.get("code", {}).get("file", ""),
            code_symbol=evidence_package.get("code", {}).get("target_symbol", ""),
            architecture_rule=json.dumps(
                evidence_package.get("architecture_rule", {}), indent=2
            ),
        )

        try:
            raw_response = self.llm.call(SYSTEM_PROMPT, user_prompt)
            rca_output = json.loads(raw_response)
            rca_output["violation_id"] = evidence_package.get(
                "violation", {}
            ).get("id", "unknown")
            self._validate_rca(rca_output)
            logger.info("LLM RCA complete")
            return rca_output
        except json.JSONDecodeError as e:
            logger.error(f"LLM returned invalid JSON: {e}")
            return self._placeholder_rca(evidence_package, error=str(e))
        except Exception as e:
            logger.error(f"LLM RCA failed: {e}")
            return self._placeholder_rca(evidence_package, error=str(e))

    def _validate_rca(self, rca: Dict[str, Any]):
        """Validate required fields in RCA output."""
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
                raise ValueError(f"Missing required field in LLM output: {field}")

        conf = rca.get("confidence", 0)
        if not (0.0 <= conf <= 1.0):
            rca["confidence"] = max(0.0, min(1.0, float(conf)))

    def _placeholder_rca(
        self, evidence_package: Dict, error: Optional[str] = None
    ) -> Dict[str, Any]:
        """Return a placeholder RCA when LLM is unavailable."""
        violation = evidence_package.get("violation", {})
        return {
            "violation_id": violation.get("id", "unknown"),
            "violation_explanation": (
                f"Architectural violation: {violation.get('source')} "
                f"→ {violation.get('target')}. "
                f"Type: {violation.get('violation_type', 'unknown')}."
            ),
            "root_cause": "LLM not available — manual review required.",
            "evidence": [],
            "affected_components": [
                violation.get("source", ""),
                violation.get("target", ""),
            ],
            "recommendation": (
                "Review the dependency and apply architectural constraints."
            ),
            "confidence": 0.0,
            "error": error,
        }
