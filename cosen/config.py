from __future__ import annotations

import os
import re
from copy import deepcopy
from pathlib import Path
from typing import Any

import yaml

_ENV_PATTERN = re.compile(r"\$\{([A-Z0-9_]+)(?::-([^}]*))?\}")


def _expand_env(value: Any) -> Any:
    if isinstance(value, str):
        def repl(match: re.Match[str]) -> str:
            name, default = match.group(1), match.group(2)
            found = os.environ.get(name)
            if found is not None:
                return found
            return default or ""

        return _ENV_PATTERN.sub(repl, value)
    if isinstance(value, dict):
        return {k: _expand_env(v) for k, v in value.items()}
    if isinstance(value, list):
        return [_expand_env(v) for v in value]
    return value


def default_policy_path() -> Path:
    return Path(__file__).resolve().parent / "policies" / "default.yaml"


def load_policy(path: str | Path | None = None) -> dict[str, Any]:
    candidates: list[Path] = []
    if path:
        candidates.append(Path(path))
    candidates.extend(
        [
            Path.cwd() / "cosen.yaml",
            Path.cwd() / "cosai.yaml",  # migration path from older name
            Path.cwd() / "cos.yaml",
            default_policy_path(),
        ]
    )
    raw: dict[str, Any] | None = None
    for candidate in candidates:
        if candidate.exists():
            raw = yaml.safe_load(candidate.read_text()) or {}
            break
    if raw is None:
        raw = yaml.safe_load(default_policy_path().read_text()) or {}
    return _expand_env(deepcopy(raw))


def data_dir() -> Path:
    override = os.environ.get("COSEN_HOME") or os.environ.get("COS_HOME")
    if override:
        path = Path(override)
    else:
        path = Path.cwd() / ".cosen"
    path.mkdir(parents=True, exist_ok=True)
    return path


def db_path() -> Path:
    return data_dir() / "cosen.db"
