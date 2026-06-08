from uuid import UUID

from app.db import get_conn
from app.services.embeddings import vector_literal


def build_retrieval_query(latest_user_message: str, recent_turns: list[dict]) -> str:
    history = "\n".join(
        f"{turn['role']}: {turn['content']}"
        for turn in reversed(recent_turns)
    )
    return f"Conversation:\n{history}\n\nLatest question:\n{latest_user_message}"


async def fetch_recent_messages(session_id: UUID, *, limit: int = 6) -> list[dict]:
    async with get_conn() as conn:
        rows = await (
            await conn.execute(
                """
                SELECT role, content
                FROM chat_messages
                WHERE session_id = %s
                ORDER BY created_at DESC
                LIMIT %s
                """,
                (session_id, limit),
            )
        ).fetchall()
    return list(reversed(rows))


async def retrieve_hybrid(
    *,
    tenant_id: UUID,
    keyword_query: str,
    query_embedding: list[float],
    limit: int = 8,
) -> list[dict]:
    async with get_conn() as conn:
        rows = await (
            await conn.execute(
                """
                SELECT id, content, metadata, score
                FROM retrieve_hybrid(%s, %s, %s::vector, %s, 60)
                """,
                (tenant_id, keyword_query, vector_literal(query_embedding), limit),
            )
        ).fetchall()
    return rows


async def retrieve_vector_only(
    *,
    tenant_id: UUID,
    query_embedding: list[float],
    limit: int = 8,
) -> list[dict]:
    async with get_conn() as conn:
        rows = await (
            await conn.execute(
                """
                SELECT id, content, metadata, distance
                FROM retrieve_vector_only(%s, %s::vector, %s)
                """,
                (tenant_id, vector_literal(query_embedding), limit),
            )
        ).fetchall()
    return rows


def format_chunks_as_context(chunks: list[dict], *, max_chars: int = 12_000) -> str:
    parts: list[str] = []
    used = 0
    for chunk in chunks:
        meta = chunk.get("metadata") or {}
        title = meta.get("title", "Neon docs")
        source = meta.get("source_id", meta.get("url", "unknown"))
        block = f"[{title} | {source}]\n{chunk['content']}\n"
        if used + len(block) > max_chars:
            break
        parts.append(block)
        used += len(block)
    if not parts:
        return "No relevant documentation chunks were retrieved."
    return "Use the following Neon documentation excerpts to answer:\n\n" + "\n---\n".join(parts)
