# Support Brain

Production RAG chatbot with an eval harness. Ingests messy real-world knowledge
(PDFs, Google Sheets, websites) and answers questions with cited sources —
served over WhatsApp (n8n) and a web widget.

**The differentiator:** a RAGAS/Langfuse evaluation pipeline with a before/after
accuracy dashboard. Not "it seems to work" — measured retrieval quality.

## Stack
- Python + FastAPI (reasoning layer)
- LlamaIndex (ingestion + retrieval)
- pgvector on Supabase (vector store)
- RAGAS + Langfuse (evals + tracing)
- n8n (WhatsApp delivery layer)
- React/Vite (eval dashboard)

## Run locally
```
.venv\Scripts\activate
uvicorn app.main:app --reload
```
Then open http://127.0.0.1:8000/docs

## Status
🚧 Week 1: ingestion + basic RAG endpoint.
