"""SARIF 2.1.0 export for SonarQube, GitHub Code Scanning, and VS Code."""

from __future__ import annotations

import json
from typing import Any
from urllib.parse import quote

from .. import __version__, security
from .owasp import map_finding

_SEVERITY_TO_LEVEL = {
    "critical": "error",
    "high": "error",
    "medium": "warning",
    "low": "note",
    "info": "note",
}

_RULES = [
    {
        "id": "secrets",
        "name": "SecretLeakage",
        "shortDescription": {"text": "Possible secret or API key"},
        "fullDescription": {
            "text": "Deterministic detector for common API keys, tokens, and private key markers."
        },
        "defaultConfiguration": {"level": "error"},
        "properties": {"security-severity": "critical", "tags": ["security", "owasp-llm02"]},
    },
    {
        "id": "pii",
        "name": "PIIDisclosure",
        "shortDescription": {"text": "Possible PII"},
        "fullDescription": {"text": "Email, phone, or payment-card shaped content."},
        "defaultConfiguration": {"level": "warning"},
        "properties": {"security-severity": "medium", "tags": ["privacy", "owasp-llm02"]},
    },
    {
        "id": "prompt_injection",
        "name": "PromptInjection",
        "shortDescription": {"text": "Prompt-injection phrasing"},
        "fullDescription": {"text": "Input resembles common prompt-injection instructions."},
        "defaultConfiguration": {"level": "error"},
        "properties": {"security-severity": "high", "tags": ["security", "owasp-llm01"]},
    },
    {
        "id": "jailbreak",
        "name": "JailbreakPhrasing",
        "shortDescription": {"text": "Jailbreak phrasing"},
        "fullDescription": {"text": "Input resembles jailbreak / unconstrained-mode phrasing."},
        "defaultConfiguration": {"level": "error"},
        "properties": {"security-severity": "high", "tags": ["security", "owasp-llm01"]},
    },
    {
        "id": "system_leak",
        "name": "SystemPromptLeak",
        "shortDescription": {"text": "Possible system-prompt leak"},
        "fullDescription": {"text": "Model output appears to disclose hidden system instructions."},
        "defaultConfiguration": {"level": "error"},
        "properties": {"security-severity": "high", "tags": ["security", "owasp-llm07"]},
    },
]


def _tool_component() -> dict[str, Any]:
    return {
        "name": "cosen",
        "version": __version__,
        "informationUri": "https://github.com/wolfxops/cosen",
        "rules": _RULES,
    }


def findings_to_sarif(
    findings: list[dict[str, Any] | security.Finding],
    *,
    uri: str = "cosen://scan",
    tool_run_id: str | None = None,
) -> dict[str, Any]:
    results: list[dict[str, Any]] = []
    for finding in findings:
        if isinstance(finding, security.Finding):
            data = {
                "scanner": finding.scanner,
                "severity": finding.severity,
                "message": finding.message,
                "excerpt": finding.excerpt,
            }
        else:
            data = finding
        rule_id = str(data.get("scanner") or "secrets")
        level = _SEVERITY_TO_LEVEL.get(str(data.get("severity") or "medium"), "warning")
        owasp = map_finding(data)
        message = str(data.get("message") or rule_id)
        excerpt = str(data.get("excerpt") or "")
        if excerpt:
            message = f"{message}: {excerpt}"
        results.append(
            {
                "ruleId": rule_id,
                "level": level,
                "message": {"text": message},
                "locations": [
                    {
                        "physicalLocation": {
                            "artifactLocation": {"uri": uri},
                            "region": {"startLine": 1},
                        }
                    }
                ],
                "properties": {
                    "severity": data.get("severity"),
                    "owasp_llm": owasp,
                },
            }
        )
    run: dict[str, Any] = {
        "tool": {"driver": _tool_component()},
        "results": results,
    }
    if tool_run_id:
        run["automationDetails"] = {"id": tool_run_id}
    return {
        "$schema": "https://json.schemastore.org/sarif-2.1.0.json",
        "version": "2.1.0",
        "runs": [run],
    }


def traces_to_sarif(traces: list[dict[str, Any]], *, hours: int | None = None) -> dict[str, Any]:
    findings: list[dict[str, Any]] = []
    for trace in traces:
        raw = trace.get("security_findings") or "[]"
        try:
            items = json.loads(raw) if isinstance(raw, str) else (raw or [])
        except json.JSONDecodeError:
            items = []
        feature = trace.get("feature") or "untagged"
        project = trace.get("project") or "default"
        trace_id = trace.get("id")
        uri = f"cosen://traces/{quote(str(project))}/{quote(str(feature))}/{trace_id}"
        for item in items:
            row = dict(item)
            row["_uri"] = uri
            findings.append(row)

    # Group by uri while preserving order
    by_uri: dict[str, list[dict[str, Any]]] = {}
    for item in findings:
        uri = str(item.pop("_uri", "cosen://traces/unknown"))
        by_uri.setdefault(uri, []).append(item)

    results: list[dict[str, Any]] = []
    for uri, items in by_uri.items():
        partial = findings_to_sarif(items, uri=uri)
        results.extend(partial["runs"][0]["results"])

    run: dict[str, Any] = {
        "tool": {"driver": _tool_component()},
        "results": results,
        "properties": {"cosen_hours": hours, "trace_count": len(traces)},
    }
    return {
        "$schema": "https://json.schemastore.org/sarif-2.1.0.json",
        "version": "2.1.0",
        "runs": [run],
    }
