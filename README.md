# Neon Production RAG

Production-grade hybrid RAG over [Neon Postgres](https://neon.com/docs/introduction) documentation using **pgvector + full-text search**, **RRF fusion (k=60)**, **FastAPI**, **Next.js**, and **OpenAI**.

https://github.com/user-attachments/assets/f7017dd8-ea23-44f1-bf36-5aeee743fa99

## Architecture

```
neon.com/docs/*.md  →  seed script (live fetch)
                   →  LangChain chunking  →  OpenAI embedMany
                   →  upsert rag_chunks (skip unchanged content_hash)

User message  →  embed(last 6 turns + latest message)
             →  keyword search latest message only
             →  retrieve_hybrid() RRF  →  stream GPT  →  persist chat_messages + chunk_ids
```

### Schema highlights

- `rag_chunks`: `content`, generated `searchable` tsvector, `embedding vector(1536)`, `tenant_id`, `content_hash`, `UNIQUE(document_id, chunk_index)`
- `retrieve_hybrid(p_tenant_id, keyword, embedding, limit=8, rrf_k=60)` — semantic + keyword lists fused via RRF with `FULL OUTER JOIN` and `COALESCE` on content/metadata
- `retrieve_vector_only()` — eval baseline only; do not ship vector-only retrieval without running `/eval/retrieval`
- `chat_sessions` + `chat_messages` with `chunk_ids` stored in assistant message metadata

## Prerequisites

- Neon project with **pgvector** enabled ([docs](https://neon.com/docs/extensions/pgvector))
- OpenAI API key
- Python 3.11+ and Node 20+

## Setup

1. Copy env files and fill in credentials:

```bash
cp .env.example .env
cp frontend/.env.local.example frontend/.env.local
```

Use the same `DATABASE_URL`, `DEFAULT_TENANT_ID`, and `OPENAI_API_KEY` in both `.env` (backend/seed) and `frontend/.env.local`.

2. Install backend dependencies and apply schema + seed (5 Neon doc pages, fetched live):

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r backend/requirements.txt
./scripts/seed.sh
```

The seed script downloads markdown from:

- `introduction`
- `postgres/overview`
- `extensions/pgvector`
- `get-started/full-backend-quickstart`
- `ai/ai-cursor-plugin`

3. Run hybrid vs vector-only eval (recommended before production):

```bash
curl -X POST http://localhost:8000/eval/retrieval -H 'Content-Type: application/json' -d '{}'
```

4. Start API and web UI:

```bash
./scripts/run-backend.sh          # http://localhost:8000
cd frontend && npm install && npm run dev   # http://localhost:3000
```

## API

| Method | Path | Description |
|--------|------|-------------|
| POST | `/admin/migrate` | Apply SQL schema |
| POST | `/ingest/document` | Ingest a single markdown document |
| POST | `/chat/sessions` | Create tenant-scoped chat session |
| POST | `/retrieve/hybrid` | Debug hybrid retrieval |
| POST | `/eval/retrieval` | Compare hybrid vs vector-only recall |
| GET | `/health` | Health check |

## Chat flow (Next.js)

`frontend/app/api/chat/route.ts`:

1. Validates session belongs to `DEFAULT_TENANT_ID`
2. Loads last 6 turns from `chat_messages`
3. Embeds conversation context; keyword-searches **latest user message only**
4. Calls `retrieve_hybrid()` (limit 8)
5. Streams OpenAI response with retrieved chunks as system context
6. Persists user + assistant messages; assistant metadata includes `chunk_ids`

## Tenant isolation

Every retrieval query filters `WHERE tenant_id = $tenant`. Chat sessions are created with the same tenant UUID. Never query `rag_chunks` without a tenant filter.

## Project layout

```
neon-production-rag/
├── backend/
│   ├── sql/001_schema.sql
│   ├── app/                 # FastAPI services
│   └── scripts/seed_neon_docs.py
├── frontend/                # Next.js chat UI + streaming route
└── scripts/
```

## License

MIT
