import type { ResultListItem } from "../api/client";
import { algorithmName, localizeMessage, metricName, statusName } from "../localization";

interface HistoryViewProps {
  results: ResultListItem[];
  loading: boolean;
  error: string | null;
  onOpenResult: (runId: string) => void;
}

function summaryRows(result: ResultListItem): Array<[string, string]> {
  const nested = result.summary.metrics;
  const metrics = typeof nested === "object" && nested !== null ? nested as Record<string, unknown> : result.summary;
  const rows: Array<[string, string]> = [];
  for (const [key, value] of Object.entries(metrics)) {
    if (value === null) rows.push([key, "不可用"]);
    else if (typeof value === "number" && Number.isFinite(value)) rows.push([key, value.toFixed(2)]);
    if (rows.length === 3) break;
  }
  return rows;
}

export function HistoryView({ results, loading, error, onOpenResult }: HistoryViewProps) {
  return (
    <main className="judge-view history-view">
      <div className="view-heading">
        <div>
          <p className="eyebrow">封存运行记录</p>
          <h2>运行历史</h2>
        </div>
        <span className="evidence-badge">封存运行证据</span>
      </div>
      {loading && <p role="status">正在加载运行历史…</p>}
      {error && <p className="inline-error" role="alert">{localizeMessage(error)}</p>}
      {!loading && !error && results.length === 0 && <p className="empty-state">暂无封存运行记录。</p>}
      {!loading && !error && results.length > 0 && (
        <section className="history-list" aria-label="封存结果历史">
          {results.map((result) => {
            const summary = summaryRows(result);
            return <article className="history-row" key={result.run_id}>
              <div>
                <h3>{result.run_id}</h3>
                <p>{algorithmName(result.algorithm)}</p>
                {summary.length > 0 && <dl className="history-summary">{summary.map(([key, value]) => <div key={key}><dt>{metricName(key)}</dt><dd>{value}</dd></div>)}</dl>}
                <button type="button" onClick={() => onOpenResult(result.run_id)}>打开封存摘要</button>
              </div>
              <div className="history-meta">
                <span className={`status status-${result.status}`}>{statusName(result.status)}</span>
                <span>场景 {result.scene_id}</span>
                <span>{result.reason ? localizeMessage(result.reason) : "已完成并生成封存摘要"}</span>
              </div>
            </article>;
          })}
        </section>
      )}
    </main>
  );
}
