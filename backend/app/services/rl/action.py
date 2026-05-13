"""
ActionInterpreter: translates RL model outputs into executable actions.

Provides:
    ActionInterpreter (ABC)
    DiscreteActionInterpreter  Discretizes to N bins (e.g. 0%, 25%, 50%, 75%, 100%).
    ContinuousActionInterpreter  Maps to [0, 1] range directly.
"""

from __future__ import annotations

from abc import ABC, abstractmethod

import numpy as np


class ActionInterpreter(ABC):
    """Translates model output into an executable action."""

    @abstractmethod
    def interpret(self, model_output: np.ndarray) -> float:
        """Convert model output to a scalar action."""

    @abstractmethod
    def action_dim(self) -> int:
        """Return the dimension of the action space."""


class DiscreteActionInterpreter(ActionInterpreter):
    """Discrete action space: choose from N bins.

    Action bins represent fractions of remaining shares to execute.

    Parameters
    ----------
    n_bins : int
        Number of discrete action choices (default 5: 0%, 25%, 50%, 75%, 100%).
    """

    def __init__(self, n_bins: int = 5):
        self.n_bins = n_bins
        self._bins = np.linspace(0, 1, n_bins)

    def action_dim(self) -> int:
        return self.n_bins

    def interpret(self, model_output: np.ndarray) -> float:
        """Model output can be logits (n_bins,) or a scalar index.

        Returns a fraction in [0, 1].
        """
        if model_output.ndim == 0:
            idx = int(np.clip(model_output, 0, self.n_bins - 1))
        else:
            idx = int(np.argmax(model_output))
        idx = min(idx, self.n_bins - 1)
        return self._bins[idx]

    @property
    def bins(self) -> np.ndarray:
        return self._bins.copy()


class ContinuousActionInterpreter(ActionInterpreter):
    """Continuous action space: directly maps to [0, 1] fraction.

    Model output is expected to be a single scalar, optionally passed
    through a sigmoid/tanh transform.
    """

    def __init__(self, use_tanh: bool = True, scale: float = 1.0):
        self.use_tanh = use_tanh
        self.scale = scale

    def action_dim(self) -> int:
        return 1

    def interpret(self, model_output: np.ndarray) -> float:
        """Map model output to [0, 1]."""
        if model_output.ndim > 0:
            val = float(model_output.ravel()[0])
        else:
            val = float(model_output)

        if self.use_tanh:
            val = (np.tanh(val * self.scale) + 1.0) / 2.0

        return float(np.clip(val, 0.0, 1.0))
