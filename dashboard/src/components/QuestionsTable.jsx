import { useMemo, useState } from "react";
import { BASELINE, FINAL, CATEGORY_LABELS, fmt, fmtDelta } from "../data/runs";

const LOW = 0.75; // scores under this get flagged in the table

function Score({ value, base }) {
  const delta = base != null ? value - base : null;
  return (
    <td className={`num score-cell ${value < LOW ? "score-low" : ""}`}>
      {fmt(value)}
      {delta != null && Math.abs(delta) >= 0.05 && (
        <span className={delta > 0 ? "d-up" : "d-down"}>
          {delta > 0 ? "↑" : "↓"}
          {fmtDelta(delta).replace("+", "").replace("-", "")}
        </span>
      )}
    </td>
  );
}

export default function QuestionsTable() {
  const [cat, setCat] = useState("all");
  const [open, setOpen] = useState(null);

  const baseById = useMemo(() => {
    const m = new Map();
    for (const q of BASELINE.per_question) m.set(q.id, q);
    return m;
  }, []);
  const answerById = useMemo(() => {
    const m = new Map();
    for (const r of FINAL.responses) m.set(r.id, r.response);
    return m;
  }, []);

  const cats = ["all", ...Object.keys(CATEGORY_LABELS)];
  const rows = FINAL.per_question.filter(
    (q) => cat === "all" || q.category === cat
  );

  return (
    <>
      <div className="filters">
        {cats.map((c) => (
          <button
            key={c}
            className={`chip ${cat === c ? "on" : ""}`}
            onClick={() => setCat(c)}
          >
            {c === "all" ? `All (${FINAL.per_question.length})` : CATEGORY_LABELS[c]}
          </button>
        ))}
      </div>
      <div className="table-wrap">
        <table>
          <thead>
            <tr>
              <th className="q-text">Question</th>
              <th>Category</th>
              <th className="num" title="Arrows show the change vs baseline where it moved by 0.05 or more">
                Faithfulness
              </th>
              <th className="num">Recall</th>
              <th className="num">Precision</th>
              <th className="num">Relevancy</th>
            </tr>
          </thead>
          <tbody>
            {rows.map((q) => {
              const base = baseById.get(q.id);
              const isOpen = open === q.id;
              return [
                <tr
                  key={q.id}
                  className="q-row"
                  onClick={() => setOpen(isOpen ? null : q.id)}
                >
                  <td className="q-text">
                    <span className={`caret ${isOpen ? "open" : ""}`}>
                      {"▶"}
                    </span>
                    {q.question}
                  </td>
                  <td>
                    <span className="badge neutral">
                      {CATEGORY_LABELS[q.category]}
                    </span>
                  </td>
                  <Score value={q.faithfulness} base={base?.faithfulness} />
                  <Score value={q.context_recall} base={base?.context_recall} />
                  <Score value={q.context_precision} base={null} />
                  <Score value={q.answer_relevancy} base={null} />
                </tr>,
                isOpen && (
                  <tr key={`${q.id}-answer`}>
                    <td colSpan={6} className="answer-cell">
                      <div className="inner">{answerById.get(q.id)}</div>
                    </td>
                  </tr>
                ),
              ];
            })}
          </tbody>
        </table>
      </div>
    </>
  );
}
