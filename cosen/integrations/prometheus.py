"""Prometheus text exposition for cost, observability, and security signals."""

from __future__ import annotations

from typing import Any

from .. import store


def _escape_label(value: str) -> str:
    return (
        value.replace("\\", "\\\\")
        .replace("\n", "\\n")
        .replace('"', '\\"')
    )


def prometheus_metrics(*, hours: int = 24) -> str:
    summary = store.summarize(hours)
    totals = summary.get("totals") or {}
    lines: list[str] = [
        "# HELP cosen_info Cosen gateway build info.",
        "# TYPE cosen_info gauge",
        'cosen_info{service="cosen"} 1',
        "# HELP cosen_scrape_window_hours Reporting window used for aggregated series.",
        "# TYPE cosen_scrape_window_hours gauge",
        f"cosen_scrape_window_hours {int(hours)}",
        "# HELP cosen_requests_total LLM calls observed in the window.",
        "# TYPE cosen_requests_total gauge",
        f"cosen_requests_total {int(totals.get('calls') or 0)}",
        "# HELP cosen_cost_usd_total Estimated USD spend in the window.",
        "# TYPE cosen_cost_usd_total gauge",
        f"cosen_cost_usd_total {float(totals.get('cost_usd') or 0.0)}",
        "# HELP cosen_tokens_total Tokens observed in the window.",
        "# TYPE cosen_tokens_total gauge",
        f"cosen_tokens_total {int(totals.get('tokens') or 0)}",
        "# HELP cosen_latency_ms_avg Average latency in milliseconds.",
        "# TYPE cosen_latency_ms_avg gauge",
        f"cosen_latency_ms_avg {float(totals.get('avg_latency_ms') or 0.0)}",
        "# HELP cosen_security_blocks_total Requests blocked or budget-killed in the window.",
        "# TYPE cosen_security_blocks_total gauge",
        f"cosen_security_blocks_total {int(totals.get('blocked') or 0)}",
        "# HELP cosen_security_flagged_total Requests with block/redact security verdict.",
        "# TYPE cosen_security_flagged_total gauge",
        f"cosen_security_flagged_total {int(totals.get('flagged') or 0)}",
        "# HELP cosen_cost_usd_by_feature Estimated USD by feature.",
        "# TYPE cosen_cost_usd_by_feature gauge",
    ]
    for row in summary.get("by_feature") or []:
        feature = _escape_label(str(row.get("feature") or "untagged"))
        lines.append(
            f'cosen_cost_usd_by_feature{{feature="{feature}"}} {float(row.get("cost_usd") or 0.0)}'
        )
    lines.extend(
        [
            "# HELP cosen_requests_by_model Calls by model.",
            "# TYPE cosen_requests_by_model gauge",
        ]
    )
    for row in summary.get("by_model") or []:
        model = _escape_label(str(row.get("model") or "unknown"))
        lines.append(f'cosen_requests_by_model{{model="{model}"}} {int(row.get("calls") or 0)}')
    lines.extend(
        [
            "# HELP cosen_security_findings Findings by scanner and severity.",
            "# TYPE cosen_security_findings gauge",
        ]
    )
    for row in summary.get("findings") or []:
        kind = _escape_label(str(row.get("kind") or "unknown"))
        severity = _escape_label(str(row.get("severity") or "info"))
        lines.append(
            f'cosen_security_findings{{scanner="{kind}",severity="{severity}"}} {int(row.get("n") or 0)}'
        )
    lines.append("")
    return "\n".join(lines)


def prometheus_as_dict(*, hours: int = 24) -> dict[str, Any]:
    """Structured companion for APIs that prefer JSON over text exposition."""
    summary = store.summarize(hours)
    return {"format": "prometheus_text_companion", "hours": hours, "summary": summary}
