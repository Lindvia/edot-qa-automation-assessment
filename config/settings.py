# Central configuration. Everything comes from environment variables
# (loaded from .env locally); nothing secret is stored in the repo.

import os
from pathlib import Path

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parent.parent
load_dotenv(ROOT / ".env")

ESUITE_URL = os.getenv("ESUITE_URL", "https://esuite.edot.id").rstrip("/")
ESUITE_EMAIL = os.getenv("ESUITE_EMAIL", "")
ESUITE_PASSWORD = os.getenv("ESUITE_PASSWORD", "")
HEADLESS = os.getenv("HEADLESS", "true").lower() != "false"
# How long a deleted company may stay in the Companies list before the delete test fails.
DELETE_WAIT_SECONDS = int(os.getenv("DELETE_WAIT_SECONDS", "180"))
EXPECT_TIMEOUT_MS = int(os.getenv("EXPECT_TIMEOUT_MS", "5000"))  # default wait of every expect()

# --- Mobile (eWork SFA) via Maestro ---
MOBILE_APP_ID = os.getenv("MOBILE_APP_ID", "")  # Android package id of eWork SFA (adb shell pm list packages)
MOBILE_COMPANY_ID = os.getenv("MOBILE_COMPANY_ID", "")
MOBILE_USERNAME = os.getenv("MOBILE_USERNAME", "")
MOBILE_PASSWORD = os.getenv("MOBILE_PASSWORD", "")
MAESTRO_CMD = os.getenv("MAESTRO_CMD", "maestro")  # on Windows: the full path to maestro.bat
MOBILE_RECORD = os.getenv("MOBILE_RECORD", "false").lower() == "true"  # screen recording through adb
MOBILE_FLOW_TIMEOUT = int(os.getenv("MOBILE_FLOW_TIMEOUT", "900"))

# --- AI test data (keys from the environment only; never committed) ---
# Either an OpenAI-compatible endpoint (Groq, Google Gemini, OpenRouter, a local Ollama: free options)
# via AI_BASE_URL + AI_MODEL (+ AI_API_KEY when the provider wants one), or Anthropic via ANTHROPIC_API_KEY.
AI_BASE_URL = os.getenv("AI_BASE_URL", "").rstrip("/")
AI_API_KEY = os.getenv("AI_API_KEY", "")
ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY", "")
AI_MODEL = os.getenv("AI_MODEL", "")  # required with AI_BASE_URL; Anthropic falls back to a small Claude model
FAKER_SEED = int(os.getenv("FAKER_SEED", "20261002"))  # fixed seed = reproducible offline fallback

AUTH_DIR = ROOT / "auth"
STORAGE_STATE = AUTH_DIR / "esuite_state.json"


def require(name: str, value: str) -> str:
    """Fail early with a clear message instead of a cryptic login timeout."""
    if not value:
        raise RuntimeError(f"{name} is not set. Copy .env.example to .env and fill it in.")
    return value
