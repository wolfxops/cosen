from __future__ import annotations

import json
import mimetypes
import os
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any
from urllib.parse import parse_qs, urlparse

import httpx

from . import cost, security, store
from .textutil import completion_text, messages_text, preview

WEB_ROOT = Path(__file__).resolve().parent / "web"
SPA_ROUTES = {
    "/",
    "/app",
    "/dashboard",
    "/cos",
    "/cos/dashboard",
    "/overview",
    "/playground",
    "/traces",
    "/security",
    "/providers",
    "/pricing",
}

MOCK_REPLY = (
    "This is the Cosen mock model. Your request was observed, costed, and scanned. "
    "Add any OpenAI-compatible or Anthropic provider in the web app to use a real model."
)


def _attr(headers: dict[str, str], name: str, body: dict[str, Any], fallback: str | None = None) -> str | None:
    header_key = f"x-cos-{name}".lower()
    alias_key = f"x-cosen-{name}".lower()
    if header_key in headers:
        return headers[header_key]
    if alias_key in headers:
        return headers[alias_key]
    meta = body.get("metadata") or {}
    if isinstance(meta, dict) and name in meta:
        return str(meta[name])
    extra = body.get("extra_headers") or {}
    if isinstance(extra, dict):
        lowered = {k.lower(): v for k, v in extra.items()}
        if header_key in lowered:
            return str(lowered.get(header_key))
        if alias_key in lowered:
            return str(lowered.get(alias_key))
    return fallback


class CosenHandler(BaseHTTPRequestHandler):
    server_version = "Cosen/0.2"
    policy: dict[str, Any] = {}
    mock: bool = False
    silent: bool = False

    def log_message(self, fmt: str, *args: Any) -> None:
        if not self.silent:
            super().log_message(fmt, *args)

    def _json(self, status: int, payload: dict[str, Any]) -> None:
        raw = json.dumps(payload).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(raw)))
        self.send_header("Cache-Control", "no-store")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
        self.wfile.write(raw)

    def do_OPTIONS(self) -> None:  # noqa: N802
        self.send_response(204)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, DELETE, OPTIONS")
        self.send_header(
            "Access-Control-Allow-Headers",
            "Content-Type, Authorization, "
            "X-COS-Feature, X-COS-Project, X-COS-User, X-COS-Session, X-COS-Provider, "
            "X-Cosen-Feature, X-Cosen-Project, X-Cosen-User, X-Cosen-Session, X-Cosen-Provider",
        )
        self.end_headers()

    def _file(self, path: Path, content_type: str | None = None) -> None:
        raw = path.read_bytes()
        ctype = content_type or mimetypes.guess_type(str(path))[0] or "application/octet-stream"
        self.send_response(200)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(raw)))
        self.end_headers()
        self.wfile.write(raw)

    def _spa(self) -> None:
        index = WEB_ROOT / "index.html"
        self._file(index, "text/html; charset=utf-8")

    def _html(self, status: int, body: str) -> None:
        raw = body.encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(raw)))
        self.end_headers()
        self.wfile.write(raw)

    def _read_json(self) -> dict[str, Any]:
        length = int(self.headers.get("Content-Length") or 0)
        if length <= 0:
            return {}
        raw = self.rfile.read(length)
        if not raw:
            return {}
        try:
            data = json.loads(raw.decode("utf-8"))
        except json.JSONDecodeError:
            return {}
        return data if isinstance(data, dict) else {}

    def _headers(self) -> dict[str, str]:
        return {k.lower(): v for k, v in self.headers.items()}

    def do_GET(self) -> None:  # noqa: N802
        parsed = urlparse(self.path)
        path = parsed.path.rstrip("/") or "/"
        qs = parse_qs(parsed.query)

        if path.startswith("/web/"):
            rel = path[len("/web/") :]
            candidate = (WEB_ROOT / rel).resolve()
            if WEB_ROOT.resolve() in candidate.parents or candidate == WEB_ROOT.resolve():
                if candidate.is_file():
                    self._file(candidate)
                    return
            self._json(404, {"error": {"message": "not found"}})
            return

        if path in SPA_ROUTES:
            self._spa()
            return
        if path in ("/health", "/cos/health", "/api/health"):
            self._json(200, {"ok": True, "service": "cosen", "mock": self.mock, "web": True})
            return
        if path in ("/v1/models", "/models", "/api/models"):
            providers = store.list_providers()
            models = [{"id": p.get("model_hint") or p["name"], "object": "model", "owned_by": p["name"]} for p in providers]
            if self.mock:
                models.insert(0, {"id": "cos-mock", "object": "model", "owned_by": "mock"})
            self._json(200, {"object": "list", "data": models})
            return
        if path in ("/cos/summary", "/summary", "/api/summary"):
            try:
                hours = int((qs.get("hours") or ["24"])[0])
            except ValueError:
                hours = 24
            self._json(200, store.summarize(hours))
            return
        if path in ("/cos/traces", "/api/traces"):
            self._json(200, {"traces": store.query_traces(limit=100)})
            return
        if path == "/api/providers":
            self._json(200, {"providers": store.list_providers()})
            return
        if path == "/api/pricing":
            self._json(200, cost.load_pricing())
            return
        if path == "/api/policy":
            self._json(200, {"policy": self.policy})
            return
        self._json(404, {"error": {"message": f"unknown path {path}", "type": "not_found"}})

    def do_POST(self) -> None:  # noqa: N802
        parsed = urlparse(self.path)
        path = parsed.path.rstrip("/") or "/"
        if path in ("/v1/chat/completions", "/chat/completions"):
            self._chat()
            return
        if path in ("/cos/scan", "/api/scan"):
            body = self._read_json()
            text = str(body.get("text") or "")
            side = str(body.get("side") or "input")
            findings = security.scan_text(text, side=side)
            self._json(200, {"findings": security.findings_as_dict(findings)})
            return
        if path == "/api/providers":
            body = self._read_json()
            try:
                saved = store.upsert_provider(body)
            except ValueError as exc:
                self._json(400, {"error": str(exc)})
                return
            self._json(200, {"provider": saved})
            return
        self._json(404, {"error": {"message": f"unknown path {path}", "type": "not_found"}})

    def do_DELETE(self) -> None:  # noqa: N802
        parsed = urlparse(self.path)
        path = parsed.path.rstrip("/") or "/"
        if path.startswith("/api/providers/"):
            name = path.split("/")[-1]
            ok = store.delete_provider(name)
            self._json(200 if ok else 404, {"deleted": ok, "name": name})
            return
        self._json(404, {"error": {"message": "unknown path", "type": "not_found"}})

    def _chat(self) -> None:
        started = time.perf_counter()
        body = self._read_json()
        headers = self._headers()
        policy = self.policy
        project = _attr(headers, "project", body, policy.get("project", "default"))
        feature = _attr(headers, "feature", body)
        user_id = _attr(headers, "user", body)
        session_id = _attr(headers, "session", body)
        model = str(body.get("model") or ("cos-mock" if self.mock else "unknown"))
        provider_name = _attr(headers, "provider", body) or body.get("provider")
        provider_row = store.get_provider(str(provider_name)) if provider_name else None
        messages = body.get("messages") if isinstance(body.get("messages"), list) else []
        req_text = messages_text(messages)
        scanners = ((policy.get("security") or {}).get("scanners")) or {}

        input_findings = security.scan_messages(messages, scanners)
        input_verdict = security.verdict(input_findings, policy, side="input")
        if input_verdict == "block":
            latency = int((time.perf_counter() - started) * 1000)
            store.insert_trace(
                {
                    "project": project,
                    "feature": feature,
                    "user_id": user_id,
                    "session_id": session_id,
                    "model": model,
                    "provider": "blocked",
                    "status": "blocked_security",
                    "latency_ms": latency,
                    "security_verdict": "block",
                    "security_findings": security.findings_as_dict(input_findings),
                    "request_preview": preview(security.redact(req_text)),
                    "response_preview": "",
                    "error": "blocked by Cosen security policy",
                }
            )
            self._json(
                403,
                {
                    "error": {
                        "message": "Cosen blocked this request (security policy).",
                        "type": "cos_security_block",
                        "findings": security.findings_as_dict(input_findings),
                    }
                },
            )
            return

        # Cheap pre-check against daily budget using a token estimate.
        est_in = cost.estimate_tokens(req_text)
        est_cost = cost.cost_usd(model, est_in, max(est_in // 3, 16))
        hit = cost.budget_hit(policy, project=project, feature=feature, extra_usd=est_cost)
        if hit:
            latency = int((time.perf_counter() - started) * 1000)
            store.insert_trace(
                {
                    "project": project,
                    "feature": feature,
                    "user_id": user_id,
                    "session_id": session_id,
                    "model": model,
                    "provider": "blocked",
                    "status": "blocked_budget",
                    "latency_ms": latency,
                    "cost_usd": 0,
                    "security_verdict": input_verdict,
                    "security_findings": security.findings_as_dict(input_findings),
                    "request_preview": preview(security.redact(req_text)),
                    "error": f"budget exceeded: {hit}",
                }
            )
            self._json(
                429,
                {
                    "error": {
                        "message": "Cosen blocked this request (daily budget).",
                        "type": "cos_budget_block",
                        "budget": hit,
                    }
                },
            )
            return

        use_mock = (
            self.mock
            or str(model).startswith("cos-")
            or (provider_row and provider_row.get("kind") == "mock")
            or (provider_row and str(provider_row.get("base_url", "")).startswith("cos://"))
        )
        if use_mock:
            upstream_payload = {
                "id": "cos-mock",
                "object": "chat.completion",
                "model": model,
                "choices": [
                    {
                        "index": 0,
                        "message": {"role": "assistant", "content": MOCK_REPLY},
                        "finish_reason": "stop",
                    }
                ],
                "usage": {
                    "prompt_tokens": est_in,
                    "completion_tokens": cost.estimate_tokens(MOCK_REPLY),
                    "total_tokens": est_in + cost.estimate_tokens(MOCK_REPLY),
                },
            }
            provider = "mock"
            status_code = 200
            err = None
        else:
            upstream_payload, status_code, err, provider = self._forward(body, headers, provider_row)

        resp_text = completion_text(upstream_payload)
        output_findings = security.scan_text(resp_text, scanners=scanners, side="output")
        output_verdict = security.verdict(output_findings, policy, side="output")
        findings = input_findings + output_findings
        combined = "block" if "block" in (input_verdict, output_verdict) else (
            "redact" if "redact" in (input_verdict, output_verdict) else input_verdict
        )

        if output_verdict == "redact" and resp_text and upstream_payload:
            redacted = security.redact(resp_text)
            try:
                upstream_payload["choices"][0]["message"]["content"] = redacted
            except (KeyError, IndexError, TypeError):
                pass
            resp_text = redacted

        if output_verdict == "block":
            latency = int((time.perf_counter() - started) * 1000)
            usage = cost.extract_usage(upstream_payload, req_text, resp_text)
            store.insert_trace(
                {
                    "project": project,
                    "feature": feature,
                    "user_id": user_id,
                    "session_id": session_id,
                    "model": model,
                    "provider": provider,
                    "status": "blocked_security_output",
                    "latency_ms": latency,
                    **usage,
                    "cost_usd": cost.cost_usd(model, usage["prompt_tokens"], usage["completion_tokens"]),
                    "security_verdict": "block",
                    "security_findings": security.findings_as_dict(findings),
                    "request_preview": preview(security.redact(req_text)),
                    "response_preview": preview(security.redact(resp_text)),
                    "error": "blocked output by Cosen security policy",
                }
            )
            self._json(
                403,
                {
                    "error": {
                        "message": "Cosen blocked the model output (security policy).",
                        "type": "cos_security_block",
                        "findings": security.findings_as_dict(output_findings),
                    }
                },
            )
            return

        usage = cost.extract_usage(upstream_payload, req_text, resp_text)
        usd = cost.cost_usd(model, usage["prompt_tokens"], usage["completion_tokens"])
        latency = int((time.perf_counter() - started) * 1000)
        status = "ok" if status_code < 400 else "upstream_error"
        store.insert_trace(
            {
                "project": project,
                "feature": feature,
                "user_id": user_id,
                "session_id": session_id,
                "model": model,
                "provider": provider,
                "status": status,
                "latency_ms": latency,
                **usage,
                "cost_usd": usd,
                "security_verdict": combined,
                "security_findings": security.findings_as_dict(findings),
                "request_preview": preview(security.redact(req_text)),
                "response_preview": preview(security.redact(resp_text)),
                "error": err,
                "raw": {"http_status": status_code},
            }
        )

        if status_code >= 400:
            self._json(status_code, upstream_payload or {"error": {"message": err or "upstream error"}})
            return
        if isinstance(upstream_payload, dict):
            upstream_payload.setdefault("cos", {})
            if isinstance(upstream_payload["cos"], dict):
                upstream_payload["cos"].update(
                    {
                        "cost_usd": round(usd, 8),
                        "latency_ms": latency,
                        "security": combined,
                        "feature": feature,
                    }
                )
        self._json(200, upstream_payload)

    def _forward(
        self,
        body: dict[str, Any],
        headers: dict[str, str],
        provider_row: dict[str, Any] | None = None,
    ) -> tuple[dict[str, Any], int, str | None, str]:
        upstream = self.policy.get("upstream") or {}
        if provider_row:
            base = str(provider_row.get("base_url") or "").rstrip("/")
            key_env = provider_row.get("api_key_env") or ""
            kind = str(provider_row.get("kind") or "openai_compat")
        else:
            base = str(upstream.get("base_url") or "https://api.openai.com/v1").rstrip("/")
            key_env = upstream.get("api_key_env") or "OPENAI_API_KEY"
            kind = "openai_compat"

        api_key = os.environ.get(str(key_env), "") if key_env else ""
        incoming_auth = headers.get("authorization")
        auth = incoming_auth or (f"Bearer {api_key}" if api_key else "")
        provider = urlparse(base).hostname or "upstream"

        if kind == "anthropic":
            return self._forward_anthropic(body, base, api_key, provider)

        url = f"{base}/chat/completions"
        fwd_headers = {"Content-Type": "application/json"}
        if auth:
            fwd_headers["Authorization"] = auth
        try:
            with httpx.Client(timeout=60.0) as client:
                response = client.post(url, headers=fwd_headers, json=body)
            try:
                payload = response.json()
            except json.JSONDecodeError:
                payload = {"error": {"message": response.text[:500]}}
            if not isinstance(payload, dict):
                payload = {"error": {"message": "unexpected upstream payload"}}
            err = None if response.status_code < 400 else str(payload.get("error") or response.text[:200])
            return payload, response.status_code, err, provider
        except httpx.HTTPError as exc:
            return {"error": {"message": str(exc), "type": "upstream_connection"}}, 502, str(exc), provider

    def _forward_anthropic(
        self,
        body: dict[str, Any],
        base: str,
        api_key: str,
        provider: str,
    ) -> tuple[dict[str, Any], int, str | None, str]:
        """Forward to Anthropic Messages API while keeping the OpenAI-shaped response."""
        model = str(body.get("model") or "claude-sonnet-4-20250514")
        max_tokens = body.get("max_tokens") or 1024
        temperature = body.get("temperature")
        messages = body.get("messages") if isinstance(body.get("messages"), list) else []

        system_parts: list[str] = []
        anthropic_messages: list[dict[str, Any]] = []
        for message in messages:
            role = str(message.get("role") or "user")
            content = message.get("content")
            text = ""
            if isinstance(content, str):
                text = content
            elif isinstance(content, list):
                text = " ".join(str(p.get("text", "")) for p in content if isinstance(p, dict))
            if role == "system":
                system_parts.append(text)
            elif role in ("user", "assistant"):
                anthropic_messages.append({"role": role, "content": text})
            else:
                anthropic_messages.append({"role": "user", "content": text})

        anthropic_body: dict[str, Any] = {
            "model": model,
            "max_tokens": int(max_tokens),
            "messages": anthropic_messages,
        }
        if system_parts:
            anthropic_body["system"] = "\n".join(system_parts)
        if temperature is not None:
            anthropic_body["temperature"] = float(temperature)

        fwd_headers = {
            "Content-Type": "application/json",
            "anthropic-version": "2023-06-01",
        }
        if api_key:
            fwd_headers["x-api-key"] = api_key
        if not api_key and os.environ.get("ANTHROPIC_API_KEY"):
            fwd_headers["x-api-key"] = os.environ["ANTHROPIC_API_KEY"]

        url = f"{base}/messages"
        try:
            with httpx.Client(timeout=60.0) as client:
                response = client.post(url, headers=fwd_headers, json=anthropic_body)
            try:
                anthropic_payload = response.json()
            except json.JSONDecodeError:
                anthropic_payload = {"error": {"message": response.text[:500]}}
            if not isinstance(anthropic_payload, dict):
                anthropic_payload = {"error": {"message": "unexpected upstream payload"}}
            if response.status_code >= 400:
                err = str(anthropic_payload.get("error") or response.text[:200])
                return anthropic_payload, response.status_code, err, provider

            content_blocks = anthropic_payload.get("content") or []
            text_parts = [str(b.get("text", "")) for b in content_blocks if isinstance(b, dict) and b.get("type") == "text"]
            content = "\n".join(text_parts)
            usage = anthropic_payload.get("usage") or {}
            prompt_tokens = usage.get("input_tokens") or cost.estimate_tokens(messages_text(messages))
            completion_tokens = usage.get("output_tokens") or cost.estimate_tokens(content)
            openai_payload = {
                "id": anthropic_payload.get("id", "anthropic-"),
                "object": "chat.completion",
                "model": model,
                "choices": [
                    {
                        "index": 0,
                        "message": {"role": "assistant", "content": content},
                        "finish_reason": anthropic_payload.get("stop_reason") or "stop",
                    }
                ],
                "usage": {
                    "prompt_tokens": prompt_tokens,
                    "completion_tokens": completion_tokens,
                    "total_tokens": prompt_tokens + completion_tokens,
                },
            }
            return openai_payload, response.status_code, None, provider
        except httpx.HTTPError as exc:
            return {"error": {"message": str(exc), "type": "upstream_connection"}}, 502, str(exc), provider


def serve(host: str, port: int, policy: dict[str, Any], *, mock: bool = False, silent: bool = False) -> ThreadingHTTPServer:
    CosenHandler.policy = policy
    CosenHandler.mock = mock
    CosenHandler.silent = silent
    httpd = ThreadingHTTPServer((host, port), CosenHandler)
    return httpd
