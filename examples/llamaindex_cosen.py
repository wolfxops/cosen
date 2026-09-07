"""LlamaIndex OpenAI-compatible LLM via Cosen."""

from llama_index.llms.openai_like import OpenAILike

llm = OpenAILike(
    model="gpt-4o-mini",
    api_base="http://127.0.0.1:8080/v1",
    api_key="not-needed-in-mock",
    is_chat_model=True,
)
print(llm.complete("What is the refund window?"))
