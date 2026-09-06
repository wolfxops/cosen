from __future__ import annotations

from typing import Any


def messages_text(messages: list[dict[str, Any]] | None) -> str:
    parts: list[str] = []
    for message in messages or []:
        content = message.get("content")
        role = message.get("role", "")
        if isinstance(content, str):
            parts.append(f"{role}: {content}")
        elif isinstance(content, list):
            texts = [p.get("text", "") for p in content if isinstance(p, dict)]
            parts.append(f"{role}: {' '.join(texts)}")
    return "\n".join(parts)


def completion_text(payload: dict[str, Any] | None) -> str:
    if not payload:
        return ""
    choices = payload.get("choices") or []
    chunks: list[str] = []
    for choice in choices:
        message = choice.get("message") or {}
        content = message.get("content")
        if isinstance(content, str):
            chunks.append(content)
        text = choice.get("text")
        if isinstance(text, str):
            chunks.append(text)
    return "\n".join(chunks)


def preview(text: str, limit: int = 400) -> str:
    text = text.replace("\n", " ").strip()
    if len(text) <= limit:
        return text
    return text[: limit - 1] + "…"
