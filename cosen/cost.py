from __future__ import annotations

from datetime import datetime, timezone
from functools import lru_cache
from pathlib import Path
from typing import Any

import yaml

from . import store


def _pricing_path() -> Path:
    return Path(__file__).resolve().parent / "data" / "pricing.yaml"


@lru_cache(maxsize=1)
def load_pricing() -> dict[str, Any]:
    return yaml.safe_load(_pricing_path().read_text()) or {}


def estimate_tokens(text: str) -> int:
    """Rough token estimate when the provider omits usage (≈ 4 chars / token)."""
    if not text:
        return 0
    return max(1, (len(text) + 3) // 4)


def _normalize_model(name: str | None) -> str:
    if not name:
        return ""
    return name.strip().lower()


def rate_for(model: str | None) -> tuple[float, float]:
    pricing = load_pricing()
    models: dict[str, Any] = pricing.get("models") or {}
    key = _normalize_model(model)
    entry = models.get(key)
    if entry is None:
        for name, data in models.items():
            if key.endswith(name) or name in key:
                entry = data
                break
    if entry is None:
        entry = pricing.get("default") or {"input": 0.5, "output": 1.5}
    return float(entry.get("input", 0.0)), float(entry.get("output", 0.0))


def cost_usd(model: str | None, prompt_tokens: int, completion_tokens: int) -> float:
    inp, out = rate_for(model)
    return (prompt_tokens / 1_000_000.0) * inp + (completion_tokens / 1_000_000.0) * out


def extract_usage(payload: dict[str, Any] | None, request_text: str, response_text: str) -> dict[str, int]:
    usage = (payload or {}).get("usage") or {}
    prompt = usage.get("prompt_tokens") or usage.get("input_tokens")
    completion = usage.get("completion_tokens") or usage.get("output_tokens")
    total = usage.get("total_tokens")
    if prompt is None:
        prompt = estimate_tokens(request_text)
    if completion is None:
        completion = estimate_tokens(response_text)
    prompt = int(prompt)
    completion = int(completion)
    if total is None:
        total = prompt + completion
    return {
        "prompt_tokens": prompt,
        "completion_tokens": completion,
        "total_tokens": int(total),
    }


def start_of_utc_day() -> str:
    now = datetime.now(timezone.utc)
    return now.replace(hour=0, minute=0, second=0, microsecond=0).isoformat()


def budget_hit(policy: dict[str, Any], *, project: str | None, feature: str | None, extra_usd: float) -> dict[str, Any] | None:
    cost_cfg = policy.get("cost") or {}
    if not cost_cfg.get("enabled", True) or not cost_cfg.get("enforce_budgets", True):
        return None
    since = start_of_utc_day()
    for budget in cost_cfg.get("budgets") or []:
        scope = budget.get("scope", "project")
        name = budget.get("name")
        cap = float(budget.get("daily_usd") or 0)
        if cap <= 0:
            continue
        if scope == "feature":
            if not feature or feature != name:
                continue
            spent = store.spend_since(since, feature=feature)
        else:
            if name and project and name not in ("*", project) and project != name:
                continue
            spent = store.spend_since(since, project=project)
        if spent + extra_usd > cap:
            return {
                "scope": scope,
                "name": name,
                "daily_usd": cap,
                "spent_usd": round(spent, 6),
                "attempt_usd": round(extra_usd, 6),
            }
    return None
