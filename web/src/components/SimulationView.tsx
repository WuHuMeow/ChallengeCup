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
  startPending: boolean;
  onStart: () => void;
  onSequence: () => void;
  onStop: () => void;
  onNativeGui: () => void;
  onSceneChange: (sceneId: string) => void;
  onAlgorithmChange: (algorithm: string) => void;
  onSelectionChange: (selection: Partial<Pick<RunStoreSnapshot, "selectedLoad" | "selectedSeed" | "selectedDuration" | "selectedWarmup" | "selectedDisturbance">>) => void;
  onReconnect: () => void;
  onDismissError: () => void;
}

export function SimulationView({
  snapshot,
  scenes,
  algorithms,
  startPending,
  onStart,
  onSequence,
  onStop,
  onNativeGui,
  onSceneChange,
  onAlgorithmChange,
  onSelectionChange,
  onReconnect,
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
      <p className="evidence-note">Sealed individual-run evidence is shown only for verified results from the evidence API; formal matrix conclusions await Task 22.</p>
      <ErrorBanner error={snapshot.error} onDismiss={onDismissError} onReconnect={onReconnect} />
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
        <label>
          Flow multiplier
          <input type="number" min="0.5" max="2" step="0.25" value={snapshot.selectedLoad} onChange={(event) => onSelectionChange({ selectedLoad: Number(event.target.value) })} />
        </label>
        <label>
          Seed
          <input type="number" min="0" step="1" value={snapshot.selectedSeed} onChange={(event) => onSelectionChange({ selectedSeed: Number(event.target.value) })} />
        </label>
        <label>
          Duration (s)
          <input type="number" min="5" max="3600" step="5" value={snapshot.selectedDuration} onChange={(event) => onSelectionChange({ selectedDuration: Number(event.target.value) })} />
        </label>
        <label>
          Warmup (s)
          <input type="number" min="0" max={Math.max(0, snapshot.selectedDuration - 1)} step="5" value={snapshot.selectedWarmup} onChange={(event) => onSelectionChange({ selectedWarmup: Number(event.target.value) })} />
        </label>
        <label>
          Disturbance
          <select value={snapshot.selectedDisturbance} onChange={(event) => onSelectionChange({ selectedDisturbance: event.target.value as RunStoreSnapshot["selectedDisturbance"] })}>
            <option value="none">None</option>
            <option value="construction">Construction closure</option>
            <option value="event_demand">Event demand</option>
            <option value="vehicle_failure">Vehicle failure</option>
          </select>
        </label>
        <div className="button-row">
          <button type="button" onClick={onStart} disabled={startPending || (active && snapshot.connection !== "idle")}>
            <Play size={16} aria-hidden="true" /> Start quick demo
          </button>
          <button type="button" onClick={onSequence} disabled={startPending || (active && snapshot.connection !== "idle")}>
            <Play size={16} aria-hidden="true" /> Run judge sequence
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
        <div className="simulation-side-panel">
          <MetricPanel metrics={snapshot.metrics} />
          <section className="safety-panel" aria-label="Safety counters">
            <h2>Safety counters</h2>
            {snapshot.safety ? (
              <dl>
                <div><dt>Collision</dt><dd>{snapshot.safety.collision}</dd></div>
                <div><dt>Red light</dt><dd>{snapshot.safety.red_light}</dd></div>
                <div><dt>Illegal transition</dt><dd>{snapshot.safety.illegal_transition}</dd></div>
                <div><dt>Harsh braking</dt><dd>{snapshot.safety.harsh_braking}</dd></div>
                <div><dt>Teleport</dt><dd>{snapshot.safety.teleport}</dd></div>
                <div><dt>Potential conflict</dt><dd>{snapshot.safety.potential_conflict}</dd></div>
              </dl>
            ) : <p>No safety observations received</p>}
          </section>
          {typeof snapshot.metrics.current_phase_name === "string" && (
            <p className="phase-status">Phase: {snapshot.metrics.current_phase_name} · {typeof snapshot.metrics.elapsed_phase_time === "number" ? snapshot.metrics.elapsed_phase_time : 0} s</p>
          )}
        </div>
      </section>
    </main>
  );
}
