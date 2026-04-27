from typing import Protocol

import httpx

from app.core.config import settings
from app.services.llm.oauth import get_valid_access_token


class LlmProvider(Protocol):
    def generate(self, prompt: str) -> str:
        ...


class LlmProviderNotConfigured(RuntimeError):
    pass


class OpenAICodexProvider:
    name = "openai_codex"

    def __init__(
        self,
        api_key: str | None = None,
        base_url: str | None = None,
        model: str | None = None,
        oauth_token: str | None = None,
    ):
        self.api_key = api_key or settings.llm_api_key
        self.base_url = (base_url or settings.llm_base_url or "").rstrip("/")
        self.model = model or settings.llm_model
        self._oauth_token = oauth_token

    def _resolve_token(self) -> str | None:
        """Return the best available bearer token (OAuth first, then API key)."""
        if self._oauth_token:
            return self._oauth_token
        # Try auto-loading from persisted OAuth tokens.
        oauth = get_valid_access_token()
        if oauth:
            return oauth
        return self.api_key

    @property
    def configured(self) -> bool:
        return bool(self._resolve_token() and self.base_url and self.model)

    def generate(self, prompt: str) -> str:
        token = self._resolve_token()
        if not token or not self.base_url or not self.model:
            raise LlmProviderNotConfigured("openai_codex provider is not fully configured")

        response = httpx.post(
            f"{self.base_url}/v1/responses",
            headers={"Authorization": f"Bearer {token}"},
            json={"model": self.model, "input": prompt},
            timeout=60,
        )
        response.raise_for_status()
        payload = response.json()
        if text := payload.get("output_text"):
            return str(text)
        return str(payload)
