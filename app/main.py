"""FastAPI application entrypoint: wires middleware, lifespan, and routes."""

from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI
from starlette.middleware.sessions import SessionMiddleware

from app.config import settings
from app.data.db import close_pool, connection, open_pool
from app.routes import vapi, web


@asynccontextmanager
async def lifespan(app: FastAPI):
    await open_pool()
    try:
        yield
    finally:
        await close_pool()


app = FastAPI(title="Voice Scheduling Assistant", lifespan=lifespan)
app.add_middleware(SessionMiddleware, secret_key=settings.session_secret)

app.include_router(web.router)
app.include_router(vapi.router)


@app.get("/")
async def root():
    return {"status": "running", "service": "voice-scheduling-assistant"}


@app.get("/health/db")
async def health_db():
    async with connection() as conn:
        async with conn.cursor() as cur:
            await cur.execute("SELECT current_database()")
            row = await cur.fetchone()
    return {"status": "ok", "database": row["current_database"]}
