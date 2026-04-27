"""Tests for the OAuth PKCE module."""

import json
import time
from pathlib import Path

from app.services.llm.oauth import (
    OAuthSession,
    _generate_code_challenge,
    _generate_code_verifier,
    _load_tokens,
    _save_tokens,
    clear_tokens,
    get_oauth_status,
    get_valid_access_token,
    start_oauth_flow,
)


def test_code_verifier_length():
    v = _generate_code_verifier(64)
    assert 43 <= len(v) <= 128


def test_code_challenge_deterministic():
    v = "dBjftJeZ4CVP-mB92K27uhbUJU1p1r_wW1gFWFOEjXk"
    c1 = _generate_code_challenge(v)
    c2 = _generate_code_challenge(v)
    assert c1 == c2
    # Must be URL-safe base64 with no padding.
    assert "=" not in c1
    assert "+" not in c1
    assert "/" not in c1


def test_oauth_session_state_unique():
    s1 = OAuthSession()
    s2 = OAuthSession()
    assert s1.state != s2.state


def test_token_persistence(tmp_path: Path):
    path = tmp_path / "tokens.json"
    assert _load_tokens(path) == {}

    data = {"access_token": "tok123", "expires_in": 3600, "obtained_at": int(time.time())}
    _save_tokens(data, path)

    loaded = _load_tokens(path)
    assert loaded["access_token"] == "tok123"


def test_get_valid_access_token_returns_none_when_empty(tmp_path: Path):
    path = tmp_path / "tokens.json"
    assert get_valid_access_token(token_path=path) is None


def test_get_valid_access_token_returns_valid(tmp_path: Path):
    path = tmp_path / "tokens.json"
    now = int(time.time())
    _save_tokens({"access_token": "fresh", "expires_in": 3600, "obtained_at": now}, path)
    assert get_valid_access_token(token_path=path) == "fresh"


def test_get_valid_access_token_returns_none_when_expired(tmp_path: Path):
    path = tmp_path / "tokens.json"
    # Token expired 200s ago, no refresh_token → should return None.
    _save_tokens(
        {"access_token": "stale", "expires_in": 100, "obtained_at": int(time.time()) - 200},
        path,
    )
    assert get_valid_access_token(token_path=path) is None


def test_oauth_status_not_authenticated(tmp_path: Path):
    path = tmp_path / "tokens.json"
    status = get_oauth_status(token_path=path)
    assert status["authenticated"] is False


def test_oauth_status_authenticated(tmp_path: Path):
    path = tmp_path / "tokens.json"
    now = int(time.time())
    _save_tokens({"access_token": "tok", "expires_in": 3600, "obtained_at": now}, path)
    status = get_oauth_status(token_path=path)
    assert status["authenticated"] is True
    assert status["expires_at"] == now + 3600


def test_clear_tokens(tmp_path: Path):
    path = tmp_path / "tokens.json"
    _save_tokens({"access_token": "tok"}, path)
    assert path.exists()
    clear_tokens(token_path=path)
    assert not path.exists()


def test_start_oauth_flow_returns_url():
    result = start_oauth_flow(redirect_uri="http://localhost:8000/api/llm/oauth/callback")
    assert "authorize_url" in result
    assert "state" in result
    assert "auth.openai.com" in result["authorize_url"]
    assert "code_challenge" in result["authorize_url"]
    assert "S256" in result["authorize_url"]
