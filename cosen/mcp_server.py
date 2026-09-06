"""Cosen MCP server for Cursor and other MCP clients.

Runs over stdin/stdout as a JSON-RPC server. Exposes Cosen security, cost,
and observability tools so Cursor can scan prompts, estimate spend, and
read reports without leaving the editor.
"""

from __future__ import annotations

import json
import sys
from typing import Any

import httpx

from . import __version__, cost, security, store
from .textutil import preview

TOOLS: list[dict[str, Any]] = [
    {
        "name": "cosen_scan",
        "description": "Scan text for secrets, PII, prompt injection, jailbreak, or system-prompt leaks.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "text": {"type": "string", "description": "Text to scan (prompt or model output)."},
                "side": {"type": "string", "enum": ["input", "output"], "default": "input"},
            },
            "required": ["text"],
        },
    },
    {
        "name": "cosen_cost",
        "description": "Estimate USD cost for a model and token count.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "model": {"type": "string", "description": "Model name, e.g. gpt-4o-mini or claude-sonnet-4."},
                "input_tokens": {"type": "integer"},
                "output_tokens": {"type": "integer"},
                "calls": {"type": "integer", "default": 1},
            },
            "required": ["model", "input_tokens", "output_tokens"],
        },
    },
    {
        "name": "cosen_report",
        "description": "Get the local Cosen cost / observability / security report for the last N hours.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "hours": {"type": "integer", "default": 24},
            },
        },
    },
    {
        "name": "cosen_gateway_chat",
        "description": "Send a chat completion through the local Cosen gateway (requires cosen serve running).",
        "inputSchema": {
            "type": "object",
            "properties": {
                "model": {"type": "string", "default": "cos-mock"},
                "messages": {
                    "type": "array",
                    "items": {"type": "object"},
                    "description": "OpenAI-style messages list.",
                },
                "feature": {"type": "string", "default": "cursor"},
                "project": {"type": "string", "default": "cursor-editor"},
                "provider": {"type": "string", "description": "Optional provider name from the Cosen provider catalog."},
                "base_url": {"type": "string", "default": "http://127.0.0.1:8080"},
            },
            "required": ["messages"],
        },
    },
]


def _error_response(request_id: Any, code: int, message: str) -> dict[str, Any]:
    return {
        "jsonrpc": "2.0",
        "id": request_id,
        "error": {"code": code, "message": message},
    }


def _result_response(request_id: Any, result: Any) -> dict[str, Any]:
    return {"jsonrpc": "2.0", "id": request_id, "result": result}


def _handle_scan(args: dict[str, Any]) -> dict[str, Any]:
    text = str(args.get("text") or "")
    side = str(args.get("side") or "input")
    findings = security.scan_text(text, side=side)
    if not findings:
        return {"content": [{"type": "text", "text": "clean - no security findings."}], "isError": False}
    lines = [f"{f.severity:<9} {f.scanner:<18} {f.message} :: {preview(f.excerpt, 60)}" for f in findings]
    return {"content": [{"type": "text", "text": "\n".join(lines)}], "isError": False}


def _handle_cost(args: dict[str, Any]) -> dict[str, Any]:
    model = str(args.get("model") or "")
    inp = int(args.get("input_tokens") or 0)
    out = int(args.get("output_tokens") or 0)
    calls = int(args.get("calls") or 1)
    usd = cost.cost_usd(model, inp, out)
    rate_in, rate_out = cost.rate_for(model)
    text = (
        f"model: {model}\n"
        f"rate / 1M tokens: input ${rate_in}, output ${rate_out}\n"
        f"tokens: in {inp}, out {out}\n"
        f"cost per call: ${usd:.8f}\n"
        f"cost for {calls} call(s): ${usd * calls:.6f}"
    )
    return {"content": [{"type": "text", "text": text}], "isError": False}


def _handle_report(args: dict[str, Any]) -> dict[str, Any]:
    hours = int(args.get("hours") or 24)
    data = store.summarize(hours)
    totals = data.get("totals") or {}
    text = (
        f"Cosen report - last {hours}h\n"
        f"  calls  {totals.get('calls', 0)}\n"
        f"  cost   ${float(totals.get('cost_usd') or 0):.6f}\n"
        f"  tokens {totals.get('tokens', 0)}\n"
        f"  avg ms {int(totals.get('avg_latency_ms') or 0)}\n"
        f"  blocked {totals.get('blocked', 0)}\n"
        f"  flagged {totals.get('flagged', 0)}"
    )
    return {"content": [{"type": "text", "text": text}], "isError": False}


def _handle_gateway_chat(args: dict[str, Any]) -> dict[str, Any]:
    base_url = str(args.get("base_url") or "http://127.0.0.1:8080").rstrip("/")
    model = str(args.get("model") or "cos-mock")
    messages = args.get("messages") or []
    feature = str(args.get("feature") or "cursor")
    project = str(args.get("project") or "cursor-editor")
    provider = str(args.get("provider") or "")
    headers = {
        "Content-Type": "application/json",
        "X-COS-Feature": feature,
        "X-COS-Project": project,
    }
    if provider:
        headers["X-COS-Provider"] = provider
    body = {"model": model, "messages": messages}
    try:
        with httpx.Client(timeout=60.0) as client:
            response = client.post(f"{base_url}/v1/chat/completions", headers=headers, json=body)
        payload = response.json()
        if not response.ok:
            return {"content": [{"type": "text", "text": json.dumps(payload, indent=2)}], "isError": True}
        text = payload.get("choices", [{}])[0].get("message", {}).get("content", "")
        meta = payload.get("cos", {})
        if meta:
            text += f"\n\n[cosen] cost ${meta.get('cost_usd')} · {meta.get('latency_ms')} ms · security {meta.get('security')}"
        return {"content": [{"type": "text", "text": text}], "isError": False}
    except Exception as exc:  # noqa: BLE001
        return {"content": [{"type": "text", "text": f"gateway error: {exc}"}], "isError": True}


def _handle_tool_call(request_id: Any, params: dict[str, Any]) -> dict[str, Any]:
    name = params.get("name")
    args = params.get("arguments") or {}
    if name == "cosen_scan":
        return _result_response(request_id, _handle_scan(args))
    if name == "cosen_cost":
        return _result_response(request_id, _handle_cost(args))
    if name == "cosen_report":
        return _result_response(request_id, _handle_report(args))
    if name == "cosen_gateway_chat":
        return _result_response(request_id, _handle_gateway_chat(args))
    return _error_response(request_id, -32601, f"unknown tool: {name}")


def handle_request(request: dict[str, Any]) -> dict[str, Any] | None:
    method = request.get("method")
    request_id = request.get("id")
    if method == "initialize":
        return _result_response(
            request_id,
            {
                "protocolVersion": "2024-11-05",
                "capabilities": {"tools": {}},
                "serverInfo": {"name": "cosen", "version": __version__},
            },
        )
    if method == "initialized":
        return None
    if method == "tools/list":
        return _result_response(request_id, {"tools": TOOLS})
    if method == "tools/call":
        params = request.get("params") or {}
        return _handle_tool_call(request_id, params)
    if method in ("prompts/list", "resources/list"):
        return _result_response(request_id, {"prompts": [], "resources": []})
    return _error_response(request_id, -32601, f"method not found: {method}")


def main() -> int:
    try:
        for line in sys.stdin:
            line = line.strip()
            if not line:
                continue
            try:
                request = json.loads(line)
            except json.JSONDecodeError as exc:
                print(json.dumps(_error_response(None, -32700, f"parse error: {exc}")), flush=True)
                continue
            response = handle_request(request)
            if response is not None:
                print(json.dumps(response), flush=True)
    except KeyboardInterrupt:
        return 0
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
