
"""
ArchLens Experiment Runner
D41: Configuration-driven and reproducible experiment execution.

Uses only Python standard-library modules.
Each run stores its configuration, execution logs and metadata.
"""

import argparse
import json
import platform
import subprocess
import sys
import time
import uuid

from datetime import datetime, timezone
from pathlib import Path
from typing import Any


class ExperimentConfigError(ValueError):
    """Raised when an experiment configuration is invalid."""


class ExperimentRunner:
    REQUIRED_FIELDS = {"name", "command"}

    def __init__(self, output_dir: str | Path = "data/experiments"):
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.registry_path = self.output_dir / "registry.jsonl"

    @staticmethod
    def load_config(config_path: str | Path) -> dict[str, Any]:
        """Load and validate an experiment JSON configuration."""

        path = Path(config_path)

        if not path.is_file():
            raise ExperimentConfigError(
                f"Configuration file not found: {path}"
            )

        try:
            with path.open("r", encoding="utf-8") as file:
                config = json.load(file)
        except json.JSONDecodeError as exc:
            raise ExperimentConfigError(
                f"Invalid JSON configuration: {exc}"
            ) from exc

        if not isinstance(config, dict):
            raise ExperimentConfigError(
                "Experiment configuration must be a JSON object."
            )

        missing = ExperimentRunner.REQUIRED_FIELDS - config.keys()
        if missing:
            raise ExperimentConfigError(
                f"Missing required fields: {sorted(missing)}"
            )

        if not isinstance(config["name"], str) or not config["name"].strip():
            raise ExperimentConfigError(
                "'name' must be a non-empty string."
            )

        command = config["command"]
        if (
            not isinstance(command, list)
            or not command
            or not all(isinstance(arg, str) for arg in command)
        ):
            raise ExperimentConfigError(
                "'command' must be a non-empty list of strings."
            )

        if "parameters" in config and not isinstance(
            config["parameters"], dict
        ):
            raise ExperimentConfigError(
                "'parameters' must be a JSON object."
            )

        return config

    @staticmethod
    def get_git_commit(working_directory: Path) -> str | None:
        """Return the current Git commit when available."""

        try:
            result = subprocess.run(
                ["git", "rev-parse", "HEAD"],
                cwd=working_directory,
                capture_output=True,
                text=True,
                timeout=10,
                check=True,
            )
            return result.stdout.strip()
        except (subprocess.SubprocessError, OSError):
            return None

    def run(self, config_path: str | Path) -> dict[str, Any]:
        """Execute an experiment and persist its artifacts."""

        config_path = Path(config_path).resolve()
        config = self.load_config(config_path)

        run_id = str(uuid.uuid4())
        started_at = datetime.now(timezone.utc)

        run_dir = self.output_dir / run_id
        run_dir.mkdir(parents=True, exist_ok=False)

        working_directory = Path(
            config.get("working_directory", ".")
        )

        if not working_directory.is_absolute():
            working_directory = config_path.parent / working_directory

        working_directory = working_directory.resolve()

        if not working_directory.is_dir():
            raise ExperimentConfigError(
                f"Working directory does not exist: {working_directory}"
            )

        seed = config.get("seed")
        if seed is not None and (
            isinstance(seed, bool) or not isinstance(seed, int)
        ):
            raise ExperimentConfigError("'seed' must be an integer.")

        config_snapshot = {
            **config,
            "run_id": run_id,
            "started_at": started_at.isoformat(),
        }

        (run_dir / "config.json").write_text(
            json.dumps(config_snapshot, indent=4),
            encoding="utf-8",
        )

        environment = {
            "python_version": sys.version,
            "platform": platform.platform(),
            "working_directory": str(working_directory),
            "git_commit": self.get_git_commit(working_directory),
        }

        (run_dir / "environment.json").write_text(
            json.dumps(environment, indent=4),
            encoding="utf-8",
        )

        command = config["command"]
        process_env = None

        # Provide experiment metadata to the executed process.
        import os

        process_env = os.environ.copy()
        process_env["ARCHLENS_EXPERIMENT_ID"] = run_id

        start_time = time.perf_counter()
        error = None

        try:
            completed = subprocess.run(
                command,
                cwd=working_directory,
                env=process_env,
                capture_output=True,
                text=True,
                timeout=config.get("timeout_seconds", 3600),
                check=False,
                shell=False,
            )

            stdout = completed.stdout
            stderr = completed.stderr
            exit_code = completed.returncode
            status = "completed" if exit_code == 0 else "failed"

        except subprocess.TimeoutExpired as exc:
            stdout = exc.stdout or ""
            stderr = exc.stderr or ""
            if isinstance(stdout, bytes):
                stdout = stdout.decode("utf-8", errors="replace")
            if isinstance(stderr, bytes):
                stderr = stderr.decode("utf-8", errors="replace")
            exit_code = None
            status = "failed"
            error = "Experiment execution timed out."

        except OSError as exc:
            stdout = ""
            stderr = str(exc)
            exit_code = None
            status = "failed"
            error = str(exc)

        duration_seconds = time.perf_counter() - start_time
        completed_at = datetime.now(timezone.utc)

        (run_dir / "stdout.txt").write_text(
            stdout, encoding="utf-8"
        )
        (run_dir / "stderr.txt").write_text(
            stderr, encoding="utf-8"
        )

        result = {
            "run_id": run_id,
            "experiment_name": config["name"],
            "status": status,
            "exit_code": exit_code,
            "started_at": started_at.isoformat(),
            "completed_at": completed_at.isoformat(),
            "duration_seconds": round(duration_seconds, 6),
            "command": command,
            "seed": seed,
            "dataset": config.get("dataset"),
            "split": config.get("split"),
            "parameters": config.get("parameters", {}),
            "artifacts_directory": str(run_dir),
            "error": error,
        }

        (run_dir / "result.json").write_text(
            json.dumps(result, indent=4),
            encoding="utf-8",
        )

        # Append a compact record to the experiment registry.
        with self.registry_path.open("a", encoding="utf-8") as file:
            file.write(json.dumps(result) + "\n")

        return result


def main():
    parser = argparse.ArgumentParser(
        description="Run a reproducible ArchLens experiment."
    )
    parser.add_argument(
        "--config",
        required=True,
        help="Path to the experiment JSON configuration.",
    )
    parser.add_argument(
        "--output-dir",
        default="data/experiments",
        help="Directory used to store experiment runs.",
    )

    args = parser.parse_args()

    try:
        runner = ExperimentRunner(args.output_dir)
        result = runner.run(args.config)
        print(json.dumps(result, indent=4))

        if result["status"] != "completed":
            sys.exit(1)

    except ExperimentConfigError as exc:
        print(f"Configuration error: {exc}", file=sys.stderr)
        sys.exit(2)


if __name__ == "__main__":
    main()
