import { metricName } from "../localization";

interface MetricPanelProps {
  metrics: Record<string, unknown>;
}

function displayValue(value: unknown): string {
  if (value === null || value === undefined) return "不可用";
  if (typeof value === "number") return Number.isFinite(value) ? value.toFixed(2) : "不可用";
  if (typeof value === "string" || typeof value === "boolean") return String(value);
  return "有详细数据";
}

export function MetricPanel({ metrics }: MetricPanelProps) {
  const rows = Object.entries(metrics).slice(0, 8);
  return (
    <section aria-labelledby="metric-panel-title" className="metric-panel">
      <h2 id="metric-panel-title">实时指标</h2>
      {rows.length === 0 ? <p>尚未收到指标数据</p> : (
        <dl>
          {rows.map(([key, value]) => <div key={key}><dt>{metricName(key)}</dt><dd>{displayValue(value)}</dd></div>)}
        </dl>
      )}
    </section>
  );
}
