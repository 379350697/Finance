"""Qlib-style model training, prediction, and registry."""

from app.services.model.trainer import ModelConfig, ModelTrainResult, ModelTrainer
from app.services.model.predictor import ModelPredictor
from app.services.model.registry import ModelRegistry, default_model_registry

# Model factory
try:
    from app.services.model.model_factory import ModelFactory
except ImportError:
    ModelFactory = None  # type: ignore[assignment]

# Deep learning trainers (optional — PyTorch required)
try:
    from app.services.model.lstm_trainer import LSTMTrainer
except ImportError:
    LSTMTrainer = None  # type: ignore[assignment]

try:
    from app.services.model.gru_trainer import GRUTrainer
except ImportError:
    GRUTrainer = None  # type: ignore[assignment]

try:
    from app.services.model.transformer_trainer import TransformerTrainer
except ImportError:
    TransformerTrainer = None  # type: ignore[assignment]

try:
    from app.services.model.tcn_trainer import TCNTrainer
except ImportError:
    TCNTrainer = None  # type: ignore[assignment]

try:
    from app.services.model.tabnet_trainer import TabNetTrainer
except ImportError:
    TabNetTrainer = None  # type: ignore[assignment]

try:
    from app.services.model.simple_nn_trainer import SimpleNNTrainer
except ImportError:
    SimpleNNTrainer = None  # type: ignore[assignment]

try:
    from app.services.model.linear_trainer import LinearTrainer
except ImportError:
    LinearTrainer = None  # type: ignore[assignment]

try:
    from app.services.model.double_ensemble_trainer import DoubleEnsembleTrainer
except ImportError:
    DoubleEnsembleTrainer = None  # type: ignore[assignment]

# Multi-level trainers (Wave 3)
try:
    from app.services.model.trainer_r import TrainerR
except ImportError:
    TrainerR = None  # type: ignore[assignment]

try:
    from app.services.model.trainer_rm import TrainerRM
except ImportError:
    TrainerRM = None  # type: ignore[assignment]

try:
    from app.services.model.delay_trainer_r import DelayTrainerR
except ImportError:
    DelayTrainerR = None  # type: ignore[assignment]

__all__ = [
    "ModelConfig",
    "ModelTrainResult",
    "ModelTrainer",
    "ModelPredictor",
    "ModelRegistry",
    "default_model_registry",
    "ModelFactory",
    "LSTMTrainer",
    "GRUTrainer",
    "TransformerTrainer",
    "TCNTrainer",
    "TabNetTrainer",
    "SimpleNNTrainer",
    "LinearTrainer",
    "DoubleEnsembleTrainer",
    "TrainerR",
    "TrainerRM",
    "DelayTrainerR",
]
