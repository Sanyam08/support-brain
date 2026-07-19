import { useEffect, useState } from "react";
import MetricsChart from "./components/MetricsChart";
import CategoryDumbbells from "./components/CategoryDumbbells";
import QuestionsTable from "./components/QuestionsTable";
import { RUNS, METRICS, BASELINE, FINAL, fmt, fmtDelta } from "./data/runs";

function useTheme() {
  // ?theme=light|dark wins (handy for screen recording), then the saved
  // choice, then the OS setting.
  const [theme, setTheme] = useState(() => {
    const fromUrl = new URLSearchParams(location.search).get("theme");
    if (fromUrl === "light" || fromUrl === "dark") return fromUrl;
    return localStorage.getItem("sb-theme") || "system";
  });
  useEffect(() => {
    const root = document.documentElement;
    if (theme === "system") root.removeAttribute("data-theme");
    else root.setAttribute("data-theme", theme);
    localStorage.setItem("sb-theme", theme);
  }, [theme]);
  const isDark =
    theme === "dark" ||
    (theme === "system" &&
      window.matchMedia("(prefers-color-scheme: dark)").matches);
  return [isDark, () => setTheme(isDark ? "light" : "dark")];
}

function KpiTile({ metric, delay }) {
  const after = FINAL.summary_core[metric.key];
  const before = BASELINE.summary_core[metric.key];
  const delta = after - before;
  const dir = Math.abs(delta) < 0.005 ? "flat" : delta > 0 ? "up" : "down";
  return (
    <div
      className="card tile rise"
      style={{ animationDelay: `${delay}ms` }}
      title={metric.help}
    >
      <div className="label">{metric.label}</div>
      <div className="value">{fmt(after)}</div>
      <div className="delta-row">
        <span className={`delta ${dir}`}>
          {dir === "up" ? "↑" : dir === "down" ? "↓" : ""} {fmtDelta(delta)}
        </span>
        vs baseline
      </div>
    </div>
  );
}

export default function App() {
  const [isDark, toggleTheme] = useTheme();
  const refusals = FINAL.refusal_probes;

  return (
    <div className="shell">
      <header className="header rise">
        <div>
          <h1>
            <span className="logo-dot" />
            Support Brain
            <span className="pill">RAG evaluation</span>
          </h1>
          <p className="sub">
            A production RAG pipeline for airline customer support, measured
            with RAGAS at every upgrade. {FINAL.n_answerable} real questions
            plus {FINAL.n_refusal_probes} refusal probes over a corpus of 131
            document chunks (policy PDFs, web pages, a fee sheet).
          </p>
        </div>
        <button
          className="theme-btn"
          onClick={toggleTheme}
          aria-label="Toggle color theme"
        >
          {isDark ? (
            <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round">
              <circle cx="12" cy="12" r="4" />
              <path d="M12 2v2m0 16v2M4.9 4.9l1.4 1.4m11.4 11.4 1.4 1.4M2 12h2m16 0h2M4.9 19.1l1.4-1.4M17.7 6.3l1.4-1.4" />
            </svg>
          ) : (
            <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
              <path d="M21 12.8A9 9 0 1 1 11.2 3a7 7 0 0 0 9.8 9.8z" />
            </svg>
          )}
        </button>
      </header>

      <div className="kpi-grid">
        {METRICS.map((m, i) => (
          <KpiTile metric={m} key={m.key} delay={40 + i * 50} />
        ))}
      </div>

      <div className="strip">
        <div className="card mini rise" style={{ animationDelay: "240ms" }}>
          <b>3 / 3</b>
          <span>out-of-scope questions correctly refused</span>
        </div>
        <div className="card mini rise" style={{ animationDelay: "280ms" }}>
          <b>$0.0004</b>
          <span>cost per answered question</span>
        </div>
        <div className="card mini rise" style={{ animationDelay: "320ms" }}>
          <b>~4s</b>
          <span>warm latency, question to cited answer</span>
        </div>
        <div className="card mini rise" style={{ animationDelay: "360ms" }}>
          <b>4 stages</b>
          <span>each pipeline change re-evaluated</span>
        </div>
      </div>

      <section className="card section rise" style={{ animationDelay: "160ms" }}>
        <div className="card-head">
          <div className="card-title">Core metrics across pipeline stages</div>
          <div className="card-desc">
            Same 36 questions, judged by RAGAS after every upgrade. Darker bars
            are later stages. Hybrid retrieval and reranking lifted recall;
            grounding rules in the prompt lifted faithfulness. The precision dip
            is a deliberate trade: keeping 6 chunks instead of 4 feeds the LLM
            more context.
          </div>
        </div>
        <div className="card-body">
          <MetricsChart />
        </div>
      </section>

      <div className="cols section">
        <section className="card rise" style={{ animationDelay: "220ms" }}>
          <div className="card-head">
            <div className="card-title">Faithfulness by category</div>
            <div className="card-desc">
              Baseline vs final pipeline. The multi-rule practical questions
              were the hardest: they dipped to 0.514 mid-pipeline and recovered
              to 0.861 once the prompt required explicit arithmetic and labeled
              assumptions.
            </div>
          </div>
          <div className="card-body">
            <CategoryDumbbells />
          </div>
        </section>

        <section className="card rise" style={{ animationDelay: "260ms" }}>
          <div className="card-head">
            <div className="card-title">Refusal probes</div>
            <div className="card-desc">
              Questions the corpus cannot answer. The right behavior is a
              refusal, not a guess.
            </div>
          </div>
          <div className="card-body" style={{ paddingTop: 6 }}>
            {refusals.map((p) => (
              <div className="probe" key={p.id}>
                <div className="q">
                  {p.question}
                  <span className={`badge ${p.refused ? "good" : "neutral"}`}>
                    {p.refused ? "refused" : "answered"}
                  </span>
                </div>
                <div className="a">{p.response}</div>
              </div>
            ))}
            <div className="note">
              Known limit, tracked honestly: one fee figure (a ₹900
              additional-piece charge in the Conditions of Carriage) never
              reaches the top 6 retrieved chunks, so one practical question
              still cites the fee sheet's ₹800 figure instead.
            </div>
          </div>
        </section>
      </div>

      <section className="card section rise" style={{ animationDelay: "300ms" }}>
        <div className="card-head">
          <div className="card-title">Every question, final pipeline</div>
          <div className="card-desc">
            Click a row to read the model's actual answer. Arrows mark scores
            that moved by 0.05 or more vs baseline; scores under 0.75 are
            highlighted.
          </div>
        </div>
        <QuestionsTable />
      </section>

      <footer className="rise" style={{ animationDelay: "340ms" }}>
        <div>
          FastAPI · LlamaIndex · pgvector on Supabase · BM25 + reciprocal rank
          fusion · ms-marco cross-encoder reranker · gpt-4o-mini · RAGAS ·
          Langfuse tracing
        </div>
        <div>
          Built by Sanyam Agarwal. Corpus: public IndiGo policy documents.
          Pipeline stages: {RUNS.map((r) => r.label).join(" → ")}.
        </div>
      </footer>
    </div>
  );
}
