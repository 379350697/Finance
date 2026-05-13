"""
Tuner: hyperparameter optimization with Optuna backend and JSON fallback.

Wraps ModelTrainer.train() as an Optuna objective, using time-series
cross-validation to evaluate each trial.
"""

from __future__ import annotations

import json
import logging
from datetime import date, timedelta
from pathlib import Path
from typing import Any

import numpy as np

from app.core.config import settings

logger = logging.getLogger(__name__)

try:
    import optuna
    _OPTUNA_AVAILABLE = True
except ImportError:
    optuna = None
    _OPTUNA_AVAILABLE = False
    logger.info("Optuna not installed; Tuner will use random search fallback.")


class TrialResult:
    """Result for a single tuning trial."""

    def __init__(
        self,
        trial_id: int,
        params: dict[str, Any],
        ic_mean: float = 0.0,
        icir: float = 0.0,
        rank_ic_mean: float = 0.0,
        rank_icir: float = 0.0,
    ) -> None:
        self.trial_id = trial_id
        self.params = params
        self.ic_mean = ic_mean
        self.icir = icir
        self.rank_ic_mean = rank_ic_mean
        self.rank_icir = rank_icir


class TuneResult:
    """Aggregate result from a tuning study."""

    def __init__(
        self,
        study_name: str,
        model_type: str,
        best_params: dict[str, Any],
        best_icir: float = 0.0,
        trials: list[TrialResult] | None = None,
    ) -> None:
        self.study_name = study_name
        self.model_type = model_type
        self.best_params = best_params
        self.best_icir = best_icir
        self.trials = trials or []


class Tuner:
    """Hyperparameter tuner with Optuna (preferred) or random search fallback.

    Parameters
    ----------
    model_type : str
        Model type to tune (lightgbm, xgboost, etc.).
    param_space : dict, optional
        Search space dict. If None, uses ParamSpace.get(model_type).
    study_name : str, optional
        Name for the Optuna study.
    n_trials : int
        Number of trials to run.
    cv_folds : int
        Number of time-series cross-validation folds.
    direction : str
        "maximize" for ICIR, "minimize" for MSE.
    """

    def __init__(
        self,
        model_type: str = "lightgbm",
        param_space: dict[str, dict] | None = None,
        study_name: str = "tune",
        n_trials: int = 20,
        cv_folds: int = 3,
        direction: str = "maximize",
    ) -> None:
        self.model_type = model_type
        self.study_name = study_name
        self.n_trials = n_trials
        self.cv_folds = cv_folds
        self.direction = direction

        if param_space is None:
            from app.services.tune.param_space import ParamSpace
            param_space = ParamSpace.get(model_type)
        self.param_space = param_space

        self._study: Any = None
        self._results_dir = Path(settings.experiment_dir) / "tuning"

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def tune(self, config: Any) -> TuneResult:
        """Run hyperparameter optimization.

        Parameters
        ----------
        config : ModelTrainRequest-like
            Base training config. The tuner will override hyperparams for
            each trial.

        Returns
        -------
        TuneResult
        """
        if _OPTUNA_AVAILABLE:
            return self._tune_optuna(config)
        else:
            return self._tune_random(config)

    # ------------------------------------------------------------------
    # Optuna backend
    # ------------------------------------------------------------------

    def _tune_optuna(self, config: Any) -> TuneResult:
        direction = "maximize" if self.direction == "maximize" else "minimize"

        # Create or load study
        storage_path = str(self._results_dir / f"{self.study_name}.db")
        self._results_dir.mkdir(parents=True, exist_ok=True)

        study = optuna.create_study(
            study_name=self.study_name,
            direction=direction,
            storage=f"sqlite:///{storage_path}",
            load_if_exists=True,
        )

        def objective(trial: optuna.Trial) -> float:
            trial_params = {}
            for name, spec in self.param_space.items():
                trial_params[name] = self._suggest(trial, name, spec)

            # Merge trial params into config
            merged_config = _merge_config(config, trial_params)

            # Time-series CV
            cv_scores = self._cv_evaluate(merged_config)
            score = float(np.mean(cv_scores)) if cv_scores else 0.0

            return score

        study.optimize(objective, n_trials=self.n_trials)

        trials = []
        for t in study.trials:
            if t.state == optuna.trial.TrialState.COMPLETE:
                trials.append(TrialResult(
                    trial_id=t.number,
                    params=t.params,
                    icir=t.value if self.direction == "maximize" else 0.0,
                    ic_mean=0.0,
                ))

        return TuneResult(
            study_name=self.study_name,
            model_type=self.model_type,
            best_params=study.best_params,
            best_icir=study.best_value if self.direction == "maximize" else 0.0,
            trials=trials,
        )

    # ------------------------------------------------------------------
    # Random search fallback
    # ------------------------------------------------------------------

    def _tune_random(self, config: Any) -> TuneResult:
        logger.info("Using random search (Optuna not available).")
        import random

        best_score = float("-inf") if self.direction == "maximize" else float("inf")
        best_params: dict[str, Any] = {}
        trials: list[TrialResult] = []

        for trial_id in range(self.n_trials):
            trial_params = {}
            for name, spec in self.param_space.items():
                trial_params[name] = self._sample_random(spec)

            merged_config = _merge_config(config, trial_params)
            cv_scores = self._cv_evaluate(merged_config)
            score = float(np.mean(cv_scores)) if cv_scores else 0.0

            is_better = (
                (self.direction == "maximize" and score > best_score)
                or (self.direction == "minimize" and score < best_score)
            )
            if is_better:
                best_score = score
                best_params = trial_params

            trials.append(TrialResult(
                trial_id=trial_id,
                params=trial_params,
                icir=score if self.direction == "maximize" else 0.0,
                ic_mean=0.0,
            ))

        return TuneResult(
            study_name=self.study_name,
            model_type=self.model_type,
            best_params=best_params,
            best_icir=best_score if self.direction == "maximize" else 0.0,
            trials=trials,
        )

    # ------------------------------------------------------------------
    # CV evaluation
    # ------------------------------------------------------------------

    def _cv_evaluate(self, config: Any) -> list[float]:
        """Time-series cross-validation: split training range into folds."""
        from app.services.model.trainer import ModelConfig, ModelTrainer

        total_days = (config.train_end - config.train_start).days
        if total_days < 60:
            return [0.0]

        fold_days = total_days // (self.cv_folds + 1)
        trainer = ModelTrainer()
        scores: list[float] = []

        for fold in range(self.cv_folds):
            fold_train_end = config.train_start + timedelta(
                days=(fold + 1) * fold_days
            )
            fold_valid_start = fold_train_end + timedelta(days=1)
            fold_valid_end = fold_valid_start + timedelta(days=max(fold_days // 3, 20))

            try:
                fold_config = ModelConfig(
                    model_name=f"{config.model_name}_cv{fold}",
                    model_type=config.model_type,
                    factor_set=config.factor_set,
                    train_start=config.train_start,
                    train_end=fold_train_end,
                    valid_start=fold_valid_start,
                    valid_end=fold_valid_end,
                    test_start=fold_valid_end + timedelta(days=1),
                    test_end=fold_valid_end + timedelta(days=max(fold_days // 3, 20)),
                    stock_pool=config.stock_pool,
                    label_type=config.label_type,
                    **getattr(config, "hyperparams", {}),
                )
                result = trainer.train(fold_config)
                scores.append(result.icir if self.direction == "maximize" else -result.icir)
            except Exception as exc:
                logger.warning("CV fold %d failed: %s", fold, exc)
                continue

        return scores

    # ------------------------------------------------------------------
    # Parameter suggestion helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _suggest(trial: Any, name: str, spec: dict) -> Any:
        """Suggest a parameter value via Optuna trial."""
        t = spec["type"]
        if t == "int":
            return trial.suggest_int(name, spec["low"], spec["high"], log=spec.get("log", False))
        elif t == "float":
            return trial.suggest_float(name, spec["low"], spec["high"], log=spec.get("log", False))
        elif t == "categorical":
            return trial.suggest_categorical(name, spec["choices"])
        raise ValueError(f"Unknown param type: {t}")

    @staticmethod
    def _sample_random(spec: dict) -> Any:
        """Randomly sample a parameter value."""
        import random
        t = spec["type"]
        if t == "int":
            if spec.get("log"):
                val = int(np.exp(random.uniform(np.log(spec["low"]), np.log(spec["high"]))))
            else:
                val = random.randint(spec["low"], spec["high"])
            return val
        elif t == "float":
            if spec.get("log"):
                val = np.exp(random.uniform(np.log(spec["low"]), np.log(spec["high"])))
            else:
                val = random.uniform(spec["low"], spec["high"])
            return float(val)
        elif t == "categorical":
            return random.choice(spec["choices"])
        raise ValueError(f"Unknown param type: {t}")


def _merge_config(config: Any, params: dict) -> Any:
    """Merge trial hyperparams into config, returning a modified copy."""
    config_copy = _shallow_copy_config(config)
    existing = getattr(config_copy, "hyperparams", {})
    if existing:
        merged = {**existing, **params}
    else:
        merged = params
    config_copy.hyperparams = merged
    return config_copy


def _shallow_copy_config(config: Any) -> Any:
    """Create a shallow copy of a Pydantic/simple config object."""
    import copy
    try:
        return config.model_copy(update={})
    except AttributeError:
        return copy.copy(config)
