"""OWASP LLM Top 10 mapping and coverage reports."""

from __future__ import annotations

import json
from typing import Any

from .. import __version__, security, store

# OWASP Top 10 for Large Language Model Applications (2025 taxonomy ids).
# Cosen maps deterministic scanners onto the categories it can observe on-path.
OWASP_LLM_CONTROLS: list[dict[str, Any]] = [
    {
        "id": "LLM01",
        "name": "Prompt Injection",
        "scanners": ["prompt_injection", "jailbreak"],
        "coverage": "partial",
        "notes": "Blocks/observes common injection and jailbreak phrasing on input.",
    },
    {
        "id": "LLM02",
        "name": "Sensitive Information Disclosure",
        "scanners": ["secrets", "pii", "system_leak"],
        "coverage": "partial",
        "notes": "Detects secrets/PII on in/out and system-prompt leak phrasing on output.",
    },
    {
        "id": "LLM03",
        "name": "Supply Chain",
        "scanners": [],
        "coverage": "none",
        "notes": "Out of band — pair with Semgrep/Trivy/Sonar for dependency and model provenance.",
    },
    {
        "id": "LLM04",
        "name": "Data and Model Poisoning",
        "scanners": [],
        "coverage": "none",
        "notes": "Training-time risk; not on the inference request path.",
    },
    {
        "id": "LLM05",
        "name": "Improper Output Handling",
        "scanners": ["system_leak", "secrets"],
        "coverage": "partial",
        "notes": "Output scan + redact/block; still sanitize downstream rendering yourself.",
    },
    {
        "id": "LLM06",
        "name": "Excessive Agency",
        "scanners": [],
        "coverage": "none",
        "notes": "Use feature budgets and product authz; Cosen does not broker tool calls.",
    },
    {
        "id": "LLM07",
        "name": "System Prompt Leakage",
        "scanners": ["system_leak"],
        "coverage": "partial",
        "notes": "Heuristic leak phrasing on model output.",
    },
    {
        "id": "LLM08",
        "name": "Vector and Embedding Weaknesses",
        "scanners": [],
        "coverage": "none",
        "notes": "Embeddings gateway not in scope for this export.",
    },
    {
        "id": "LLM09",
        "name": "Misinformation",
        "scanners": [],
        "coverage": "none",
        "notes": "Requires eval/judge workflows; intentionally out of Cosen core.",
    },
    {
        "id": "LLM10",
        "name": "Unbounded Consumption",
        "scanners": [],
        "coverage": "partial",
        "notes": "Daily feature/project USD budgets act as a kill-switch for spend/DoS-by-token.",
        "budget_control": True,
    },
]

SCANNER_TO_OWASP: dict[str, list[str]] = {}
for control in OWASP_LLM_CONTROLS:
    for scanner in control.get("scanners") or []:
        SCANNER_TO_OWASP.setdefault(scanner, []).append(control["id"])


def map_finding(finding: dict[str, Any] | security.Finding) -> list[str]:
    if isinstance(finding, security.Finding):
        scanner = finding.scanner
    else:
        scanner = str(finding.get("scanner") or finding.get("kind") or "")
    return list(SCANNER_TO_OWASP.get(scanner, []))


def owasp_llm_report(*, hours: int = 24, include_findings: bool = True) -> dict[str, Any]:
    summary = store.summarize(hours)
    events = summary.get("findings") or []
    by_scanner: dict[str, int] = {}
    for row in events:
        kind = str(row.get("kind") or "unknown")
        by_scanner[kind] = by_scanner.get(kind, 0) + int(row.get("n") or 0)

    controls: list[dict[str, Any]] = []
    for control in OWASP_LLM_CONTROLS:
        hits = 0
        for scanner in control.get("scanners") or []:
            hits += by_scanner.get(scanner, 0)
        if control.get("budget_control"):
            hits += int((summary.get("totals") or {}).get("blocked") or 0)
        controls.append(
            {
                **control,
                "findings_in_window": hits,
                "status": "observed" if hits else control.get("coverage"),
            }
        )

    finding_rows: list[dict[str, Any]] = []
    if include_findings:
        for trace in summary.get("recent") or []:
            raw = trace.get("security_findings") or "[]"
            try:
                items = json.loads(raw) if isinstance(raw, str) else (raw or [])
            except json.JSONDecodeError:
                items = []
            for item in items:
                finding_rows.append(
                    {
                        "trace_id": trace.get("id"),
                        "ts": trace.get("ts"),
                        "feature": trace.get("feature"),
                        "model": trace.get("model"),
                        "scanner": item.get("scanner"),
                        "severity": item.get("severity"),
                        "message": item.get("message"),
                        "owasp": map_finding(item),
                    }
                )

    covered = sum(1 for c in controls if c.get("coverage") != "none")
    return {
        "schema": "cosen.owasp_llm_report.v1",
        "framework": "OWASP Top 10 for Large Language Model Applications",
        "generator": {"name": "cosen", "version": __version__},
        "window_hours": hours,
        "coverage": {
            "controls_total": len(controls),
            "controls_with_runtime_signal": covered,
            "scanners_active": sorted(by_scanner),
        },
        "totals": summary.get("totals") or {},
        "controls": controls,
        "findings": finding_rows,
        "companion_tools": [
            {
                "name": "Semgrep",
                "use": "Static rules for LLM01/LLM03 patterns in source and prompts-as-code.",
            },
            {
                "name": "SonarQube",
                "use": "Import Cosen SARIF for LLM security findings beside SAST.",
            },
            {
                "name": "Trivy / Grype",
                "use": "LLM03 supply-chain: container and dependency CVEs around model servers.",
            },
            {
                "name": "Prometheus + Grafana",
                "use": "LLM10 unbounded consumption: alert on cosen_cost_usd_total and blocks.",
            },
        ],
    }
