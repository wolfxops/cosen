"""Render and optionally write integration snippets for CLIs and SDKs."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from .catalog import INTEGRATIONS, get_integration


def render_integration(key: str) -> str:
    meta = get_integration(key)
    if not meta:
        known = ", ".join(sorted(INTEGRATIONS))
        raise KeyError(f"unknown integration {key!r}; choose one of: {known}")
    lines = [
        f"# {meta['name']}",
        f"# category: {meta['category']}",
        f"# pillars: {', '.join(meta.get('pillars') or [])}",
        f"# {meta.get('summary') or ''}",
        "",
    ]
    env = meta.get("env") or {}
    if env:
        lines.append("# Environment")
        for name, value in env.items():
            lines.append(f"export {name}={value}")
        lines.append("")
    lines.append(str(meta.get("snippet") or "").rstrip())
    lines.append("")
    write = meta.get("write")
    if write and write.get("note"):
        lines.append(f"# note: {write['note']}")
        lines.append("")
    return "\n".join(lines)


def apply_integration(key: str, *, root: Path | None = None, force: bool = False) -> dict[str, Any]:
    """Write example config/snippet files when the integration defines a write target."""
    meta = get_integration(key)
    if not meta:
        raise KeyError(key)
    write = meta.get("write")
    if not write:
        return {
            "id": key,
            "wrote": False,
            "path": None,
            "message": "No file write target — print with: cosen integrate show " + key,
            "snippet": render_integration(key),
        }
    base = root or Path.cwd()
    rel = Path(str(write["path"]))
    dest = base / rel
    if dest.exists() and not force:
        return {
            "id": key,
            "wrote": False,
            "path": str(dest),
            "message": f"already exists: {dest} (pass --force to overwrite)",
            "snippet": render_integration(key),
        }
    dest.parent.mkdir(parents=True, exist_ok=True)
    content = write.get("content")
    if content is None:
        content = str(meta.get("snippet") or "")
        if not content.endswith("\n"):
            content += "\n"
    dest.write_text(content if content.endswith("\n") else content + "\n")
    return {
        "id": key,
        "wrote": True,
        "path": str(dest),
        "message": f"wrote {dest}",
        "snippet": render_integration(key),
    }
