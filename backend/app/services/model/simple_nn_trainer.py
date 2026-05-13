"""
SimpleNN trainer: configurable MLP with flexible hidden layers.

More flexible than the sklearn-based MLPTrainer. Supports arbitrary depths
and widths via config, with PyTorch backend.
"""

from __future__ import annotations

import logging
from typing import Any

import numpy as np

from app.services.model.base import BaseModel

logger = logging.getLogger(__name__)

try:
    import torch
    import torch.nn as nn

    from app.services.model.torch_utils import TorchTrainerMixin, _PT_AVAILABLE
except ImportError:
    nn = None  # type: ignore[assignment]
    TorchTrainerMixin = None  # type: ignore[assignment]
    _PT_AVAILABLE = False


if _PT_AVAILABLE:

    class _MLPModel(nn.Module):
        """Configurable MLP with batch norm and dropout."""

        def __init__(
            self,
            n_features: int,
            hidden_sizes: list[int] | None = None,
            dropout: float = 0.2,
        ):
            super().__init__()
            if hidden_sizes is None:
                hidden_sizes = [128, 64, 32]

            layers = []
            in_dim = n_features
            for h in hidden_sizes:
                layers.append(nn.Linear(in_dim, h))
                layers.append(nn.BatchNorm1d(h))
                layers.append(nn.ReLU())
                layers.append(nn.Dropout(dropout))
                in_dim = h
            layers.append(nn.Linear(in_dim, 1))
            self.net = nn.Sequential(*layers)

        def forward(self, x):
            return self.net(x)


    class SimpleNNTrainer(BaseModel, TorchTrainerMixin):
        """Simple MLP trainer with configurable architecture."""

        def __init__(self):
            TorchTrainerMixin.__init__(self)
            self._criterion = nn.MSELoss()

        def fit(
            self,
            X_train: np.ndarray,
            y_train: np.ndarray,
            X_valid: np.ndarray,
            y_valid: np.ndarray,
            config: Any,
        ) -> nn.Module:
            hidden = getattr(config, "num_leaves", 128)
            layers = [hidden, hidden // 2, hidden // 4]

            model = _MLPModel(
                n_features=X_train.shape[1],
                hidden_sizes=layers,
                dropout=getattr(config, "subsample", 0.2),
            )
            return self._train_loop(model, X_train, y_train, X_valid, y_valid, config)

        def predict(self, model: nn.Module, X: np.ndarray) -> np.ndarray:
            return self._predict_batches(model, X)

        def get_feature_importance(
            self, model: nn.Module, feature_names: list[str]
        ) -> dict[str, float]:
            try:
                model = model.to(self._device)
                model.eval()
                n_sample = min(len(X), 1000)
                X_sample = X[:n_sample]
                X_t = torch.tensor(X_sample, dtype=torch.float32, device=self._device)
                X_t.requires_grad_(True)
                out = model(X_t)
                grad = torch.autograd.grad(out.sum(), X_t)[0]
                imp = grad.abs().mean(dim=0).cpu().numpy()
                return dict(
                    sorted(zip(feature_names, imp), key=lambda kv: -kv[1])
                )
            except Exception:
                return {}

        def save(self, model: nn.Module, path: str) -> None:
            torch.save(model.state_dict(), path)

        def load(self, path: str) -> nn.Module:
            raise NotImplementedError(
                "SimpleNN loading requires n_features; use SimpleNNTrainer.fit() instead"
            )

else:
    class SimpleNNTrainer:
        def __init__(self):
            raise RuntimeError("PyTorch is required for SimpleNNTrainer.")
