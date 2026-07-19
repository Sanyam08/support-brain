// The four RAGAS eval runs, in pipeline order. Raw JSON is committed as-is
// from scripts/run_eval.py output; nothing here is hand-edited.
import baseline from "./baseline_naive.json";
import hybrid from "./after_hybrid.json";
import rerank from "./after_hybrid_rerank6.json";
import prompt from "./after_prompt.json";

export const RUNS = [
  {
    key: "baseline_naive",
    label: "Baseline",
    desc: "Naive vector search, top 4 chunks straight to the LLM",
    color: "var(--run-1)",
    data: baseline,
  },
  {
    key: "after_hybrid",
    label: "Hybrid retrieval",
    desc: "Vector search plus BM25 keyword search, fused with reciprocal rank fusion",
    color: "var(--run-2)",
    data: hybrid,
  },
  {
    key: "after_hybrid_rerank6",
    label: "Hybrid + reranker",
    desc: "Cross-encoder reranks the fused pool and keeps the best 6 chunks",
    color: "var(--run-3)",
    data: rerank,
  },
  {
    key: "after_prompt",
    label: "Final: prompt rules",
    desc: "Adds grounding rules: show arithmetic, label assumptions, flag conflicting figures",
    color: "var(--run-4)",
    data: prompt,
  },
];

export const METRICS = [
  {
    key: "faithfulness",
    label: "Faithfulness",
    help: "Share of claims in the answer that are supported by the retrieved documents",
  },
  {
    key: "context_recall",
    label: "Context recall",
    help: "Did retrieval surface the chunks needed to answer the question?",
  },
  {
    key: "context_precision",
    label: "Context precision",
    help: "How much of what was retrieved was actually relevant",
  },
  {
    key: "answer_relevancy",
    label: "Answer relevancy",
    help: "Does the answer directly address what was asked?",
  },
];

export const BASELINE = RUNS[0].data;
export const FINAL = RUNS[RUNS.length - 1].data;

export const CATEGORY_LABELS = {
  baggage_allowance: "Baggage allowance",
  cancellations_refunds: "Cancellations, refunds",
  check_in_boarding: "Check-in, boarding",
  fees: "Fees",
  liability: "Liability",
  practical: "Practical (multi-rule)",
  special_items: "Special items",
};

export const fmt = (v) => (v == null ? "?" : v.toFixed(3));
export const fmtDelta = (v) => (v >= 0 ? "+" : "") + v.toFixed(3);
