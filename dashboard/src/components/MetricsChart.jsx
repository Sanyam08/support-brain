import {
  BarChart,
  Bar,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  LabelList,
  ResponsiveContainer,
} from "recharts";
import { RUNS, METRICS, fmt } from "../data/runs";

// Grouped bars: one group per core metric, one bar per pipeline stage.
// Stages are ordered, so they wear a single-hue ordinal ramp (light to dark),
// not four unrelated colors.
//
// All colors are applied through CSS classes (see index.css): SVG presentation
// attributes cannot resolve var(), and CSS keeps the chart in sync with the
// theme toggle.
const chartData = METRICS.map((m) => {
  const row = { metric: m.label };
  for (const run of RUNS) row[run.key] = run.data.summary_core[m.key];
  return row;
});

const reducedMotion = window.matchMedia(
  "(prefers-reduced-motion: reduce)"
).matches;

function ChartTip({ active, payload, label }) {
  if (!active || !payload || !payload.length) return null;
  return (
    <div className="tip">
      <div className="t">{label}</div>
      {payload.map((p) => {
        const run = RUNS.find((r) => r.key === p.dataKey);
        return (
          <div className="row" key={p.dataKey}>
            <span
              className="swatch"
              style={{
                width: 9,
                height: 9,
                borderRadius: 3,
                background: run.color,
              }}
            />
            {run.label}
            <b>{fmt(p.value)}</b>
          </div>
        );
      })}
    </div>
  );
}

export default function MetricsChart() {
  return (
    <>
      <ResponsiveContainer width="100%" height={300}>
        <BarChart data={chartData} barGap={2} barCategoryGap="22%">
          <CartesianGrid vertical={false} />
          <XAxis
            dataKey="metric"
            tickLine={false}
            tick={{ fontSize: 12.5 }}
            className="x-axis"
          />
          <YAxis
            domain={[0, 1]}
            ticks={[0, 0.25, 0.5, 0.75, 1]}
            tickLine={false}
            axisLine={false}
            tick={{ fontSize: 12 }}
            width={34}
            className="y-axis"
          />
          <Tooltip
            content={<ChartTip />}
            cursor={{ className: "chart-cursor" }}
          />
          {RUNS.map((run, i) => (
            <Bar
              key={run.key}
              dataKey={run.key}
              className={`bar-run-${i + 1}`}
              radius={[4, 4, 0, 0]}
              isAnimationActive={!reducedMotion}
              animationDuration={600}
              animationEasing="ease-out"
            >
              {/* Selective direct labels: only the final stage gets a number. */}
              {i === RUNS.length - 1 ? (
                <LabelList
                  dataKey={run.key}
                  position="top"
                  formatter={(v) => fmt(v)}
                  style={{
                    fill: "var(--fg)",
                    fontSize: 11.5,
                    fontWeight: 600,
                  }}
                />
              ) : null}
            </Bar>
          ))}
        </BarChart>
      </ResponsiveContainer>
      <div className="legend">
        {RUNS.map((run) => (
          <div className="item" key={run.key} title={run.desc}>
            <span className="swatch" style={{ background: run.color }} />
            {run.label}
          </div>
        ))}
      </div>
    </>
  );
}
