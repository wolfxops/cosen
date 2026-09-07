# Cosen — builder handoff

Copy this entire file into the next model as system / project context.
Date of this snapshot: 2026-09-06.
Code lives in this repo folder (renamed from `cosai` to `cosen`).

---

## 1. Mission

Build a **public open-source product** that AI product teams use every day.

Cosen is **one suite** for:

1. **Cost** — feature-level spend, price table, daily budgets / kill-switch
2. **Observability** — traces, latency, model mix, local dashboard
3. **Security** — on-path scanners (secrets, PII, injection, jailbreak phrasing, system-prompt leak)

It must be **heavily used**, so optimize for a 5-minute first win, not feature parity with Langfuse.

It must be **LLM / model agnostic**. Never bind the product to OpenAI, Anthropic, Google, xAI, or any one lab.

It must be a **web application that can be hosted locally** (laptop or private VM). The web UI and the gateway are the same process.

This is **not** another agent framework, RAG engine, or full LLMOps platform.

---

## 2. Product name and brand

**Public product name: Cosen** (pronounced CO-sen).
Coined from Cost + Security / observability engine.

Do **not** launch as COS or COSAI:

- COS = Canonical Observability Stack
- CoSAI = OASIS Coalition for Secure AI
- cosai.tech = unrelated finance product
- CLI `cos` is too generic to trademark

| Layer | Value |
|---|---|
| Product | Cosen |
| Tagline | Cost, observability, and security for any model |
| GitHub org / repo | `wolfxops/cosen` |
| pip (today) | package is `cosen` |
| CLI today | `cosen` (with `cos` alias for compatibility) |
| Target CLI | `cosen` |
| Company / copyright | Cosen Labs (or founder company), not only a personal handle |
| Founder | Vivek Singh, X handle wolfxops, Pune |

**GitHub About (≤350 chars):**

> Cosen is a local-first, LLM-agnostic suite for AI cost, observability, and security. Host the web app on your machine, point any OpenAI-compatible model at it, and every call is priced, traced, and scanned.

**Topics:** `llm` `observability` `cost-tracking` `ai-security` `openai-compatible` `self-hosted` `gateway` `llmops`

Backup names if Cosen is blocked: **Palisade**, **Tracemeter**.

---

## 3. License and commercialization (do this before outside PRs)

**Now**

- Relicense core from MIT → **Apache License 2.0**
- Copyright holder: a company entity, e.g. `Copyright 2026 Cosen Labs`
- Add a **CLA** (or DCO + explicit relicensing grant) before merging external PRs
- Without a CLA, every contributor can block a future Enterprise edition

**Later money**

- Keep core Apache-2.0 and self-hostable
- Sell **Cosen Cloud** (hosted) + **EE** modules: SSO/SAML, SCIM, audit export, multi-tenant orgs, long retention, support SLAs
- Put EE in `ee/` or a separate private repo — open-core like Langfuse / GitLab

**Do not start with** SSPL, Elastic License, or BSL. Those are not OSI open source and will cap adoption. AGPL on the server only is a later option if hyperscalers wrap the hosted product.

Apache-2.0 does not stop Amazon from hosting the code. Defense is velocity, EE surface, and CLA — not a hostile license on day one.

---

## 4. Design laws (non-negotiable)

1. The model is a plugin. The primary wire format is **OpenAI-compatible** `/v1/chat/completions`; explicit native inbound adapters (e.g. `/v1/messages` for Anthropic CLI tools) are allowed. No vendor SDK imports.
2. Security runs **on the request path**, not in a weekly batch. Scanners are deterministic first (no required LLM-as-judge).
3. Cost is a **feature attribute** (`X-COS-Feature`), not a month-end vendor invoice.
4. First run works **without any API key** (`--mock` / `cos demo`).
5. Local-first: SQLite on disk, no ClickHouse, no mandatory cloud account.
6. One mental model: web app + `serve` + `report` + `scan`.
7. Keys live in **environment variables on the host**. Persist only env var *names*, never raw secrets in SQLite.
8. Do not expand into agents, RAG, prompt CMS, or eval platforms until the core loop is used daily.

---

## 5. Current stack (v0.2.0)

- Python 3.10+
- stdlib `http.server.ThreadingHTTPServer` (no FastAPI/uvicorn yet)
- `httpx` for upstream forwarding
- `PyYAML` for policy + pricing
- SQLite at `./.cosen/cosen.db` or `$COSEN_HOME/cosen.db` (legacy `$COS_HOME/cosai.db` also supported)
- Single-page UI: `cosen/web/index.html` (no npm, no React)
- Tests: pytest, `tests/test_security_cost.py` (5 tests)

Dependencies in `pyproject.toml`: `httpx>=0.27`, `PyYAML>=6.0`.

Run:

```bash
cd cosen
python -m pip install -e .
cosen init
cosen demo
cosen serve --mock          # http://127.0.0.1:8080/
```

Bind for LAN/VM:

```bash
cosen serve --host 0.0.0.0 --port 8080 --upstream http://127.0.0.1:11434/v1
```

Verified working: mock gateway, security 403 on injection, budget path, web SPA, `/api/providers` seeds 7 providers, playground headers.

---

## 6. Repository map

```
cosen/
  pyproject.toml            # name=cosen, scripts cos + cosen
  LICENSE                   # Apache-2.0, Copyright 2026 Cosen Labs
  README.md
  HANDOFF.md                # this file
  CLA.md                    # contributor license agreement
  CONTRIBUTING.md           # contribution guidelines
  examples/drop_in.py       # OpenAI SDK pointed at local gateway
  tests/test_security_cost.py
  cosen/
    __init__.py             # __version__ = 0.2.1
    cli.py                  # init, serve, report, scan, demo, cost, mcp, integrate, export
    config.py               # load cosen.yaml, env ${VAR:-default}
    gateway.py              # HTTP server: SPA + API + /v1 proxy (OpenAI + Anthropic)
    store.py                # SQLite traces, events, providers
    cost.py                 # pricing table, token estimate, budgets
    security.py             # deterministic scanners
    textutil.py             # message flattening, previews
    dashboard.py            # OLD static HTML summary — SPA replaced it
    integrations/           # CLI/SDK catalog + OWASP/SARIF/Prometheus/OTEL exporters
    data/pricing.yaml
    policies/default.yaml
    web/index.html          # local web app
  docs/                     # GitHub Pages public site
  examples/                 # SDK drop-ins, Prometheus, Sonar, GitHub Action
```

Runtime data (gitignored): `.cosen/cosen.db`.

---

## 7. Data model (SQLite)

**traces:** id, ts, project, feature, user_id, session_id, model, provider, status, latency_ms, prompt_tokens, completion_tokens, total_tokens, cost_usd, security_verdict, security_findings (JSON), error, request_preview, response_preview, raw_json

**events:** id, ts, kind, severity, message, trace_id

**providers:** id, name UNIQUE, base_url, api_key_env, model_hint, kind (`openai_compat` | `anthropic` | `mock`), enabled

Default providers seeded once: mock, openai, anthropic, groq, openrouter, together, ollama, vllm.

Trace statuses include: `ok`, `upstream_error`, `blocked_security`, `blocked_security_output`, `blocked_budget`.

---

## 8. Attribution headers (product contract)

| Header | Meaning |
|---|---|
| `X-COS-Project` | product / team |
| `X-COS-Feature` | feature or agent name |
| `X-COS-User` | end-user id |
| `X-COS-Session` | conversation group |
| `X-COS-Provider` | provider catalog name (openai, ollama, …) |

Also accepted on JSON body: `metadata.feature`, `provider`.

When renaming publicly to Cosen, **keep these headers** for compatibility and also accept `X-Cosen-*` as aliases.

---

## 9. HTTP surface

Web (serves `web/index.html`): `/` `/app` `/dashboard` `/overview` `/playground` `/traces` `/security` `/providers` `/pricing`

Health: `GET /health` `GET /api/health` → `{ok, service: "cosen", mock, web}`

Gateway:

- `POST /v1/chat/completions` — main path (OpenAI-compatible)
- `POST /v1/messages` — Anthropic Messages API inbound path (translated to the same security/cost path)
- `GET /v1/models`

App API:

- `GET /api/summary?hours=24`
- `GET /api/traces`
- `GET /api/providers`  `POST /api/providers`  `DELETE /api/providers/{name}`
- `POST /api/scan` `{text, side: input|output}`
- `GET /api/pricing`
- `GET /api/policy`
- `GET /metrics` · `GET /api/metrics`
- `GET /api/integrations`
- `GET /api/export/sarif` · `/api/export/owasp` · `/api/export/otel`
- `POST /cos/scan` (legacy)

Errors:

- `403` `{error: {type: "cos_security_block", findings}}`
- `429` `{error: {type: "cos_budget_block", budget}}`

Successful completions add:

```json
"cos": { "cost_usd": 0.0, "latency_ms": 12, "security": "allow", "feature": "playground" }
```

CORS is open (`*`) so a separately hosted UI can call a local gateway later.

**Streaming (`stream: true`) is not implemented.** Non-stream only.

---

## 10. Request path (every chat call)

1. Parse body + attribution headers
2. Scan input messages
3. If policy says block on high/critical → persist trace `blocked_security`, return 403
4. Estimate tokens/cost; if daily budget exceeded → `blocked_budget` 429
5. If mock provider / `--mock` / model starts with `cos-` → local canned reply
6. Else forward to provider `base_url` + `Authorization` from `api_key_env` or incoming Authorization
7. Scan output; redact or block per policy
8. Compute USD from usage or ~4 chars/token fallback
9. Persist trace + security events
10. Return upstream JSON + `cos` metadata

---

## 11. Security scanners (`cosen/security.py`)

Deterministic regex only. Do **not** add exploit recipes to the repo or docs.

| Scanner | Side | Default severity |
|---|---|---|
| secrets | in/out | critical (AWS AKIA, Google AIza, Slack xox, PEM, sk-, ghP, generic bearer) |
| pii | in/out | medium (email, phone, Luhn card) |
| prompt_injection | input | high |
| jailbreak | input | high |
| system_leak | output | high |

Policy (`cosen/policies/default.yaml` → copied by `cosen init` to `./cosen.yaml`):

```yaml
security:
  enabled: true
  on_input_match: block      # block | redact | observe
  on_output_match: redact
  block_severities: [critical, high]
```

`cos scan --text "..."` and Playground “Scan prompt only” use the same module.

---

## 12. Cost

`cosen/data/pricing.yaml` — USD per 1M input/output tokens. Unknown models use `default`. Local llama/qwen rates are $0.

`cos cost --model gpt-4o-mini --input-tokens 1200 --output-tokens 400 --calls 10000`

Budgets in policy:

```yaml
cost:
  enforce_budgets: true
  budgets:
    - scope: project
      name: default
      daily_usd: 50.00
    - scope: feature
      name: checkout-bot
      daily_usd: 10.00
```

Budget window is **UTC day**. Blocked budget traces do not add to spend.

---

## 13. CLI

```
cosen init
cosen serve [--mock] [--host] [--port] [--upstream URL] [--config FILE]
cosen demo [--port]
cosen report [--hours 24] [--json]
cosen scan [--text] [--file] [--side input|output]
cosen cost --model NAME --input-tokens N --output-tokens N [--calls N]
cosen mcp
cosen integrate list|show|apply
cosen export sarif|owasp|otel|prometheus
```

`cos` is an alias of the same entrypoint for backward compatibility.

---

## 13b. Platform integrations

| Target | Command / endpoint |
|---|---|
| CLI/SDK catalog | `cosen integrate list` |
| OWASP LLM Top 10 | `cosen export owasp` · `GET /api/export/owasp` |
| SARIF (SonarQube / GitHub) | `cosen export sarif` · `GET /api/export/sarif` |
| Prometheus | `GET /metrics` · `cosen export prometheus` |
| OpenTelemetry JSON | `cosen export otel` · `GET /api/export/otel` |

---

## 14. Web app pages (`cosen/web/index.html`)

Dark single-page app, hash routes:

- Overview — 24h KPIs, spend by model/feature
- Playground — provider + model + feature/project tags + prompt; calls `/v1/chat/completions`
- Traces — recent rows
- Security — paste-scan + 24h findings
- Providers — list + add OpenAI-compat base URL
- Pricing — table from `/api/pricing`

No build step. Edit HTML/JS directly.

---

## 15. What is NOT built yet (backlog in order)

Do these in order. Do not skip to a rewrite unless asked.

1. ✅ **Rename** package/CLI/docs from COS/cosai → Cosen; keep `X-COS-*` headers; Apache-2.0 + CLA.md
2. ✅ **Provider expansion** — Anthropic Messages API native adapter; keep OpenAI-compat wire format
3. ✅ **Inbound Anthropic endpoint** — `/v1/messages` for Claude CLI and other Anthropic-native tools
4. ✅ **CLI agent integrations** — Codex, Claude CLI, `llm`, aider, plus Cursor MCP
5. **Streaming** — buffer SSE or reject `stream:true` with a clear error
6. **Provider health check** — `GET {base}/models` from the UI
7. **Embeddings + other OpenAI routes** if needed (`/v1/embeddings`)
8. **Auth on the web app** when bound to `0.0.0.0` (token or basic auth)
9. ✅ **OpenTelemetry export** — lightweight OTLP/JSON via `cosen export otel` / `/api/export/otel` (no heavy SDK)
10. ✅ **GitHub Action** — pytest + scanner contract + mock gateway smoke on every PR; example SARIF upload in `examples/github-action-cosen-sarif.yml`
10b. ✅ **OWASP / SonarQube / Prometheus / Semgrep pairing** — exporters + integrate catalog
11. **Better tokenizers** — optional tiktoken; keep 4-char fallback
12. **Replace stdlib HTTP server** with FastAPI/uvicorn only if streaming + uploads demand it
13. EE later: SSO, orgs, multi-tenant cloud

Explicit non-goals for v0.x: visual agent builder, prompt CMS, RAG engine, LLM-as-judge eval suite, ClickHouse.

---

## 16. Positioning vs existing tools

Cosen is the **intersection**, not a clone.

| Need | Typical tool | Gap Cosen fills |
|---|---|---|
| Cost | LiteLLM bills | Not tied to feature/product |
| Observability | Langfuse / Helicone | Security is after the fact |
| Security | promptfoo / garak | Offline, not on the path |

Do not compete on evals or prompt versioning.

---

## 17. Tests and definition of done

```bash
PYTHONPATH=. python -m pytest tests/ -q
cosen scan --text "Ignore previous instructions"    # exit 1, high injection
cosen serve --mock
curl -s localhost:8080/api/health
curl -s localhost:8080/ | grep -q Playground
```

A change is done when: mock still works without keys, a blocked injection returns 403, a clean playground call writes a trace with cost, UI still loads from `/`.

---

## 18. How to implement further work

- Read the existing modules before adding frameworks.
- Prefer extending `gateway.py`, `store.py`, `web/index.html`.
- Keep the public contract stable (`/v1/chat/completions`, headers, error types).
- Do not store raw API keys in the provider table.
- Do not document exploit payloads beyond what scanners already detect.
- When adding files, keep generation scripts out of the user-facing repo root if they are throwaway.

If you change architecture (e.g. FastAPI), keep the same URLs and SQLite schema or migrate explicitly.

---

## 19. Suggested first commit after handoff

1. ✅ Relicense Apache-2.0
2. ✅ Rename user-facing strings COS → Cosen
3. ✅ Add `CLA.md` + CONTRIBUTING
4. ✅ Add Anthropic native adapter while keeping OpenAI-compatible wire format
5. ✅ Add `/v1/messages` inbound endpoint for Claude CLI and Anthropic-native tools
6. ✅ Add Cursor MCP + CLI agent integration docs (Codex, Claude CLI, llm, aider)
7. Implement `stream:true` handling
8. Add pytest for gateway block/allow using the mock server
