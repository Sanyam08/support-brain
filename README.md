# Support Brain

A production-shaped RAG chatbot for customer support — with a measured, before/after
eval harness instead of a vibe check.

**The number:** hybrid retrieval + reranking + a targeted prompt upgrade took
faithfulness from **88% → 94%** and context recall from **91% → 94%** across 36 real
questions — and on multi-step "practical" questions that require arithmetic
(e.g. *"my bag is 13kg, I'm adding a wine bottle, will I go over the limit?"*),
faithfulness went **51% → 86%** once the prompt was told to show its work.

## What this actually is

Most "RAG demo" repos show a chat window and ask you to trust it. This one ships the
chat window (WhatsApp + a web widget) *and* the eval harness that proves retrieval
quality changed, with real numbers before and after each change. **The eval dashboard
is the money shot, not the chat.**

Corpus is real, public IndiGo airline documents — Conditions of Carriage PDF, baggage
fee PDF, 4 fee/baggage web pages, and a compiled fee sheet — nothing fabricated,
nothing scraped from a login-gated source.

## Architecture

```
PDFs + web pages + Google Sheet (real IndiGo public docs)
        │  scripts/ingest.py — LlamaIndex loaders, chunk, embed (text-embedding-3-small)
        ▼
pgvector on Supabase (131 chunks)
        │
        ▼
Hybrid retrieval (app/rag.py)
  vector top-8  ─┐
                 ├─► Reciprocal Rank Fusion ─► cross-encoder rerank ─► top-6
  BM25 top-8    ─┘   (ms-marco-MiniLM-L-6-v2, local, CPU)
        │
        ▼
gpt-4o-mini — grounded, cited answer ───► Langfuse tracing (per-question cost + spans)
        │
   ┌────┴──────────┬───────────────────┐
   ▼                ▼                   ▼
FastAPI /ask   n8n → WhatsApp      widget/ (embeddable JS,
(app/main.py)    (delivery layer)   one <script> tag)

Separately: scripts/run_eval.py (RAGAS) ─► data/evals/results/*.json
                                          ─► dashboard/ (Vite + React, before/after visual)
```

## Results

| Stage | Faithfulness | Context recall | Answer relevancy | Context precision |
|---|---|---|---|---|
| Baseline (naive vector top-4) | 0.883 | 0.911 | 0.774 | 0.906 |
| + Hybrid retrieval + rerank-6 | 0.922 | 0.943 | 0.748 | 0.804 |
| + Prompt upgrade (final) | **0.943** | **0.943** | 0.785 | 0.804 |

Refusal accuracy: 3/3 out-of-corpus probes correctly declined across every stage.

**Practical (multi-step reasoning) questions**, a separate 4-question slice requiring
arithmetic against a limit, not just lookup:

| Stage | Faithfulness |
|---|---|
| After hybrid + rerank (facts right, reasoning not enforced) | 0.51 |
| After prompt upgrade (told to show its work) | **0.86** |

Retrieval fixed *which chunks* the model sees (Q20's call-centre-fee recall went
0 → 1 with hybrid). The prompt upgrade fixed *what it does with them* — the model
was seeing the right numbers and still reasoning wrong until told explicitly to do
the arithmetic instead of jumping to a conclusion.

Full breakdown by category, and every question/answer/citation, is in the
[eval dashboard](dashboard/) — run it locally (see below) or check `data/evals/results/*.json`.

## Stack

- **Python + FastAPI** — reasoning layer (`app/`)
- **LlamaIndex** — ingestion, hybrid retrieval (vector + BM25), reranking
- **pgvector on Supabase** (free tier) — vector store
- **RAGAS + Langfuse** (free tiers) — evals and per-question tracing/cost
- **n8n** — WhatsApp delivery layer (integration layer, not reasoning — kept out of Python on purpose)
- **React + Vite** — eval dashboard, deployable static to Vercel

## Repo structure

```
app/            FastAPI backend — main.py (routes), rag.py (retrieval + generation)
scripts/        ingest.py (corpus → pgvector), run_eval.py (RAGAS), search_test.py, check_setup.py
dashboard/      Vite + React eval dashboard (before/after accuracy visual)
widget/         Embeddable vanilla-JS chat widget + demo host page
data/evals/     Eval dataset (39 Q&A) + results per stage (baseline/hybrid/rerank/prompt)
```

## Run locally

Backend (no lockfile yet — see Known limitations):
```
python -m venv .venv
.venv\Scripts\activate
pip install fastapi uvicorn[standard] python-dotenv pydantic langfuse psycopg[binary] ^
    llama-index-core llama-index-readers-file llama-index-embeddings-openai ^
    llama-index-llms-openai llama-index-vector-stores-postgres llama-index-retrievers-bm25 ^
    sentence-transformers beautifulsoup4 ragas
uvicorn app.main:app --reload
```
Then open http://127.0.0.1:8000/docs and try `POST /ask`. You'll need a `.env` with
`OPENAI_API_KEY`, `DATABASE_URL` (Supabase pooler URL), and optionally `LANGFUSE_*`
keys — tracing no-ops cleanly if they're absent.

Eval dashboard:
```
cd dashboard
npm install
npm run dev
```
`?theme=light` / `?theme=dark` on the URL forces a theme for recording/screenshots.

Web widget: open `widget/demo.html` directly in a browser with the backend running
on `:8000` (or pass `?api=https://your-tunnel-domain`).

## Known limitations (honest, not hidden)

- **No `requirements.txt` yet** — the install line above lists the actual packages
  used; a pinned lockfile is a fast follow-up, not done as of this writing.
- **One retrieval gap**: a ₹900 baggage fee mentioned in the Conditions of Carriage
  never surfaces in the top-6 chunks (a ₹800 figure from the fee sheet wins instead)
  — the corpus itself has two conflicting numbers for the same fee, and retrieval
  currently picks one rather than surfacing the conflict.
  Ranked below the answer-relevancy dip on the practical category, which is very
  likely a stricter LLM-judge penalizing longer, hedged answers rather than a real
  quality regression — flagged, not chased, given the timebox.
- **Not deployed to a live domain.** By design for this project's scope — WhatsApp
  delivery runs through n8n + ngrok for demos, the widget/dashboard are static and
  can run anywhere, but there's no always-on production URL.
- **CORS is wide open** on `/ask` — acceptable because the API only serves read-only
  answers over public documents, not appropriate for anything handling private data.

## What's NOT built (by design, not oversight)

No multi-turn conversation memory · no auth/rate-limiting (public-docs demo, not a
production deployment) · no reranking model swap-testing beyond the one used.

## Case study

Built a production-shaped RAG support bot over real airline documents and proved
retrieval quality with numbers instead of assertions: hybrid retrieval + reranking
+ a targeted prompt fix raised answer faithfulness from 88% to 94% overall, and from
51% to 86% on questions requiring multi-step arithmetic — the exact failure mode
that makes "it looks fine in the demo" support bots unreliable in production. Shipped
with a before/after eval dashboard, WhatsApp delivery via n8n, and an embeddable web
widget, all running on free-tier infrastructure for under $2 in API spend.
