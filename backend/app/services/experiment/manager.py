"""
ExpManager: manages multiple experiments and enables comparison.
"""

from __future__ import annotations

import json
import logging
from datetime import datetime
from pathlib import Path
from typing import Any

from app.services.experiment.experiment import Experiment

logger = logging.getLogger(__name__)


class ExpManager:
    """Creates, lists, and compares experiments.

    Parameters
    ----------
    tracking_uri : str | None
        MLflow tracking URI. If None, use JSON backend.
    artifact_dir : str | None
        Directory for local experiment records.
    """

    def __init__(
        self,
        tracking_uri: str | None = None,
        artifact_dir: str | None = None,
    ):
        self.tracking_uri = tracking_uri
        self.artifact_dir = Path(artifact_dir or "data/experiments")
        self._experiments: dict[str, Experiment] = {}

    def create_experiment(self, name: str) -> Experiment:
        """Create a new experiment and start it.

        Returns an active ``Experiment``.
        """
        exp = Experiment(
            name=name,
            tracking_uri=self.tracking_uri,
            artifact_dir=str(self.artifact_dir),
        )
        exp.start()
        self._experiments[name] = exp
        return exp

    def get_experiment(self, name: str) -> Experiment | None:
        """Get a running experiment by name."""
        return self._experiments.get(name)

    def list_experiments(self) -> list[dict]:
        """List all experiments with summary data.

        Scans both running experiments and persisted JSON records.
        """
        results: list[dict] = []

        # Running experiments
        for name, exp in self._experiments.items():
            results.append({
                "name": name,
                "run_id": exp._run_id,
                "backend": exp._backend,
                "status": "running",
            })

        # Persisted experiments (JSON backend)
        exp_dir = self.artifact_dir
        if exp_dir.exists():
            for subdir in exp_dir.iterdir():
                if subdir.is_dir():
                    for json_file in subdir.glob("run_*.json"):
                        try:
                            data = json.loads(json_file.read_text("utf-8"))
                            results.append({
                                "name": data.get("name", subdir.name),
                                "run_id": data.get("run_id", json_file.stem),
                                "backend": data.get("backend", "json"),
                                "status": "completed",
                                "file": str(json_file),
                            })
                        except Exception:
                            pass

        return results

    def compare_experiments(self, names: list[str]) -> dict[str, Any]:
        """Compare metrics across named experiments.

        Returns a dict with per-experiment metric summaries.
        """
        comparison: dict[str, Any] = {"experiments": {}, "comparison": {}}

        for name in names:
            # Check running first
            exp = self._experiments.get(name)
            if exp is not None:
                metrics = exp._metrics
                params = exp._params
            else:
                # Try JSON persistence
                exp_subdir = self.artifact_dir / name
                if exp_subdir.exists():
                    metrics, params = [], {}
                    for f in sorted(exp_subdir.glob("run_*.json")):
                        data = json.loads(f.read_text("utf-8"))
                        metrics.extend(data.get("metrics", []))
                        params.update(data.get("params", {}))
                else:
                    continue

            # Aggregate metrics by key (last value wins)
            metric_summary: dict[str, float] = {}
            for m in metrics:
                metric_summary[m["key"]] = m["value"]

            comparison["experiments"][name] = {
                "params": params,
                "metrics": metric_summary,
            }

        # Cross-experiment comparison: find best per metric
        all_metrics: dict[str, list[tuple[str, float]]] = {}
        for exp_name, data in comparison["experiments"].items():
            for key, val in data["metrics"].items():
                all_metrics.setdefault(key, []).append((exp_name, val))

        for key, pairs in all_metrics.items():
            comparison["comparison"][key] = {
                "best": max(pairs, key=lambda x: x[1]) if pairs else None,
                "worst": min(pairs, key=lambda x: x[1]) if pairs else None,
                "values": {name: val for name, val in pairs},
            }

        return comparison
