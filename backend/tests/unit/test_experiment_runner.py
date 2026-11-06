
import json
import sys

import pytest

from app.modules.evaluation.experiment_runner import (
    ExperimentConfigError,
    ExperimentRunner,
)


def create_config(tmp_path, command=None, **overrides):
    config = {
        "name": "test_experiment",
        "command": command or [
            sys.executable,
            "-c",
            "print('experiment successful')",
        ],
        "working_directory": str(tmp_path),
        "seed": 42,
        "parameters": {"threshold": 0.5},
    }
    config.update(overrides)

    config_path = tmp_path / "experiment.json"
    config_path.write_text(
        json.dumps(config),
        encoding="utf-8",
    )
    return config_path


def test_load_valid_config(tmp_path):
    config_path = create_config(tmp_path)

    config = ExperimentRunner.load_config(config_path)

    assert config["name"] == "test_experiment"
    assert config["seed"] == 42


def test_missing_config_file(tmp_path):
    with pytest.raises(ExperimentConfigError):
        ExperimentRunner.load_config(
            tmp_path / "missing.json"
        )


def test_missing_required_field(tmp_path):
    config_path = tmp_path / "invalid.json"
    config_path.write_text(
        json.dumps({"name": "invalid"}),
        encoding="utf-8",
    )

    with pytest.raises(ExperimentConfigError):
        ExperimentRunner.load_config(config_path)


def test_invalid_command_format(tmp_path):
    config_path = create_config(
        tmp_path,
        command="python script.py",
    )

    with pytest.raises(ExperimentConfigError):
        ExperimentRunner.load_config(config_path)


def test_successful_experiment_run(tmp_path):
    config_path = create_config(tmp_path)
    output_dir = tmp_path / "experiments"

    runner = ExperimentRunner(output_dir)
    result = runner.run(config_path)

    assert result["status"] == "completed"
    assert result["exit_code"] == 0
    assert result["experiment_name"] == "test_experiment"
    assert result["seed"] == 42

    run_dir = output_dir / result["run_id"]

    assert (run_dir / "config.json").exists()
    assert (run_dir / "environment.json").exists()
    assert (run_dir / "stdout.txt").exists()
    assert (run_dir / "stderr.txt").exists()
    assert (run_dir / "result.json").exists()

    stdout = (run_dir / "stdout.txt").read_text(
        encoding="utf-8"
    )
    assert "experiment successful" in stdout


def test_failed_experiment_is_recorded(tmp_path):
    config_path = create_config(
        tmp_path,
        command=[
            sys.executable,
            "-c",
            "raise SystemExit(1)",
        ],
    )

    output_dir = tmp_path / "experiments"
    runner = ExperimentRunner(output_dir)

    result = runner.run(config_path)

    assert result["status"] == "failed"
    assert result["exit_code"] == 1

    assert (output_dir / "registry.jsonl").exists()


def test_registry_records_multiple_runs(tmp_path):
    config_path = create_config(tmp_path)
    output_dir = tmp_path / "experiments"

    runner = ExperimentRunner(output_dir)

    first = runner.run(config_path)
    second = runner.run(config_path)

    assert first["run_id"] != second["run_id"]

    registry = output_dir / "registry.jsonl"
    records = [
        json.loads(line)
        for line in registry.read_text(
            encoding="utf-8"
        ).splitlines()
    ]

    assert len(records) == 2


def test_invalid_seed_is_rejected(tmp_path):
    config_path = create_config(
        tmp_path,
        seed="not-an-integer",
    )

    runner = ExperimentRunner(tmp_path / "experiments")

    with pytest.raises(ExperimentConfigError):
        runner.run(config_path)
