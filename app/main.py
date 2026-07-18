from contextlib import asynccontextmanager

from fastapi import FastAPI
from langfuse import get_client
from pydantic import BaseModel, Field

from app.rag import answer as rag_answer


# Langfuse batches traces in memory and ships them in the background (so tracing
# never slows down /ask). A lifespan hook flushes that buffer on shutdown —
# without it, the last few traces can die with the process on Ctrl+C.
@asynccontextmanager
async def lifespan(app: FastAPI):
    yield
    get_client().shutdown()


# FastAPI concept #1: this `app` object IS your web server's brain.
# Every @app.get / @app.post decorator below registers a URL route on it.
# uvicorn (the server) imports this object and forwards HTTP requests to it.
app = FastAPI(title="Support Brain", version="0.1.0", lifespan=lifespan)


@app.get("/")
def root():
    # FastAPI concept #2: return a plain dict and FastAPI serializes it
    # to JSON automatically — no manual json.dumps, no response objects.
    return {"service": "support-brain", "status": "alive"}


@app.get("/health")
def health():
    # A /health route is a production habit: n8n (and later, uptime checks)
    # can ping this to confirm the backend is up before routing user messages.
    return {"ok": True}


# FastAPI concept #3: a pydantic model as the request body = automatic validation
# AND automatic docs. POST /ask with {"question": "..."} — anything else is
# rejected with a clear error before our code even runs.
class AskRequest(BaseModel):
    question: str = Field(min_length=3, max_length=500)


@app.post("/ask")
def ask(req: AskRequest):
    # The whole RAG flow lives in app/rag.py; the endpoint stays a thin wrapper.
    # Same pattern n8n/WhatsApp will call in W3-1.
    return rag_answer(req.question)
