"""Lightweight OpenTelemetry-compatible JSON export (no OTEL SDK dependency)."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any

from .. import __version__, store


def _ts_to_nano(ts: str | None) -> str:
    if not ts:
        return str(int(datetime.now(timezone.utc).timestamp() * 1_000_000_000))
    try:
        dt = datetime.fromisoformat(ts.replace("Z", "+00:00"))
    except ValueError:
        return str(int(datetime.now(timezone.utc).timestamp() * 1_000_000_000))
    return str(int(dt.timestamp() * 1_000_000_000))


def otel_traces_export(*, hours: int = 24, limit: int = 200) -> dict[str, Any]:
    """Export recent Cosen traces as OTLP/JSON-shaped spans for collectors."""
    traces = store.query_traces(limit=limit, since_hours=hours)
    spans: list[dict[str, Any]] = []
    for trace in traces:
        latency_ms = int(trace.get("latency_ms") or 0)
        start = _ts_to_nano(str(trace.get("ts") or ""))
        try:
            end = str(int(start) + latency_ms * 1_000_000)
        except ValueError:
            end = start
        attrs = [
            {"key": "cosen.trace_id", "value": {"intValue": str(trace.get("id") or 0)}},
            {"key": "cosen.project", "value": {"stringValue": str(trace.get("project") or "")}},
            {"key": "cosen.feature", "value": {"stringValue": str(trace.get("feature") or "")}},
            {"key": "cosen.model", "value": {"stringValue": str(trace.get("model") or "")}},
            {"key": "cosen.provider", "value": {"stringValue": str(trace.get("provider") or "")}},
            {"key": "cosen.status", "value": {"stringValue": str(trace.get("status") or "")}},
            {"key": "cosen.security_verdict", "value": {"stringValue": str(trace.get("security_verdict") or "")}},
            {"key": "cosen.cost_usd", "value": {"doubleValue": float(trace.get("cost_usd") or 0.0)}},
            {"key": "cosen.total_tokens", "value": {"intValue": str(trace.get("total_tokens") or 0)}},
            {"key": "http.route", "value": {"stringValue": "/v1/chat/completions"}},
        ]
        status_code = 1  # STATUS_CODE_OK
        status = str(trace.get("status") or "")
        if status.startswith("blocked") or status == "upstream_error":
            status_code = 2  # STATUS_CODE_ERROR
        spans.append(
            {
                "traceId": f"{int(trace.get('id') or 0):032x}",
                "spanId": f"{int(trace.get('id') or 0):016x}",
                "name": "cosen.llm.call",
                "kind": 3,  # SPAN_KIND_CLIENT
                "startTimeUnixNano": start,
                "endTimeUnixNano": end,
                "attributes": attrs,
                "status": {
                    "code": status_code,
                    "message": str(trace.get("error") or ""),
                },
            }
        )
    return {
        "resourceSpans": [
            {
                "resource": {
                    "attributes": [
                        {"key": "service.name", "value": {"stringValue": "cosen"}},
                        {"key": "service.version", "value": {"stringValue": __version__}},
                        {"key": "telemetry.sdk.name", "value": {"stringValue": "cosen"}},
                    ]
                },
                "scopeSpans": [
                    {
                        "scope": {"name": "cosen.gateway", "version": __version__},
                        "spans": spans,
                    }
                ],
            }
        ],
        "cosen": {
            "schema": "cosen.otel_json.v1",
            "hours": hours,
            "span_count": len(spans),
            "note": "OTLP/JSON shaped for collectors; push with your preferred OTLP HTTP exporter.",
        },
    }


def otel_dump(*, hours: int = 24, limit: int = 200) -> str:
    return json.dumps(otel_traces_export(hours=hours, limit=limit), indent=2)
