"""
TCN trainer: Temporal Convolutional Network with dilated causal convolutions.

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

    class _CausalConv1d(nn.Module):
        """Causal (left-padded) 1D convolution."""

        def __init__(self, in_channels: int, out_channels: int, kernel_size: int,
                     dilation: int = 1):
            super().__init__()
            self.padding = (kernel_size - 1) * dilation
            self.conv = nn.Conv1d(
                in_channels, out_channels, kernel_size,
                dilation=dilation, padding=self.padding,
            )

        def forward(self, x):
            out = self.conv(x)
            if self.padding > 0:
                out = out[:, :, : -self.padding]
            return out


    class _TCNBlock(nn.Module):
        """TCN residual block with dilation."""

        def __init__(self, channels: int, kernel_size: int, dilation: int, dropout: float):
            super().__init__()
            self.conv1 = _CausalConv1d(channels, channels, kernel_size, dilation)
            self.conv2 = _CausalConv1d(channels, channels, kernel_size, dilation)
            self.relu = nn.ReLU()
            self.dropout = nn.Dropout(dropout)

        def forward(self, x):
            residual = x
            out = self.relu(self.conv1(x))
            out = self.dropout(out)
            out = self.relu(self.conv2(out))
            out = self.dropout(out)
            return self.relu(out + residual)


    class _TCNModel(nn.Module):
        """TCN encoder with a linear head."""

        def __init__(
            self,
            n_features: int,
            hidden_size: int = 64,
            kernel_size: int = 3,
            num_layers: int = 4,
            dropout: float = 0.2,
        ):
            super().__init__()
            self.input_proj = nn.Linear(n_features, hidden_size)
            layers = []
            for i in range(num_layers):
                layers.append(
                    _TCNBlock(hidden_size, kernel_size, 2 ** i, dropout)
                )
            self.tcn = nn.Sequential(*layers)
            self.head = nn.Linear(hidden_size, 1)

        def forward(self, x):
            x = self.input_proj(x).unsqueeze(2)
            x = self.tcn(x)
            last = x[:, :, -1]
            return self.head(last)


    class TCNTrainer(BaseModel, TorchTrainerMixin):
        """TCN model trainer."""

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
            model = _TCNModel(
                n_features=X_train.shape[1],
                hidden_size=getattr(config, "num_leaves", 64),
                kernel_size=3,
                num_layers=4,
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
                "TCN model loading requires n_features; use TCNTrainer.fit() instead"
            )

else:
    class TCNTrainer:
        def __init__(self):
            raise RuntimeError("PyTorch is required for TCNTrainer.")
