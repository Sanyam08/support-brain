"""Ingestion pipeline: IndiGo corpus (PDFs + saved HTML + Google Sheet) -> chunks -> embeddings -> pgvector.

Usage:
    python scripts/ingest.py --dry-run   # load + chunk only, print token/cost estimate, NO API calls
    python scripts/ingest.py             # full run: embed everything and store in Supabase
    python scripts/ingest.py --reset     # drop the vector table first, then full run
"""
import argparse
import io
import os
import re
import sys
import urllib.request
from pathlib import Path
from urllib.parse import urlparse

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parent.parent
load_dotenv(ROOT / ".env")

TABLE_NAME = "support_brain"  # PGVectorStore creates it as data_support_brain
EMBED_MODEL = "text-embedding-3-small"
EMBED_DIM = 1536
EMBED_PRICE_PER_M = 0.02  # USD per 1M tokens


def load_pdfs():
    from llama_index.readers.file import PDFReader

    docs = []
    for pdf in sorted((ROOT / "data" / "raw").glob("*.pdf")):
        pages = PDFReader().load_data(pdf)
        for d in pages:
            d.metadata["source"] = pdf.name
            d.metadata["doc_type"] = "pdf"
        docs.extend(pages)
        print(f"  PDF  {pdf.name}: {len(pages)} pages")
    return docs


def load_html():
    from bs4 import BeautifulSoup
    from llama_index.core import Document

    docs = []
    for page in sorted((ROOT / "data" / "raw" / "web").glob("*.html")):
        soup = BeautifulSoup(page.read_text(encoding="utf-8", errors="ignore"), "html.parser")
        for tag in soup(["script", "style", "noscript", "header", "footer", "nav"]):
            tag.decompose()
        text = re.sub(r"\n{3,}", "\n\n", soup.get_text("\n")).strip()
        docs.append(
            Document(
                text=text,
                metadata={"source": page.name, "doc_type": "web", "url_slug": page.stem},
            )
        )
        print(f"  HTML {page.name}: {len(text)} chars")
    return docs


def load_sheet():
    """One document per row — each fee row is a self-contained fact, so it becomes its own chunk."""
    import csv

    from llama_index.core import Document

    sheet_id = re.search(r"/d/([\w-]+)", os.environ["GOOGLE_SHEET_URL"]).group(1)
    url = f"https://docs.google.com/spreadsheets/d/{sheet_id}/export?format=csv"
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    raw = urllib.request.urlopen(req, timeout=30).read().decode("utf-8", errors="ignore")
    rows = list(csv.DictReader(io.StringIO(raw)))
    docs = []
    for i, row in enumerate(rows):
        text = "IndiGo fee information: " + " | ".join(
            f"{k.strip()}: {v.strip()}" for k, v in row.items() if v and v.strip()
        )
        docs.append(
            Document(
                text=text,
                metadata={"source": "google-sheet-fees", "doc_type": "sheet", "row": i + 1},
            )
        )
    print(f"  SHEET fees & baggage: {len(docs)} rows")
    return docs


def chunk(docs):
    from llama_index.core.node_parser import SentenceSplitter

    splitter = SentenceSplitter(chunk_size=512, chunk_overlap=50)
    nodes = splitter.get_nodes_from_documents(docs)
    return nodes


def make_vector_store():
    url = urlparse(os.environ["DATABASE_URL"])
    from llama_index.vector_stores.postgres import PGVectorStore

    return PGVectorStore.from_params(
        host=url.hostname,
        port=url.port or 5432,
        database=url.path.lstrip("/"),
        user=url.username,
        password=url.password,
        table_name=TABLE_NAME,
        embed_dim=EMBED_DIM,
    )


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true", help="chunk + estimate cost, no API calls")
    parser.add_argument("--reset", action="store_true", help="drop existing vector table first")
    args = parser.parse_args()

    print("Loading corpus...")
    docs = load_pdfs() + load_html() + load_sheet()
    print(f"Loaded {len(docs)} documents. Chunking...")
    nodes = chunk(docs)

    est_tokens = sum(len(n.get_content()) for n in nodes) // 4  # ~4 chars per token
    est_cost = est_tokens / 1_000_000 * EMBED_PRICE_PER_M
    print(f"{len(nodes)} chunks, ~{est_tokens:,} tokens -> estimated embedding cost ${est_cost:.4f}")

    if args.dry_run:
        print("Dry run - stopping before any API call.")
        return

    if args.reset:
        import psycopg

        with psycopg.connect(os.environ["DATABASE_URL"], connect_timeout=15) as conn:
            conn.execute(f"DROP TABLE IF EXISTS data_{TABLE_NAME}")
            conn.commit()
        print(f"Dropped table data_{TABLE_NAME}.")

    from llama_index.core import Settings, StorageContext, VectorStoreIndex
    from llama_index.embeddings.openai import OpenAIEmbedding

    Settings.embed_model = OpenAIEmbedding(model=EMBED_MODEL)
    storage_context = StorageContext.from_defaults(vector_store=make_vector_store())
    VectorStoreIndex(nodes, storage_context=storage_context, show_progress=True)

    import psycopg

    with psycopg.connect(os.environ["DATABASE_URL"], connect_timeout=15) as conn:
        count = conn.execute(f"select count(*) from data_{TABLE_NAME}").fetchone()[0]
    print(f"Done. data_{TABLE_NAME} now holds {count} embedded chunks.")


if __name__ == "__main__":
    main()
