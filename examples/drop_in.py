"""Drop-in pattern: keep the OpenAI client, change the base URL to Cosen."""

from openai import OpenAI

client = OpenAI(
    base_url="http://127.0.0.1:8080/v1",
    api_key="sk-not-needed-for-mock",
)

response = client.chat.completions.create(
    model="gpt-4o-mini",
    messages=[{"role": "user", "content": "Summarize our refund policy in one sentence."}],
    extra_headers={
        "X-COS-Project": "shop",
        "X-COS-Feature": "support-bot",
        "X-COS-User": "user_42",
        # X-Cosen-* aliases are also accepted.
    },
)
print(response.choices[0].message.content)
print(getattr(response, "cos", None) or response.model_extra)
