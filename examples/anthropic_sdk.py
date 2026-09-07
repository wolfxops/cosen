"""Anthropic Python SDK pointed at Cosen (/v1/messages)."""

import anthropic

client = anthropic.Anthropic(
    base_url="http://127.0.0.1:8080",
    api_key="not-needed-in-mock",
)
client.messages.create(
    model="claude-sonnet-4-20250514",
    max_tokens=256,
    messages=[{"role": "user", "content": "hello"}],
)
