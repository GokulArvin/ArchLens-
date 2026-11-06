import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
FIX = ROOT / "fixtures" / "synthetic"


@pytest.fixture
def gw(tmp_path):
    from archlens_llm.gateway import LLMGateway
    from archlens_llm.gateway.mock_provider import MockProvider
    return LLMGateway(MockProvider(), run_dir=tmp_path, cache=False, backoff_s=0)


def make_gw(tmp_path, faults):
    from archlens_llm.gateway import LLMGateway
    from archlens_llm.gateway.mock_provider import MockProvider
    return LLMGateway(MockProvider(faults=faults), run_dir=tmp_path, cache=False, backoff_s=0)


def load(system, name):
    return json.loads((FIX / system / name).read_text())
