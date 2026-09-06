# Cosen

**LLM-agnostic cost, observability, and security — as a local web app.**

Host it on your laptop or a private VM. Point any OpenAI-compatible model at it. Every call is priced, traced, and scanned before it can burn budget or leak a secret.

The web UI ships in the same process as the gateway. No SaaS account required.

```
Browser (Cosen web app) ─┐
Your product SDK        ─┼→  Cosen  →  any OpenAI-compatible model
CI / curl               ─┘       │
                                 ├── Cost ledger + daily budgets
                                 ├── Trace store (SQLite)
                                 └── Security policy (block / redact / observe)
```

This is the first public project in the AIDP line: tools that help people *ship AI products*, not another agent framework.

## Why a single suite

Most teams already run three products that do not share a data model:

| Need | Typical tool | Gap |
|---|---|---|
| Cost | LiteLLM / OpenRouter bills | Not tied to *feature* or *product* |
| Observability | Langfuse / Helicone / Phoenix | Security is an afterthought |
| Security | promptfoo / guardrails / garak | Offline, not on the request path |

Cosen puts all three on the same request:

1. **Cost** — token usage × model price, tagged by `feature` / `project` / `user`, with daily kill-switches.
2. **Observability** — traces, latency, model mix, local web app, a CLI report.
3. **Security** — deterministic scanners on input and output (secrets, PII, injection phrasing, jailbreak phrasing, system-prompt leak). No extra judge model required.

It is deliberately small. SQLite on disk. No ClickHouse. No account. Apache-2.0.

## Five-minute start

```bash
python -m pip install -e .
cosen init
cosen demo          # seeds mock traces
cosen serve --mock  # http://127.0.0.1:8080/
```

Open the local web app at [http://127.0.0.1:8080/](http://127.0.0.1:8080/).

Pages: Overview · Playground · Traces · Security · Providers · Pricing.

Talk to it like OpenAI:

```python
from openai import OpenAI

client = OpenAI(base_url="http://127.0.0.1:8080/v1", api_key="not-needed-in-mock")
client.chat.completions.create(
    model="gpt-4o-mini",
    messages=[{"role": "user", "content": "Reset my password flow?"}],
    extra_headers={"X-COS-Feature": "support-bot", "X-COS-Project": "acme"},
)
```

Or curl:

```bash
curl http://127.0.0.1:8080/v1/chat/completions \
  -H 'Content-Type: application/json' \
  -H 'X-COS-Feature: support-bot' \
  -d '{"model":"gpt-4o-mini","messages":[{"role":"user","content":"hello"}]}'
```

## LLM-agnostic by contract

Cosen never imports OpenAI, Anthropic, or Google SDKs. The only wire format is OpenAI-compatible `/v1/chat/completions`. Add providers in the web app (or `POST /api/providers`):

| Provider | Example base URL | Kind |
|---|---|---|
| OpenAI | `https://api.openai.com/v1` | openai_compat |
| Anthropic | `https://api.anthropic.com/v1` | anthropic |
| Groq | `https://api.groq.com/openai/v1` | openai_compat |
| OpenRouter | `https://openrouter.ai/api/v1` |
| Together | `https://api.together.xyz/v1` |
| Ollama (local) | `http://127.0.0.1:11434/v1` |
| vLLM (local) | `http://127.0.0.1:8000/v1` |
| Any gateway | LiteLLM, Azure-compat, Fireworks, … |

API keys stay in environment variables on the host (`OPENAI_API_KEY`, `GROQ_API_KEY`, …). The playground sends `X-COS-Provider` so one Cosen process can fan out to many labs.

```bash
export OPENAI_API_KEY=sk-...
cosen serve --upstream https://api.openai.com/v1

# Anthropic (native Messages API)
export ANTHROPIC_API_KEY=sk-ant-...
cosen serve --upstream https://api.anthropic.com/v1

# Local model
cosen serve --upstream http://127.0.0.1:11434/v1
```

Host the web app only on loopback, or bind a private interface:

```bash
cosen serve --mock --host 127.0.0.1 --port 8080
# LAN / VM
cosen serve --host 0.0.0.0 --port 8080 --upstream http://127.0.0.1:11434/v1
```

Set `upstream.base_url` and `upstream.api_key_env` in `cosen.yaml` for a permanent default when the request does not name a provider.

## Attribution headers

These turn a token bill into a *product* bill.

| Header | Meaning |
|---|---|
| `X-COS-Project` | Product / team |
| `X-COS-Feature` | Feature or agent name |
| `X-COS-User` | End user id (hashed if you want) |
| `X-COS-Session` | Conversation / trace group |

## CLI

```
cosen init                 Write cosen.yaml
cosen serve --mock         Run gateway + dashboard
cosen demo                 Seed sample traffic
cosen report --hours 24    Cost / obs / security summary
cosen scan --text "..."    Scan a prompt or output
cosen cost --model gpt-4o-mini --input-tokens 1200 --output-tokens 400 --calls 10000
cosen mcp                  Start the MCP server for Cursor
```

`cos` is still an alias of the same entrypoint.

## Cursor integration (MCP)

Cosen exposes security, cost, and observability tools inside Cursor via the Model Context Protocol.

Add this to your Cursor MCP settings (`.cursor/mcp.json` or **Settings → MCP**):

```json
{
  "mcpServers": {
    "cosen": {
      "command": "cosen",
      "args": ["mcp"]
    }
  }
}
```

Cursor can then:
- **Scan** prompts/outputs for secrets, PII, or injection phrasing.
- **Estimate cost** for a model and token count.
- **Read the local report** for cost, latency, and security findings.
- **Send chat calls** through the running Cosen gateway.

## CLI agent integrations

Cosen also sits in front of LLM CLI agents. Because it exposes both `/v1/chat/completions` (OpenAI) and `/v1/messages` (Anthropic), you can point most CLI tools at the local gateway.

### OpenAI Codex CLI

```bash
export OPENAI_BASE_URL=http://127.0.0.1:8080/v1
codex "summarize the refund policy"
```

### Anthropic Claude CLI

```bash
export ANTHROPIC_BASE_URL=http://127.0.0.1:8080/v1
claude "explain this function"
```

> Claude CLI sends Anthropic Messages API calls; Cosen translates them internally and runs the same security/cost path.

### Simon Willison's `llm`

Register Cosen as an OpenAI-compatible model:

```bash
llm models --options
llm -m cosen "what is the refund window?"
```

(Use `llm` plugins or templates to set `base_url` to `http://127.0.0.1:8080/v1`.)

### aider

```bash
export OPENAI_API_BASE=http://127.0.0.1:8080/v1
aider --model gpt-4o-mini
```

### What gets traced

Every CLI call goes through the same path: input scan, budget check, model call, output scan, trace, cost. You can see them in the web app or with `cosen report`.

## Policy

`cosen init` copies a default policy. The important knobs:

```yaml
security:
  on_input_match: block    # block | redact | observe
  on_output_match: redact
  block_severities: [critical, high]

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

Blocked calls return:

- `403` `cos_security_block`
- `429` `cos_budget_block`

## What v0.1 does not do (yet)

- Streaming (`stream: true`) — buffer/reject; non-stream first
- Multi-modal parts other than text
- LLM-as-judge evals (out of scope on purpose)
- ClickHouse / multi-node
- Learned jailbreak classifiers

Those belong in v0.2 only if this core loop is used daily.

## Layout

```
cosen/
  cli.py          cosen command
  gateway.py      OpenAI-compatible proxy + Anthropic + mock model
  cost.py         pricing table + budgets
  security.py     deterministic scanners
  store.py        SQLite traces + events
  dashboard.py    single-page local UI
  web/index.html  local web app
  data/pricing.yaml
  policies/default.yaml
```

Data lives in `./.cosen/cosen.db` (or `$COSEN_HOME` / `$COS_HOME`).

## Design rules

1. The model is a plugin. Cosen never depends on one lab's API shape beyond OpenAI-compat and explicit native adapters.
2. Security runs *on the path*, not in a weekly batch.
3. Cost is a feature attribute, not a month-end surprise.
4. First run works without an API key (`--mock` / `cosen demo`).
5. One binary mental model: `serve`, `report`, `scan`.

## License

Apache License 2.0. See [LICENSE](LICENSE) and [CLA.md](CLA.md) for contribution terms.
