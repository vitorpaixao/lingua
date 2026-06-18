"""Tests for the Credential Vault: encryption round-trip, masking, first-run gate."""

from pathlib import Path

import pytest

from lingua.settings_store import SettingsStore


@pytest.fixture
def store(monkeypatch, tmp_path) -> SettingsStore:
    # A valid Fernet key so crypto.encrypt/decrypt work.
    from cryptography.fernet import Fernet

    monkeypatch.setenv("LINGUA_SECRET_KEY", Fernet.generate_key().decode())
    # Reset the cached Fernet so it picks up the per-test key.
    from lingua import crypto

    crypto._fernet.cache_clear()
    return SettingsStore(Path(tmp_path) / "lingua.db")


async def test_empty_vault_is_not_configured(store: SettingsStore):
    assert await store.is_configured() is False
    assert await store.get_model_connection() is None
    assert await store.get_github_token() is None
    read = await store.to_read()
    assert read["has_github_token"] is False
    assert read["is_configured"] is False


async def test_secret_round_trip_and_masking(store: SettingsStore):
    await store.update(github_token="ghp_secret", model_api_key="sk-or-secret")

    # Decryptable back to plaintext...
    assert await store.get_github_token() == "ghp_secret"
    # ...but never returned over the masked read view.
    read = await store.to_read()
    assert read["has_github_token"] is True
    assert read["has_model_api_key"] is True
    assert "ghp_secret" not in str(read)
    assert "sk-or-secret" not in str(read)


async def test_model_connection_drives_first_run_gate(store: SettingsStore):
    await store.update(
        model_provider="openrouter",
        model_base_url="https://openrouter.ai/api/v1",
        model_id="anthropic/claude-sonnet-4.5",
        model_api_key="sk-or-x",
    )
    assert await store.is_configured() is True
    conn = await store.get_model_connection()
    assert conn == {
        "provider": "openrouter",
        "base_url": "https://openrouter.ai/api/v1",
        "api_key": "sk-or-x",
        "model_id": "anthropic/claude-sonnet-4.5",
    }


async def test_omitted_fields_are_preserved_and_empty_clears(store: SettingsStore):
    await store.update(github_token="ghp_keep", model_id="m1", model_base_url="u")
    # Updating only the model_id must not wipe the token.
    await store.update(model_id="m2")
    assert await store.get_github_token() == "ghp_keep"
    # Passing "" clears a secret.
    await store.update(github_token="")
    assert await store.get_github_token() is None
