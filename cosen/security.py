from __future__ import annotations

import re
from dataclasses import asdict, dataclass
from typing import Any, Iterable

# Defensive detectors only. Patterns catch common leakage / injection shapes
# seen in production AI products. They are not an exploit cookbook.


@dataclass
class Finding:
    scanner: str
    severity: str  # critical | high | medium | low
    message: str
    excerpt: str = ""


_SECRET_PATTERNS = [
    ("aws_key", re.compile(r"AKIA[0-9A-Z]{16}")),
    ("google_api_key", re.compile(r"AIza[0-9A-Za-z\-_]{20,}")),
    ("slack_token", re.compile(r"xox[baprs]-[0-9A-Za-z-]{10,}")),
    ("private_key", re.compile(r"-----BEGIN (?:RSA |OPENSSH |EC )?PRIVATE KEY-----")),
    ("generic_bearer", re.compile(r"(?i)\b(?:sk|rk|key|token)[-_]?(?:live|test|prod)?[-_]?[A-Za-z0-9]{20,}\b")),
    ("openai_key", re.compile(r"\bsk-[A-Za-z0-9]{20,}\b")),
    ("github_pat", re.compile(r"\bgh[pousr]_[A-Za-z0-9]{20,}\b")),
]

_PII_PATTERNS = [
    ("email", re.compile(r"\b[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}\b", re.I)),
    ("phone", re.compile(r"\b(?:\+?\d{1,3}[-. ]?)?(?:\(?\d{3}\)?[-. ]?)\d{3}[-. ]?\d{4}\b")),
    ("card", re.compile(r"\b(?:\d[ -]*?){13,19}\b")),
]

_INJECTION_PATTERNS = [
    re.compile(r"(?i)\bignore (?:all )?(?:previous|prior|above) instructions\b"),
    re.compile(r"(?i)\bdisregard (?:your )?(?:system )?prompt\b"),
    re.compile(r"(?i)\byou are now (?:in )?(?:dan|developer mode|jailbreak)\b"),
    re.compile(r"(?i)\boverride (?:your )?(?:safety|content) (?:policy|rules|guidelines)\b"),
    re.compile(r"(?i)\bnew system prompt\s*[:=]"),
    re.compile(r"(?i)\breveal (?:the )?(?:hidden )?system (?:prompt|instructions)\b"),
]

_JAILBREAK_PATTERNS = [
    re.compile(r"(?i)\bdo anything now\b"),
    re.compile(r"(?i)\bjailbreak\b"),
    re.compile(r"(?i)\bwithout (?:any )?(?:ethical|safety|legal) (?:constraints|limits|restrictions)\b"),
    re.compile(r"(?i)\bpretend (?:you )?(?:have no|are unrestricted)\b"),
]

_LEAK_PATTERNS = [
    re.compile(r"(?i)\bhere (?:is|are) (?:my|the) system (?:prompt|instructions)\b"),
    re.compile(r"(?i)\bmy secret (?:is|key|password)\b"),
    re.compile(r"(?i)\bas an ai language model, my (?:hidden|internal) instructions\b"),
]


def _excerpt(text: str, match: re.Match[str], width: int = 40) -> str:
    start = max(0, match.start() - 8)
    end = min(len(text), match.end() + width)
    snippet = text[start:end].replace("\n", " ")
    return snippet[:80]


def _luhn_ok(number: str) -> bool:
    digits = [int(ch) for ch in number if ch.isdigit()]
    if len(digits) < 13 or len(digits) > 19:
        return False
    checksum = 0
    flip = False
    for digit in reversed(digits):
        if flip:
            digit *= 2
            if digit > 9:
                digit -= 9
        checksum += digit
        flip = not flip
    return checksum % 10 == 0


def scan_text(text: str, *, scanners: dict[str, bool] | None = None, side: str = "input") -> list[Finding]:
    if not text:
        return []
    enabled = scanners or {}
    findings: list[Finding] = []

    def on(name: str) -> bool:
        return enabled.get(name, True)

    if on("secrets"):
        for label, pattern in _SECRET_PATTERNS:
            for match in pattern.finditer(text):
                findings.append(
                    Finding(
                        scanner="secrets",
                        severity="critical",
                        message=f"Possible {label} detected on {side}",
                        excerpt=_excerpt(text, match),
                    )
                )

    if on("pii"):
        for label, pattern in _PII_PATTERNS:
            for match in pattern.finditer(text):
                if label == "card" and not _luhn_ok(match.group(0)):
                    continue
                if label == "phone" and len(re.sub(r"\D", "", match.group(0))) < 10:
                    continue
                findings.append(
                    Finding(
                        scanner="pii",
                        severity="medium",
                        message=f"Possible {label} on {side}",
                        excerpt=_excerpt(text, match),
                    )
                )

    if side == "input" and on("prompt_injection"):
        for pattern in _INJECTION_PATTERNS:
            match = pattern.search(text)
            if match:
                findings.append(
                    Finding(
                        scanner="prompt_injection",
                        severity="high",
                        message="Prompt-injection phrasing on input",
                        excerpt=_excerpt(text, match),
                    )
                )

    if side == "input" and on("jailbreak"):
        for pattern in _JAILBREAK_PATTERNS:
            match = pattern.search(text)
            if match:
                findings.append(
                    Finding(
                        scanner="jailbreak",
                        severity="high",
                        message="Jailbreak phrasing on input",
                        excerpt=_excerpt(text, match),
                    )
                )

    if side == "output" and on("system_leak"):
        for pattern in _LEAK_PATTERNS:
            match = pattern.search(text)
            if match:
                findings.append(
                    Finding(
                        scanner="system_leak",
                        severity="high",
                        message="Possible system-prompt leak on output",
                        excerpt=_excerpt(text, match),
                    )
                )

    return findings


def scan_messages(messages: Iterable[dict[str, Any]], scanners: dict[str, bool] | None = None) -> list[Finding]:
    blobs: list[str] = []
    for message in messages:
        content = message.get("content")
        if isinstance(content, str):
            blobs.append(content)
        elif isinstance(content, list):
            for part in content:
                if isinstance(part, dict) and isinstance(part.get("text"), str):
                    blobs.append(part["text"])
    return scan_text("\n".join(blobs), scanners=scanners, side="input")


def verdict(findings: list[Finding], policy: dict[str, Any], *, side: str) -> str:
    security = policy.get("security") or {}
    if not security.get("enabled", True):
        return "allow"
    block_severities = set(security.get("block_severities") or ["critical", "high"])
    actionable = [f for f in findings if f.severity in block_severities]
    if not actionable:
        return "allow"
    mode_key = "on_input_match" if side == "input" else "on_output_match"
    mode = security.get(mode_key, "block")
    if mode == "observe":
        return "observe"
    return mode  # block | redact


def redact(text: str) -> str:
    redacted = text
    for _, pattern in _SECRET_PATTERNS:
        redacted = pattern.sub("[REDACTED_SECRET]", redacted)
    email = re.compile(r"\b[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}\b", re.I)
    redacted = email.sub("[REDACTED_EMAIL]", redacted)
    return redacted


def findings_as_dict(findings: list[Finding]) -> list[dict[str, Any]]:
    return [asdict(f) for f in findings]
