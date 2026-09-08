"""OpenAI Python SDK pointed at the local Cosen gateway."""

from openai import OpenAI

client = OpenAI(
    base_url="http://127.0.0.1:8080/v1",
    api_key="not-needed-in-mock",
)
client.chat.completions.create(
    model="gpt-4o-mini",
    messages=[{"role": "user", "content": "hello"}],
    extra_headers={"X-COS-Feature": "my-feature", "X-COS-Project": "acme"},
)
