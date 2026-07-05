from contextlib import asynccontextmanager

from fastapi import FastAPI, Response

from app import db


@asynccontextmanager
async def lifespan(app: FastAPI):
    yield
    await db.close_pool()


app = FastAPI(title="OpsPilot RAG service", lifespan=lifespan)


@app.get("/health")
async def health(response: Response):
    db_ok = await db.check_db()
    if not db_ok:
        response.status_code = 503
    return {"status": "ok" if db_ok else "unavailable", "db": db_ok}
