import { MonitorPlay, Play, Square } from "lucide-react";
import type { AlgorithmSpec, JudgeApiClient, SceneManifest } from "../api/client";
import type { RunStoreSnapshot } from "../state/runStore";
import { ErrorBanner } from "./ErrorBanner";
import { MetricPanel } from "./MetricPanel";
import { SumoFrame } from "./SumoFrame";

interface SimulationViewProps {
  api: JudgeApiClient;
  snapshot: RunStoreSnapshot;
  scenes: SceneManifest[];
  algorithms: AlgorithmSpec[];
  onStart: () => void;
  onStop: () => void;
  onNativeGui: () => void;
  onSceneChange: (sceneId: string) => void;
  onAlgorithmChange: (algorithm: string) => void;
  onDismissError: () => void;
}

export function SimulationView({
  snapshot,
  scenes,
  algorithms,
  onStart,
  onStop,
  onNativeGui,
  onSceneChange,
  onAlgorithmChange,
  onDismissError,
}: SimulationViewProps) {
  const active = Boolean(snapshot.activeRun);
  return (
    <main className="simulation-view">
      <div className="view-heading">
        <div>
          <p className="eyebrow">Judge workflow</p>
          <h2>Live simulation</h2>
        </div>
        <span className="demo-badge">Quick demo output</span>
      </div>
      <p className="evidence-note">Formal evidence is shown only for sealed results from the evidence API.</p>
      <ErrorBanner error={snapshot.error} onDismiss={onDismissError} />
      <section className="control-panel" aria-label="Simulation controls">
        <label>
          Scene
          <select value={snapshot.selectedScene} onChange={(event) => onSceneChange(event.target.value)}>
            {(scenes.length ? scenes : [{ scene_id: "1", intersection_id: "1", name: "Intersection 1" } as SceneManifest]).map((scene) => (
              <option key={scene.scene_id} value={scene.intersection_id}>{scene.name}</option>
            ))}
          </select>
        </label>
        <label>
          Algorithm
          <select value={snapshot.selectedAlgorithm} onChange={(event) => onAlgorithmChange(event.target.value)}>
            {(algorithms.length ? algorithms : [{ key: "fixed_time", display_name: "Fixed Time" } as AlgorithmSpec]).map((algorithm) => (
              <option key={algorithm.key} value={algorithm.key}>{algorithm.display_name}</option>
            ))}
          </select>
        </label>
        <div className="button-row">
          <button type="button" onClick={onStart} disabled={active && snapshot.connection !== "idle"}>
            <Play size={16} aria-hidden="true" /> Start quick demo
          </button>
          <button type="button" onClick={onStop} disabled={!active}>
            <Square size={16} aria-hidden="true" /> Stop run
          </button>
          <button type="button" onClick={onNativeGui} disabled={!active} title="Show native SUMO GUI">
            <MonitorPlay size={16} aria-hidden="true" /> Show native SUMO GUI
          </button>
        </div>
      </section>
      <div className="status-strip" aria-live="polite">
        <span>Status: {snapshot.activeRun?.status ?? "idle"}</span>
        <span>Connection: {snapshot.connection}</span>
        {snapshot.activeRun?.reason && <span>{snapshot.activeRun.reason}</span>}
      </div>
      <section className="simulation-grid">
        <SumoFrame src={snapshot.frameUrl} sequence={snapshot.frameSequence} simulationTime={snapshot.simulationTime} />
        <MetricPanel metrics={snapshot.metrics} />
      </section>
    </main>
  );
}
