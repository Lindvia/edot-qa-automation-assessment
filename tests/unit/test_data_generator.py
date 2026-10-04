"""Offline unit tests for the AI test-data module (no browser, no network, no API key)."""

import json
from pathlib import Path

import pytest

from ai import data_generator as gen
from ai import schemas

VALID_COMPANY = {
    "name": "PT Nusantara Digital",
    "email": "info.nusantara@example.co.id",
    "phone": "81234567890",
    "street_address": "Jl. Jenderal Sudirman No. 45",
    "industry_type": "Technology",
    "company_type": "Distributor",
}


def completer_returning(*answers):
    """Fake model: returns the given answers in order and records the prompts it got."""
    calls = []

    def complete(system, user):
        calls.append(user)
        return answers[min(len(calls), len(answers)) - 1]

    complete.calls = calls
    return complete


def test_valid_ai_output_should_be_accepted_as_ai_data():
    result = gen.generate_company(completer_returning(json.dumps(VALID_COMPANY)))
    assert result.source == "ai"
    assert result.data["name"].startswith("PT Nusantara Digital QA")
    assert result.data["industry_type"] == "Technology"


def test_json_wrapped_in_markdown_should_still_be_parsed():
    wrapped = "```json\n" + json.dumps(VALID_COMPANY) + "\n```"
    assert gen.generate_company(completer_returning(wrapped)).source == "ai"


def test_malformed_output_should_be_retried_then_accepted():
    complete = completer_returning("sorry, I cannot do that", json.dumps(VALID_COMPANY))
    result = gen.generate_company(complete)
    assert result.source == "ai"
    assert len(complete.calls) == 2
    assert "rejected" in complete.calls[1]  # the retry carries the error hint
    assert len(result.attempts) == 1


def test_schema_invalid_output_should_fall_back_to_faker_after_retries():
    bad_enum = dict(VALID_COMPANY, industry_type="Space Mining")
    result = gen.generate_company(completer_returning(json.dumps(bad_enum)))
    assert result.source == "faker"
    assert len(result.attempts) == gen.MAX_ATTEMPTS
    assert result.data["industry_type"] in schemas.INDUSTRY_TYPES  # never the rejected "Space Mining"


def test_ai_error_should_fall_back_to_faker_without_retrying():
    def broken(system, user):
        raise ConnectionError("provider down")

    result = gen.generate_company(broken)
    assert result.source == "faker"
    assert "unavailable" in result.note


def test_missing_api_key_should_use_faker():
    result = gen.generate_company()
    assert result.source == "faker"
    assert "no API key" in result.note


# ------------------------------------------- OpenAI-compatible provider (Groq, Gemini, OpenRouter, Ollama)
@pytest.fixture
def fake_provider():
    """A throwaway local server that speaks the chat-completions protocol and records what it receives."""
    import http.server
    import threading

    seen = {}
    state = {"status": 200, "content": json.dumps(VALID_COMPANY)}

    class Handler(http.server.BaseHTTPRequestHandler):
        def do_POST(self):
            seen["path"] = self.path
            seen["auth"] = self.headers.get("Authorization")
            seen["agent"] = self.headers.get("User-Agent")
            seen["body"] = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
            reply = json.dumps({"choices": [{"message": {"content": state["content"]}}]}).encode()
            self.send_response(state["status"])
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(reply if state["status"] == 200 else b"{}")

        def log_message(self, *args):  # keep the test output quiet
            pass

    server = http.server.HTTPServer(("127.0.0.1", 0), Handler)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    yield f"http://127.0.0.1:{server.server_port}/v1", seen, state
    server.shutdown()


def test_openai_compatible_completer_should_send_a_chat_completion_and_return_the_text(fake_provider):
    base_url, seen, _ = fake_provider
    complete = gen.openai_compatible_completer(base_url, "secret-key", "some-model")
    text = complete("system prompt", "user prompt")
    assert json.loads(text)["name"] == VALID_COMPANY["name"]
    assert seen["path"] == "/v1/chat/completions"
    assert seen["auth"] == "Bearer secret-key" and seen["agent"]  # a User-Agent: some providers reject urllib's
    assert seen["body"]["model"] == "some-model" and seen["body"]["max_tokens"] == gen.MAX_TOKENS
    assert [m["role"] for m in seen["body"]["messages"]] == ["system", "user"]
    assert complete.model == "some-model"


def test_openai_compatible_completer_should_send_no_authorization_header_without_a_key(fake_provider):
    base_url, seen, _ = fake_provider
    gen.openai_compatible_completer(base_url, "", "local-model")("s", "u")  # e.g. a local Ollama
    assert seen["auth"] is None


def test_a_provider_error_should_fall_back_to_faker(fake_provider):
    base_url, _, state = fake_provider
    state["status"] = 500
    result = gen.generate_company(gen.openai_compatible_completer(base_url, "k", "m"))
    assert result.source == "faker" and "unavailable" in result.note
    assert "HTTPError 500" in result.attempts[0]  # the status says WHY (e.g. 429 = rate limited)


def test_generated_data_should_come_from_the_provider_when_it_is_valid(fake_provider):
    base_url, _, _ = fake_provider
    result = gen.generate_company(gen.openai_compatible_completer(base_url, "k", "m"))
    assert result.source == "ai" and result.data["name"].startswith(VALID_COMPANY["name"])


def test_provider_choice_should_prefer_the_endpoint_then_anthropic_then_nothing(monkeypatch):
    monkeypatch.setattr(gen.settings, "AI_MODEL", "my-model")
    monkeypatch.setattr(gen.settings, "AI_BASE_URL", "http://localhost:11434/v1")
    monkeypatch.setattr(gen.settings, "ANTHROPIC_API_KEY", "x")
    assert gen.default_completer().model == "my-model"
    monkeypatch.setattr(gen.settings, "AI_BASE_URL", "")
    assert gen.default_completer().model == "my-model"  # the Anthropic client, built lazily from the key
    monkeypatch.setattr(gen.settings, "ANTHROPIC_API_KEY", "")
    assert gen.default_completer() is None


def test_an_endpoint_without_a_model_should_fail_loudly_instead_of_sending_a_wrong_name(monkeypatch):
    monkeypatch.setattr(gen.settings, "AI_BASE_URL", "http://localhost:11434/v1")
    monkeypatch.setattr(gen.settings, "AI_MODEL", "")
    with pytest.raises(RuntimeError, match="AI_MODEL"):
        gen.default_completer()


def test_fallback_should_be_deterministic_for_a_seed_apart_from_the_unique_suffix():
    first = gen.generate_company(seed=7).data
    second = gen.generate_company(seed=7).data
    assert first["name"].split(" QA")[0] == second["name"].split(" QA")[0]
    assert first["phone"] == second["phone"]
    assert first["name"] != second["name"]  # unique suffix differs per call


@pytest.mark.parametrize("seed", range(40))
def test_faker_fallback_should_always_satisfy_the_schema(seed):
    gen.validate(gen._faker_company(seed), schemas.COMPANY_SCHEMA)
    gen.validate(gen._faker_customer(seed), schemas.CUSTOMER_SCHEMA)


def test_company_data_should_include_the_verified_location_cascade():
    data = gen.generate_company(completer_returning(json.dumps(VALID_COMPANY))).data
    assert (data["province"], data["city"], data["district"], data["sub_district"], data["postal_code"]) == (
        "DKI JAKARTA", "JAKARTA SELATAN", "SETIABUDI", "KARET KUNINGAN", "12940")
    assert data["language"] == "Indonesia"
    assert data["country"] == "Indonesia"


def test_generated_records_should_be_unique_per_call():
    names = {gen.generate_company(seed=1).data["name"] for _ in range(5)}
    assert len(names) == 5


def test_ai_email_outside_the_reserved_domain_should_be_rejected():
    real_domain = dict(VALID_COMPANY, email="boss@gmail.com")
    assert gen.generate_company(completer_returning(json.dumps(real_domain))).source == "faker"


@pytest.mark.parametrize("prompt", [gen.COMPANY_PROMPT, gen.CUSTOMER_PROMPT])
def test_ai_usage_doc_should_show_the_exact_prompts_the_code_sends(prompt):
    # AI_USAGE.md must list the exact prompts (brief); this fails when the code changes and the doc does not
    doc = (Path(__file__).resolve().parents[2] / "AI_USAGE.md").read_text(encoding="utf-8")
    assert prompt in doc


@pytest.mark.parametrize("seed", range(300))
def test_generated_company_name_with_its_suffix_should_fit_the_app_limit(seed):
    # eSuite keeps Next disabled for a name over 30 characters (this made AI-named companies fail to register)
    assert len(gen.generate_company(seed=seed).data["name"]) <= schemas.COMPANY_NAME_LIMIT


def test_ai_company_name_that_would_exceed_the_app_limit_should_be_rejected():
    too_long = dict(VALID_COMPANY, name="PT Maju Sejahtera Abadi Jaya")
    result = gen.generate_company(completer_returning(json.dumps(too_long)))
    assert result.source == "faker" and len(result.data["name"]) <= schemas.COMPANY_NAME_LIMIT
