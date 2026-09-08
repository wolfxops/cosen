import OpenAI from "openai";

const client = new OpenAI({
  baseURL: "http://127.0.0.1:8080/v1",
  apiKey: "not-needed-in-mock",
});

await client.chat.completions.create({
  model: "gpt-4o-mini",
  messages: [{ role: "user", content: "hello" }],
}, {
  headers: { "X-COS-Feature": "my-feature", "X-COS-Project": "acme" },
});
