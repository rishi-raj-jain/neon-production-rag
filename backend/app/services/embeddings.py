from openai import AsyncOpenAI

from app.config import get_settings


def get_openai_client() -> AsyncOpenAI:
    settings = get_settings()
    return AsyncOpenAI(api_key=settings.openai_api_key)


async def embed_text(text: str) -> list[float]:
    settings = get_settings()
    client = get_openai_client()
    response = await client.embeddings.create(
        model=settings.openai_embedding_model,
        input=text,
    )
    return response.data[0].embedding


async def embed_many(texts: list[str]) -> list[list[float]]:
    if not texts:
        return []
    settings = get_settings()
    client = get_openai_client()
    response = await client.embeddings.create(
        model=settings.openai_embedding_model,
        input=texts,
    )
    return [item.embedding for item in sorted(response.data, key=lambda row: row.index)]


def vector_literal(values: list[float]) -> str:
    return "[" + ",".join(f"{v:.8f}" for v in values) + "]"
