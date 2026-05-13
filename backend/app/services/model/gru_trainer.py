"""
GRU trainer: 2-layer GRU with dropout for time-series stock prediction.

Implements BaseModel interface. Requires PyTorch.
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

    class _GRUModel(nn.Module):
        """2-layer GRU followed by a linear head."""

        def __init__(
            self,
            n_features: int,
            hidden_size: int = 64,
            num_layers: int = 2,
            dropout: float = 0.2,
        ):
            super().__init__()
            self.gru = nn.GRU(
                input_size=n_features,
                hidden_size=hidden_size,
                num_layers=num_layers,
                dropout=dropout if num_layers > 1 else 0.0,
                batch_first=True,
            )
            self.head = nn.Linear(hidden_size, 1)

        def forward(self, x):
            x = x.unsqueeze(1)
            out, _ = self.gru(x)
            last = out[:, -1, :]
            return self.head(last)


    class GRUTrainer(BaseModel, TorchTrainerMixin):
        """GRU model trainer."""

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
            model = _GRUModel(
                n_features=X_train.shape[1],
                hidden_size=getattr(config, "num_leaves", 64),
                num_layers=2,
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
                "GRU model loading requires n_features; use GRUTrainer.fit() instead"
            )

else:
    class GRUTrainer:
        def __init__(self):
            raise RuntimeError("PyTorch is required for GRUTrainer.")
