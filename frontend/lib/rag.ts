import { getSql, getTenantId, vectorLiteral } from "@/lib/db";

export type ChunkRow = {
  id: string;
  content: string;
  metadata: Record<string, unknown>;
  score: number;
};

export type ChatTurn = {
  role: "user" | "assistant" | "system";
  content: string;
};

export function buildRetrievalQuery(latestUserMessage: string, recent: ChatTurn[]) {
  const history = [...recent]
    .reverse()
    .map((turn) => `${turn.role}: ${turn.content}`)
    .join("\n");
  return `Conversation:\n${history}\n\nLatest question:\n${latestUserMessage}`;
}

export async function fetchRecentMessages(sessionId: string, limit = 6): Promise<ChatTurn[]> {
  const sql = getSql();
  const rows = await sql<{ role: ChatTurn["role"]; content: string }[]>`
    SELECT role, content
    FROM chat_messages
    WHERE session_id = ${sessionId}::uuid
    ORDER BY created_at DESC
    LIMIT ${limit}
  `;
  return rows.reverse();
}

export async function retrieveHybrid(params: {
  tenantId: string;
  keywordQuery: string;
  embedding: number[];
  limit?: number;
}): Promise<ChunkRow[]> {
  const sql = getSql();
  const rows = await sql<ChunkRow[]>`
    SELECT id::text, content, metadata, score
    FROM retrieve_hybrid(
      ${params.tenantId}::uuid,
      ${params.keywordQuery},
      ${vectorLiteral(params.embedding)}::vector,
      ${params.limit ?? 8},
      60
    )
  `;
  return rows;
}

export async function insertMessage(params: {
  sessionId: string;
  role: ChatTurn["role"];
  content: string;
  metadata?: Record<string, unknown>;
}) {
  const sql = getSql();
  await sql`
    INSERT INTO chat_messages (session_id, role, content, metadata)
    VALUES (
      ${params.sessionId}::uuid,
      ${params.role},
      ${params.content},
      ${JSON.stringify(params.metadata ?? {})}::jsonb
    )
  `;
  await sql`
    UPDATE chat_sessions SET updated_at = now()
    WHERE id = ${params.sessionId}::uuid
  `;
}

export async function assertSessionTenant(sessionId: string, tenantId: string) {
  const sql = getSql();
  const rows = await sql<{ tenant_id: string }[]>`
    SELECT tenant_id::text
    FROM chat_sessions
    WHERE id = ${sessionId}::uuid
    LIMIT 1
  `;
  if (!rows.length) {
    throw new Error("Chat session not found");
  }
  if (rows[0].tenant_id !== tenantId) {
    throw new Error("Session tenant mismatch");
  }
}

export async function createSession(userId = "demo-user") {
  const sql = getSql();
  const tenantId = getTenantId();
  const rows = await sql<{ id: string }[]>`
    INSERT INTO chat_sessions (tenant_id, user_id)
    VALUES (${tenantId}::uuid, ${userId})
    RETURNING id::text
  `;
  return { sessionId: rows[0].id, tenantId };
}

export function formatChunksAsContext(chunks: ChunkRow[], maxChars = 12000) {
  const parts: string[] = [];
  let used = 0;
  for (const chunk of chunks) {
    const title = String(chunk.metadata?.title ?? "Neon docs");
    const source = String(chunk.metadata?.source_id ?? chunk.metadata?.url ?? "unknown");
    const block = `[${title} | ${source}]\n${chunk.content}\n`;
    if (used + block.length > maxChars) break;
    parts.push(block);
    used += block.length;
  }
  if (!parts.length) return "No relevant documentation chunks were retrieved.";
  return `Use the following Neon documentation excerpts to answer:\n\n${parts.join("\n---\n")}`;
}
