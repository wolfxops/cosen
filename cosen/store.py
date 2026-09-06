from __future__ import annotations

import json
import sqlite3
from contextlib import contextmanager
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Iterator

from .config import db_path

SCHEMA = """
CREATE TABLE IF NOT EXISTS traces (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  ts TEXT NOT NULL,
  project TEXT,
  feature TEXT,
  user_id TEXT,
  session_id TEXT,
  model TEXT,
  provider TEXT,
  status TEXT,
  latency_ms INTEGER,
  prompt_tokens INTEGER,
  completion_tokens INTEGER,
  total_tokens INTEGER,
  cost_usd REAL,
  security_verdict TEXT,
  security_findings TEXT,
  error TEXT,
  request_preview TEXT,
  response_preview TEXT,
  raw_json TEXT
);

CREATE INDEX IF NOT EXISTS idx_traces_ts ON traces(ts);
CREATE INDEX IF NOT EXISTS idx_traces_feature ON traces(feature);
CREATE INDEX IF NOT EXISTS idx_traces_model ON traces(model);

CREATE TABLE IF NOT EXISTS events (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  ts TEXT NOT NULL,
  kind TEXT NOT NULL,
  severity TEXT,
  message TEXT,
  trace_id INTEGER
);

CREATE TABLE IF NOT EXISTS providers (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  name TEXT NOT NULL UNIQUE,
  base_url TEXT NOT NULL,
  api_key_env TEXT,
  model_hint TEXT,
  kind TEXT NOT NULL DEFAULT 'openai_compat',
  enabled INTEGER NOT NULL DEFAULT 1
);
"""


def utcnow() -> str:
    return datetime.now(timezone.utc).isoformat()


@contextmanager
def connect(path: Path | None = None) -> Iterator[sqlite3.Connection]:
    db = path or db_path()
    conn = sqlite3.connect(db)
    conn.row_factory = sqlite3.Row
    try:
        conn.executescript(SCHEMA)
        yield conn
        conn.commit()
    finally:
        conn.close()


def insert_trace(row: dict[str, Any], path: Path | None = None) -> int:
    payload = {
        "ts": row.get("ts") or utcnow(),
        "project": row.get("project"),
        "feature": row.get("feature"),
        "user_id": row.get("user_id"),
        "session_id": row.get("session_id"),
        "model": row.get("model"),
        "provider": row.get("provider"),
        "status": row.get("status"),
        "latency_ms": row.get("latency_ms"),
        "prompt_tokens": row.get("prompt_tokens") or 0,
        "completion_tokens": row.get("completion_tokens") or 0,
        "total_tokens": row.get("total_tokens") or 0,
        "cost_usd": row.get("cost_usd") or 0.0,
        "security_verdict": row.get("security_verdict"),
        "security_findings": json.dumps(row.get("security_findings") or []),
        "error": row.get("error"),
        "request_preview": row.get("request_preview"),
        "response_preview": row.get("response_preview"),
        "raw_json": json.dumps(row.get("raw") or {}, default=str),
    }
    with connect(path) as conn:
        cur = conn.execute(
            """
            INSERT INTO traces (
              ts, project, feature, user_id, session_id, model, provider,
              status, latency_ms, prompt_tokens, completion_tokens, total_tokens,
              cost_usd, security_verdict, security_findings, error,
              request_preview, response_preview, raw_json
            ) VALUES (
              :ts, :project, :feature, :user_id, :session_id, :model, :provider,
              :status, :latency_ms, :prompt_tokens, :completion_tokens, :total_tokens,
              :cost_usd, :security_verdict, :security_findings, :error,
              :request_preview, :response_preview, :raw_json
            )
            """,
            payload,
        )
        trace_id = int(cur.lastrowid)
        for finding in row.get("security_findings") or []:
            conn.execute(
                "INSERT INTO events (ts, kind, severity, message, trace_id) VALUES (?, ?, ?, ?, ?)",
                (
                    payload["ts"],
                    finding.get("scanner", "security"),
                    finding.get("severity", "info"),
                    finding.get("message", ""),
                    trace_id,
                ),
            )
        return trace_id


def spend_since(since_iso: str, *, feature: str | None = None, project: str | None = None) -> float:
    clauses = ["ts >= ?", "status != 'blocked_budget'"]
    args: list[Any] = [since_iso]
    if feature:
        clauses.append("feature = ?")
        args.append(feature)
    if project:
        clauses.append("project = ?")
        args.append(project)
    sql = f"SELECT COALESCE(SUM(cost_usd), 0) AS total FROM traces WHERE {' AND '.join(clauses)}"
    with connect() as conn:
        row = conn.execute(sql, args).fetchone()
        return float(row["total"] if row else 0.0)


def query_traces(limit: int = 100, since_hours: int | None = 24) -> list[dict[str, Any]]:
    clauses: list[str] = []
    args: list[Any] = []
    if since_hours is not None:
        start = datetime.now(timezone.utc) - timedelta(hours=since_hours)
        clauses.append("ts >= ?")
        args.append(start.isoformat())
    where = f"WHERE {' AND '.join(clauses)}" if clauses else ""
    sql = f"SELECT * FROM traces {where} ORDER BY id DESC LIMIT ?"
    args.append(limit)
    with connect() as conn:
        rows = conn.execute(sql, args).fetchall()
        return [dict(r) for r in rows]


def summarize(since_hours: int = 24) -> dict[str, Any]:
    start = datetime.now(timezone.utc) - timedelta(hours=since_hours)
    start_iso = start.isoformat()
    with connect() as conn:
        totals = conn.execute(
            """
            SELECT
              COUNT(*) AS calls,
              COALESCE(SUM(cost_usd), 0) AS cost_usd,
              COALESCE(AVG(latency_ms), 0) AS avg_latency_ms,
              COALESCE(SUM(total_tokens), 0) AS tokens,
              SUM(CASE WHEN status LIKE 'blocked%' THEN 1 ELSE 0 END) AS blocked,
              SUM(CASE WHEN security_verdict IN ('block', 'redact') THEN 1 ELSE 0 END) AS flagged
            FROM traces
            WHERE ts >= ?
            """,
            (start_iso,),
        ).fetchone()
        by_model = conn.execute(
            """
            SELECT model,
                   COUNT(*) AS calls,
                   COALESCE(SUM(cost_usd), 0) AS cost_usd,
                   COALESCE(AVG(latency_ms), 0) AS avg_latency_ms
            FROM traces
            WHERE ts >= ?
            GROUP BY model
            ORDER BY cost_usd DESC
            """,
            (start_iso,),
        ).fetchall()
        by_feature = conn.execute(
            """
            SELECT COALESCE(feature, 'untagged') AS feature,
                   COUNT(*) AS calls,
                   COALESCE(SUM(cost_usd), 0) AS cost_usd
            FROM traces
            WHERE ts >= ?
            GROUP BY COALESCE(feature, 'untagged')
            ORDER BY cost_usd DESC
            """,
            (start_iso,),
        ).fetchall()
        findings = conn.execute(
            """
            SELECT kind, severity, COUNT(*) AS n
            FROM events
            WHERE ts >= ?
            GROUP BY kind, severity
            ORDER BY n DESC
            """,
            (start_iso,),
        ).fetchall()
        recent = conn.execute(
            "SELECT * FROM traces WHERE ts >= ? ORDER BY id DESC LIMIT 25",
            (start_iso,),
        ).fetchall()
    return {
        "since_hours": since_hours,
        "totals": dict(totals) if totals else {},
        "by_model": [dict(r) for r in by_model],
        "by_feature": [dict(r) for r in by_feature],
        "findings": [dict(r) for r in findings],
        "recent": [dict(r) for r in recent],
    }


DEFAULT_PROVIDERS = [
    {
        "name": "mock",
        "base_url": "cos://mock",
        "api_key_env": "",
        "model_hint": "cos-mock",
        "kind": "mock",
    },
    {
        "name": "openai",
        "base_url": "https://api.openai.com/v1",
        "api_key_env": "OPENAI_API_KEY",
        "model_hint": "gpt-4o-mini",
        "kind": "openai_compat",
    },
    {
        "name": "anthropic",
        "base_url": "https://api.anthropic.com/v1",
        "api_key_env": "ANTHROPIC_API_KEY",
        "model_hint": "claude-sonnet-4-20250514",
        "kind": "anthropic",
    },
    {
        "name": "groq",
        "base_url": "https://api.groq.com/openai/v1",
        "api_key_env": "GROQ_API_KEY",
        "model_hint": "llama-3.3-70b-versatile",
        "kind": "openai_compat",
    },
    {
        "name": "openrouter",
        "base_url": "https://openrouter.ai/api/v1",
        "api_key_env": "OPENROUTER_API_KEY",
        "model_hint": "openai/gpt-4o-mini",
        "kind": "openai_compat",
    },
    {
        "name": "together",
        "base_url": "https://api.together.xyz/v1",
        "api_key_env": "TOGETHER_API_KEY",
        "model_hint": "meta-llama/Llama-3.3-70B-Instruct-Turbo",
        "kind": "openai_compat",
    },
    {
        "name": "ollama",
        "base_url": "http://127.0.0.1:11434/v1",
        "api_key_env": "OLLAMA_API_KEY",
        "model_hint": "llama3.2",
        "kind": "openai_compat",
    },
    {
        "name": "vllm",
        "base_url": "http://127.0.0.1:8000/v1",
        "api_key_env": "",
        "model_hint": "local-model",
        "kind": "openai_compat",
    },
]


def seed_providers() -> None:
    with connect() as conn:
        existing = conn.execute("SELECT COUNT(*) AS n FROM providers").fetchone()
        if existing and int(existing["n"]) > 0:
            return
        for provider in DEFAULT_PROVIDERS:
            conn.execute(
                """
                INSERT OR IGNORE INTO providers (name, base_url, api_key_env, model_hint, kind, enabled)
                VALUES (:name, :base_url, :api_key_env, :model_hint, :kind, 1)
                """,
                provider,
            )


def list_providers() -> list[dict[str, Any]]:
    seed_providers()
    with connect() as conn:
        rows = conn.execute("SELECT * FROM providers ORDER BY id").fetchall()
        return [dict(r) for r in rows]


def get_provider(name: str) -> dict[str, Any] | None:
    seed_providers()
    with connect() as conn:
        row = conn.execute("SELECT * FROM providers WHERE name = ?", (name,)).fetchone()
        return dict(row) if row else None


def upsert_provider(payload: dict[str, Any]) -> dict[str, Any]:
    name = str(payload.get("name") or "").strip().lower().replace(" ", "-")
    if not name:
        raise ValueError("provider name is required")
    base_url = str(payload.get("base_url") or "").strip().rstrip("/")
    if not base_url:
        raise ValueError("base_url is required")
    record = {
        "name": name,
        "base_url": base_url,
        "api_key_env": str(payload.get("api_key_env") or ""),
        "model_hint": str(payload.get("model_hint") or ""),
        "kind": str(payload.get("kind") or "openai_compat"),
        "enabled": 1 if payload.get("enabled", True) else 0,
    }
    with connect() as conn:
        conn.execute(
            """
            INSERT INTO providers (name, base_url, api_key_env, model_hint, kind, enabled)
            VALUES (:name, :base_url, :api_key_env, :model_hint, :kind, :enabled)
            ON CONFLICT(name) DO UPDATE SET
              base_url=excluded.base_url,
              api_key_env=excluded.api_key_env,
              model_hint=excluded.model_hint,
              kind=excluded.kind,
              enabled=excluded.enabled
            """,
            record,
        )
    found = get_provider(name)
    assert found is not None
    return found


def delete_provider(name: str) -> bool:
    with connect() as conn:
        cur = conn.execute("DELETE FROM providers WHERE name = ?", (name,))
        return cur.rowcount > 0
