"use client";

import { useEffect, useState } from "react";

import { ChatPanel } from "@/components/ChatPanel";

export default function HomePage() {
  const [sessionId, setSessionId] = useState<string | null>(null);
  const [bootError, setBootError] = useState<string | null>(null);

  useEffect(() => {
    async function boot() {
      try {
        const apiUrl = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";
        const response = await fetch(`${apiUrl}/chat/sessions`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ user_id: "demo-user" }),
        });
        if (!response.ok) throw new Error("Failed to create chat session");
        const data = await response.json();
        setSessionId(data.session_id);
      } catch (error) {
        setBootError(error instanceof Error ? error.message : "Boot failed");
      }
    }
    boot();
  }, []);

  return (
    <main style={{ maxWidth: 860, margin: "0 auto", padding: "2rem 1rem", fontFamily: "Inter, system-ui, sans-serif" }}>
      <header style={{ marginBottom: "1.5rem" }}>
        <h1 style={{ margin: 0, fontSize: "1.75rem" }}>Neon Docs RAG</h1>
        <p style={{ color: "#555", marginTop: "0.5rem" }}>
          Hybrid pgvector + tsvector retrieval with RRF (k=60), tenant-scoped, session-aware context.
        </p>
      </header>

      {bootError && <p style={{ color: "#b00020" }}>{bootError}</p>}
      {sessionId ? <ChatPanel sessionId={sessionId} /> : <p style={{ color: "#666" }}>Starting session…</p>}
    </main>
  );
}
