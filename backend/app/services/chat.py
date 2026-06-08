import json
from uuid import UUID

from app.db import get_conn


async def create_session(*, tenant_id: UUID, user_id: str) -> UUID:
    async with get_conn() as conn:
        row = await (
            await conn.execute(
                """
                INSERT INTO chat_sessions (tenant_id, user_id)
                VALUES (%s, %s)
                RETURNING id
                """,
                (tenant_id, user_id),
            )
        ).fetchone()
        await conn.commit()
        return row["id"]


async def insert_message(
    *,
    session_id: UUID,
    role: str,
    content: str,
    metadata: dict | None = None,
) -> UUID:
    async with get_conn() as conn:
        row = await (
            await conn.execute(
                """
                INSERT INTO chat_messages (session_id, role, content, metadata)
                VALUES (%s, %s, %s, %s::jsonb)
                RETURNING id
                """,
                (session_id, role, content, json.dumps(metadata or {})),
            )
        ).fetchone()
        await conn.execute(
            "UPDATE chat_sessions SET updated_at = now() WHERE id = %s",
            (session_id,),
        )
        await conn.commit()
        return row["id"]
