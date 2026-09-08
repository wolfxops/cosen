"""Catalog of CLI, SDK, and visibility-tool integrations."""

from __future__ import annotations

from typing import Any

# Each entry describes how Cosen plugs into a developer tool or org platform.
# category: cli | sdk | security | observability | cost | editor

INTEGRATIONS: dict[str, dict[str, Any]] = {
    # --- LLM CLIs ---
    "codex": {
        "name": "OpenAI Codex CLI",
        "category": "cli",
        "pillars": ["cost", "observability", "security"],
        "summary": "Point Codex at Cosen via OPENAI_BASE_URL.",
        "env": {"OPENAI_BASE_URL": "http://127.0.0.1:8080/v1"},
        "snippet": '''export OPENAI_BASE_URL=http://127.0.0.1:8080/v1
cosen serve --mock   # or --upstream https://api.openai.com/v1
codex "refactor this function"''',
        "write": None,
    },
    "claude-cli": {
        "name": "Anthropic Claude CLI",
        "category": "cli",
        "pillars": ["cost", "observability", "security"],
        "summary": "Claude CLI uses /v1/messages; Cosen translates and enforces policy.",
        "env": {"ANTHROPIC_BASE_URL": "http://127.0.0.1:8080/v1"},
        "snippet": '''export ANTHROPIC_BASE_URL=http://127.0.0.1:8080/v1
cosen serve --upstream https://api.anthropic.com/v1
claude "explain this function"''',
        "write": None,
    },
    "llm": {
        "name": "Simon Willison llm",
        "category": "cli",
        "pillars": ["cost", "observability", "security"],
        "summary": "Register Cosen as an OpenAI-compatible endpoint for llm.",
        "env": {},
        "snippet": '''cosen serve --mock
llm -o base_url http://127.0.0.1:8080/v1 -m gpt-4o-mini "what is the refund window?"''',
        "write": None,
    },
    "aider": {
        "name": "aider",
        "category": "cli",
        "pillars": ["cost", "observability", "security"],
        "summary": "Route aider through Cosen with OPENAI_API_BASE.",
        "env": {"OPENAI_API_BASE": "http://127.0.0.1:8080/v1"},
        "snippet": '''export OPENAI_API_BASE=http://127.0.0.1:8080/v1
aider --model gpt-4o-mini''',
        "write": None,
    },
    "continue": {
        "name": "Continue.dev",
        "category": "editor",
        "pillars": ["cost", "observability", "security"],
        "summary": "Configure Continue to use Cosen as an OpenAI-compatible provider.",
        "env": {},
        "snippet": '''{
  "models": [
    {
      "title": "Cosen",
      "provider": "openai",
      "model": "gpt-4o-mini",
      "apiBase": "http://127.0.0.1:8080/v1",
      "apiKey": "not-needed-when-mock"
    }
  ]
}''',
        "write": {
            "path": ".continue/config.json",
            "mode": "snippet_hint",
            "note": "Merge the models[] entry into your Continue config.",
        },
    },
    "gemini-cli": {
        "name": "Google Gemini CLI / OpenAI-compat wrappers",
        "category": "cli",
        "pillars": ["cost", "observability", "security"],
        "summary": "Any OpenAI-compatible Gemini proxy can use Cosen as base URL.",
        "env": {"OPENAI_BASE_URL": "http://127.0.0.1:8080/v1"},
        "snippet": '''export OPENAI_BASE_URL=http://127.0.0.1:8080/v1
# Point your Gemini OpenAI-compat shim or gateway at Cosen first.''',
        "write": None,
    },
    # --- SDKs ---
    "openai-python": {
        "name": "OpenAI Python SDK",
        "category": "sdk",
        "pillars": ["cost", "observability", "security"],
        "summary": "Drop-in base_url for openai>=1.0 clients.",
        "env": {},
        "snippet": '''from openai import OpenAI

client = OpenAI(
    base_url="http://127.0.0.1:8080/v1",
    api_key="not-needed-in-mock",
)
client.chat.completions.create(
    model="gpt-4o-mini",
    messages=[{"role": "user", "content": "hello"}],
    extra_headers={"X-COS-Feature": "my-feature", "X-COS-Project": "acme"},
)''',
        "write": {"path": "examples/openai_sdk.py", "mode": "file"},
    },
    "openai-node": {
        "name": "OpenAI Node.js SDK",
        "category": "sdk",
        "pillars": ["cost", "observability", "security"],
        "summary": "Drop-in baseURL for the official OpenAI JS client.",
        "env": {},
        "snippet": '''import OpenAI from "openai";

const client = new OpenAI({
  baseURL: "http://127.0.0.1:8080/v1",
  apiKey: "not-needed-in-mock",
});

await client.chat.completions.create({
  model: "gpt-4o-mini",
  messages: [{ role: "user", content: "hello" }],
}, {
  headers: { "X-COS-Feature": "my-feature", "X-COS-Project": "acme" },
});''',
        "write": {"path": "examples/openai_sdk.mjs", "mode": "file"},
    },
    "anthropic-python": {
        "name": "Anthropic Python SDK",
        "category": "sdk",
        "pillars": ["cost", "observability", "security"],
        "summary": "Point Anthropic SDK base_url at Cosen /v1 (Messages API).",
        "env": {},
        "snippet": '''import anthropic

client = anthropic.Anthropic(
    base_url="http://127.0.0.1:8080",
    api_key="not-needed-in-mock",
)
client.messages.create(
    model="claude-sonnet-4-20250514",
    max_tokens=256,
    messages=[{"role": "user", "content": "hello"}],
)''',
        "write": {"path": "examples/anthropic_sdk.py", "mode": "file"},
    },
    "langchain": {
        "name": "LangChain",
        "category": "sdk",
        "pillars": ["cost", "observability", "security"],
        "summary": "ChatOpenAI with base_url pointed at Cosen.",
        "env": {},
        "snippet": '''from langchain_openai import ChatOpenAI

llm = ChatOpenAI(
    base_url="http://127.0.0.1:8080/v1",
    api_key="not-needed-in-mock",
    model="gpt-4o-mini",
    default_headers={"X-COS-Feature": "langchain-agent", "X-COS-Project": "acme"},
)
print(llm.invoke("Summarize the refund policy").content)''',
        "write": {"path": "examples/langchain_cosen.py", "mode": "file"},
    },
    "llamaindex": {
        "name": "LlamaIndex",
        "category": "sdk",
        "pillars": ["cost", "observability", "security"],
        "summary": "OpenAI-compatible LLM class via Cosen gateway.",
        "env": {},
        "snippet": '''from llama_index.llms.openai_like import OpenAILike

llm = OpenAILike(
    model="gpt-4o-mini",
    api_base="http://127.0.0.1:8080/v1",
    api_key="not-needed-in-mock",
    is_chat_model=True,
)
print(llm.complete("What is the refund window?"))''',
        "write": {"path": "examples/llamaindex_cosen.py", "mode": "file"},
    },
    "cursor-mcp": {
        "name": "Cursor MCP",
        "category": "editor",
        "pillars": ["cost", "observability", "security"],
        "summary": "Expose cosen_scan / cosen_cost / cosen_report / cosen_gateway_chat in Cursor.",
        "env": {},
        "snippet": '''{
  "mcpServers": {
    "cosen": {
      "command": "cosen",
      "args": ["mcp"]
    }
  }
}''',
        "write": {"path": ".cursor/mcp.json", "mode": "file"},
    },
    # --- Security / visibility platforms ---
    "owasp-llm": {
        "name": "OWASP LLM Top 10",
        "category": "security",
        "pillars": ["security"],
        "summary": "Map Cosen scanners to OWASP LLM Top 10 and export a coverage report.",
        "env": {},
        "snippet": '''cosen export owasp --hours 24 --out cosen-owasp.json
# Also: GET http://127.0.0.1:8080/api/export/owasp?hours=24''',
        "write": None,
        "export": "owasp",
    },
    "sarif": {
        "name": "SARIF 2.1.0",
        "category": "security",
        "pillars": ["security"],
        "summary": "Industry-standard findings format for SonarQube, GitHub Code Scanning, VS Code.",
        "env": {},
        "snippet": '''cosen export sarif --hours 24 --out cosen-security.sarif
# Upload to GitHub Advanced Security or import into SonarQube.''',
        "write": None,
        "export": "sarif",
    },
    "sonarqube": {
        "name": "SonarQube / SonarCloud",
        "category": "security",
        "pillars": ["security"],
        "summary": "Import Cosen SARIF via sonar.sarifReportPaths (no proprietary plugin required).",
        "env": {},
        "snippet": '''# Generate SARIF from live traces or a prompt scan
cosen export sarif --hours 24 --out reports/cosen-security.sarif

# sonar-project.properties
sonar.projectKey=my-ai-app
sonar.sarifReportPaths=reports/cosen-security.sarif

# Or CI:
# sonar-scanner -Dsonar.sarifReportPaths=reports/cosen-security.sarif''',
        "write": {
            "path": "examples/sonar-project.properties.example",
            "mode": "file",
            "content": """sonar.projectKey=my-ai-app
sonar.projectName=My AI App
sonar.sources=.
sonar.sarifReportPaths=reports/cosen-security.sarif
""",
        },
    },
    "github-code-scanning": {
        "name": "GitHub Code Scanning",
        "category": "security",
        "pillars": ["security"],
        "summary": "Upload Cosen SARIF with github/codeql-action/upload-sarif.",
        "env": {},
        "snippet": '''# .github/workflows/cosen-security.yml (see integrations/github-action)
cosen export sarif --hours 168 --out cosen-security.sarif
# then: upload-sarif with sarif_file: cosen-security.sarif''',
        "write": None,
    },
    "semgrep": {
        "name": "Semgrep",
        "category": "security",
        "pillars": ["security"],
        "summary": "Complement Semgrep SAST with runtime LLM findings via shared SARIF in CI.",
        "env": {},
        "snippet": '''# Run Semgrep for code + Cosen for LLM traffic/prompt policy
semgrep --config auto --sarif -o semgrep.sarif
cosen export sarif --hours 24 --out cosen-security.sarif
# Both SARIF files can be uploaded to the same code-scanning dashboard.''',
        "write": None,
    },
    "prometheus": {
        "name": "Prometheus",
        "category": "observability",
        "pillars": ["cost", "observability", "security"],
        "summary": "Scrape GET /metrics for calls, cost, latency, and security blocks.",
        "env": {},
        "snippet": '''# prometheus.yml
scrape_configs:
  - job_name: cosen
    static_configs:
      - targets: ["127.0.0.1:8080"]
    metrics_path: /metrics

# Or print once:
cosen export prometheus --hours 24''',
        "write": {
            "path": "examples/prometheus-cosen.yml",
            "mode": "file",
            "content": """scrape_configs:
  - job_name: cosen
    scrape_interval: 15s
    static_configs:
      - targets: ["127.0.0.1:8080"]
    metrics_path: /metrics
""",
        },
    },
    "opentelemetry": {
        "name": "OpenTelemetry",
        "category": "observability",
        "pillars": ["cost", "observability"],
        "summary": "Export traces as OTLP-compatible JSON for collectors and backends.",
        "env": {},
        "snippet": '''cosen export otel --hours 24 --out cosen-otel.json
# Also: GET http://127.0.0.1:8080/api/export/otel?hours=24
# Feed into an OTLP collector, Jaeger, Grafana Tempo, etc.''',
        "write": None,
        "export": "otel",
    },
    "grafana": {
        "name": "Grafana",
        "category": "observability",
        "pillars": ["cost", "observability", "security"],
        "summary": "Use Prometheus datasource against Cosen /metrics for cost and block dashboards.",
        "env": {},
        "snippet": '''# 1. Scrape Cosen with Prometheus (see prometheus integration)
# 2. Add Prometheus as a Grafana datasource
# 3. Panel examples:
#    sum(cosen_cost_usd_total) 
#    sum(cosen_requests_total)
#    sum(cosen_security_blocks_total)''',
        "write": None,
    },
}


def list_integrations(*, category: str | None = None, pillar: str | None = None) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for key, meta in INTEGRATIONS.items():
        if category and meta.get("category") != category:
            continue
        if pillar and pillar not in (meta.get("pillars") or []):
            continue
        rows.append(
            {
                "id": key,
                "name": meta["name"],
                "category": meta["category"],
                "pillars": list(meta.get("pillars") or []),
                "summary": meta.get("summary") or "",
            }
        )
    return rows


def get_integration(key: str) -> dict[str, Any] | None:
    meta = INTEGRATIONS.get(key)
    if not meta:
        return None
    return {"id": key, **meta}
