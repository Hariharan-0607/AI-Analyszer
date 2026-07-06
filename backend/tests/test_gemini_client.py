"""Gemini client configuration tests (no live API calls)."""

import pytest

from app.config import get_settings
from app.services.gemini_client import GeminiClient


def test_gemini_settings_defaults():
    settings = get_settings()
    assert settings.gemini_model == "gemini-2.0-flash"
    assert isinstance(settings.gemini_api_key, str)


@pytest.mark.asyncio
async def test_gemini_check_health_without_valid_key():
    client = GeminiClient()
    key = get_settings().gemini_api_key.strip()
    healthy = await client.check_health()
    if not key or key == "your_gemini_api_key_here":
        assert healthy is False
    else:
        assert healthy is True
