"""Similarity-search sanity check against pgvector. Run: python scripts/search_test.py "your question"

Embeds ONLY the query (a few tokens), then retrieves the closest stored chunks — no generation.
"""
import sys
from pathlib import Path

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parent.parent
load_dotenv(ROOT / ".env")
sys.path.insert(0, str(ROOT / "scripts"))

from ingest import EMBED_MODEL, make_vector_store  # noqa: E402

from llama_index.core import Settings, VectorStoreIndex  # noqa: E402
from llama_index.embeddings.openai import OpenAIEmbedding  # noqa: E402

question = sys.argv[1] if len(sys.argv) > 1 else "How much does 5kg of excess baggage cost?"
Settings.embed_model = OpenAIEmbedding(model=EMBED_MODEL)

index = VectorStoreIndex.from_vector_store(make_vector_store())
retriever = index.as_retriever(similarity_top_k=3)

print(f"Q: {question}\n")
for i, hit in enumerate(retriever.retrieve(question), 1):
    src = hit.metadata.get("source", "?")
    page = hit.metadata.get("page_label") or hit.metadata.get("row") or ""
    print(f"--- #{i}  score={hit.score:.3f}  [{src} {page}]")
    print(hit.get_content()[:300].replace("\n", " ").strip(), "\n")
