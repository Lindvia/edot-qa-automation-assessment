import pytest

from config import settings


@pytest.fixture(autouse=True)
def offline_ai(monkeypatch):
    """Unit tests never reach a model, whatever the developer has in .env: with no provider configured
    the generators use the Faker fallback and triage runs rules-only. Tests that need a provider pass a
    fake one or set the settings themselves."""
    monkeypatch.setattr(settings, "AI_BASE_URL", "")
    monkeypatch.setattr(settings, "AI_API_KEY", "")
    monkeypatch.setattr(settings, "ANTHROPIC_API_KEY", "")
    monkeypatch.setattr(settings, "AI_MODEL", "")
