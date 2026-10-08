"""FastAPI entry point. Run with: uvicorn app.main:app --reload --port 8000"""

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api import analytics, analyze, applications, files, health, truth_bank
from app.config import get_settings
from app.db.session import init_db


@asynccontextmanager
async def lifespan(api: FastAPI) -> AsyncIterator[None]:
    # Apply pending migrations; the data persists in data/jobpilot.db. Honour test overrides
    # so tests never touch the real database.
    settings_provider = api.dependency_overrides.get(get_settings, get_settings)
    init_db(settings_provider())
    yield


settings = get_settings()

app = FastAPI(title="JobPilot", version="0.2.0", lifespan=lifespan)

# The frontend normally reaches the API through a Next.js rewrite (same origin),
# so CORS only matters when calling the API directly from the browser.
app.add_middleware(
    CORSMiddleware,
    allow_origins=[settings.frontend_origin],
    allow_methods=["*"],
    allow_headers=["*"],
)

for module in (health, analyze, applications, analytics, truth_bank, files):
    app.include_router(module.router, prefix="/api")
