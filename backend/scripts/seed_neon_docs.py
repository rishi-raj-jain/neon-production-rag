import asyncio
import re
from uuid import UUID

import httpx

from app.config import get_settings
from app.db import close_pool, get_conn, init_pool
from app.services.chunking import chunk_markdown
from app.services.ingest import ingest_chunks, upsert_document

DOCS_BASE = "https://neon.com/docs"
MAX_PAGES = 5

# Seed script discovers pages live from Neon docs (markdown endpoints), not hard-coded content.
SEED_PATHS = [
    "introduction",
    "postgres/overview",
    "extensions/pgvector",
    "get-started/full-backend-quickstart",
    "ai/ai-cursor-plugin",
]


def extract_title(markdown: str, fallback: str) -> str:
    for line in markdown.splitlines():
        if line.startswith("# "):
            return line[2:].strip()
    return fallback


def discover_extra_paths(markdown: str, limit: int) -> list[str]:
    """Pull additional internal /docs links from the introduction page when needed."""
    paths: list[str] = []
    for match in re.finditer(r"\]\((?:https://neon\.com)?/docs/([^)#?]+)\)", markdown):
        slug = match.group(1).removesuffix(".md")
        if slug not in paths and slug not in SEED_PATHS:
            paths.append(slug)
        if len(paths) >= limit:
            break
    return paths


async def fetch_markdown(client: httpx.AsyncClient, slug: str) -> tuple[str, str]:
    url = f"{DOCS_BASE}/{slug}.md"
    response = await client.get(url, timeout=30.0, follow_redirects=True)
    response.raise_for_status()
    text = response.text
    title = extract_title(text, slug.replace("/", " - "))
    return title, text


async def apply_schema() -> None:
    from pathlib import Path

    schema = (Path(__file__).resolve().parents[1] / "sql" / "001_schema.sql").read_text(
        encoding="utf-8"
    )
    async with get_conn() as conn:
        await conn.execute(schema)
        await conn.commit()


async def seed() -> None:
    settings = get_settings()
    tenant_id: UUID = settings.default_tenant_id

    await init_pool()
    await apply_schema()

    paths = list(SEED_PATHS)
    async with httpx.AsyncClient(headers={"User-Agent": "neon-production-rag-seed/1.0"}) as client:
        intro_title, intro_md = await fetch_markdown(client, "introduction")
        if len(paths) < MAX_PAGES:
            paths.extend(discover_extra_paths(intro_md, MAX_PAGES - len(paths)))
        paths = paths[:MAX_PAGES]

        print(f"Seeding {len(paths)} Neon docs pages for tenant {tenant_id}")
        for slug in paths:
            title, markdown = await fetch_markdown(client, slug)
            source_id = f"neon-docs:{slug}"
            document_id = await upsert_document(source_id=source_id, title=title)
            chunks = chunk_markdown(markdown, source_id=source_id, title=title)
            stats = await ingest_chunks(
                tenant_id=tenant_id,
                document_id=document_id,
                chunks=chunks,
            )
            print(
                f"  ✓ {slug} -> {len(chunks)} chunks "
                f"(embedded={stats['embedded']}, skipped={stats['skipped_unchanged']})"
            )

    await close_pool()
    print("Seed complete.")


if __name__ == "__main__":
    asyncio.run(seed())
