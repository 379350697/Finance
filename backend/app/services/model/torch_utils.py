"""
Torch utilities: training loop, early stopping, LR scheduling, device management.

Used by all PyTorch-based model trainers. Gracefully degrades if PyTorch is
not installed.
"""

from __future__ import annotations

import logging
from typing import Any

import numpy as np

logger = logging.getLogger(__name__)

try:
    import torch
    import torch.nn as nn
    from torch.utils.data import DataLoader, TensorDataset

    _PT_AVAILABLE = True
except ImportError:  # pragma: no cover
    torch = None  # type: ignore[assignment]
    nn = None  # type: ignore[assignment]
    DataLoader = None  # type: ignore[assignment]
    TensorDataset = None  # type: ignore[assignment]
    _PT_AVAILABLE = False
    logger.info("PyTorch not installed; DL models will be unavailable.")


# ---------------------------------------------------------------------------
# Early stopping (always available — no torch dependency)
# ---------------------------------------------------------------------------


class EarlyStopping:
    """Early stopping tracker.

    Parameters
    ----------
    patience : int
        Number of epochs with no improvement before stopping.
    min_delta : float
        Minimum change to qualify as improvement.
    mode : str
        "min" (loss) or "max" (IC, etc.).
    """

    def __init__(self, patience: int = 10, min_delta: float = 1e-4, mode: str = "min"):
        self.patience = patience
        self.min_delta = min_delta
        self.mode = mode
        self.best_score: float | None = None
        self.counter = 0
        self.early_stop = False

    def __call__(self, score: float) -> bool:
        if self.best_score is None:
            self.best_score = score
            return False

        if self.mode == "min":
            improved = score < self.best_score - self.min_delta
        else:
            improved = score > self.best_score + self.min_delta

        if improved:
            self.best_score = score
            self.counter = 0
        else:
            self.counter += 1
            if self.counter >= self.patience:
                self.early_stop = True

        return self.early_stop


# ---------------------------------------------------------------------------
# PyTorch-dependent classes (only defined when PyTorch is available)
# ---------------------------------------------------------------------------

if _PT_AVAILABLE:

    class TorchDataset:
        """Wraps numpy arrays into a PyTorch TensorDataset."""

        def __init__(self, X: np.ndarray, y: np.ndarray | None = None):
            self.X_t = torch.tensor(X, dtype=torch.float32)
            self.y_t = (
                torch.tensor(y, dtype=torch.float32).reshape(-1, 1)
                if y is not None
                else None
            )

        def to_loader(self, batch_size: int = 1024, shuffle: bool = False) -> Any:
            ds = (
                TensorDataset(self.X_t, self.y_t)
                if self.y_t is not None
                else TensorDataset(self.X_t)
            )
            return DataLoader(ds, batch_size=batch_size, shuffle=shuffle)

    class TorchTrainerMixin:
        """Mixin providing standard PyTorch training loop, LR scheduling, and device
        management for DL model trainers.

        Subclasses must define:
            - self._build_model(n_features: int) -> nn.Module
            - self._criterion (nn.Module)
        """

        def __init__(self):
            self._device = torch.device(
                "cuda" if torch.cuda.is_available() else "cpu"
            )

        def _train_loop(
            self,
            model: nn.Module,
            X_train: np.ndarray,
            y_train: np.ndarray,
            X_valid: np.ndarray,
            y_valid: np.ndarray,
            config: Any,
        ) -> nn.Module:
            lr = getattr(config, "learning_rate", 1e-3)
            epochs = getattr(config, "n_estimators", 100)
            patience = getattr(config, "early_stopping_rounds", 10)

            model = model.to(self._device)

            ds_train = TorchDataset(X_train, y_train)
            ds_valid = TorchDataset(X_valid, y_valid)

            train_loader = ds_train.to_loader(batch_size=1024, shuffle=True)
            valid_loader = ds_valid.to_loader(batch_size=4096, shuffle=False)

            optimizer = torch.optim.Adam(model.parameters(), lr=lr)
            scheduler = torch.optim.lr_scheduler.ReduceLROnPlateau(
                optimizer, mode="min", factor=0.5, patience=max(1, patience // 2)
            )

            stopper = EarlyStopping(patience=patience, mode="min")
            best_state: dict | None = None

            for epoch in range(epochs):
                model.train()
                for batch in train_loader:
                    if len(batch) == 2:
                        Xb, yb = batch
                    else:
                        Xb = batch[0]
                        continue
                    Xb, yb = Xb.to(self._device), yb.to(self._device)
                    optimizer.zero_grad()
                    pred = model(Xb)
                    loss = self._criterion(pred, yb)
                    loss.backward()
                    optimizer.step()

                model.eval()
                val_loss = 0.0
                val_batches = 0
                with torch.no_grad():
                    for batch in valid_loader:
                        if len(batch) == 2:
                            Xb, yb = batch
                        else:
                            continue
                        Xb, yb = Xb.to(self._device), yb.to(self._device)
                        pred = model(Xb)
                        val_loss += self._criterion(pred, yb).item()
                        val_batches += 1

                avg_val = val_loss / max(val_batches, 1)
                scheduler.step(avg_val)

                if best_state is None or avg_val < stopper.best_score - stopper.min_delta:
                    best_state = {k: v.cpu().clone() for k, v in model.state_dict().items()}

                if stopper(avg_val):
                    logger.debug("Early stopping at epoch %d", epoch + 1)
                    break

            if best_state is not None:
                model.load_state_dict(best_state)

            model.eval()
            return model

        def _predict_batches(self, model: nn.Module, X: np.ndarray) -> np.ndarray:
            model = model.to(self._device)
            model.eval()
            ds = TorchDataset(X)
            loader = ds.to_loader(batch_size=4096, shuffle=False)

            preds: list[np.ndarray] = []
            with torch.no_grad():
                for batch in loader:
                    Xb = batch[0].to(self._device)
                    p = model(Xb).cpu().numpy()
                    preds.append(p)

            return np.concatenate(preds, axis=0).ravel()

else:
    TorchDataset = None  # type: ignore[assignment]
    TorchTrainerMixin = None  # type: ignore[assignment]
