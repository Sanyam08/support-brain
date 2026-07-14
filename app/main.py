from fastapi import FastAPI

# FastAPI concept #1: this `app` object IS your web server's brain.
# Every @app.get / @app.post decorator below registers a URL route on it.
# uvicorn (the server) imports this object and forwards HTTP requests to it.
app = FastAPI(title="Support Brain", version="0.1.0")


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
