# AI_USAGE

How AI is used in this repository, where it runs, what it is sent, what happens when it fails, and
what it is deliberately **not** allowed to do. The prompts below are generated from the constants in
the code, so they are exactly what is sent.

## 1. Model and why

| | |
|---|---|
| Provider | Provider-neutral. Either any **OpenAI-compatible endpoint** (`AI_BASE_URL` + `AI_MODEL`, e.g. the free tiers of Groq or Google Gemini, or a local Ollama), or Anthropic (`ANTHROPIC_API_KEY`, default model `claude-haiku-4-5-20251001`). The endpoint wins when both are set; with neither set the suite uses the Faker fallback. The choice is made in one function, `ai/data_generator.py::default_completer`. |
| Model used | `AI_MODEL`. The triage report header shows it ("AI judge: on (<model>)"); the Allure attachment of generated data shows whether the record came from `ai` or from `faker`. |
| API key | `AI_API_KEY` / `ANTHROPIC_API_KEY` from the environment only. Never in the repo (`.env` is gitignored). A local Ollama needs no key. |
| Why this model | Both jobs are tiny: one small JSON object (company / customer) or one true/false/null answer. A small, fast, cheap model is enough because **the output is validated by a schema and a deterministic fallback exists**, so a weaker answer is rejected, not trusted. |
| Token budget | `max_tokens=300` per call. Data generation sends about 1,300 characters of prompt (most of it is the list of allowed dropdown values); the triage judge sends at most about 1,800 characters (the sheet text is trimmed to 400 chars and the assertion excerpt to 600). At most 2 data calls per test that needs data (1 retry) and 0 or 1 triage call per failure. |

## 2. Where AI runs

| When | What | Where in the code |
|---|---|---|
| While writing the tests | Claude Code (an AI coding assistant) helped draft the page objects, tests and the AI modules. The author reviews the result and must be able to explain every line before submitting. | (development only; no AI is involved when the suite runs) |
| During the run | Generates realistic Indonesian **test data** (company, customer). | `ai/data_generator.py` |
| After the run | **Failure triage**: rules decide most verdicts; a model is asked only at step 4 ("was the expected value correct per the test case?"). | `ai/triage/` |

## 3. The exact prompts

### 3.1 Test data (system prompt, shared)

```
You generate realistic Indonesian business test data. Reply with exactly one JSON object and nothing else: no markdown, no commentary.
```

### 3.2 Company data (user prompt)

```
Create one fictional Indonesian company for QA testing. JSON keys:
"name": legal name starting with PT, CV or UD, letters/spaces/dots only, no digits, at most 22 characters in total including the prefix, e.g. "PT Maju Jaya Abadi";
"email": lowercase, must end with @example.co.id;
"phone": Indonesian mobile number WITHOUT the leading 0 or +62, starts with 8, 9-12 digits, random digits (never a sequence like 81234567890);
"street_address": a plausible street in Jakarta with a random house number, 10-80 chars, e.g. "Jl. Jenderal Sudirman No. 45";
"industry_type": exactly one of ['Retail', 'Real Estate', 'Nonprofit and Social Services', 'Manufacturing', 'Hospitality', 'Food & Beverage', 'Finance and Banking', 'Transportation and Logistics', 'Telecommunications', 'Technology', 'Construction', 'Mining and Metals', 'Automotive', 'Fast Moving Customer Goods (FMCG)', 'Entertainment and Media', 'Energy', 'Agriculture', 'Healthcare', 'Education'];
"company_type": exactly one of ['Importer/Exporter', 'Consignor/Consignee', 'Marketplace', 'Retailer', 'Service Aggregator', 'Third-Party Logistics (3PL) Provider', 'Holding Company', 'Cooperative (Co-op)', 'Franchisee/Franchisor', 'Manufacturer', 'Principal', 'Agent', 'Dropshipper', 'Freight Forwarder', 'Distributor', 'Service', 'Service Provider'].
```

### 3.3 Customer data (user prompt)

```
Create one fictional Indonesian retail outlet (customer) for QA testing. JSON keys:
"outlet_name": shop name, letters/spaces only, no digits, max 50 chars, e.g. "Toko Maju Jaya";
"phone": Indonesian mobile number WITHOUT the leading 0 or +62, starts with 8, 9-12 digits, random digits (never a sequence like 81234567890);
"email": lowercase, must end with @example.co.id;
"contact_person": a common Indonesian person name;
"street_address": a street address on a well-known Indonesian main road (e.g. Jl. Sudirman, Jl. Thamrin, Jl. Asia Afrika, Jl. Diponegoro) with a random house number, 10-80 chars, e.g. "Jl. Asia Afrika No. 8". Use only common words a phone keyboard will not autocorrect.
```

### 3.4 Retry hint (added once, only after a rejected answer)

```
<same prompt>
Your previous answer was rejected: <jsonschema message>. Fix it.
```

### 3.5 Triage judge (system prompt)

```
You are a QA triage assistant. You compare what a failing automated assertion expected with the manual test case. Reply with exactly one JSON object and nothing else.
```

### 3.6 Triage judge (user prompt template)

```
Test case {case_id} - {title}
Expected result (from the test case): {expected}
Test data: {data}

Failing assertion output:
{excerpt}

Does the value the assertion EXPECTED agree with the test case's expected result? Reply {{"expected_value_correct": true|false|null, "reason": "<= 25 words"}}. Use null if you cannot tell. Do not judge whether the product is right.
```

The placeholders are filled with: the case id and title, the **Expected Result** and **Test Data**
from `docs/edot-test-cases.xlsx` (trimmed), and a short excerpt of the assertion output (the
"expected / actual / waiting for" lines only). No page content, credentials or screenshots are sent.

## 4. What happens when AI is unavailable or returns something invalid

### Test data

1. The reply is parsed as one JSON object (markdown fences are tolerated) and validated against the
   JSON schema in `ai/schemas.py` (patterns for name / email / phone / street, exact dropdown values
   for industry and company type, the email must end in `@example.co.id`).
2. Malformed or schema-invalid output is **rejected and retried once** with the validation error as a hint.
3. After the last attempt the **deterministic Faker fallback** (Indonesian locale, fixed seed
   `FAKER_SEED`) is used. The fallback must satisfy the same schema, which is unit-tested over 40 seeds.
4. **No API key**, or a provider error / timeout (no retry in that case): Faker is used straight away,
   so the suite runs offline and in CI.
5. The data actually used, where it came from (`ai` or `faker`) and every rejected attempt are attached
   to the Allure report (`attach_to_allure`).

### Triage

- **No API key or `--no-ai`**: rules only. A failure that survives all rule steps is reported as a
  *product bug with low confidence*, with step 4 marked "not checked".
- **Invalid or missing model answer, or provider error**: the judge returns "no opinion"; the verdict
  falls back to the rules and the report says the expected value was not verified.
- The model can only say *expected value correct / wrong / cannot tell*. It cannot set a verdict by
  itself: a "wrong" answer moves a failure to *script/environment defect*, never to *passed*.

## 5. What AI is deliberately not allowed to do (and why)

| Not allowed | Why |
|---|---|
| Write, weaken, skip, retry-away or rewrite an assertion; change an expected value to match the actual result; swallow a failure in `try/except` | A failing test must stay failing. The only `try/except` blocks catch a *screenshot* error (so it cannot hide the real failure), the model call itself, and a bounded reload loop that re-raises on the last attempt. |
| Decide a test passes | Data generation happens before the test; triage happens after it and only writes a report. |
| File, update or close bugs / tickets | The triage verdict is a **proposal for a human**. The code has no bug-tracker integration at all. |
| Choose the address cascade (province, city, district, sub district, postal code) | A model cannot know which dropdown values exist. These come from a verified catalog (`LOCATIONS` in `ai/schemas.py`). |
| Produce credentials, passwords or real contact details | Credentials come from environment variables only. Generated emails must end in `@example.co.id`, so no real mailbox is ever used. |
| Create or delete anything on the shared environment | Data creation and cleanup are plain scripted UI steps; AI only supplies input values. The module teardown deletes the company even when a test fails. |
| See the application, the page, the screenshots or the repository | The prompts contain only the fields shown above. |
| Run tests or change code | The triage script reads result files and writes Markdown. `--rerun` runs the same test again in a separate pytest process and only records pass/fail. |

## 6. Where to look

- Data module and its offline tests: `ai/data_generator.py`, `tests/unit/test_data_generator.py`
- Triage and its offline tests: `ai/triage/`, `tests/unit/test_triage.py`
- Triage evidence: see "Triage evidence" in the README.
