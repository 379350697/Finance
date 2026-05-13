"""
EnvFactory: assembles RL environment from components.

Composes Simulator + StateInterpreter + ActionInterpreter + Reward into
a unified Gym-compatible environment.
"""

from __future__ import annotations

import logging
from typing import Any

import numpy as np

logger = logging.getLogger(__name__)

try:
    import gymnasium as gym

    _GYM_AVAILABLE = True
except ImportError:
    gym = None  # type: ignore[assignment]
    _GYM_AVAILABLE = False
    logger.info("gymnasium not installed; RL EnvFactory will be unavailable.")


if _GYM_AVAILABLE:

    class _OrderExecEnv(gym.Env):
        """Gym-compatible order execution environment."""

        def __init__(
            self,
            simulator: Any,
            state_interpreter: Any,
            action_interpreter: Any,
            reward_fn: Any,
        ):
            super().__init__()
            self.simulator = simulator
            self.state_interpreter = state_interpreter
            self.action_interpreter = action_interpreter
            self.reward_fn = reward_fn

            state_dim = state_interpreter.state_dim()
            self.observation_space = gym.spaces.Box(
                low=-np.inf, high=np.inf, shape=(state_dim,), dtype=np.float32
            )

            act_dim = action_interpreter.action_dim()
            if act_dim > 1:
                self.action_space = gym.spaces.Discrete(act_dim)
            else:
                self.action_space = gym.spaces.Box(
                    low=0.0, high=1.0, shape=(1,), dtype=np.float32
                )

        def reset(self, *, seed: int | None = None, options: dict | None = None):
            if seed is not None:
                self.simulator.seed(seed)
            raw_state = self.simulator.reset()
            if hasattr(self.state_interpreter, "reset"):
                self.state_interpreter.reset()
            obs = self.state_interpreter.build_state({
                "remain": float(raw_state[0]) * 10000 if hasattr(raw_state, '__getitem__') else 5000,
                "step_count": 0,
                "current_price": 100.0,
                "executed": 0,
            })
            return obs, {}

        def step(self, action):
            if isinstance(self.action_space, gym.spaces.Discrete):
                frac = self.action_interpreter.interpret(np.array([action]))
            else:
                frac = self.action_interpreter.interpret(action)

            next_state, reward, done, info = self.simulator.step(frac)
            obs = self.state_interpreter.build_state({
                "remain": info.get("remain", 0),
                "step_count": info.get("step", 0),
                "current_price": info.get("price", 100.0),
                "executed": info.get("shares_executed", 0),
            })

            r = self.reward_fn.compute(info)
            return obs, r, done, False, info

else:
    _OrderExecEnv = None  # type: ignore[assignment]


class EnvFactory:
    """Assembles RL environments from components.

    Parameters
    ----------
    simulator : Simulator
    state_interpreter : StateInterpreter
    action_interpreter : ActionInterpreter
    reward_fn : Reward
    """

    def __init__(
        self,
        simulator: Any | None = None,
        state_interpreter: Any | None = None,
        action_interpreter: Any | None = None,
        reward_fn: Any | None = None,
    ):
        self.simulator = simulator
        self.state_interpreter = state_interpreter
        self.action_interpreter = action_interpreter
        self.reward_fn = reward_fn

    def build(self) -> Any:
        """Build and return a Gym-compatible environment."""
        if not _GYM_AVAILABLE:
            raise RuntimeError("gymnasium is required for RL environments.")

        if self.simulator is None:
            from app.services.rl.simulator import OrderExecutionSimulator
            self.simulator = OrderExecutionSimulator()
        if self.state_interpreter is None:
            from app.services.rl.interpreter import ExecutionStateInterpreter
            self.state_interpreter = ExecutionStateInterpreter()
        if self.action_interpreter is None:
            from app.services.rl.action import DiscreteActionInterpreter
            self.action_interpreter = DiscreteActionInterpreter()
        if self.reward_fn is None:
            from app.services.rl.reward import ExecutionCostReward
            self.reward_fn = ExecutionCostReward()

        return _OrderExecEnv(
            simulator=self.simulator,
            state_interpreter=self.state_interpreter,
            action_interpreter=self.action_interpreter,
            reward_fn=self.reward_fn,
        )
