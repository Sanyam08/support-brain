# Support Brain — Quiz Q&A (study file)

Started 2026-07-17 after the W2-3 hybrid-retrieval session. Format: the question,
what Sanyam answered, what was right/wrong, the full explanation, and a
"client-call one-liner" to reuse in videos and sales calls.

---

## Q1. Walk through what happens between a question arriving and the answer coming back.

**Your answer:** "It first goes to the LLM, it understands it and finds relevant
chunks from the database, retrieves the answer, and the LLM forms an answer
according to the prompt."

**Right:** chunks come from the database; the LLM writes the final answer per the prompt.

**Wrong:** the LLM is NOT the thing that searches. It never touches the database
and doesn't see the question until the very last step.

**The real pipeline (v2, current):**
1. **Embedding model** (text-embedding-3-small — not an LLM, cannot write) turns the
   question into a vector (~1,536 numbers capturing its meaning).
2. **pgvector** (Supabase) finds the 8 stored chunks whose vectors are nearest — pure math.
3. **BM25** simultaneously keyword-scores all 131 chunks, takes its own top 8 — pure word statistics.
4. **RRF fusion** merges both lists into 10 candidates; the **cross-encoder reranker**
   re-reads each against the question and keeps the best 6.
5. **Only now the LLM** (gpt-4o-mini) gets one prompt: system rules + those 6 chunks
   pasted as text + the question. It writes the answer from that text only.

Also: retrieval never finds "the answer" — it finds chunks of raw document text that
*probably contain* the answer. If the right chunk isn't retrieved, the LLM can't be right.

**Client-call line:** "The LLM is the writer, not the librarian. Cheap specialized
tools fetch the right pages; the LLM only writes from those pages — and is
forbidden from using anything else."

---

## Q2. Why did Q20 (call-centre cancellation fee) score ZERO with pure vector search, and why did BM25 fix it?

**Your answer:** "BM25 works as a ctrl+F but simpler, gives more relevant answers;
vector search was searching linearly and gave top 4 relevant chunks."

**Right:** the ctrl+F instinct.

**Wrong:** "searching linearly" isn't a thing, BM25 is a *smarter* (not simpler)
ctrl+F, and neither method is universally "more relevant."

**The blur problem:** the corpus has a dozen chunks that all mean "some IndiGo fee
for some booking action" (change fees, refund fees, agent fees, page-printing fees…).
Embeddings compress each chunk into one meaning-vector, so they all land in the same
neighborhood of the map, packed tightly. The specific ₹500 call-centre chunk ranked
7th-nearest — outside the old top-4 cut. Not a malfunction: compressing a paragraph
into one vector inherently blurs fine distinctions.

**Why BM25 nailed it:** BM25 = ctrl+F + weighting: **rare words count more** (IDF).
"Fee" appears everywhere → worth ~nothing. "Call centre" appears in 2-3 chunks →
matching it is a huge signal. BM25 put the gold chunk at rank #1.

**Neither is better overall — they fail in opposite directions.** Paraphrased
question ("phone booking charge") → BM25 helpless, vectors shine. Exact rare term
("call centre fee") → reversed. That's the entire case for hybrid.

**Client-call line:** "Semantic search finds meaning but blurs specifics; keyword
search nails specifics but can't handle paraphrasing. Production systems run both."

---

## Q3. What IS an embedding, and what does "close/similar" actually mean?

**Your answer:** "LlamaIndex finds similar chunks and puts them together — wherever
cancellation/cancel/delete/remove appears it's stored in one vector. A 50-page PDF
can't be ingested at once, so we break it into ~125 chunks of ~2 paragraphs."

**Right:** the chunking half (we really have 131 chunks of ~512 tokens ≈ 1-2 paragraphs).

**Wrong:** nothing is grouped or merged. **Every chunk gets its own vector: 131
chunks = 131 vectors.** Similar words never share a vector.

**The map model:** a vector is a list of 1,536 numbers = **coordinates** — a location
on a giant "meaning map." The embedding model (trained on billions of texts) answers
one question per chunk: *where does this text live on the map?* Chunks about
cancellation fees get pinned in the cancellation-fee neighborhood; pet-travel chunks
get pinned far away. Chunks *using* cancel/delete/remove end up **near each other**
because the model learned those words mean similar things — synonyms become
neighbors without anyone programming it.

"Similar" = the question gets pinned on the same map, and retrieval is literally
"which chunk-pins are nearest to the question-pin?" — a distance calculation.

**Why chunk small (the deeper reason):** one vector per 50-page PDF = ONE pin trying
to represent baggage AND refunds AND pets AND liability = pinned in the middle of
nowhere, matching nothing well. It's Q2's blur problem at maximum scale. Small
chunks = one precise pin per specific meaning. Bonus: the LLM gets 6 relevant
paragraphs, not 50 pages.

**Client-call line:** "An embedding is coordinates for meaning. We pin every
paragraph on a map, pin the question too, and grab its nearest neighbors. Chunk
small, or the pins land in mush."

---

## Q4. Faithfulness vs context_recall — what does each measure, and what failure does each catch?

*(Sanyam asked for this one explained directly — it's the eval-dashboard story for the video.)*

The four RAGAS metrics grade the two halves of the pipeline separately:

| metric | grades | question it asks | failure it catches |
|---|---|---|---|
| **context_recall** | the librarian (retrieval) | "Did the retrieved chunks contain the facts needed for the correct answer?" | **Blindness** — the right chunk never reached the LLM |
| **context_precision** | the librarian | "Of the chunks retrieved, how many were actually relevant?" | **Junk** — prompt stuffed with noise |
| **faithfulness** | the writer (LLM) | "Is every claim in the answer supported by the retrieved chunks?" | **Hallucination** — the LLM inventing beyond its sources |
| **answer_relevancy** | the writer | "Does the answer actually address what was asked?" | **Dodging** — accurate text that answers the wrong question |

**High faithfulness + low recall — the dangerous combo.** Real example from our own
runs: Q15 ("by when do I cancel?") in the rerank-4 run. Retrieval fetched real but
WRONG chunks (the 48-hour free-cancellation window). The LLM faithfully summarized
them. Perfectly grounded, zero invention — and the customer got the wrong deadline.
Faithfulness can't see this failure; only recall can. A bot that always says "I
don't know" is also perfectly faithful and perfectly useless.

**High recall + low faithfulness — the opposite.** Our practical questions after the
hybrid upgrade: retrieval now delivers the ₹700/kg fee (recall fine), but the LLM
does its own unlabeled arithmetic ("20kg × ₹700 = ₹14,000, and a wine bottle weighs
about 1.3kg…") — claims not literally in any chunk. Faithfulness fell to 0.51.
Recall can't see this failure; only faithfulness can.

**Why this matters for the video:** one blended "accuracy score" would hide which
half broke. Separate metrics = diagnosis, not just a grade → you know whether to fix
the librarian (retrieval work, like W2-3) or the writer (prompt work, up next).

**Client-call line:** "Faithfulness catches lying; recall catches blindness. You
need both, because each one is blind to the other's failure."

---

## Q5. Why does the RAG brain live behind FastAPI, with n8n only doing delivery — instead of building the whole thing in n8n?

*(Attempt it before reading. Hint: strategic rule #2 in the roadmap, and think about
what the eval harness imports.)*

**The architecture:** `app/rag.py` holds the brain (retrieve → fuse → rerank →
generate). FastAPI wraps it in a `POST /ask` endpoint. WhatsApp (n8n), the web
widget, and the eval harness are all just *callers* of that same brain.

**Reason 1 — one brain, many mouths.** WhatsApp, web widget, eval harness: three
consumers, zero duplicated logic. Improve retrieval once (like W2-3 did) and every
channel gets it instantly. Built inside n8n, the logic would be trapped in one
workflow — the widget would need a copy, and copies drift apart.

**Reason 2 — evals must measure the REAL system.** `run_eval.py` imports the same
`answer()` function the API serves. The scores describe production itself, not a
lookalike. If the brain lived in an n8n workflow, the eval harness would have to
call a re-implementation — and the before/after numbers would be about the copy.

**Reason 3 — right tool per layer (roadmap rule #2).** n8n is unbeatable at
integration plumbing: WhatsApp webhooks, auth, channel quirks, retries — days of
boring code you get for free. But hybrid retrieval + reranking + eval harnesses
need real Python libraries (LlamaIndex, torch, RAGAS) that don't exist as n8n nodes.
So: **n8n = integration/delivery layer, Python/FastAPI = reasoning layer.** The
hybrid is the point — don't rebuild in code what n8n does faster, don't force into
n8n what needs code.

**Reason 4 — the reranker physically needs a Python process.** The cross-encoder is
~90MB of model weights loaded into the FastAPI process's memory. There's nowhere for
it to live inside an n8n workflow.

**Client-call line:** "n8n owns the channels, Python owns the reasoning. One brain,
many mouths — and the evals grade the exact brain that customers talk to."
