import json
from pathlib import Path
from uuid import UUID

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from app.config import get_settings
from app.db import get_conn
from app.services.chat import create_session, insert_message
from app.services.chunking import chunk_markdown
from app.services.embeddings import embed_text
from app.services.eval import EvalRequest, run_retrieval_eval
from app.services.ingest import ingest_chunks, upsert_document
from app.services.retrieval import (
    build_retrieval_query,
    fetch_recent_messages,
    format_chunks_as_context,
    retrieve_hybrid,
)

router = APIRouter()


class IngestDocumentRequest(BaseModel):
    tenant_id: UUID | None = None
    source_id: str
    title: str
    content: str


class ChatSessionRequest(BaseModel):
    tenant_id: UUID | None = None
    user_id: str = "demo-user"


class RetrieveRequest(BaseModel):
    tenant_id: UUID | None = None
    session_id: UUID | None = None
    message: str


@router.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}


@router.post("/admin/migrate")
async def migrate() -> dict[str, str]:
    schema_path = Path(__file__).resolve().parents[2] / "sql" / "001_schema.sql"
    sql = schema_path.read_text(encoding="utf-8")
    async with get_conn() as conn:
        await conn.execute(sql)
        await conn.commit()
    return {"status": "migrated"}


@router.post("/ingest/document")
async def ingest_document_route(body: IngestDocumentRequest) -> dict:
    settings = get_settings()
    tenant_id = body.tenant_id or settings.default_tenant_id
    document_id = await upsert_document(source_id=body.source_id, title=body.title)
    chunks = chunk_markdown(body.content, source_id=body.source_id, title=body.title)
    stats = await ingest_chunks(tenant_id=tenant_id, document_id=document_id, chunks=chunks)
    return {"document_id": str(document_id), "chunks": len(chunks), **stats}


@router.post("/chat/sessions")
async def create_chat_session(body: ChatSessionRequest) -> dict:
    settings = get_settings()
    tenant_id = body.tenant_id or settings.default_tenant_id
    session_id = await create_session(tenant_id=tenant_id, user_id=body.user_id)
    return {"session_id": str(session_id), "tenant_id": str(tenant_id)}


@router.post("/retrieve/hybrid")
async def hybrid_retrieve(body: RetrieveRequest) -> dict:
    settings = get_settings()
    tenant_id = body.tenant_id or settings.default_tenant_id
    recent = []
    if body.session_id:
        recent = await fetch_recent_messages(body.session_id, limit=6)
    retrieval_text = build_retrieval_query(body.message, recent)
    embedding = await embed_text(retrieval_text)
    chunks = await retrieve_hybrid(
        tenant_id=tenant_id,
        keyword_query=body.message,
        query_embedding=embedding,
    )
    return {
        "retrieval_text": retrieval_text,
        "keyword_query": body.message,
        "chunks": chunks,
        "context": format_chunks_as_context(chunks),
    }


@router.post("/eval/retrieval")
async def eval_retrieval(body: EvalRequest) -> dict:
    return await run_retrieval_eval(body)


@router.get("/chat/sessions/{session_id}/messages")
async def list_messages(session_id: UUID) -> dict:
    async with get_conn() as conn:
        rows = await (
            await conn.execute(
                """
                SELECT id, role, content, metadata, created_at
                FROM chat_messages
                WHERE session_id = %s
                ORDER BY created_at ASC
                """,
                (session_id,),
            )
        ).fetchall()
    return {"messages": rows}


@router.post("/chat/sessions/{session_id}/messages")
async def append_message(session_id: UUID, body: dict) -> dict:
    role = body.get("role")
    content = body.get("content")
    metadata = body.get("metadata", {})
    if role not in {"user", "assistant", "system"} or not content:
        raise HTTPException(status_code=400, detail="Invalid message payload")
    message_id = await insert_message(
        session_id=session_id,
        role=role,
        content=content,
        metadata=metadata,
    )
    return {"id": str(message_id)}
