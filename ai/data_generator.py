"""AI-generated test data with schema validation and an offline fallback.

Flow for every request:
  1. No API key (or AI unavailable)  -> deterministic Faker fallback.
  2. Ask the model for one JSON object.
  3. Validate it against the JSON schema in ai/schemas.py. Malformed or
     schema-invalid output is rejected and retried (once, with the validation
     error as a hint); after the last attempt the Faker fallback is used.
  4. Only validated data is returned, together with where it came from.

The model never sees the application, the tests or any assertion - it only
produces input values. A failing test is never touched by this module.
"""

import json
import random
import re
import urllib.request
from dataclasses import dataclass, field
from typing import Callable, Optional

import jsonschema
from faker import Faker

from ai import schemas
from config import settings
from utils.helpers import generate_unique_alphabetic_name

Completer = Callable[[str, str], str]  # (system_prompt, user_prompt) -> raw model text

MAX_ATTEMPTS = 2
MAX_TOKENS = 300  # one small JSON object; keeps token cost low
ANTHROPIC_DEFAULT_MODEL = "claude-haiku-4-5-20251001"  # small + cheap: one tiny JSON object per call

SYSTEM_PROMPT = (
    "You generate realistic Indonesian business test data. "
    "Reply with exactly one JSON object and nothing else: no markdown, no commentary."
)

COMPANY_PROMPT = (
    "Create one fictional Indonesian company for QA testing. JSON keys:\n"
    '"name": legal name starting with PT, CV or UD, letters/spaces/dots only, no digits, max 50 chars after the prefix;\n'
    '"email": lowercase, must end with @example.co.id;\n'
    '"phone": Indonesian mobile number WITHOUT the leading 0 or +62, starts with 8, 9-12 digits, random digits (never a sequence like 81234567890);\n'
    '"street_address": a plausible street in Jakarta with a random house number, 10-80 chars, e.g. "Jl. Jenderal Sudirman No. 45";\n'
    f'"industry_type": exactly one of {schemas.INDUSTRY_TYPES};\n'
    f'"company_type": exactly one of {schemas.COMPANY_TYPES}.'
)

CUSTOMER_PROMPT = (
    "Create one fictional Indonesian retail outlet (customer) for QA testing. JSON keys:\n"
    '"outlet_name": shop name, letters/spaces only, no digits, max 50 chars, e.g. "Toko Maju Jaya";\n'
    '"phone": Indonesian mobile number WITHOUT the leading 0 or +62, starts with 8, 9-12 digits, random digits (never a sequence like 81234567890);\n'
    '"email": lowercase, must end with @example.co.id;\n'
    '"contact_person": a common Indonesian person name;\n'
    '"street_address": a plausible street address with a random house number, 10-80 chars, e.g. "Jl. Asia Afrika No. 8".'
)


@dataclass(frozen=True)
class GeneratedData:
    data: dict
    source: str  # "ai" or "faker"
    note: str = ""  # why the fallback was used / how many attempts
    attempts: list = field(default_factory=list)  # rejection reasons, for the report


# ----------------------------------------------------------------- AI client
def anthropic_completer(api_key: str, model: str) -> Completer:
    import anthropic

    client = anthropic.Anthropic(api_key=api_key)

    def complete(system: str, user: str) -> str:
        message = client.messages.create(
            model=model,
            max_tokens=MAX_TOKENS,
            system=system,
            messages=[{"role": "user", "content": user}],
        )
        return "".join(block.text for block in message.content if getattr(block, "type", "") == "text")

    complete.model = model
    return complete


def openai_compatible_completer(base_url: str, api_key: str, model: str, timeout: int = 60) -> Completer:
    """Any provider that speaks the OpenAI chat-completions protocol (Groq, Gemini, OpenRouter, Ollama).
    Standard library only, so the free options need no extra dependency."""
    url = base_url.rstrip("/") + "/chat/completions"

    def complete(system: str, user: str) -> str:
        body = json.dumps({
            "model": model,
            "max_tokens": MAX_TOKENS,
            "messages": [{"role": "system", "content": system}, {"role": "user", "content": user}],
        }).encode("utf-8")
        # a User-Agent is set because some providers sit behind a firewall that rejects urllib's default
        headers = {"Content-Type": "application/json", "User-Agent": "edot-qa-assessment"}
        if api_key:
            headers["Authorization"] = f"Bearer {api_key}"
        with urllib.request.urlopen(urllib.request.Request(url, body, headers), timeout=timeout) as response:
            payload = json.load(response)
        return payload["choices"][0]["message"]["content"] or ""

    complete.model = model
    return complete


def default_completer() -> Optional[Completer]:
    """The one place that picks the provider: an OpenAI-compatible endpoint when AI_BASE_URL is set,
    else Anthropic when its key is set, else None (the Faker fallback / rules-only triage)."""
    if settings.AI_BASE_URL:
        return openai_compatible_completer(
            settings.AI_BASE_URL, settings.AI_API_KEY, settings.require("AI_MODEL", settings.AI_MODEL))
    if settings.ANTHROPIC_API_KEY:
        return anthropic_completer(settings.ANTHROPIC_API_KEY, settings.AI_MODEL or ANTHROPIC_DEFAULT_MODEL)
    return None


# ------------------------------------------------------------------- parsing
def parse_json_object(text: str) -> dict:
    """Extract the JSON object from the model text; raises ValueError if absent/invalid."""
    start, end = text.find("{"), text.rfind("}")
    if start == -1 or end <= start:
        raise ValueError("no JSON object in the response")
    value = json.loads(text[start : end + 1])
    if not isinstance(value, dict):
        raise ValueError("response JSON is not an object")
    return value


def validate(value: dict, schema: dict) -> None:
    """Raise jsonschema.ValidationError when the value does not match the schema."""
    jsonschema.validate(value, schema)


# ------------------------------------------------------------ Faker fallback
def _faker(seed: Optional[int]) -> tuple:
    seed = settings.FAKER_SEED if seed is None else seed
    fake = Faker("id_ID")
    fake.seed_instance(seed)
    return fake, random.Random(seed)


def _slug(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", ".", text.lower()).strip(".")[:30] or "qa"


def _faker_company(seed: Optional[int] = None) -> dict:
    fake, rng = _faker(seed)
    name = f"{rng.choice(['PT', 'CV', 'UD'])} {fake.last_name()} {fake.last_name()}"
    return {
        "name": name,
        "email": f"{_slug(name)}@example.co.id",
        "phone": "8" + "".join(rng.choice("0123456789") for _ in range(10)),
        "street_address": f"Jl. {fake.last_name()} No. {rng.randint(1, 99)}",
        "industry_type": rng.choice(schemas.INDUSTRY_TYPES),
        "company_type": rng.choice(schemas.COMPANY_TYPES),
    }


def _faker_customer(seed: Optional[int] = None) -> dict:
    fake, rng = _faker(seed)
    outlet = f"{rng.choice(['Toko', 'Warung', 'Kios'])} {fake.last_name()} {fake.last_name()}"
    return {
        "outlet_name": outlet,
        "phone": "8" + "".join(rng.choice("0123456789") for _ in range(10)),
        "email": f"{_slug(outlet)}@example.co.id",
        "contact_person": f"{fake.first_name()} {fake.last_name()}",
        "street_address": f"Jl. {fake.last_name()} No. {rng.randint(1, 99)}",
    }


# ------------------------------------------------------------------- engine
def _generate(schema: dict, prompt: str, fallback: Callable[[Optional[int]], dict],
              complete: Optional[Completer], seed: Optional[int]) -> GeneratedData:
    complete = complete if complete is not None else default_completer()
    rejected: list = []

    if complete is None:
        return _from_fallback(schema, fallback, seed, "no API key; used Faker", rejected)

    user_prompt = prompt
    for attempt in range(1, MAX_ATTEMPTS + 1):
        try:
            raw = complete(SYSTEM_PROMPT, user_prompt)
        except Exception as error:  # noqa: BLE001 - provider down / auth / network: data only, never a test result
            status = f" {error.code}" if hasattr(error, "code") else ""  # e.g. HTTPError 429 = rate limited
            rejected.append(f"attempt {attempt}: AI unavailable ({type(error).__name__}{status})")
            return _from_fallback(schema, fallback, seed, "AI unavailable; used Faker", rejected)
        try:
            value = parse_json_object(raw)
            validate(value, schema)
        except (ValueError, jsonschema.ValidationError) as error:
            reason = getattr(error, "message", str(error))
            rejected.append(f"attempt {attempt}: rejected ({reason})")
            user_prompt = f"{prompt}\nYour previous answer was rejected: {reason}. Fix it."
            continue
        return GeneratedData(value, "ai", f"accepted on attempt {attempt}", rejected)

    return _from_fallback(schema, fallback, seed, "AI output invalid after retries; used Faker", rejected)


def _from_fallback(schema: dict, fallback, seed, note: str, rejected: list) -> GeneratedData:
    value = fallback(seed)
    validate(value, schema)  # the fallback must satisfy the same contract as the AI
    return GeneratedData(value, "faker", note, rejected)


def _with_unique_suffix(value: dict, name_key: str) -> dict:
    """Make the record unique on the shared environment and easy to find for cleanup."""
    suffix = generate_unique_alphabetic_name("").upper()
    out = dict(value)
    out[name_key] = f"{value[name_key]} QA{suffix}"
    local, domain = value["email"].split("@")
    out["email"] = f"{local}.{suffix.lower()}@{domain}"
    return out


# --------------------------------------------------------------- public API
def generate_company(complete: Optional[Completer] = None, seed: Optional[int] = None) -> GeneratedData:
    result = _generate(schemas.COMPANY_SCHEMA, COMPANY_PROMPT, _faker_company, complete, seed)
    data = _with_unique_suffix(result.data, "name")
    data.update({"language": "Indonesia", **schemas.LOCATIONS[0]})
    return GeneratedData(data, result.source, result.note, result.attempts)


def generate_customer(complete: Optional[Completer] = None, seed: Optional[int] = None) -> GeneratedData:
    result = _generate(schemas.CUSTOMER_SCHEMA, CUSTOMER_PROMPT, _faker_customer, complete, seed)
    return GeneratedData(_with_unique_suffix(result.data, "outlet_name"), result.source, result.note, result.attempts)


def attach_to_allure(result: GeneratedData, title: str) -> None:
    """Attach the data actually used by the test (and where it came from) to the report."""
    import allure

    payload = {"source": result.source, "note": result.note, "rejected": result.attempts, "data": result.data}
    allure.attach(json.dumps(payload, indent=2, ensure_ascii=False), name=title,
                  attachment_type=allure.attachment_type.JSON)
