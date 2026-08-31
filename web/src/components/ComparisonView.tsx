import { useMemo, useState } from "react";
import { Bar, BarChart, CartesianGrid, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import type { ResultListItem } from "../api/client";
import { algorithmName, localizeMessage, unitName } from "../localization";

interface ComparisonViewProps {
  results: ResultListItem[];
  loading: boolean;
  error: string | null;
}

const METRICS = [
  { key: "avg_queue_length", label: "平均排队长度", unit: "辆" },
  { key: "throughput", label: "通行量", unit: "辆" },
  { key: "avg_delay", label: "平均延误", unit: "秒" },
  { key: "avg_travel_time", label: "平均行程时间", unit: "秒" },
  { key: "fuel_ml", label: "燃油消耗", unit: "毫升" },
  { key: "co2_g", label: "二氧化碳排放", unit: "克" },
  { key: "collision_count", label: "碰撞次数", unit: "次" },
  { key: "red_light_count", label: "闯红灯次数", unit: "次" },
  { key: "illegal_transition_count", label: "非法相位切换次数", unit: "次" },
  { key: "harsh_braking_count", label: "急刹车次数", unit: "次" },
  { key: "teleport_count", label: "车辆传送次数", unit: "次" },
  { key: "potential_conflict_count", label: "潜在冲突次数", unit: "次" },
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
  if (value === null) return "不可用";
  if (value === undefined) return "未报告";
  if (typeof value !== "number" || !Number.isFinite(value)) return "未报告";
  if (unit === "count" || unit === "次") return String(value);
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
        ? [{ algorithm: algorithmName(result.algorithm), value }]
        : [];
    }),
  }));
  return (
    <main className="judge-view comparison-view">
      <div className="view-heading">
        <div>
          <p className="eyebrow">已验证结果集</p>
          <h2>算法对比</h2>
        </div>
        <span className="evidence-badge">封存运行证据</span>
      </div>
      <p className="evidence-note">这些记录是单次运行的封存证据，不代表正式矩阵结论；缺失指标不会被推断或补零。</p>
      {results.length > 0 && <label className="comparison-filter">对比场景
        <select aria-label="对比场景" value={effectiveScene} onChange={(event) => setSelectedScene(event.target.value)}>
          {sceneIds.map((sceneId) => <option key={sceneId} value={sceneId}>{sceneId}</option>)}
        </select>
      </label>}
      {loading && <p role="status">正在加载封存运行结果…</p>}
      {error && <p className="inline-error" role="alert">{localizeMessage(error)}</p>}
      {!loading && !error && results.length === 0 && <p className="empty-state">暂无已验证结果。</p>}
      {!loading && !error && visibleResults.length > 0 && (
        <section className="comparison-panel" aria-labelledby="comparison-table-title">
          <div className="panel-heading">
            <h3 id="comparison-table-title">单次运行指标</h3>
            <span>延误和排队越低越好，通行量越高越好。</span>
          </div>
          <p>硬性安全门槛：碰撞、闯红灯和非法相位切换。</p>
          <p>观测性安全指标：急刹车、车辆传送和潜在冲突。</p>
          <div className="comparison-chart" data-testid="comparison-chart" role="region" aria-label="封存运行结果对比">
            <div className="chart-grid">
              {series.map((metric) => (
                <section className="metric-chart" key={metric.key} aria-label={`${metric.label}图表`}>
                  <h4>{metric.label} <small>{unitName(metric.unit)}</small></h4>
                  {metric.rows.length > 0 ? (
                    <ResponsiveContainer width="100%" height={190}>
                      <BarChart data={metric.rows} margin={{ top: 8, right: 12, bottom: 30, left: 8 }}>
                        <CartesianGrid strokeDasharray="3 3" />
                        <XAxis dataKey="algorithm" angle={-18} textAnchor="end" interval={0} height={55} tick={{ fontSize: 10 }} />
                        <YAxis width={52} tick={{ fontSize: 10 }} />
                        <Tooltip formatter={(value) => [`${Number(value).toFixed(2)} ${unitName(metric.unit)}`, metric.label]} />
                        <Bar dataKey="value" fill="#176b72" radius={[3, 3, 0, 0]} />
                      </BarChart>
                    </ResponsiveContainer>
                  ) : <p>暂无数值序列。</p>}
                </section>
              ))}
            </div>
            <table>
              <thead>
                <tr>
                  <th scope="col">算法</th>
                  {METRICS.map((metric) => <th key={metric.key} scope="col">{metric.label}<small>{unitName(metric.unit)}</small></th>)}
                </tr>
              </thead>
              <tbody>
                {visibleResults.map((result) => {
                  const metrics = metricRecord(result);
                  const units = unitRecord(result);
                  return (
                    <tr key={result.run_id}>
                      <th scope="row">{algorithmName(result.algorithm)}<small>来源：{result.run_id}</small></th>
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
          <p className="chart-footnote">正式的 95% 置信区间尚未生成，需等待任务 22 完成并封存 540 次运行矩阵。缺失值会明确保留，绝不会转换为零。</p>
        </section>
      )}
    </main>
  );
}
