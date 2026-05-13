"""Model training, prediction, and comparison API routes."""

from fastapi import APIRouter, HTTPException, status

from app.schemas.factor import (
    ModelCompareItem,
    ModelCompareRequest,
    ModelCompareResponse,
    ModelPredictRequest,
    ModelPredictResponse,
    ModelTrainRequest,
    ModelTrainResponse,
    RollingTrainRequest,
    RollingTrainResponse,
    StockScore,
    WindowResultSchema,
)
from app.services.model.trainer import ModelConfig, ModelTrainer
from app.services.model.predictor import ModelPredictor
from app.services.model.rolling_retrainer import RollingRetrainer
from app.schemas.tune import TuneConfig, TuneResultSchema, TrialResultSchema

router = APIRouter(prefix="/models", tags=["models"])


@router.post("/train", response_model=ModelTrainResponse)
def train_model(req: ModelTrainRequest) -> ModelTrainResponse:
    # Validate model_type against available trainers
    valid_types = {
        "lightgbm", "xgboost", "catboost", "mlp",
        "lstm", "gru", "transformer", "tcn", "tabnet",
        "simple_nn", "ridge", "lasso", "double_ensemble",
    }
    if req.model_type not in valid_types:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Unsupported model_type: {req.model_type!r}. Valid: {sorted(valid_types)}",
        )

    config = ModelConfig(
        model_name=req.model_name,
        model_type=req.model_type,
        factor_set=req.factor_set,
        train_start=req.train_start,
        train_end=req.train_end,
        valid_start=req.valid_start,
        valid_end=req.valid_end,
        test_start=req.test_start,
        test_end=req.test_end,
        stock_pool=req.stock_pool,
        label_type=req.label_type,
        **req.hyperparams,
    )
    trainer = ModelTrainer()
    result = trainer.train(config)
    return ModelTrainResponse(
        model_name=result.model_name,
        model_type=result.model_type,
        factor_set=result.factor_set,
        ic_mean=result.ic_mean,
        ic_std=result.ic_std,
        icir=result.icir,
        rank_ic_mean=result.rank_ic_mean,
        rank_ic_std=result.rank_ic_std,
        rank_icir=result.rank_icir,
        mse=result.mse,
        mae=result.mae,
        feature_importance=result.feature_importance,
        status="completed",
    )


@router.post("/predict", response_model=ModelPredictResponse)
def predict(req: ModelPredictRequest) -> ModelPredictResponse:
    predictor = ModelPredictor()
    df = predictor.predict(
        model_name=req.model_name,
        codes=req.codes,
        predict_date=req.predict_date,
        model_type=req.model_type,
    )
    predictions = [
        StockScore(code=row["code"], score=row["score"], rank=row["rank"])
        for _, row in df.iterrows()
    ]
    return ModelPredictResponse(predictions=predictions)


@router.get("")
def list_models() -> list[dict]:
    trainer = ModelTrainer()
    names = trainer.list_trained_models()
    result: list[dict] = []
    for name in names:
        item: dict = {"model_name": name}
        # Detect model type from file extensions
        from pathlib import Path
        from app.core.config import settings

        model_dir = Path(settings.model_dir)
        for mt, ext in [("lightgbm", ".txt"), ("xgboost", ".json"), ("catboost", ".cbm"), ("mlp", ".joblib")]:
            p = model_dir / f"{name}{ext}"
            if p.exists():
                item["model_type"] = mt
                item["file"] = p.name
                break
        result.append(item)
    return result


@router.get("/{model_name}")
def get_model(model_name: str) -> dict:
    trainer = ModelTrainer()
    names = trainer.list_trained_models()
    if model_name not in names:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Model not found")
    return {"model_name": model_name, "status": "trained"}


@router.post("/compare", response_model=ModelCompareResponse)
def compare_models(req: ModelCompareRequest) -> ModelCompareResponse:
    from app.services.model.comparison import ModelComparator

    config = ModelConfig(
        model_name=req.model_name_prefix,
        factor_set=req.factor_set,
        train_start=req.train_start,
        train_end=req.train_end,
        valid_start=req.valid_start,
        valid_end=req.valid_end,
        test_start=req.test_start,
        test_end=req.test_end,
        stock_pool=req.stock_pool,
        label_type=req.label_type,
        **req.hyperparams,
    )
    comparator = ModelComparator(ModelTrainer())
    raw = comparator.compare(config, req.model_types)

    items = [ModelCompareItem(**r) for r in raw]
    best = max(
        (i for i in items if i.status == "completed"),
        key=lambda x: x.icir,
        default=None,
    )
    return ModelCompareResponse(
        comparison=items,
        best_model=best.model_type if best else "",
    )


@router.post("/rolling-train", response_model=RollingTrainResponse)
def rolling_train(req: RollingTrainRequest) -> RollingTrainResponse:
    """Run rolling-window retraining to measure IC stability and alpha decay.

    Trains the same model type on successive time windows, tracking IC
    metrics across each window.  The ``ic_decay_trend`` field captures the
    slope of per-window IC — a negative value indicates alpha decay.
    """
    import numpy as np

    retrainer = RollingRetrainer()
    results = retrainer.run(req)

    windows = [
        WindowResultSchema(
            window_index=r.window_index,
            train_start=r.train_start,
            train_end=r.train_end,
            valid_start=r.valid_start,
            valid_end=r.valid_end,
            test_start=r.test_start,
            test_end=r.test_end,
            ic_mean=r.ic_mean,
            icir=r.icir,
            rank_ic_mean=r.rank_ic_mean,
            rank_icir=r.rank_icir,
            model_path=r.model_path,
        )
        for r in results
    ]

    # Compute IC decay trend (slope of IC over windows)
    decay_trend = 0.0
    valid_ics = [w.ic_mean for w in results if w.ic_mean != 0]
    if len(valid_ics) >= 2:
        x = np.arange(len(valid_ics))
        y = np.array(valid_ics)
        decay_trend = float(np.polyfit(x, y, 1)[0])

    return RollingTrainResponse(
        windows=windows,
        ic_decay_trend=round(decay_trend, 6),
        model_type=req.model_type,
        factor_set=req.factor_set,
        total_windows=len(windows),
    )


@router.post("/multitask", response_model=dict)
def train_multitask(req: ModelTrainRequest) -> dict:
    """Train a multi-task model predicting multiple return horizons jointly.

    Trains separate models for next_ret1/5/10/20, sharing factor data.
    """
    try:
        from app.services.model.trainer_rm import TrainerRM
    except ImportError:
        raise HTTPException(
            status_code=status.HTTP_501_NOT_IMPLEMENTED,
            detail="Multi-task trainer not available.",
        )

    trainer_rm = TrainerRM()
    config = ModelConfig(
        model_name=req.model_name,
        model_type=req.model_type,
        factor_set=req.factor_set,
        train_start=req.train_start,
        train_end=req.train_end,
        valid_start=req.valid_start,
        valid_end=req.valid_end,
        test_start=req.test_start,
        test_end=req.test_end,
        stock_pool=req.stock_pool,
        label_type=req.label_type,
        **req.hyperparams,
    )
    result = trainer_rm.train(config)

    return {
        "model_name": result.model_name,
        "horizons": result.horizons,
        "ic_means": result.ic_means,
        "rank_ic_means": result.rank_ic_means,
        "icirs": result.icirs,
        "rank_icirs": result.rank_icirs,
        "feature_importance": result.feature_importance,
        "model_paths": result.model_paths,
        "status": "completed",
    }


@router.post("/tune", response_model=TuneResultSchema)
def tune_model(req: TuneConfig) -> TuneResultSchema:
    """Run hyperparameter optimization for a model type."""
    try:
        from app.services.tune.tuner import Tuner
    except ImportError:
        raise HTTPException(
            status_code=status.HTTP_501_NOT_IMPLEMENTED,
            detail="Tuner not available. Install optuna.",
        )

    tuner = Tuner(
        model_type=req.model_type,
        study_name=req.study_name,
        n_trials=req.n_trials,
        cv_folds=req.cv_folds,
        direction=req.direction,
    )
    result = tuner.tune(req)

    return TuneResultSchema(
        study_name=result.study_name,
        model_type=result.model_type,
        best_params=result.best_params,
        best_icir=result.best_icir,
        trials=[
            TrialResultSchema(
                trial_id=t.trial_id,
                params=t.params,
                ic_mean=t.ic_mean,
                icir=t.icir,
                rank_ic_mean=t.rank_ic_mean,
                rank_icir=t.rank_icir,
            )
            for t in result.trials
        ],
    )


@router.get("/tune/{study_name}", response_model=TuneResultSchema)
def get_tune_result(study_name: str) -> TuneResultSchema:
    """Retrieve results from a previous tuning study."""
    from pathlib import Path
    from app.core.config import settings

    results_dir = Path(settings.experiment_dir) / "tuning"
    db_path = results_dir / f"{study_name}.db"

    if not db_path.exists():
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Study '{study_name}' not found.",
        )

    try:
        import optuna
        study = optuna.load_study(
            study_name=study_name,
            storage=f"sqlite:///{db_path}",
        )
    except ImportError:
        raise HTTPException(
            status_code=status.HTTP_501_NOT_IMPLEMENTED,
            detail="Optuna not installed.",
        )
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Study '{study_name}' could not be loaded.",
        )

    trials = []
    for t in study.trials:
        if t.state == optuna.trial.TrialState.COMPLETE:
            trials.append(TrialResultSchema(
                trial_id=t.number,
                params=t.params,
                icir=t.value if t.value is not None else 0.0,
            ))

    return TuneResultSchema(
        study_name=study_name,
        model_type="",
        best_params=study.best_params,
        best_icir=study.best_value if study.best_value is not None else 0.0,
        trials=trials,
    )
