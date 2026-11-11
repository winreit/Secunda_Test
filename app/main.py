from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.api.v1.payments import router as payments_router
from app.db.database import engine


@asynccontextmanager
async def lifespan(app: FastAPI):
    yield
    await engine.dispose()


app = FastAPI(
    title="Async Payment Processing Service",
    description="Asynchronous payment processing with PostgreSQL, RabbitMQ and Transactional Outbox",
    version="1.0.0",
    lifespan=lifespan,
)
app.include_router(payments_router, prefix="/api/v1")


@app.get("/health", tags=["Health Check"])
async def health_check() -> dict[str, str]:
    return {"status": "ok"}
