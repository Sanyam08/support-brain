"""The RAG core: question -> retrieve chunks from pgvector -> LLM writes a grounded, cited answer.

Kept separate from main.py so the same brain can later serve WhatsApp (n8n),
the web widget, and the eval harness without touching the API layer.
"""
import os
from functools import lru_cache
from urllib.parse import urlparse

from dotenv import load_dotenv

load_dotenv()

TABLE_NAME = "support_brain"
EMBED_MODEL = "text-embedding-3-small"  # must match what ingest.py used, or vectors won't line up
EMBED_DIM = 1536
LLM_MODEL = "gpt-4o-mini"  # cheap + good enough for grounded answering (~$0.0005/question)
TOP_K = 4

# RAG concept #1: the system prompt is the guardrail. The LLM may ONLY use the
# retrieved context — "I don't know" is a feature, not a failure. An airline bot
# that invents refund policies is a lawsuit; one that says "not in my docs" is honest.
SYSTEM_PROMPT = """You are a customer-support assistant for IndiGo airlines.
Answer the user's question using ONLY the context provided below.
Rules:
- If the context does not contain the answer, say you don't have that information \
and suggest contacting IndiGo support. Never guess or use outside knowledge.
- Quote specific numbers (fees, weights, time limits) exactly as written in the context.
- Be concise: 2-5 sentences unless the question genuinely needs more.
"""


@lru_cache  # RAG concept #2: build the retriever ONCE at first request, then reuse.
def _get_retriever():
    from llama_index.core import Settings, VectorStoreIndex
    from llama_index.embeddings.openai import OpenAIEmbedding
    from llama_index.vector_stores.postgres import PGVectorStore

    Settings.embed_model = OpenAIEmbedding(model=EMBED_MODEL)
    url = urlparse(os.environ["DATABASE_URL"])
    store = PGVectorStore.from_params(
        host=url.hostname,
        port=url.port or 5432,
        database=url.path.lstrip("/"),
        user=url.username,
        password=url.password,
        table_name=TABLE_NAME,
        embed_dim=EMBED_DIM,
    )
    index = VectorStoreIndex.from_vector_store(store)
    return index.as_retriever(similarity_top_k=TOP_K)


@lru_cache
def _get_llm():
    from llama_index.llms.openai import OpenAI

    # temperature 0.1: support answers should be boring and repeatable, not creative
    return OpenAI(model=LLM_MODEL, temperature=0.1, max_tokens=500)


def answer(question: str, include_contexts: bool = False) -> dict:
    """include_contexts=True adds the full retrieved chunk texts — used by the eval
    harness (RAGAS grades retrieval on the exact contexts the LLM saw), not the API."""
    from llama_index.core.llms import ChatMessage

    # Step 1 — RETRIEVE: embed the question (one tiny API call), let pgvector
    # find the TOP_K chunks whose vectors sit closest to it.
    hits = _get_retriever().retrieve(question)

    # Step 2 — AUGMENT: paste those chunks into the prompt, labeled [1]..[4]
    # so the model can only see (and cite) what retrieval surfaced.
    context = "\n\n".join(
        f"[{i}] (source: {h.metadata.get('source', '?')}"
        f"{', page ' + h.metadata['page_label'] if h.metadata.get('page_label') else ''})\n"
        f"{h.get_content()}"
        for i, h in enumerate(hits, 1)
    )

    # Step 3 — GENERATE: one LLM call writes the answer from that context.
    response = _get_llm().chat(
        [
            ChatMessage(role="system", content=SYSTEM_PROMPT),
            ChatMessage(role="user", content=f"Context:\n{context}\n\nQuestion: {question}"),
        ]
    )

    result = {
        "answer": response.message.content.strip(),
        "sources": [
            {
                "source": h.metadata.get("source", "?"),
                "location": h.metadata.get("page_label") or h.metadata.get("row"),
                "score": round(h.score, 3),
                "snippet": h.get_content()[:200].strip(),
            }
            for h in hits
        ],
    }
    if include_contexts:
        result["contexts"] = [h.get_content() for h in hits]
    return result
