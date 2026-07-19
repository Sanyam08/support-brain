import { BASELINE, FINAL, CATEGORY_LABELS, fmt } from "../data/runs";

// Before/after per category is exactly the dumbbell's job: gray dot = baseline,
// blue dot = final pipeline, a faint segment showing the move. Plain HTML/CSS,
// no chart library needed.
const rows = Object.keys(CATEGORY_LABELS)
  .map((key) => ({
    key,
    label: CATEGORY_LABELS[key],
    n: FINAL.summary_by_category[key]?.n,
    before: BASELINE.summary_by_category[key]?.faithfulness,
    after: FINAL.summary_by_category[key]?.faithfulness,
  }))
  .filter((r) => r.before != null && r.after != null)
  .sort((a, b) => b.after - b.before - (a.after - a.before));

const pct = (v) => `${(v * 100).toFixed(1)}%`;

export default function CategoryDumbbells() {
  return (
    <div>
      {rows.map((r) => {
        const lo = Math.min(r.before, r.after);
        const hi = Math.max(r.before, r.after);
        return (
          <div className="db-row" key={r.key}>
            <div className="db-label">
              {r.label} <span className="n">n={r.n}</span>
            </div>
            <div
              className="db-track"
              title={`${r.label}: ${fmt(r.before)} baseline, ${fmt(r.after)} final`}
            >
              <div className="db-rail" />
              <div
                className="db-seg"
                style={{ left: pct(lo), width: pct(hi - lo) }}
              />
              <div className="db-dot before" style={{ left: pct(r.before) }} />
              <div className="db-dot after" style={{ left: pct(r.after) }} />
            </div>
            <div className="db-vals">
              {fmt(r.before)} <b>{fmt(r.after)}</b>
            </div>
          </div>
        );
      })}
      <div className="legend" style={{ marginTop: 10 }}>
        <div className="item">
          <span
            className="swatch"
            style={{ background: "var(--muted)", borderRadius: "50%" }}
          />
          Baseline
        </div>
        <div className="item">
          <span
            className="swatch"
            style={{ background: "var(--accent)", borderRadius: "50%" }}
          />
          Final pipeline
        </div>
      </div>
    </div>
  );
}
