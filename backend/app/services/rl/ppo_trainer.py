"""
PPOTrainer: Proximal Policy Optimization for order execution.

Two backends:
    1. stable-baselines3 PPO (preferred if installed)
    2. Minimal pure-PyTorch PPO implementation (fallback)
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

import numpy as np

logger = logging.getLogger(__name__)

# ── Optional: stable-baselines3 ──────────────────────────────────────────

try:
    from stable_baselines3 import PPO
    from stable_baselines3.common.vec_env import DummyVecEnv

    _SB3_AVAILABLE = True
except ImportError:  # pragma: no cover
    PPO = None  # type: ignore[assignment]
    DummyVecEnv = None  # type: ignore[assignment]
    _SB3_AVAILABLE = False
    logger.info("stable-baselines3 not installed; using minimal PPO implementation.")

# ── Optional: PyTorch (for minimal implementation) ───────────────────────

try:
    import torch
    import torch.nn as nn
    import torch.optim as optim

    _PT_AVAILABLE = True
except ImportError:  # pragma: no cover
    torch = None  # type: ignore[assignment]
    nn = None  # type: ignore[assignment]
    optim = None  # type: ignore[assignment]
    _PT_AVAILABLE = False


# ===========================================================================
# PyTorch-dependent classes
# ===========================================================================

if _PT_AVAILABLE:

    class _ActorCritic(nn.Module):
        """Shared-backbone Actor-Critic network."""

        def __init__(self, state_dim: int, action_dim: int, hidden: int = 64):
            super().__init__()
            self.shared = nn.Sequential(
                nn.Linear(state_dim, hidden),
                nn.ReLU(),
                nn.Linear(hidden, hidden),
                nn.ReLU(),
            )
            self.actor = nn.Linear(hidden, action_dim)
            self.critic = nn.Linear(hidden, 1)

        def forward(self, x):
            f = self.shared(x)
            return self.actor(f), self.critic(f)


    class _MinimalPPO:
        """Minimal PPO implementation (actor-critic, clipping, GAE)."""

        def __init__(
            self,
            state_dim: int,
            action_dim: int,
            lr: float = 3e-4,
            gamma: float = 0.99,
            eps_clip: float = 0.2,
            gae_lambda: float = 0.95,
            epochs: int = 4,
            hidden: int = 64,
            device: str = "cpu",
        ):
            self.gamma = gamma
            self.eps_clip = eps_clip
            self.gae_lambda = gae_lambda
            self.epochs = epochs

            self.model = _ActorCritic(state_dim, action_dim, hidden).to(device)
            self.optimizer = optim.Adam(self.model.parameters(), lr=lr)
            self.device = device

        def train_step(self, trajectories: list[dict]) -> float:
            if not trajectories:
                return 0.0

            states = torch.FloatTensor(
                np.array([t["state"] for t in trajectories])
            ).to(self.device)
            actions = torch.LongTensor(
                [t["action"] for t in trajectories]
            ).to(self.device)
            rewards = torch.FloatTensor(
                [t["reward"] for t in trajectories]
            ).to(self.device)
            dones = torch.FloatTensor(
                [t["done"] for t in trajectories]
            ).to(self.device)
            old_log_probs = torch.FloatTensor(
                [t["log_prob"] for t in trajectories]
            ).to(self.device)

            with torch.no_grad():
                _, values = self.model(states)
                values = values.squeeze()
                next_values = torch.cat([values[1:], values[-1:]])

            gae = 0.0
            returns = torch.zeros_like(rewards)
            for t in reversed(range(len(rewards))):
                delta = rewards[t] + self.gamma * next_values[t] * (1 - dones[t]) - values[t]
                gae = delta + self.gamma * self.gae_lambda * (1 - dones[t]) * gae
                returns[t] = gae + values[t]

            total_loss = 0.0
            for _ in range(self.epochs):
                logits, values_pred = self.model(states)
                values_pred = values_pred.squeeze()

                log_probs = nn.functional.log_softmax(logits, dim=-1)
                action_log_probs = log_probs.gather(1, actions.unsqueeze(1)).squeeze()

                ratios = torch.exp(action_log_probs - old_log_probs)
                advantages = returns - values_pred.detach()
                advantages = (advantages - advantages.mean()) / (advantages.std() + 1e-8)

                surr1 = ratios * advantages
                surr2 = torch.clamp(ratios, 1 - self.eps_clip, 1 + self.eps_clip) * advantages
                actor_loss = -torch.min(surr1, surr2).mean()

                critic_loss = nn.functional.mse_loss(values_pred, returns)
                loss = actor_loss + 0.5 * critic_loss

                self.optimizer.zero_grad()
                loss.backward()
                self.optimizer.step()
                total_loss += loss.item()

            return total_loss / self.epochs

        def get_action(self, state: np.ndarray) -> tuple[int, float]:
            s = torch.FloatTensor(state).unsqueeze(0).to(self.device)
            with torch.no_grad():
                logits, _ = self.model(s)
                probs = nn.functional.softmax(logits, dim=-1)
                dist = torch.distributions.Categorical(probs)
                action = dist.sample()
                log_prob = dist.log_prob(action).item()
            return int(action.item()), float(log_prob)

        def save(self, path: str) -> None:
            torch.save(self.model.state_dict(), path)

        def load(self, path: str) -> None:
            self.model.load_state_dict(torch.load(path, map_location=self.device))

else:
    _ActorCritic = None  # type: ignore[assignment]
    _MinimalPPO = None  # type: ignore[assignment]


# ===========================================================================
# Public trainer
# ===========================================================================


class PPOTrainer:
    """PPO trainer with auto-backend selection.

    Parameters
    ----------
    use_sb3 : bool
        If True, prefer stable-baselines3. Otherwise use minimal PyTorch.
    """

    def __init__(self, use_sb3: bool = True):
        self._algo: Any = None
        self._backend: str = "none"

        if use_sb3 and _SB3_AVAILABLE:
            self._backend = "sb3"
        elif _PT_AVAILABLE:
            self._backend = "minimal"
        else:
            raise RuntimeError(
                "PPOTrainer requires either stable-baselines3 or PyTorch."
            )

    def train(
        self,
        env,
        total_timesteps: int = 10_000,
        learning_rate: float = 3e-4,
        n_steps: int = 128,
        batch_size: int = 64,
        gamma: float = 0.99,
        gae_lambda: float = 0.95,
        ent_coef: float = 0.01,
        verbose: int = 0,
    ) -> Any:
        if self._backend == "sb3":
            vec_env = DummyVecEnv([lambda: env])
            self._algo = PPO(
                "MlpPolicy",
                vec_env,
                learning_rate=learning_rate,
                n_steps=n_steps,
                batch_size=batch_size,
                gamma=gamma,
                gae_lambda=gae_lambda,
                ent_coef=ent_coef,
                verbose=verbose,
            )
            self._algo.learn(total_timesteps=total_timesteps)
            return self._algo
        else:
            obs_dim = env.reset().shape[0]
            try:
                act_dim = env.action_space.n
            except AttributeError:
                act_dim = 5

            ppo = _MinimalPPO(
                state_dim=obs_dim,
                action_dim=act_dim,
                lr=learning_rate,
                gamma=gamma,
                gae_lambda=gae_lambda,
            )

            obs = env.reset()
            trajectories: list[dict] = []
            step_count = 0

            while step_count < total_timesteps:
                action, log_prob = ppo.get_action(obs)
                next_obs, reward, done, info = env.step(action)
                trajectories.append({
                    "state": obs,
                    "action": action,
                    "reward": reward,
                    "done": float(done),
                    "log_prob": log_prob,
                })
                obs = next_obs
                step_count += 1

                if done:
                    obs = env.reset()

                if len(trajectories) >= n_steps:
                    ppo.train_step(trajectories)
                    trajectories = []

            if trajectories:
                ppo.train_step(trajectories)

            self._algo = ppo
            return ppo

    def predict(self, obs: np.ndarray, deterministic: bool = True) -> tuple[int, Any]:
        if self._algo is None:
            raise RuntimeError("Model not trained. Call train() first.")
        if self._backend == "sb3":
            return self._algo.predict(obs, deterministic=deterministic)
        else:
            action, _ = self._algo.get_action(obs)
            return action, None

    def save(self, path: str) -> None:
        if self._backend == "sb3":
            self._algo.save(path)
        else:
            self._algo.save(path)

    def load(self, path: str) -> None:
        if self._backend == "sb3":
            self._algo = PPO.load(path)
        else:
            raise NotImplementedError(
                "Minimal PPO load requires state_dim; re-create and use .load() on model"
            )
