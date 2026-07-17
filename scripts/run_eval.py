"""RAGAS eval harness: run the eval dataset through the RAG pipeline and score it.

Usage:
    python scripts/run_eval.py --limit 3 --name smoke              # cheap plumbing test (~$0.05)
    python scripts/run_eval.py --name baseline_naive               # full run (~$0.25-0.50)
    python scripts/run_eval.py --ids 36-39 --name practical_naive --merge-into baseline_naive

Answerable questions get 4 RAGAS metrics (LLM-as-judge, gpt-4o-mini):
  - faithfulness:      is the answer supported by the retrieved chunks? (anti-hallucination)
  - answer_relevancy:  does the answer actually address the question?
  - context_precision: are the retrieved chunks relevant (little junk)?
  - context_recall:    did retrieval find the chunks needed for the ground truth?
Refusal probes (answerable=false) are scored separately: did the bot decline to guess?

Scores are reported per category. The headline "summary" averages every category EXCEPT
'practical' — those need labeled assumptions, which RAGAS faithfulness penalizes by design,
so they get their own row in summary_by_category instead of muddying the core numbers.

--merge-into appends this run's rows into an existing results file (same id wins = newest),
recomputing all summaries — used to extend a saved baseline apples-to-apples.

Results land in data/evals/results/<name>.json — the before/after numbers for the dashboard.
"""
import argparse
import json
import re
import sys
from pathlib import Path

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parent.parent
load_dotenv(ROOT / ".env")
sys.path.insert(0, str(ROOT))

JUDGE_MODEL = "gpt-4o-mini"  # judging is pattern-matching against provided text; mini is fine
NON_METRIC_COLS = ("user_input", "response", "retrieved_contexts", "reference")
REFUSAL_MARKERS = re.compile(
    r"don'?t have|do not have|not (?:available|contain|mentioned|specified)|no information"
    r"|contact indigo|reach out to indigo|unable to find|cannot find",
    re.IGNORECASE,
)


def parse_ids(spec: str) -> set[int]:
    """'36-39' or '1,5,20' or a mix like '1,36-39'."""
    ids = set()
    for part in spec.split(","):
        if "-" in part:
            lo, hi = part.split("-")
            ids.update(range(int(lo), int(hi) + 1))
        else:
            ids.add(int(part))
    return ids


def summarize(per_question: list[dict]) -> tuple[dict, dict]:
    """Headline summary (all categories except 'practical') + per-category breakdown."""
    metric_keys = sorted({k for r in per_question for k in r if k not in ("id", "question", "category")})

    def means(rows):
        return {k: round(sum(r[k] for r in rows) / len(rows), 4) for k in metric_keys} if rows else {}

    core = [r for r in per_question if r.get("category") != "practical"]
    by_cat = {}
    for cat in sorted({r.get("category", "?") for r in per_question}):
        rows = [r for r in per_question if r.get("category") == cat]
        by_cat[cat] = {"n": len(rows), **means(rows)}
    return means(core), by_cat


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--limit", type=int, default=0, help="only run the first N questions (0 = all)")
    parser.add_argument("--ids", help="only run these question ids, e.g. '36-39' or '1,5,20'")
    parser.add_argument("--name", required=True, help="results file name, e.g. baseline_naive")
    parser.add_argument("--merge-into", help="append results into this existing results file")
    args = parser.parse_args()

    all_items = json.loads((ROOT / "data" / "evals" / "eval_dataset.json").read_text(encoding="utf-8"))["items"]
    category_of = {it["id"]: it["category"] for it in all_items}
    items = all_items
    if args.ids:
        wanted = parse_ids(args.ids)
        items = [it for it in items if it["id"] in wanted]
    if args.limit:
        items = items[: args.limit]

    # ---- Step 1: run every question through OUR pipeline (same code the API uses)
    from app.rag import answer

    print(f"Running {len(items)} questions through the RAG pipeline...")
    records = []
    for it in items:
        out = answer(it["question"], include_contexts=True)
        records.append({**it, "response": out["answer"], "contexts": out["contexts"]})
        print(f"  [{it['id']:>2}] {it['question'][:60]}")

    answerable = [r for r in records if r["answerable"]]
    probes = [r for r in records if not r["answerable"]]

    # ---- Step 2: refusal probes — plain string check, no LLM judge needed
    for p in probes:
        p["refused"] = bool(REFUSAL_MARKERS.search(p["response"]))

    # ---- Step 3: RAGAS metrics on answerable questions
    per_question = []
    if answerable:
        from langchain_openai import ChatOpenAI, OpenAIEmbeddings
        from ragas import EvaluationDataset, evaluate
        from ragas.llms import LangchainLLMWrapper
        from ragas.embeddings import LangchainEmbeddingsWrapper
        from ragas.metrics import answer_relevancy, context_precision, context_recall, faithfulness

        dataset = EvaluationDataset.from_list(
            [
                {
                    "user_input": r["question"],
                    "response": r["response"],
                    "retrieved_contexts": r["contexts"],
                    "reference": r["ground_truth"],
                }
                for r in answerable
            ]
        )
        print(f"\nScoring {len(answerable)} answerable questions with RAGAS ({JUDGE_MODEL} judge)...")
        result = evaluate(
            dataset=dataset,
            metrics=[faithfulness, answer_relevancy, context_precision, context_recall],
            llm=LangchainLLMWrapper(ChatOpenAI(model=JUDGE_MODEL, temperature=0)),
            embeddings=LangchainEmbeddingsWrapper(OpenAIEmbeddings(model="text-embedding-3-small")),
        )
        df = result.to_pandas()
        metric_cols = [c for c in df.columns if c not in NON_METRIC_COLS]
        for r, (_, row) in zip(answerable, df.iterrows()):
            per_question.append(
                {
                    "id": r["id"],
                    "question": r["question"],
                    "category": r["category"],
                    **{c: round(float(row[c]), 4) for c in metric_cols},
                }
            )

    new_probe_rows = [
        {"id": p["id"], "question": p["question"], "refused": p["refused"], "response": p["response"]}
        for p in probes
    ]
    new_response_rows = [{"id": r["id"], "question": r["question"], "response": r["response"]} for r in answerable]

    # ---- Step 4: optionally merge into an existing results file (newest id wins)
    results_dir = ROOT / "data" / "evals" / "results"
    results_dir.mkdir(parents=True, exist_ok=True)
    out_name = args.merge_into or args.name

    if args.merge_into:
        existing = json.loads((results_dir / f"{args.merge_into}.json").read_text(encoding="utf-8"))

        def merge(old_rows, new_rows):
            by_id = {r["id"]: r for r in old_rows}
            for r in new_rows:
                by_id[r["id"]] = r
            return [by_id[i] for i in sorted(by_id)]

        per_question = merge(existing.get("per_question", []), per_question)
        for r in per_question:  # older baseline rows predate the category field
            r.setdefault("category", category_of.get(r["id"], "?"))
        new_probe_rows = merge(existing.get("refusal_probes", []), new_probe_rows)
        new_response_rows = merge(existing.get("responses", []), new_response_rows)

    summary, by_cat = summarize(per_question)
    refusal_rate = (
        sum(p["refused"] for p in new_probe_rows) / len(new_probe_rows) if new_probe_rows else None
    )
    out = {
        "name": out_name,
        "n_answerable": len(per_question),
        "n_refusal_probes": len(new_probe_rows),
        "summary_core": summary,
        "summary_by_category": by_cat,
        "refusal_accuracy": refusal_rate,
        "per_question": per_question,
        "refusal_probes": new_probe_rows,
        "responses": new_response_rows,
    }
    path = results_dir / f"{out_name}.json"
    path.write_text(json.dumps(out, indent=2, ensure_ascii=False), encoding="utf-8")

    print(f"\n===== {out_name} (core = all categories except practical) =====")
    for k, v in summary.items():
        print(f"  {k:<22} {v:.3f}")
    if refusal_rate is not None:
        print(f"  {'refusal_accuracy':<22} {refusal_rate:.3f}  ({sum(p['refused'] for p in new_probe_rows)}/{len(new_probe_rows)} probes correctly refused)")
    print("  --- by category ---")
    for cat, row in by_cat.items():
        metrics = "  ".join(f"{k}={v:.2f}" for k, v in row.items() if k != "n")
        print(f"  {cat:<22} n={row['n']}  {metrics}")
    print(f"Saved to {path.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
