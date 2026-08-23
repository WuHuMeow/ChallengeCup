import { useEffect, useRef, useState } from "react";
import { createApiClient, type AlgorithmSpec, type RunEvent, type RunStatus, type SafetyCounters, type SceneManifest } from "./api/client";
import { SimulationView } from "./components/SimulationView";
import { runStore, type RunStoreSnapshot } from "./state/runStore";

const api = createApiClient();

function useRunSnapshot(): RunStoreSnapshot {
  const [snapshot, setSnapshot] = useState(runStore.getSnapshot());
  useEffect(() => {
    const unsubscribe = runStore.subscribe(() => setSnapshot(runStore.getSnapshot()));
    return () => unsubscribe();
  }, []);
  return snapshot;
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null;
}

export default function App() {
  const snapshot = useRunSnapshot();
  const [view, setView] = useState("simulation");
  const [scenes, setScenes] = useState<SceneManifest[]>([]);
  const [algorithms, setAlgorithms] = useState<AlgorithmSpec[]>([]);
  const unsubscribeEvents = useRef<(() => void) | null>(null);

  useEffect(() => {
    void Promise.all([api.listScenes(), api.listAlgorithms()])
      .then(([sceneRows, algorithmRows]) => {
        setScenes(sceneRows);
        setAlgorithms(algorithmRows.formal);
      })
      .catch((error: unknown) => runStore.setError({ kind: "network", message: error instanceof Error ? error.message : "Unable to load judge metadata" }));
  }, []);

  useEffect(() => () => unsubscribeEvents.current?.(), []);

  useEffect(() => {
    const runId = snapshot.activeRun?.run_id;
    if (!runId || snapshot.connection === "idle") return;
    let cancelled = false;
    const poll = async () => {
      if (cancelled || runStore.getSnapshot().connection === "idle") return;
      try {
        const frame = await api.getFrame(runId, runStore.getSnapshot().frameSequence);
        runStore.acceptFrame(frame);
        if (!cancelled && runStore.getSnapshot().connection !== "idle") window.setTimeout(poll, 80);
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
  }, [snapshot.activeRun?.run_id, snapshot.connection]);

  const onEvent = (event: RunEvent) => {
    runStore.addEvent(event);
    if (event.type === "metrics" && isRecord(event.metrics)) runStore.setMetrics(event.metrics);
    if (event.type === "safety" && isRecord(event.safety)) runStore.setSafety(event.safety as unknown as SafetyCounters);
    if (event.type === "status" && typeof event.status === "string") runStore.setRunStatus(event.status as RunStatus);
  };

  const startQuickDemo = async () => {
    unsubscribeEvents.current?.();
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
      unsubscribeEvents.current = api.subscribeEvents(run.run_id, onEvent, () => runStore.setConnection("disconnected"));
    } catch (error: unknown) {
      runStore.setError({ kind: "network", message: error instanceof Error ? error.message : "Unable to start demo" });
    }
  };

  const stopRun = async () => {
    const runId = runStore.getSnapshot().activeRun?.run_id;
    if (!runId) return;
    try {
      const result = await api.stopRun(runId);
      unsubscribeEvents.current?.();
      runStore.setActiveRun(result);
      runStore.setConnection("idle");
    } catch (error: unknown) {
      runStore.setError({ kind: "http", message: error instanceof Error ? error.message : "Unable to stop run" });
    }
  };

  const showNativeGui = async () => {
    const runId = runStore.getSnapshot().activeRun?.run_id;
    if (!runId) return;
    try {
      await api.openNativeGui(runId);
    } catch (error: unknown) {
      const typed = error as { message?: string; status?: number };
      runStore.setError({ kind: "http", message: typed.message ?? "Native SUMO GUI unavailable", status: typed.status });
    }
  };

  return (
    <div className="app-shell">
      <header className="app-header">
        <div>
          <p className="eyebrow">XH-202613 · Judge release</p>
          <h1>Judge Simulation Console</h1>
        </div>
        <nav aria-label="Primary">
          {["simulation", "comparison", "history", "scene"].map((key) => (
            <button key={key} type="button" onClick={() => setView(key)} aria-current={view === key ? "page" : undefined}>
              {key[0].toUpperCase() + key.slice(1)}
            </button>
          ))}
        </nav>
      </header>
      {view === "simulation" ? (
        <SimulationView
          api={api}
          snapshot={snapshot}
          scenes={scenes}
          algorithms={algorithms}
          onStart={() => void startQuickDemo()}
          onStop={() => void stopRun()}
          onNativeGui={() => void showNativeGui()}
          onSceneChange={(selectedScene) => runStore.setSelection({ selectedScene })}
          onAlgorithmChange={(selectedAlgorithm) => runStore.setSelection({ selectedAlgorithm: selectedAlgorithm as RunStoreSnapshot["selectedAlgorithm"] })}
          onDismissError={() => runStore.setError(null)}
        />
      ) : <main className="placeholder-view"><h2>{view[0].toUpperCase() + view.slice(1)}</h2></main>}
    </div>
  );
}
