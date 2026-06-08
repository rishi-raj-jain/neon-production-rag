import hashlib
import json
from uuid import UUID

from app.db import get_conn
from app.services.embeddings import embed_many, vector_literal


def content_hash(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


async def upsert_document(*, source_id: str, title: str) -> UUID:
    async with get_conn() as conn:
        row = await (
            await conn.execute(
                """
                INSERT INTO rag_documents (source_id, title)
                VALUES (%s, %s)
                ON CONFLICT (source_id) DO UPDATE
                  SET title = EXCLUDED.title
                RETURNING id
                """,
                (source_id, title),
            )
        ).fetchone()
        await conn.commit()
        return row["id"]


async def ingest_chunks(
    *,
    tenant_id: UUID,
    document_id: UUID,
    chunks: list[dict],
) -> dict[str, int]:
    if not chunks:
        return {"inserted_or_updated": 0, "skipped_unchanged": 0, "embedded": 0}

    chunk_hashes = {chunk["index"]: content_hash(chunk["content"]) for chunk in chunks}

    async with get_conn() as conn:
        existing_rows = await (
            await conn.execute(
                """
                SELECT chunk_index, content_hash
                FROM rag_chunks
                WHERE document_id = %s
                """,
                (document_id,),
            )
        ).fetchall()
        existing = {row["chunk_index"]: row["content_hash"] for row in existing_rows}

        changed_chunks = [
            chunk for chunk in chunks if existing.get(chunk["index"]) != chunk_hashes[chunk["index"]]
        ]
        embeddings = await embed_many([chunk["content"] for chunk in changed_chunks])
        embedding_by_index = {
            chunk["index"]: vector_literal(vector)
            for chunk, vector in zip(changed_chunks, embeddings, strict=True)
        }

        skipped = 0
        embedded = 0

        for chunk in chunks:
            idx = chunk["index"]
            digest = chunk_hashes[idx]
            if existing.get(idx) == digest:
                skipped += 1
                continue

            embedding_text = embedding_by_index.get(idx)
            if embedding_text is None:
                row = await (
                    await conn.execute(
                        """
                        SELECT embedding::text AS embedding
                        FROM rag_chunks
                        WHERE document_id = %s AND chunk_index = %s
                        """,
                        (document_id, idx),
                    )
                ).fetchone()
                embedding_text = row["embedding"] if row else None
            else:
                embedded += 1

            await conn.execute(
                """
                INSERT INTO rag_chunks
                  (document_id, tenant_id, chunk_index, content, metadata, embedding, content_hash)
                VALUES
                  (%s, %s, %s, %s, %s::jsonb, %s::vector, %s)
                ON CONFLICT (document_id, chunk_index) DO UPDATE
                  SET content = EXCLUDED.content,
                      metadata = EXCLUDED.metadata,
                      embedding = EXCLUDED.embedding,
                      content_hash = EXCLUDED.content_hash
                  WHERE rag_chunks.content_hash IS DISTINCT FROM EXCLUDED.content_hash
                """,
                (
                    document_id,
                    tenant_id,
                    idx,
                    chunk["content"],
                    json.dumps(chunk["metadata"]),
                    embedding_text,
                    digest,
                ),
            )

        await conn.commit()

    return {
        "inserted_or_updated": len(chunks) - skipped,
        "skipped_unchanged": skipped,
        "embedded": embedded,
    }
