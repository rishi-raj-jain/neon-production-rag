CREATE EXTENSION IF NOT EXISTS vector;
CREATE EXTENSION IF NOT EXISTS pgcrypto;

CREATE TABLE IF NOT EXISTS rag_documents (
  id           uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  source_id    text NOT NULL UNIQUE,
  title        text,
  created_at   timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS rag_chunks (
  id           uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  document_id  uuid NOT NULL REFERENCES rag_documents(id) ON DELETE CASCADE,
  tenant_id    uuid NOT NULL,
  chunk_index  int NOT NULL,
  content      text NOT NULL,
  metadata     jsonb NOT NULL DEFAULT '{}',
  searchable   tsvector GENERATED ALWAYS AS (
    to_tsvector('english', coalesce(content, ''))
  ) STORED,
  embedding    vector(1536),
  content_hash text NOT NULL,
  created_at   timestamptz NOT NULL DEFAULT now(),
  UNIQUE (document_id, chunk_index)
);

CREATE INDEX IF NOT EXISTS rag_chunks_searchable_idx ON rag_chunks USING GIN (searchable);
CREATE INDEX IF NOT EXISTS rag_chunks_embedding_idx ON rag_chunks
  USING hnsw (embedding vector_cosine_ops);
CREATE INDEX IF NOT EXISTS rag_chunks_tenant_idx ON rag_chunks (tenant_id);

CREATE TABLE IF NOT EXISTS chat_sessions (
  id           uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id    uuid NOT NULL,
  user_id      text NOT NULL,
  summary      text,
  updated_at   timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS chat_messages (
  id           uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  session_id   uuid NOT NULL REFERENCES chat_sessions(id) ON DELETE CASCADE,
  role         text NOT NULL CHECK (role IN ('user', 'assistant', 'system')),
  content      text NOT NULL,
  metadata     jsonb NOT NULL DEFAULT '{}',
  created_at   timestamptz NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS chat_messages_session_idx
  ON chat_messages (session_id, created_at DESC);

-- Hybrid retrieval: RRF (k=60), FULL OUTER JOIN, COALESCE content/metadata, limit 8
CREATE OR REPLACE FUNCTION retrieve_hybrid(
  p_tenant_id uuid,
  p_keyword_query text,
  p_query_embedding vector(1536),
  p_limit int DEFAULT 8,
  p_rrf_k double precision DEFAULT 60
)
RETURNS TABLE (
  id uuid,
  content text,
  metadata jsonb,
  score double precision
)
LANGUAGE sql
STABLE
AS $$
  WITH
  semantic AS (
    SELECT c.id, c.content, c.metadata,
           ROW_NUMBER() OVER (ORDER BY c.embedding <=> p_query_embedding) AS rank
    FROM rag_chunks c
    WHERE c.tenant_id = p_tenant_id
      AND c.embedding IS NOT NULL
    ORDER BY c.embedding <=> p_query_embedding
    LIMIT 20
  ),
  keyword AS (
    SELECT c.id, c.content, c.metadata,
           ROW_NUMBER() OVER (
             ORDER BY ts_rank_cd(c.searchable, websearch_to_tsquery('english', p_keyword_query)) DESC
           ) AS rank
    FROM rag_chunks c
    WHERE c.tenant_id = p_tenant_id
      AND c.searchable @@ websearch_to_tsquery('english', p_keyword_query)
    ORDER BY ts_rank_cd(c.searchable, websearch_to_tsquery('english', p_keyword_query)) DESC
    LIMIT 20
  ),
  fused AS (
    SELECT
      COALESCE(s.id, k.id) AS id,
      COALESCE(s.content, k.content) AS content,
      COALESCE(s.metadata, k.metadata) AS metadata,
      COALESCE(1.0 / (p_rrf_k + s.rank), 0) + COALESCE(1.0 / (p_rrf_k + k.rank), 0) AS score
    FROM semantic s
    FULL OUTER JOIN keyword k USING (id)
  )
  SELECT f.id, f.content, f.metadata, f.score
  FROM fused f
  ORDER BY f.score DESC
  LIMIT p_limit;
$$;

-- Vector-only baseline for eval comparison (never use alone in production without eval)
CREATE OR REPLACE FUNCTION retrieve_vector_only(
  p_tenant_id uuid,
  p_query_embedding vector(1536),
  p_limit int DEFAULT 8
)
RETURNS TABLE (
  id uuid,
  content text,
  metadata jsonb,
  distance double precision
)
LANGUAGE sql
STABLE
AS $$
  SELECT c.id, c.content, c.metadata, (c.embedding <=> p_query_embedding) AS distance
  FROM rag_chunks c
  WHERE c.tenant_id = p_tenant_id
    AND c.embedding IS NOT NULL
  ORDER BY c.embedding <=> p_query_embedding
  LIMIT p_limit;
$$;
