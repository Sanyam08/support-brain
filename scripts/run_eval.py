"""RAGAS eval harness: run the eval dataset through the RAG pipeline and score it.

Usage:
    python scripts/run_eval.py --limit 3 --name smoke      # cheap plumbing test (~$0.05)
    python scripts/run_eval.py --name baseline_naive       # full run (~$0.25-0.50)

Answerable questions get 4 RAGAS metrics (LLM-as-judge, gpt-4o-mini):
  - faithfulness:      is the answer supported by the retrieved chunks? (anti-hallucination)
  - answer_relevancy:  does the answer actually address the question?
  - context_precision: are the retrieved chunks relevant (little junk)?
  - context_recall:    did retrieval find the chunks needed for the ground truth?
Refusal probes (answerable=false) are scored separately: did the bot decline to guess?

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
REFUSAL_MARKERS = re.compile(
    r"don'?t have|do not have|not (?:available|contain|mentioned|specified)|no information"
    r"|contact indigo|reach out to indigo|unable to find|cannot find",
    re.IGNORECASE,
)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--limit", type=int, default=0, help="only run the first N questions (0 = all)")
    parser.add_argument("--name", required=True, help="results file name, e.g. baseline_naive")
    args = parser.parse_args()

    items = json.loads((ROOT / "data" / "evals" / "eval_dataset.json").read_text(encoding="utf-8"))["items"]
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
    scores_summary, per_question = {}, []
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
        metric_cols = [c for c in df.columns if c not in ("user_input", "response", "retrieved_contexts", "reference")]
        scores_summary = {c: round(float(df[c].mean()), 4) for c in metric_cols}
        for r, (_, row) in zip(answerable, df.iterrows()):
            per_question.append(
                {"id": r["id"], "question": r["question"], **{c: round(float(row[c]), 4) for c in metric_cols}}
            )

    # ---- Step 4: save + print
    refusal_rate = (sum(p["refused"] for p in probes) / len(probes)) if probes else None
    out = {
        "name": args.name,
        "n_answerable": len(answerable),
        "n_refusal_probes": len(probes),
        "summary": scores_summary,
        "refusal_accuracy": refusal_rate,
        "per_question": per_question,
        "refusal_probes": [
            {"id": p["id"], "question": p["question"], "refused": p["refused"], "response": p["response"]}
            for p in probes
        ],
        "responses": [
            {"id": r["id"], "question": r["question"], "response": r["response"]} for r in answerable
        ],
    }
    results_dir = ROOT / "data" / "evals" / "results"
    results_dir.mkdir(parents=True, exist_ok=True)
    path = results_dir / f"{args.name}.json"
    path.write_text(json.dumps(out, indent=2, ensure_ascii=False), encoding="utf-8")

    print(f"\n===== {args.name} =====")
    for k, v in scores_summary.items():
        print(f"  {k:<22} {v:.3f}")
    if refusal_rate is not None:
        print(f"  {'refusal_accuracy':<22} {refusal_rate:.3f}  ({sum(p['refused'] for p in probes)}/{len(probes)} probes correctly refused)")
    print(f"Saved to {path.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
