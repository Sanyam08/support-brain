# Support Brain — build explained in simple terms

Source notes for the end-of-project Excalidraw diagram + demo video narration.
One section per milestone; written so Sanyam can explain every box on a client call.

---

## W1-1 · Environment setup (done 2026-07-14)

- Created the project folder `support-brain/` with a Python **virtual environment** (`.venv`) — an isolated toolbox so this project's libraries don't clash with anything else on the machine.
- **FastAPI** hello-world running — FastAPI is the Python web framework that will later expose the chatbot as an API other systems (n8n, WhatsApp, web widget) can call.
- Git repo initialized — every milestone is a commit, so the build history tells the story.

**Diagram idea:** a laptop box labeled "FastAPI app (the brain's front door)".

## W1-2 · Corpus + database (done 2026-07-15)

- Assembled the **knowledge corpus**: real public IndiGo docs — Conditions of Carriage PDF (31pp), baggage policy PDF (9pp), 4 saved HTML pages from goindigo.in, and a 26-row fee table in a public Google Sheet. Three different formats on purpose: messy, mixed-format knowledge is what real clients have.
- Created a free **Supabase** project (Mumbai region). Supabase = hosted Postgres database in the cloud. Enabled the **pgvector** extension, which teaches Postgres to store and compare *vectors* (see below).

**Diagram idea:** three source icons (PDF / web page / spreadsheet) on the left; a cloud database cylinder on the right.

## W1-3 · Ingestion pipeline (done 2026-07-17)

The script `scripts/ingest.py` is a regular Python file run **once** from the terminal — a *loading dock worker*: it moves knowledge from files into the database, then exits. It stays in the repo to re-run only when the source documents change.

What it does, step by step:

1. **Load (local machine, no AI):** open the PDFs and pull text from every page; strip menus/scripts out of the saved HTML; download the Google Sheet as CSV over the internet. Just file reading.
2. **Chunk (local machine, no OpenAI):** *our code* (the LlamaIndex library, running locally) cut the text into **131 chunks** of ~512 tokens (~2 paragraphs), splitting at sentence boundaries. Why: when someone asks "what's the cancellation fee?", you don't hand the LLM a 31-page PDF — you hand it the 2-3 paragraphs that contain the answer. **Chunks are the unit of retrieval.**
3. **Embed (the only OpenAI part):** send the chunk *text* to OpenAI's embedding API (`text-embedding-3-small`); get back one **vector** per chunk — a list of 1,536 numbers capturing the chunk's *meaning*. OpenAI's entire role: text in, numbers out. It doesn't store or remember anything.
4. **Store (Supabase cloud):** write each chunk's text + vector + metadata (source file, page number) into the `data_support_brain` table. That table is now the "brain" — it lives in the cloud, independent of the script.

**The magic trick of RAG:** texts with similar *meaning* get vectors that are mathematically close. A user's question gets embedded the same way, and Postgres finds the stored vectors nearest to it. That's how "how much for extra luggage?" found the excess-baggage fee table without sharing a single keyword with it.

**Verified with** `scripts/search_test.py`: the baggage question retrieved the prebook-excess-baggage fee table; the refund question retrieved the exact Conditions of Carriage pages. Right sources ranked on top.

**Cost:** embedding the whole corpus ≈ **$0.001**. Ingestion is a one-time "teaching" cost; only questions cost money afterwards (≈1/100,000th of a dollar per query embed).

**Diagram idea (the money flow):**
`PDFs + Web + Sheet → [Load] → [Chunk ×131] → [Embed via OpenAI] → (Supabase pgvector)`
with a callout: "runs once — the brain now lives in the database".

### The `data_support_brain` table (what's visible in Supabase)

Auto-created by the script (LlamaIndex's PGVectorStore). 131 rows = 131 chunks. 5 columns:

| Column | What it holds |
|---|---|
| `id` | auto-number for each row |
| `node_id` | LlamaIndex's internal ID for the chunk |
| `text` | the actual chunk text, human-readable |
| `metadata_` | JSON: source file, page number / sheet row, doc type |
| `embedding` | the vector — 1,536 numbers (this is most of the table's ~1.3 MB) |

**Client-call one-liner:** "Every row is one piece of the airline's documentation, stored twice — once as text a human can read, once as numbers a database can search by meaning."

## W1-4 · RAG query endpoint (done 2026-07-17)

The chatbot is now askable: `POST /ask` on the FastAPI app takes `{"question": "..."}` and returns a grounded answer + the sources it used. The flow per question (this is the diagram's centerpiece):

1. **Retrieve** — embed the incoming question (one tiny OpenAI call, ~1/100,000th of a dollar) and let pgvector find the 4 stored chunks whose vectors sit closest to it.
2. **Augment** — paste those 4 chunks into the prompt, labeled [1]–[4]. The LLM literally cannot see anything else from the corpus.
3. **Generate** — `gpt-4o-mini` (cheap, ~$0.0005/question) writes the answer under a strict system prompt: *answer ONLY from the context; if it's not there, say so and point to IndiGo support; quote numbers exactly.*

That's what RAG stands for: **R**etrieve → **A**ugment → **G**enerate.

**Verified live:** "prepaid excess baggage for 5/10/15kg domestic?" → exact fees (₹3,250 / ₹6,500 / ₹9,750) cited from the right page. "Pet dogs in cabin?" (not in corpus) → the bot *refused to guess* and pointed to support. The refusal is the demo-worthy part — an airline bot that invents refund policy is a liability; one that says "not in my docs" is trustworthy.

**Bug fixed along the way (good war story):** the saved web pages carried double-encoded characters (₹ stored as `â‚¹`). Fixed with the `ftfy` library at ingestion + re-ingested (cost: another $0.001). Lesson: in RAG, garbage in the chunks surfaces verbatim in answers — data cleaning is part of the pipeline, not an afterthought.

**Diagram idea:** user → `POST /ask` → [embed question] → (pgvector: nearest 4 chunks) → [LLM + guardrail prompt] → answer + citations. Side note: "each question ≈ $0.0005".

## W2-1 · Eval dataset (done 2026-07-17)

35 questions with hand-verified correct answers ("ground truths") — the **answer key** the bot gets graded against. 32 answerable + 3 "refusal probes" (questions whose answers are NOT in the docs — the bot passes by admitting it doesn't know). Questions use casual customer phrasing ("bag is overweight") while docs use formal language ("excess baggage charges") — retrieval must bridge that gap. Sanyam reviewed before use: the grader of the system shouldn't be graded by its own author.

**War story:** the corpus contradicts itself twice (additional-piece fee ₹800 in the sheet vs ₹900 in the CoC; excess baggage "starting at ₹1,280" vs cheapest table slab ₹1,950). Real client knowledge bases do this constantly — evals surface it.

## W2-2 · RAGAS baseline (done 2026-07-17)

`scripts/run_eval.py` runs all 35 questions through the bot, then a judge LLM (gpt-4o-mini) scores each answer on 4 metrics. **LLM-as-judge** = a second model grades the first model's work against the retrieved chunks and the answer key.

The 4 metrics in plain words:
- **faithfulness** — did the answer only say things the retrieved chunks support? (anti-hallucination)
- **answer_relevancy** — did it actually answer the question asked?
- **context_precision** — were the retrieved chunks on-topic, or padded with junk?
- **context_recall** — did retrieval find the chunks needed to answer correctly? (measures the retriever, not the writer)

**Baseline (naive vector-only retrieval):** faithfulness 0.883 · answer_relevancy 0.774 · context_precision 0.906 · context_recall 0.911 · refusals 3/3 correct.

**The demo-perfect failure:** Q20 "Is there an extra charge for cancelling through the call centre?" scored context_recall 0.00 — retrieval completely missed the ₹500 facilitation-fee paragraph. Meaning-based (vector) search struggles with keyword-shaped facts. That's precisely what W2-3's hybrid retrieval (vectors + keyword search) exists to fix → the before/after numbers.

**Diagram idea:** a report card with 4 bars (the baseline), one bar circled in red (recall miss on Q20), arrow to "hybrid retrieval" box, second report card with higher bars. THE money shot of the whole project.

## W2-3+ — hybrid retrieval + reranking, Langfuse, W3 delivery — *next*

*(Add sections as milestones complete.)*
