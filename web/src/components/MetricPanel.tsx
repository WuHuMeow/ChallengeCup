interface MetricPanelProps {
  metrics: Record<string, unknown>;
}

function displayValue(value: unknown): string {
  if (value === null || value === undefined) return "Unavailable";
  if (typeof value === "number") return Number.isFinite(value) ? value.toFixed(2) : "Unavailable";
  if (typeof value === "string" || typeof value === "boolean") return String(value);
  return "Details available";
}

export function MetricPanel({ metrics }: MetricPanelProps) {
  const rows = Object.entries(metrics).slice(0, 8);
  return (
    <section aria-labelledby="metric-panel-title" className="metric-panel">
      <h2 id="metric-panel-title">Live metrics</h2>
      {rows.length === 0 ? <p>No metrics received</p> : (
        <dl>
          {rows.map(([key, value]) => <div key={key}><dt>{key.replace(/_/g, " ")}</dt><dd>{displayValue(value)}</dd></div>)}
        </dl>
      )}
    </section>
  );
}
