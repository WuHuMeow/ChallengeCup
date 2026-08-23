import { useMemo, useState } from "react";
import { Bar, BarChart, CartesianGrid, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import type { ResultListItem } from "../api/client";

interface ComparisonViewProps {
  results: ResultListItem[];
  loading: boolean;
  error: string | null;
}

const ALGORITHM_NAMES: Record<string, string> = {
  fixed_time: "Fixed-time baseline",
  actuated: "Actuated baseline",
  classic_maxpressure: "Classic MaxPressure",
  capacity_aware_maxpressure: "Capacity-aware MaxPressure",
};

const METRICS = [
  { key: "avg_queue_length", label: "Average queue length", unit: "vehicles" },
  { key: "throughput", label: "Throughput", unit: "vehicles" },
  { key: "avg_delay", label: "Average delay", unit: "seconds" },
  { key: "avg_travel_time", label: "Average travel time", unit: "seconds" },
  { key: "fuel_ml", label: "Fuel", unit: "ml" },
  { key: "co2_g", label: "CO2", unit: "g" },
  { key: "collision_count", label: "Collisions", unit: "count" },
  { key: "red_light_count", label: "Red-light violations", unit: "count" },
  { key: "illegal_transition_count", label: "Illegal transitions", unit: "count" },
  { key: "harsh_braking_count", label: "Harsh braking", unit: "count" },
  { key: "teleport_count", label: "Teleports", unit: "count" },
  { key: "potential_conflict_count", label: "Potential conflicts", unit: "count" },
];

function metricRecord(result: ResultListItem): Record<string, unknown> {
  const nested = result.summary.metrics;
  return typeof nested === "object" && nested !== null ? nested as Record<string, unknown> : result.summary;
}

function unitRecord(result: ResultListItem): Record<string, unknown> {
  const nested = result.summary.units;
  return typeof nested === "object" && nested !== null ? nested as Record<string, unknown> : {};
}

function formatValue(value: unknown, unit: string): string {
  if (value === null) return "Unavailable";
  if (value === undefined) return "Not reported";
  if (typeof value !== "number" || !Number.isFinite(value)) return "Not reported";
  if (unit === "count") return String(value);
  return value.toFixed(2);
}

export function ComparisonView({ results, loading, error }: ComparisonViewProps) {
  const sceneIds = useMemo(() => Array.from(new Set(results.map((result) => result.scene_id))), [results]);
  const [selectedScene, setSelectedScene] = useState("");
  const effectiveScene = sceneIds.includes(selectedScene) ? selectedScene : sceneIds[0] || "";
  const visibleResults = results.filter((result) => result.scene_id === effectiveScene);
  const series = METRICS.map((metric) => ({
    ...metric,
    unit: visibleResults
      .map((result) => unitRecord(result)[metric.key])
      .find((unit): unit is string => typeof unit === "string") ?? metric.unit,
    rows: visibleResults.flatMap((result) => {
      const value = metricRecord(result)[metric.key];
      return typeof value === "number" && Number.isFinite(value)
        ? [{ algorithm: ALGORITHM_NAMES[result.algorithm] ?? result.algorithm, value }]
        : [];
    }),
  }));
  return (
    <main className="judge-view comparison-view">
      <div className="view-heading">
        <div>
          <p className="eyebrow">Verified result set</p>
          <h2>Comparison</h2>
        </div>
        <span className="evidence-badge">Sealed run evidence</span>
      </div>
      <p className="evidence-note">These rows are sealed individual-run evidence, not a formal matrix conclusion. Missing metrics are never inferred.</p>
      {results.length > 0 && <label className="comparison-filter">Comparison scene
        <select aria-label="Comparison scene" value={effectiveScene} onChange={(event) => setSelectedScene(event.target.value)}>
          {sceneIds.map((sceneId) => <option key={sceneId} value={sceneId}>{sceneId}</option>)}
        </select>
      </label>}
      {loading && <p role="status">Loading sealed run results...</p>}
      {error && <p className="inline-error" role="alert">{error}</p>}
      {!loading && !error && results.length === 0 && <p className="empty-state">No validated results available.</p>}
      {!loading && !error && visibleResults.length > 0 && (
        <section className="comparison-panel" aria-labelledby="comparison-table-title">
          <div className="panel-heading">
            <h3 id="comparison-table-title">Individual-run metrics</h3>
            <span>Lower is better for delay and queue; higher is better for throughput.</span>
          </div>
          <p>Hard safety gates: collisions, red-light violations, and illegal transitions.</p>
          <p>Observational safety: harsh braking, teleports, and potential conflicts.</p>
          <div className="comparison-chart" data-testid="comparison-chart" role="region" aria-label="Sealed run result comparison">
            <div className="chart-grid">
              {series.map((metric) => (
                <section className="metric-chart" key={metric.key} aria-label={`${metric.label} chart`}>
                  <h4>{metric.label} <small>{metric.unit}</small></h4>
                  {metric.rows.length > 0 ? (
                    <ResponsiveContainer width="100%" height={190}>
                      <BarChart data={metric.rows} margin={{ top: 8, right: 12, bottom: 30, left: 8 }}>
                        <CartesianGrid strokeDasharray="3 3" />
                        <XAxis dataKey="algorithm" angle={-18} textAnchor="end" interval={0} height={55} tick={{ fontSize: 10 }} />
                        <YAxis width={52} tick={{ fontSize: 10 }} />
                        <Tooltip formatter={(value) => [`${Number(value).toFixed(2)} ${metric.unit}`, metric.label]} />
                        <Bar dataKey="value" fill="#176b72" radius={[3, 3, 0, 0]} />
                      </BarChart>
                    </ResponsiveContainer>
                  ) : <p>No numeric series available.</p>}
                </section>
              ))}
            </div>
            <table>
              <thead>
                <tr>
                  <th scope="col">Algorithm</th>
                  {METRICS.map((metric) => <th key={metric.key} scope="col">{metric.label}<small>{metric.unit}</small></th>)}
                </tr>
              </thead>
              <tbody>
                {visibleResults.map((result) => {
                  const metrics = metricRecord(result);
                  const units = unitRecord(result);
                  return (
                    <tr key={result.run_id}>
                      <th scope="row">{ALGORITHM_NAMES[result.algorithm] ?? result.algorithm}<small>source: {result.run_id}</small></th>
                      {METRICS.map((metric) => {
                        const reportedUnit = units[metric.key];
                        const unit = typeof reportedUnit === "string" ? reportedUnit : metric.unit;
                        return <td key={metric.key}>{formatValue(metrics[metric.key], unit)}</td>;
                      })}
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
          <p className="chart-footnote">Formal 95% CI has not yet been generated; it awaits Task 22&apos;s complete sealed 540-run matrix. Missing values remain explicit and are never converted to zero.</p>
        </section>
      )}
    </main>
  );
}
