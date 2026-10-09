from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager

from app.api.artifacts import router
from app.api.dataset import router as dataset_router
from app.api.rag import router as rag_router
from app.api.local import router as local_router
from app.api.sentinel import router as sentinel_router, sentinel_service
from app.api.quarantine import router as quarantine_router
from app.core.config import settings


@asynccontextmanager
async def lifespan(_app: FastAPI):
    sentinel_service.start()
    try:
        yield
    finally:
        sentinel_service.stop()


app = FastAPI(title="PRISM Backend", lifespan=lifespan)
if settings.cors_origins:
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=False,
        allow_methods=["GET", "POST"],
        allow_headers=["Content-Type"],
    )
app.include_router(router)
app.include_router(dataset_router)
app.include_router(rag_router)
app.include_router(local_router)
app.include_router(sentinel_router)
app.include_router(quarantine_router)


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok", "service": "prism-backend"}
