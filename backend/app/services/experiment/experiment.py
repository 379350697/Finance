"""
Experiment: training run recorder with MLflow and JSON backends.

Supports:
    - MLflow: full tracking server integration
    - JSON: local file-based fallback (no server required)
"""

from __future__ import annotations

import json
import logging
from datetime import datetime
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

try:
    import mlflow

    _MLFLOW_AVAILABLE = True
except ImportError:  # pragma: no cover
    mlflow = None  # type: ignore[assignment]
    _MLFLOW_AVAILABLE = False
    logger.info("MLflow not installed; using JSON experiment backend.")


class Experiment:
    """Records metrics, params, and artifacts for a single training run.

    Parameters
    ----------
    name : str
        Experiment name.
    tracking_uri : str | None
        MLflow tracking URI. If None, use JSON backend.
    artifact_dir : str | None
        Directory for JSON artifacts (default: data/experiments).
    """

    def __init__(
        self,
        name: str,
        tracking_uri: str | None = None,
        artifact_dir: str | None = None,
    ):
        self.name = name
        self.tracking_uri = tracking_uri
        self.artifact_dir = Path(artifact_dir or "data/experiments")
        self._run_id: str | None = None
        self._active = False
        self._backend = "mlflow" if (_MLFLOW_AVAILABLE and tracking_uri) else "json"
        self._metrics: list[dict] = []
        self._params: dict = {}

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    def start(self) -> Experiment:
        """Start the experiment run."""
        if self._backend == "mlflow" and _MLFLOW_AVAILABLE:
            mlflow.set_tracking_uri(self.tracking_uri)
            mlflow.set_experiment(self.name)
            run = mlflow.start_run()
            self._run_id = run.info.run_id
        else:
            self._run_id = datetime.utcnow().strftime("%Y%m%d_%H%M%S_%f")
            self.artifact_dir = self.artifact_dir / self.name
            self.artifact_dir.mkdir(parents=True, exist_ok=True)

        self._active = True
        logger.info(
            "Experiment '%s' started (backend=%s, run=%s)",
            self.name, self._backend, self._run_id,
        )
        return self

    def end(self) -> None:
        """End the experiment run and persist records."""
        if not self._active:
            return

        if self._backend == "mlflow" and _MLFLOW_AVAILABLE:
            mlflow.end_run()
        else:
            self._persist_json()

        self._active = False
        logger.info("Experiment '%s' ended (run=%s)", self.name, self._run_id)

    # ------------------------------------------------------------------
    # Logging
    # ------------------------------------------------------------------

    def log_metric(self, key: str, value: float, step: int = 0) -> None:
        """Log a scalar metric."""
        if self._backend == "mlflow" and _MLFLOW_AVAILABLE:
            mlflow.log_metric(key, value, step=step)
        else:
            self._metrics.append({"key": key, "value": value, "step": step, "ts": datetime.utcnow().isoformat()})

    def log_params(self, params: dict[str, Any]) -> None:
        """Log hyperparameters."""
        self._params.update(params)
        if self._backend == "mlflow" and _MLFLOW_AVAILABLE:
            mlflow.log_params(params)

    def log_artifact(self, local_path: str | Path) -> None:
        """Log a file artifact."""
        if self._backend == "mlflow" and _MLFLOW_AVAILABLE:
            mlflow.log_artifact(str(local_path))
        else:
            import shutil
            dest = self.artifact_dir / Path(local_path).name
            shutil.copy2(local_path, dest)
            logger.info("Artifact copied: %s -> %s", local_path, dest)

    # ------------------------------------------------------------------
    # JSON persistence
    # ------------------------------------------------------------------

    def _persist_json(self) -> None:
        """Write metrics and params to a JSON file."""
        path = self.artifact_dir / f"run_{self._run_id}.json"
        data = {
            "run_id": self._run_id,
            "name": self.name,
            "backend": "json",
            "params": self._params,
            "metrics": self._metrics,
            "started_at": self._run_id,
            "ended_at": datetime.utcnow().isoformat(),
        }
        path.write_text(json.dumps(data, indent=2, default=str), encoding="utf-8")
        logger.info("Experiment record saved to %s", path)

    # ------------------------------------------------------------------
    # Context manager
    # ------------------------------------------------------------------

    def __enter__(self):
        return self.start()

    def __exit__(self, *args):
        self.end()
