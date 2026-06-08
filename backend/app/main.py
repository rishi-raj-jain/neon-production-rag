from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import get_settings
from app.db import close_pool, init_pool
from app.routes.api import router


@asynccontextmanager
async def lifespan(_: FastAPI):
    await init_pool()
    yield
    await close_pool()


def create_app() -> FastAPI:
    settings = get_settings()
    app = FastAPI(title="Neon Production RAG API", lifespan=lifespan)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=[origin.strip() for origin in settings.cors_origins.split(",")],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    app.include_router(router)
    return app


app = create_app()
