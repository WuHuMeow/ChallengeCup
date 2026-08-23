import type { ResultListItem } from "../api/client";

interface HistoryViewProps {
  results: ResultListItem[];
  loading: boolean;
  error: string | null;
  onOpenResult: (runId: string) => void;
}

const ALGORITHM_NAMES: Record<string, string> = {
  fixed_time: "Fixed-time baseline",
  actuated: "Actuated baseline",
  classic_maxpressure: "Classic MaxPressure",
  capacity_aware_maxpressure: "Capacity-aware MaxPressure",
};

function summaryRows(result: ResultListItem): Array<[string, string]> {
  const nested = result.summary.metrics;
  const metrics = typeof nested === "object" && nested !== null ? nested as Record<string, unknown> : result.summary;
  const rows: Array<[string, string]> = [];
  for (const [key, value] of Object.entries(metrics)) {
    if (value === null) rows.push([key, "Unavailable"]);
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
          <p className="eyebrow">Sealed run records</p>
          <h2>History</h2>
        </div>
        <span className="evidence-badge">Sealed run evidence</span>
      </div>
      {loading && <p role="status">Loading result history...</p>}
      {error && <p className="inline-error" role="alert">{error}</p>}
      {!loading && !error && results.length === 0 && <p className="empty-state">No sealed runs available.</p>}
      {!loading && !error && results.length > 0 && (
        <section className="history-list" aria-label="Sealed result history">
          {results.map((result) => {
            const summary = summaryRows(result);
            return <article className="history-row" key={result.run_id}>
              <div>
                <h3>{result.run_id}</h3>
                <p>{ALGORITHM_NAMES[result.algorithm] ?? result.algorithm}</p>
                {summary.length > 0 && <dl className="history-summary">{summary.map(([key, value]) => <div key={key}><dt>{key.replace(/_/g, " ")}</dt><dd>{value}</dd></div>)}</dl>}
                <button type="button" onClick={() => onOpenResult(result.run_id)}>Open sealed summary</button>
              </div>
              <div className="history-meta">
                <span className={`status status-${result.status}`}>{result.status}</span>
                <span>Scene {result.scene_id}</span>
                <span>{result.reason || "Completed with sealed summary"}</span>
              </div>
            </article>;
          })}
        </section>
      )}
    </main>
  );
}
