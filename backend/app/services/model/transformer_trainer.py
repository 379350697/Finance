"""
Transformer trainer: positional encoding + multi-head self-attention + feed-forward.

Implements BaseModel interface. Requires PyTorch.
"""

from __future__ import annotations

import logging
import math
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

    class _PositionalEncoding(nn.Module):
        """Sinusoidal positional encoding."""

        def __init__(self, d_model: int, max_len: int = 1):
            super().__init__()
            pe = torch.zeros(max_len, d_model)
            position = torch.arange(0, max_len, dtype=torch.float).unsqueeze(1)
            div_term = torch.exp(
                torch.arange(0, d_model, 2).float()
                * (-math.log(10000.0) / d_model)
            )
            pe[:, 0::2] = torch.sin(position * div_term)
            pe[:, 1::2] = torch.cos(position * div_term)
            self.register_buffer("pe", pe)

        def forward(self, x):
            return x + self.pe[: x.size(1)]


    class _TransformerModel(nn.Module):
        """Transformer encoder with a linear prediction head."""

        def __init__(
            self,
            n_features: int,
            d_model: int = 64,
            nhead: int = 4,
            num_layers: int = 2,
            dropout: float = 0.1,
        ):
            super().__init__()
            self.input_proj = nn.Linear(n_features, d_model)
            self.pos_encoder = _PositionalEncoding(d_model, max_len=1)
            encoder_layer = nn.TransformerEncoderLayer(
                d_model=d_model, nhead=nhead, dropout=dropout, batch_first=True,
            )
            self.encoder = nn.TransformerEncoder(encoder_layer, num_layers=num_layers)
            self.head = nn.Linear(d_model, 1)

        def forward(self, x):
            x = self.input_proj(x).unsqueeze(1)
            x = self.pos_encoder(x)
            x = self.encoder(x)
            last = x[:, -1, :]
            return self.head(last)


    class TransformerTrainer(BaseModel, TorchTrainerMixin):
        """Transformer model trainer."""

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
            d_model = getattr(config, "num_leaves", 64)
            model = _TransformerModel(
                n_features=X_train.shape[1],
                d_model=d_model,
                nhead=max(2, d_model // 16),
                num_layers=2,
                dropout=getattr(config, "subsample", 0.1),
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
                "Transformer model loading requires n_features; use fit() instead"
            )

else:
    class TransformerTrainer:
        def __init__(self):
            raise RuntimeError("PyTorch is required for TransformerTrainer.")
