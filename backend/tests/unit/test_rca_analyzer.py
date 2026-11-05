
import json

from app.modules.llm_rca.analyzer import RCAAnalyzer


class MockLLMGateway:
    """Simulates an LLM response without making API calls."""

    provider = "mock"
    model = "mock-model"
    last_cache_hit = False

    def __init__(self, response):
        self.response = response

    def call(self, system_prompt, user_prompt):
        return json.dumps(self.response)


def create_evidence_package():
    return {
        "violation": {
            "id": "TEST001",
            "verdict": "VIOLATION",
            "violation_type": "forbidden_dependency",
            "source": "controller",
            "target": "repository"
        },
        "architecture_rule": "Controllers must not directly access repositories.",
        "dependency_path": ["controller", "repository"],
        "evidence_items": [
            {
                "evidence_id": "E001",
                "type": "conformance_finding",
                "content": {
                    "source": "controller",
                    "target": "repository"
                }
            },
            {
                "evidence_id": "E002",
                "type": "source_code",
                "content": {
                    "file": "backend/app/example.py"
                }
            }
        ]
    }


def valid_llm_response():
    return {
        "violation_explanation": (
            "The controller directly depends on the repository."
        ),
        "root_cause": (
            "The controller contains a direct repository dependency."
        ),
        "evidence": ["E001", "E002"],
        "affected_components": ["controller", "repository"],
        "recommendation": (
            "Introduce an appropriate service layer."
        ),
        "confidence": 0.85
    }


def test_valid_evidence_ids_are_accepted():
    gateway = MockLLMGateway(valid_llm_response())
    analyzer = RCAAnalyzer(gateway)

    result = analyzer.analyze(create_evidence_package())

    assert result["analysis_status"] == "success"
    assert result["evidence"] == ["E001", "E002"]
    assert result["confidence"] == 0.85
    assert result["provider"] == "mock"
    assert result["model"] == "mock-model"


def test_invalid_evidence_ids_are_rejected():
    response = valid_llm_response()
    response["evidence"] = ["E001", "E999"]

    analyzer = RCAAnalyzer(MockLLMGateway(response))

    result = analyzer.analyze(create_evidence_package())

    assert result["analysis_status"] == "failed"
    assert result["evidence"] == []
    assert "invalid evidence IDs" in result["error"]


def test_invalid_confidence_is_rejected():
    response = valid_llm_response()
    response["confidence"] = 1.5

    analyzer = RCAAnalyzer(MockLLMGateway(response))

    result = analyzer.analyze(create_evidence_package())

    assert result["analysis_status"] == "failed"
    assert result["confidence"] == 0.0
    assert "confidence" in result["error"]


def test_missing_evidence_returns_safe_fallback():
    package = create_evidence_package()
    package["evidence_items"] = []

    analyzer = RCAAnalyzer(MockLLMGateway(valid_llm_response()))

    result = analyzer.analyze(package)

    assert result["analysis_status"] == "insufficient_evidence"
    assert result["confidence"] == 0.0
    assert result["evidence"] == []
