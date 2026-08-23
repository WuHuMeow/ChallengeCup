import { useEffect, useState } from "react";
import { createApiClient, type AlgorithmSpec, type SceneManifest } from "./api/client";
import { runStore, type RunStoreSnapshot } from "./state/runStore";

const api = createApiClient();
const EMPTY_PNG = "data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADElEQVR42mNk+M/wHwAF/gL+e7QeVQAAAABJRU5ErkJggg==";

function useRunSnapshot(): RunStoreSnapshot {
  const [snapshot, setSnapshot] = useState(runStore.getSnapshot());
  useEffect(() => runStore.subscribe(() => setSnapshot(runStore.getSnapshot())), []);
  return snapshot;
}

export default function App() {
  const snapshot = useRunSnapshot();
  const [view, setView] = useState("simulation");
  const [scenes, setScenes] = useState<SceneManifest[]>([]);
  const [algorithms, setAlgorithms] = useState<AlgorithmSpec[]>([]);
  const [pollToken, setPollToken] = useState(0);

  useEffect(() => {
    void Promise.all([api.listScenes(), api.listAlgorithms()])
      .then(([sceneRows, algorithmRows]) => {
        setScenes(sceneRows);
        setAlgorithms(algorithmRows.formal);
      })
      .catch((error: unknown) => runStore.setError({ kind: "network", message: error instanceof Error ? error.message : "Unable to load judge metadata" }));
  }, []);

  useEffect(() => {
    const runId = snapshot.activeRun?.run_id;
    if (!runId) return;
    let cancelled = false;
    const poll = async () => {
      if (cancelled) return;
      try {
        const frame = await api.getFrame(runId, runStore.getSnapshot().frameSequence);
        runStore.acceptFrame(frame);
        if (!cancelled && runStore.getSnapshot().frameSequence !== null) {
          window.setTimeout(poll, 80);
        }
      } catch (error: unknown) {
        if (!cancelled && (error as { status?: number }).status !== 404) {
          runStore.setError({ kind: "frame", message: error instanceof Error ? error.message : "Frame unavailable" });
        }
      }
    };
    void poll();
    return () => {
      cancelled = true;
    };
  }, [snapshot.activeRun?.run_id, pollToken]);

  const startQuickDemo = async () => {
    runStore.resetRun();
    const selection = runStore.getSnapshot();
    try {
      const run = await api.startRun({
        intersection_id: selection.selectedScene,
        algorithm: selection.selectedAlgorithm,
        flow_multiplier: selection.selectedLoad,
        seed: 42,
        duration_seconds: 30,
        warmup_seconds: 0,
      });
      runStore.setActiveRun(run);
      setPollToken((token) => token + 1);
    } catch (error: unknown) {
      runStore.setError({ kind: "network", message: error instanceof Error ? error.message : "Unable to start demo" });
    }
  };

  return (
    <div>
      <header>
        <h1>Judge Simulation Console</h1>
        <nav aria-label="Primary">
          {["simulation", "comparison", "history", "scene"].map((key) => (
            <button key={key} type="button" onClick={() => setView(key)} aria-current={view === key ? "page" : undefined}>
              {key[0].toUpperCase() + key.slice(1)}
            </button>
          ))}
        </nav>
      </header>
      {view === "simulation" ? (
        <main>
          <p>Quick demo output</p>
          <p>Formal evidence: sealed results only</p>
          <label>
            Scene
            <select aria-label="Scene" value={snapshot.selectedScene} onChange={(event) => runStore.setSelection({ selectedScene: event.target.value })}>
              {(scenes.length ? scenes : [{ scene_id: "1", intersection_id: "1", name: "Intersection 1" } as SceneManifest]).map((scene) => <option key={scene.scene_id} value={scene.intersection_id}>{scene.name}</option>)}
            </select>
          </label>
          <label>
            Algorithm
            <select aria-label="Algorithm" value={snapshot.selectedAlgorithm} onChange={(event) => runStore.setSelection({ selectedAlgorithm: event.target.value as typeof snapshot.selectedAlgorithm })}>
              {(algorithms.length ? algorithms : [{ key: "fixed_time", display_name: "Fixed Time" } as AlgorithmSpec]).map((algorithm) => <option key={algorithm.key} value={algorithm.key}>{algorithm.display_name}</option>)}
            </select>
          </label>
          <button type="button" onClick={() => void startQuickDemo()}>Start quick demo</button>
          <div aria-live="polite">{snapshot.error?.message}</div>
          <div>
            <img src={snapshot.frameUrl ?? EMPTY_PNG} alt="SUMO simulation frame" data-testid="sumo-frame" />
            <span data-testid="frame-sequence">{snapshot.frameSequence ?? "-"}</span>
            <span data-testid="simulation-time">{snapshot.simulationTime ?? "-"}</span>
          </div>
        </main>
      ) : <main><h2>{view[0].toUpperCase() + view.slice(1)}</h2></main>}
    </div>
  );
}
