"""ModelRegistry: central registry for model configurations."""

from __future__ import annotations

from app.services.model.trainer import ModelConfig


class ModelRegistry:
    """Registry that stores ModelConfig objects keyed by model name.

    Follows the same pattern as StrategyRegistry.
    """

    def __init__(self) -> None:
        self._models: dict[str, ModelConfig] = {}

    def register(self, config: ModelConfig) -> None:
        """Register a model configuration."""
        self._models[config.model_name] = config

    def get(self, name: str) -> ModelConfig:
        """Retrieve a registered model config by name."""
        if name not in self._models:
            raise KeyError(
                f"Model '{name}' not found. Available: {list(self._models)}"
            )
        return self._models[name]

    def list_models(self) -> list[ModelConfig]:
        """Return all registered model configs."""
        return list(self._models.values())

    def model_names(self) -> list[str]:
        """Return the names of all registered models."""
        return list(self._models.keys())


def default_model_registry() -> ModelRegistry:
    """Factory that creates a ModelRegistry pre-populated with defaults.

    Currently empty; callers should call :meth:`ModelRegistry.register`
    after training or when loading a persisted model.
    """
    registry = ModelRegistry()

    # Placeholder: register built-in / pre-trained model configs here.
    # Example:
    #   from datetime import date
    #   registry.register(ModelConfig(
    #       model_name="lgb_alpha158_v1",
    #       train_start=date(2024, 1, 1),
    #       train_end=date(2024, 6, 30),
    #       valid_start=date(2024, 7, 1),
    #       valid_end=date(2024, 9, 30),
    #       test_start=date(2024, 10, 1),
    #       test_end=date(2024, 12, 31),
    #   ))

    return registry
