"""
Unit tests for Rime voice preflight validation module.
"""

from __future__ import annotations

import asyncio
from typing import Any
import pytest
import httpx

from agent.preflight import (
    RIME_VOICES_URL,
    _parse_catalog,
    run_preflight,
    validate_rime_voice,
)


class MockTransport(httpx.AsyncBaseTransport):
    """Custom transport for mocking httpx responses without network calls."""

    def __init__(self, handler: Any) -> None:
        self.handler = handler

    async def handle_async_request(self, request: httpx.Request) -> httpx.Response:
        return self.handler(request)


def test_parse_catalog_standard_rime_structure() -> None:
    """Test standard Rime all-v2.json schema (model -> lang -> voices list)."""
    data = {
        "coda": {
            "eng": ["astra", "luna", "celeste", "masonry"],
            "fra": ["lucie"],
        },
        "mist-v3": {
            "eng": ["cove"],
        },
    }
    model_found, voices, all_models = _parse_catalog(data, "coda")
    assert model_found is True
    assert "astra" in voices
    assert "luna" in voices
    assert "lucie" in voices
    assert "coda" in all_models


def test_parse_catalog_flat_list_structure() -> None:
    """Test defensive parsing for a flat list of voice records."""
    data = [
        {"model": "coda", "speaker": "astra"},
        {"model": "coda", "name": "luna"},
        {"model": "mist", "speaker": "cove"},
    ]
    model_found, voices, all_models = _parse_catalog(data, "coda")
    assert model_found is True
    assert "astra" in voices
    assert "luna" in voices
    assert "cove" not in voices


def test_parse_catalog_wrapped_models_structure() -> None:
    """Test defensive parsing for nested models dictionary."""
    data = {
        "models": {
            "coda": ["astra", "luna"],
            "mist": ["cove"],
        }
    }
    model_found, voices, all_models = _parse_catalog(data, "coda")
    assert model_found is True
    assert "astra" in voices
    assert "luna" in voices


def test_parse_catalog_speaker_keyed_structure() -> None:
    """Test defensive parsing when catalog is keyed by speaker."""
    data = {
        "astra": {"model": "coda"},
        "luna": {"model": "coda"},
        "cove": {"model": "mist"},
    }
    model_found, voices, all_models = _parse_catalog(data, "coda")
    assert model_found is True
    assert "astra" in voices
    assert "luna" in voices


@pytest.mark.asyncio
async def test_validate_rime_voice_success(monkeypatch: pytest.MonkeyPatch) -> None:
    """Test successful voice validation when coda/astra is present."""
    payload = {
        "coda": {
            "eng": ["astra", "luna"],
        }
    }

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json=payload, request=request)

    async def mock_get(self: Any, url: str, **kwargs: Any) -> httpx.Response:
        return httpx.Response(200, json=payload, request=httpx.Request("GET", url))

    monkeypatch.setattr(httpx.AsyncClient, "get", mock_get)

    result = await validate_rime_voice(model="coda", speaker="astra")
    assert result is True


@pytest.mark.asyncio
async def test_validate_rime_voice_missing_speaker(monkeypatch: pytest.MonkeyPatch) -> None:
    """Test that missing speaker raises SystemExit(1)."""
    payload = {
        "coda": {
            "eng": ["luna", "celeste"],
        }
    }

    async def mock_get(self: Any, url: str, **kwargs: Any) -> httpx.Response:
        return httpx.Response(200, json=payload, request=httpx.Request("GET", url))

    monkeypatch.setattr(httpx.AsyncClient, "get", mock_get)

    with pytest.raises(SystemExit) as exc_info:
        await validate_rime_voice(model="coda", speaker="astra")
    assert exc_info.value.code == 1


@pytest.mark.asyncio
async def test_validate_rime_voice_missing_model(monkeypatch: pytest.MonkeyPatch) -> None:
    """Test that missing model raises SystemExit(1)."""
    payload = {
        "mist": {
            "eng": ["cove"],
        }
    }

    async def mock_get(self: Any, url: str, **kwargs: Any) -> httpx.Response:
        return httpx.Response(200, json=payload, request=httpx.Request("GET", url))

    monkeypatch.setattr(httpx.AsyncClient, "get", mock_get)

    with pytest.raises(SystemExit) as exc_info:
        await validate_rime_voice(model="coda", speaker="astra")
    assert exc_info.value.code == 1


@pytest.mark.asyncio
async def test_validate_rime_voice_network_error(monkeypatch: pytest.MonkeyPatch) -> None:
    """Test that network error logs a warning and returns False without crashing."""
    async def mock_get_error(self: Any, url: str, **kwargs: Any) -> httpx.Response:
        raise httpx.ConnectError("Connection refused")

    monkeypatch.setattr(httpx.AsyncClient, "get", mock_get_error)

    result = await validate_rime_voice(model="coda", speaker="astra")
    assert result is False


@pytest.mark.asyncio
async def test_validate_rime_voice_unparseable_json(monkeypatch: pytest.MonkeyPatch) -> None:
    """Test that unrecognizable catalog structure logs warning and returns False without crashing."""
    async def mock_get(self: Any, url: str, **kwargs: Any) -> httpx.Response:
        return httpx.Response(200, json={}, request=httpx.Request("GET", url))

    monkeypatch.setattr(httpx.AsyncClient, "get", mock_get)

    result = await validate_rime_voice(model="coda", speaker="astra")
    assert result is False
