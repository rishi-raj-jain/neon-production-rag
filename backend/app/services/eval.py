from uuid import UUID

from pydantic import BaseModel, Field

from app.config import get_settings
from app.services.embeddings import embed_text
from app.services.retrieval import retrieve_hybrid, retrieve_vector_only


class EvalQuery(BaseModel):
    query: str
    keyword_query: str | None = None
    expected_chunk_substring: str | None = None


class EvalRequest(BaseModel):
    tenant_id: UUID | None = None
    queries: list[EvalQuery] = Field(default_factory=list)


async def run_retrieval_eval(payload: EvalRequest) -> dict:
    settings = get_settings()
    tenant_id = payload.tenant_id or settings.default_tenant_id
    queries = payload.queries or [
        EvalQuery(
            query="What is Neon serverless Postgres branching?",
            expected_chunk_substring="branch",
        ),
        EvalQuery(
            query="pgvector extension HNSW index",
            keyword_query="pgvector HNSW",
            expected_chunk_substring="pgvector",
        ),
        EvalQuery(
            query="How do I connect Neon to Cursor MCP?",
            keyword_query="Cursor MCP",
            expected_chunk_substring="Cursor",
        ),
    ]

    results = []
    hybrid_hits = 0
    vector_hits = 0

    for item in queries:
        embedding = await embed_text(item.query)
        keyword = item.keyword_query or item.query
        hybrid = await retrieve_hybrid(
            tenant_id=tenant_id,
            keyword_query=keyword,
            query_embedding=embedding,
        )
        vector = await retrieve_vector_only(
            tenant_id=tenant_id,
            query_embedding=embedding,
        )

        needle = (item.expected_chunk_substring or "").lower()
        hybrid_ok = any(needle in (row["content"] or "").lower() for row in hybrid) if needle else bool(hybrid)
        vector_ok = any(needle in (row["content"] or "").lower() for row in vector) if needle else bool(vector)
        hybrid_hits += int(hybrid_ok)
        vector_hits += int(vector_ok)

        results.append(
            {
                "query": item.query,
                "keyword_query": keyword,
                "hybrid_hit": hybrid_ok,
                "vector_hit": vector_ok,
                "hybrid_top_ids": [str(row["id"]) for row in hybrid[:3]],
                "vector_top_ids": [str(row["id"]) for row in vector[:3]],
            }
        )

    total = len(queries)
    return {
        "tenant_id": str(tenant_id),
        "total_queries": total,
        "hybrid_recall": hybrid_hits / total if total else 0,
        "vector_recall": vector_hits / total if total else 0,
        "recommendation": (
            "Use hybrid retrieval in production; vector-only underperforms on this eval set."
            if hybrid_hits >= vector_hits
            else "Review eval set — hybrid did not beat vector-only on these queries."
        ),
        "results": results,
    }
