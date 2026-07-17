"""The RAG core: question -> hybrid retrieval (vector + BM25, fused, reranked) -> LLM writes a grounded, cited answer.

Kept separate from main.py so the same brain can later serve WhatsApp (n8n),
the web widget, and the eval harness without touching the API layer.

Retrieval history (the before/after story):
  v1 (baseline_naive):  embed question -> pgvector top-4. Failed on keyword-shaped
     questions — Q20 "call centre fee" scored recall 0 because every fee-chunk
     looks alike in embedding space.
  v2 (current): vector top-8 AND BM25 keyword top-8 -> Reciprocal Rank Fusion
     -> cross-encoder reranks the merged 10 -> top-6 to the LLM.
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
TOP_K = 6  # final chunks handed to the LLM. Baseline used 4; local coverage testing showed
# the reranker sometimes cuts the gold chunk at 4, and keeping 6 of the fused 10 fixed
# nearly all misses (mean ground-truth-number coverage 0.874 -> 0.963) at ~zero extra cost.
CANDIDATE_K = 8  # each retriever's shortlist before fusion
FUSED_K = 10  # merged shortlist the reranker scores
RERANK_MODEL = "cross-encoder/ms-marco-MiniLM-L-6-v2"  # small local model (~90MB, one-time download), CPU, no API cost

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


@lru_cache
def _load_all_nodes():
    """Pull every chunk out of the pgvector table once — BM25's in-memory corpus.

    BM25 scores keyword overlap, so it needs the raw text of ALL chunks (131
    today — trivially fits in RAM). Nodes are rebuilt with their ORIGINAL ids
    so fusion can tell when vector and BM25 surfaced the SAME chunk (that
    agreement is exactly what RRF rewards).
    """
    import psycopg
    from llama_index.core.schema import TextNode
    from llama_index.core.vector_stores.utils import metadata_dict_to_node

    with psycopg.connect(os.environ["DATABASE_URL"], connect_timeout=15) as conn:
        rows = conn.execute(f"SELECT node_id, text, metadata_ FROM data_{TABLE_NAME}").fetchall()

    nodes = []
    for node_id, text, meta in rows:
        try:
            node = metadata_dict_to_node(meta)  # restores id + source/page metadata for citations
            node.set_content(text)  # text lives in its own column, not in metadata_
        except Exception:
            node = TextNode(
                id_=node_id,
                text=text,
                metadata={k: v for k, v in (meta or {}).items() if not k.startswith("_")},
            )
        nodes.append(node)
    return nodes


@lru_cache  # RAG concept #2: build the retriever ONCE at first request, then reuse.
def _get_retriever():
    """Hybrid retrieval: vector search (meaning) + BM25 (exact keywords), fused with RRF.

    Reciprocal Rank Fusion: a chunk earns 1/(60 + rank) from each list it appears
    in, summed. Near the top of EITHER list -> decent score; top of BOTH -> best.
    num_queries=1 turns off LlamaIndex's LLM query-rewriting (zero extra API calls).
    """
    from llama_index.core import Settings, VectorStoreIndex
    from llama_index.core.retrievers import QueryFusionRetriever
    from llama_index.embeddings.openai import OpenAIEmbedding
    from llama_index.retrievers.bm25 import BM25Retriever
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
    vector_retriever = index.as_retriever(similarity_top_k=CANDIDATE_K)
    bm25_retriever = BM25Retriever.from_defaults(nodes=_load_all_nodes(), similarity_top_k=CANDIDATE_K)
    return QueryFusionRetriever(
        [vector_retriever, bm25_retriever],
        similarity_top_k=FUSED_K,
        num_queries=1,
        mode="reciprocal_rerank",
        use_async=False,
    )


@lru_cache
def _get_reranker():
    """Cross-encoder reranker — the precision pass after fusion's recall pass.

    Embedding search compresses question and chunk into separate vectors before
    comparing (fast but lossy). A cross-encoder reads question + chunk TOGETHER
    and scores actual relevance — too slow to run on a whole corpus, cheap to
    run on 10 fused candidates. Keeps the best TOP_K.
    """
    from llama_index.core.postprocessor import SentenceTransformerRerank

    return SentenceTransformerRerank(model=RERANK_MODEL, top_n=TOP_K)


@lru_cache
def _get_llm():
    from llama_index.llms.openai import OpenAI

    # temperature 0.1: support answers should be boring and repeatable, not creative
    return OpenAI(model=LLM_MODEL, temperature=0.1, max_tokens=500)


def answer(question: str, include_contexts: bool = False) -> dict:
    """include_contexts=True adds the full retrieved chunk texts — used by the eval
    harness (RAGAS grades retrieval on the exact contexts the LLM saw), not the API."""
    from llama_index.core.llms import ChatMessage

    # Step 1 — RETRIEVE (hybrid): vector + BM25 shortlists fused into FUSED_K
    # candidates, then the cross-encoder keeps the TOP_K genuinely relevant ones.
    # Note: after reranking, `score` is a cross-encoder logit (can be negative;
    # higher = more relevant), not a 0-1 cosine similarity.
    hits = _get_retriever().retrieve(question)
    hits = _get_reranker().postprocess_nodes(hits, query_str=question)

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
