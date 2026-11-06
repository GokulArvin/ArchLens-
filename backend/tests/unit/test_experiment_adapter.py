import json
from pathlib import Path

import pytest

from app.modules.evaluation.experiment_adapter import (
    EvaluationAdapter,
    load_json,
    save_json,
    set_seed,
)


def write_config(tmp_path, data):
    path = tmp_path / "config.json"
    path.write_text(json.dumps(data), encoding="utf-8")
    return path


def test_load_json_reads_valid_file(tmp_path):
    path = tmp_path / "input.json"
    path.write_text('{"name": "test"}', encoding="utf-8")
    assert load_json(path) == {"name": "test"}


def test_load_json_rejects_missing_file(tmp_path):
    with pytest.raises(FileNotFoundError):
        load_json(tmp_path / "missing.json")


def test_save_json_creates_parent_directories(tmp_path):
    path = tmp_path / "nested" / "output.json"
    save_json(path, {"value": 42})
    assert json.loads(path.read_text(encoding="utf-8")) == {"value": 42}


def test_set_seed_accepts_none():
    assert set_seed(None) is None


def test_execute_rejects_unsupported_mode(tmp_path):
    path = write_config(tmp_path, {"mode": "invalid"})
    adapter = EvaluationAdapter(tmp_path / "output")

    with pytest.raises(ValueError, match="Unsupported experiment mode"):
        adapter.execute(path)


def test_execute_rejects_boolean_seed(tmp_path):
    path = write_config(
        tmp_path, {"mode": "static", "seed": True}
    )
    adapter = EvaluationAdapter(tmp_path / "output")

    with pytest.raises(ValueError, match="seed must be an integer"):
        adapter.execute(path)


def test_execute_rejects_non_integer_seed(tmp_path):
    path = write_config(
        tmp_path, {"mode": "static", "seed": "42"}
    )
    adapter = EvaluationAdapter(tmp_path / "output")

    with pytest.raises(ValueError, match="seed must be an integer"):
        adapter.execute(path)


def test_execute_rejects_empty_run_id(tmp_path):
    path = write_config(
        tmp_path, {"mode": "static", "run_id": " "}
    )
    adapter = EvaluationAdapter(tmp_path / "output")

    with pytest.raises(ValueError, match="run_id must be a non-empty string"):
        adapter.execute(path)


def test_execute_saves_successful_result(tmp_path, monkeypatch):
    path = write_config(
        tmp_path,
        {"name": "adapter_test", "mode": "static", "seed": 42}
    )
    adapter = EvaluationAdapter(tmp_path / "output")

    monkeypatch.setattr(
        adapter,
        "_dispatch",
        lambda **kwargs: (
            {"components": []},
            {"analyzer": "mock"}
        ),
    )

    result = adapter.execute(path)

    assert result["status"] == "completed"
    assert result["output"] == {"components": []}
    assert result["execution_mode"]["analyzer"] == "mock"

    run_dir = tmp_path / "output" / result["run_id"]
    assert (run_dir / "output.json").is_file()
    assert (run_dir / "result.json").is_file()


def test_execute_records_dispatch_failure(tmp_path, monkeypatch):
    path = write_config(
        tmp_path, {"mode": "static"}
    )
    adapter = EvaluationAdapter(tmp_path / "output")

    def fail_dispatch(**kwargs):
        raise RuntimeError("Mock analysis failure")

    monkeypatch.setattr(adapter, "_dispatch", fail_dispatch)

    result = adapter.execute(path)

    assert result["status"] == "failed"
    assert result["error"] == "Mock analysis failure"
    assert "traceback" in result

    saved = json.loads(
        (tmp_path / "output" / result["run_id"] / "result.json")
        .read_text(encoding="utf-8")
    )
    assert saved["status"] == "failed"


def test_dispatch_rejects_non_object_inputs(tmp_path):
    adapter = EvaluationAdapter(tmp_path / "output")

    with pytest.raises(ValueError, match="inputs must be a JSON object"):
        adapter._dispatch(
            mode="static",
            config={"inputs": []},
            config_path=tmp_path / "config.json",
        )


def test_dispatch_selects_static_mode(tmp_path, monkeypatch):
    adapter = EvaluationAdapter(tmp_path / "output")
    expected = ({"components": []}, {"analyzer": "mock"})

    monkeypatch.setattr(
        adapter, "_run_static", lambda inputs: expected
    )

    result = adapter._dispatch(
        mode="static",
        config={"inputs": {"repo_path": "."}},
        config_path=tmp_path / "config.json",
    )

    assert result == expected


def test_dispatch_rejects_unknown_mode(tmp_path):
    adapter = EvaluationAdapter(tmp_path / "output")

    with pytest.raises(ValueError, match="Unsupported mode"):
        adapter._dispatch(
            mode="unknown",
            config={"inputs": {}},
            config_path=tmp_path / "config.json",
        )
