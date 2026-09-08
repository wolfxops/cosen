"""LangChain ChatOpenAI routed through Cosen."""

from langchain_openai import ChatOpenAI

llm = ChatOpenAI(
    base_url="http://127.0.0.1:8080/v1",
    api_key="not-needed-in-mock",
    model="gpt-4o-mini",
    default_headers={"X-COS-Feature": "langchain-agent", "X-COS-Project": "acme"},
)
print(llm.invoke("Summarize the refund policy").content)
