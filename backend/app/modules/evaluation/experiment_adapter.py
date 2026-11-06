
"""
ArchLens Evaluation Adapter
Sprint 9, D42.

Provides a common, configuration-driven interface for executing
existing ArchLens analysis capabilities and saving their outputs.

Supported modes:
- cv: diagram extraction
- static: repository architecture recovery
- conformance: deterministic graph comparison
- alignment: intended/current graph alignment
- rca: evidence-grounded RCA

This adapter does not invent missing baselines or metrics.
"""

import argparse
import json
import os
import random
import time
import traceback
import uuid


from datetime import datetime, timezone
from pathlib import Path
from typing import Any


SUPPORTED_MODES = {
    "cv",
    "static",
    "conformance",
    "alignment",
    "rca",
}


def load_json(path: str | Path) -> Any:
    """Read a JSON input file."""
    path = Path(path)

    if not path.is_file():
        raise FileNotFoundError(f"Input file not found: {path}")

    with path.open("r", encoding="utf-8") as file:
        return json.load(file)


def save_json(path: Path, data: Any) -> None:
    """Save JSON with support for Pydantic and Path values."""
    path.parent.mkdir(parents=True, exist_ok=True)

    path.write_text(
        json.dumps(data, indent=4, default=str),
        encoding="utf-8",
    )


def set_seed(seed: int | None) -> None:
    """Set available random seeds."""
    if seed is None:
        return

    random.seed(seed)

    try:
        import numpy as np
        np.random.seed(seed)
    except ImportError:
        pass


class EvaluationAdapter:
    """Execute existing ArchLens modules using a common interface."""

    def __init__(self, output_dir: str | Path = "data/evaluation"):
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)

    @staticmethod
    def _resolve_input(
        config_path: Path,
        value: str,
    ) -> Path:
        """Resolve input paths relative to the experiment config."""
        path = Path(value)

        if not path.is_absolute():
            path = config_path.parent / path

        return path.resolve()

    def execute(
        self,
        config_path: str | Path,
    ) -> dict[str, Any]:

        config_path = Path(config_path).resolve()

        with config_path.open("r", encoding="utf-8") as file:
            config = json.load(file)

        if not isinstance(config, dict):
            raise ValueError("Experiment configuration must be an object.")

        mode = config.get("mode")

        if mode not in SUPPORTED_MODES:
            raise ValueError(
                f"Unsupported experiment mode: {mode}. "
                f"Supported modes: {sorted(SUPPORTED_MODES)}"
            )

        seed = config.get("seed")

        if seed is not None and (
            isinstance(seed, bool) or not isinstance(seed, int)
        ):
            raise ValueError("seed must be an integer or null.")

        set_seed(seed)

        run_id = (
            config.get("run_id")
            or os.environ.get("ARCHLENS_EXPERIMENT_ID")
            or str(uuid.uuid4())
        )

        if not isinstance(run_id, str) or not run_id.strip():
            raise ValueError("run_id must be a non-empty string.")

        run_dir = self.output_dir / run_id
        run_dir.mkdir(parents=True, exist_ok=True)

        started_at = datetime.now(timezone.utc)
        start_time = time.perf_counter()

        result = {
            "run_id": run_id,
            "experiment_name": config.get("name", "unnamed"),
            "mode": mode,
            "status": "failed",
            "started_at": started_at.isoformat(),
            "seed": seed,
            "input_manifest": config.get("inputs", {}),
            "execution_mode": None,
            "output": None,
            "error": None,
        }

        try:
            output, execution_metadata = self._dispatch(
                mode=mode,
                config=config,
                config_path=config_path,
            )

            result["status"] = "completed"
            result["output"] = output
            result["execution_mode"] = execution_metadata

            save_json(run_dir / "output.json", output)

        except Exception as exc:
            result["error"] = str(exc)
            result["traceback"] = traceback.format_exc()

        result["duration_seconds"] = round(
            time.perf_counter() - start_time,
            6,
        )

        result["completed_at"] = datetime.now(
            timezone.utc
        ).isoformat()

        save_json(run_dir / "result.json", result)

        return result

    def _dispatch(
        self,
        mode: str,
        config: dict[str, Any],
        config_path: Path,
    ) -> tuple[Any, dict[str, Any]]:

        inputs = config.get("inputs", {})

        if not isinstance(inputs, dict):
            raise ValueError("inputs must be a JSON object.")

        if mode == "cv":
            return self._run_cv(inputs, config_path)

        if mode == "static":
            return self._run_static(inputs)

        if mode == "conformance":
            return self._run_conformance(inputs, config_path)

        if mode == "alignment":
            return self._run_alignment(inputs, config_path)

        if mode == "rca":
            return self._run_rca(inputs, config_path)

        raise ValueError(f"Unsupported mode: {mode}")

    def _run_cv(self, inputs, config_path):
        from app.modules.cv_pipeline.pipeline import CVPipeline

        image = inputs.get("diagram_path")

        if not image:
            raise ValueError("cv mode requires inputs.diagram_path.")

        image_path = self._resolve_input(config_path, image)

        pipeline = CVPipeline()
        output = pipeline.analyze(str(image_path))

        metadata = output.get("metadata", {})

        return output, {
            "detector": metadata.get("detection_method"),
            "relationship_method": metadata.get("relationship_method"),
            "ocr_method": metadata.get("ocr_method"),
            "is_interim_detector": metadata.get("is_interim_detector"),
        }

    def _run_static(self, inputs):
        from app.modules.architecture_recovery.ast_parser import (
            ArchitectureRecoveryPipeline,
        )

        repo_path = inputs.get("repo_path")

        if not repo_path:
            raise ValueError("static mode requires inputs.repo_path.")

        language = inputs.get("language", "python")

        pipeline = ArchitectureRecoveryPipeline()
        output = pipeline.analyze_repository(repo_path, language)

        return output, {
            "analyzer": "ArchitectureRecoveryPipeline",
            "language": language,
        }

    def _run_conformance(self, inputs, config_path):
        from app.api.routes.conformance import run_conformance_check

        intended_path = inputs.get("intended_graph")
        current_path = inputs.get("current_graph")

        if not intended_path or not current_path:
            raise ValueError(
                "conformance mode requires intended_graph "
                "and current_graph input files."
            )

        intended = load_json(
            self._resolve_input(config_path, intended_path)
        )
        current = load_json(
            self._resolve_input(config_path, current_path)
        )

        response = run_conformance_check(intended, current)

        output = response.model_dump(mode="json")

        return output, {
            "engine": "ConformanceEngine",
            "authority": "deterministic",
        }

    def _run_alignment(self, inputs, config_path):
        from app.modules.architecture_recovery.graph_alignment import (
            align_architecture_graphs,
        )

        intended_path = inputs.get("intended_graph")
        current_path = inputs.get("current_graph")

        if not intended_path or not current_path:
            raise ValueError(
                "alignment mode requires intended_graph "
                "and current_graph input files."
            )

        intended = load_json(
            self._resolve_input(config_path, intended_path)
        )
        current = load_json(
            self._resolve_input(config_path, current_path)
        )

        manual_mappings = inputs.get("manual_mappings", {})

        output = align_architecture_graphs(
            intended_graph=intended,
            current_graph=current,
            manual_mappings=manual_mappings,
        )

        return output, {
            "method": "align_architecture_graphs",
        }

    def _run_rca(self, inputs, config_path):
        from app.modules.llm_rca.analyzer import RCAAnalyzer

        evidence_path = inputs.get("evidence_package")

        if not evidence_path:
            raise ValueError(
                "rca mode requires inputs.evidence_package."
            )

        evidence_package = load_json(
            self._resolve_input(config_path, evidence_path)
        )

        analyzer = RCAAnalyzer()
        output = analyzer.analyze(evidence_package)

        return output, {
            "analyzer": "RCAAnalyzer",
            "analysis_status": output.get("analysis_status"),
            "provider": output.get("provider"),
            "model": output.get("model"),
            "prompt_version": output.get("prompt_version"),
        }


def main():
    parser = argparse.ArgumentParser(
        description="Run an ArchLens evaluation experiment."
    )

    parser.add_argument(
        "--config",
        required=True,
        help="Path to the evaluation JSON configuration.",
    )

    parser.add_argument(
        "--output-dir",
        default="data/evaluation",
    )

    args = parser.parse_args()

    adapter = EvaluationAdapter(args.output_dir)
    result = adapter.execute(args.config)

    print(json.dumps(result, indent=4))

    if result["status"] != "completed":
        raise SystemExit(1)


if __name__ == "__main__":
    main()
