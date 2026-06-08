"use client";

import { useChat } from "ai/react";
import { FormEvent } from "react";

type ChatPanelProps = {
  sessionId: string;
};

export function ChatPanel({ sessionId }: ChatPanelProps) {
  const { messages, input, handleInputChange, handleSubmit, isLoading } = useChat({
    api: "/api/chat",
    body: { sessionId },
  });

  function onSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!input.trim()) return;
    handleSubmit(event);
  }

  return (
    <>
      <section
        style={{
          border: "1px solid #ddd",
          borderRadius: 12,
          padding: "1rem",
          minHeight: 420,
          background: "#fafafa",
          marginBottom: "1rem",
        }}
      >
        {messages.length === 0 && (
          <p style={{ color: "#666" }}>
            Ask about Neon Postgres, pgvector, branching, or Cursor MCP integration.
          </p>
        )}
        {messages.map((message) => (
          <article key={message.id} style={{ marginBottom: "1rem" }}>
            <strong>{message.role === "user" ? "You" : "Assistant"}</strong>
            <p style={{ whiteSpace: "pre-wrap", margin: "0.35rem 0 0" }}>{message.content}</p>
          </article>
        ))}
      </section>

      <form onSubmit={onSubmit} style={{ display: "flex", gap: "0.75rem" }}>
        <input
          value={input}
          onChange={handleInputChange}
          placeholder="Ask a question…"
          disabled={isLoading}
          style={{ flex: 1, padding: "0.75rem 1rem", borderRadius: 10, border: "1px solid #ccc" }}
        />
        <button
          type="submit"
          disabled={isLoading || !input.trim()}
          style={{ padding: "0.75rem 1rem", borderRadius: 10, border: "none", background: "#111", color: "#fff" }}
        >
          Send
        </button>
      </form>
    </>
  );
}
