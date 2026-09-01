import { useCallback, useEffect, useRef, useState } from "react";
import { createApiClient, type AlgorithmKey, type AlgorithmSpec, type RunEvent, type RunStatus, type SafetyCounters, type SceneManifest } from "./api/client";
import { SimulationView } from "./components/SimulationView";
import { ComparisonView } from "./components/ComparisonView";
import { HistoryView } from "./components/HistoryView";
import { SceneView } from "./components/SceneView";
import { runStore, type RunStoreSnapshot } from "./state/runStore";

const api = createApiClient();
const TERMINAL_STATUSES: RunStatus[] = ["completed", "stopped", "ended_early", "disconnected", "interrupted", "failed"];

function isTerminalStatus(status: string | undefined): status is RunStatus {
  return status !== undefined && TERMINAL_STATUSES.includes(status as RunStatus);
}

interface EventSubscription {
  runId: string;
  close: () => void;
  intentional: boolean;
}

interface TerminalWaiter {
  resolve: () => void;
  reject: (error: Error) => void;
  timer: number;
}

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

function boundedNumber(value: number, minimum: number, maximum: number, fallback: number): number {
  return Number.isFinite(value) ? Math.min(maximum, Math.max(minimum, value)) : fallback;
}

export default function App() {
  const snapshot = useRunSnapshot();
  const [view, setView] = useState("simulation");
  const [scenes, setScenes] = useState<SceneManifest[]>([]);
  const [algorithms, setAlgorithms] = useState<AlgorithmSpec[]>([]);
  const [results, setResults] = useState<Awaited<ReturnType<typeof api.listResults>>["items"]>([]);
  const [scenesLoading, setScenesLoading] = useState(true);
  const [sceneError, setSceneError] = useState<string | null>(null);
  const [resultsLoading, setResultsLoading] = useState(true);
  const [resultsError, setResultsError] = useState<string | null>(null);
  const [openedResult, setOpenedResult] = useState<Awaited<ReturnType<typeof api.getResult>> | null>(null);
  const [startPending, setStartPending] = useState(false);
  const mounted = useRef(true);
  const resultsRequest = useRef(0);
  const startPendingRef = useRef(false);
  const subscriptionRef = useRef<EventSubscription | null>(null);
  const terminalWaiters = useRef(new Map<string, TerminalWaiter>());

  const loadResults = useCallback(async () => {
    const requestId = ++resultsRequest.current;
    setResultsLoading(true);
    try {
      const resultRows = await api.listResults();
      if (!mounted.current || requestId !== resultsRequest.current) return;
      setResults(resultRows.items);
      setResultsError(null);
    } catch (error: unknown) {
      if (!mounted.current || requestId !== resultsRequest.current) return;
      setResultsError(error instanceof Error ? error.message : "Unable to load sealed run results");
    } finally {
      if (mounted.current && requestId === resultsRequest.current) setResultsLoading(false);
    }
  }, []);

  const closeSubscription = (runId?: string) => {
    const subscription = subscriptionRef.current;
    if (!subscription || (runId && subscription.runId !== runId)) return;
    subscription.intentional = true;
    subscription.close();
    if (subscriptionRef.current === subscription) subscriptionRef.current = null;
  };

  useEffect(() => {
    let cancelled = false;
    void Promise.all([api.listScenes(), api.listAlgorithms()])
      .then(([sceneRows, algorithmRows]) => {
        if (cancelled) return;
        setScenes(sceneRows);
        setAlgorithms(algorithmRows.formal);
      })
      .catch((error: unknown) => {
        if (cancelled) return;
        const message = error instanceof Error ? error.message : "Unable to load judge metadata";
        setSceneError(message);
        runStore.setError({ kind: "network", message });
      })
      .finally(() => {
        if (!cancelled) setScenesLoading(false);
      });
    void loadResults();
    return () => {
      cancelled = true;
    };
  }, [loadResults]);

  useEffect(() => {
    mounted.current = true;
    return () => {
      mounted.current = false;
      resultsRequest.current += 1;
      closeSubscription();
      for (const [runId, waiter] of terminalWaiters.current) {
        window.clearTimeout(waiter.timer);
        waiter.reject(new Error(`Judge console closed while waiting for ${runId}`));
      }
      terminalWaiters.current.clear();
    };
  }, []);

  useEffect(() => {
    if (view === "comparison" || view === "history") void loadResults();
  }, [loadResults, view]);

  useEffect(() => {
    const runId = snapshot.activeRun?.run_id;
    if (!runId || snapshot.connection === "idle" || isTerminalStatus(snapshot.activeRun?.status)) return;
    let cancelled = false;
    let timer: number | null = null;
    const schedule = () => {
      const current = runStore.getSnapshot();
      if (cancelled || current.activeRun?.run_id !== runId || current.connection === "idle" || isTerminalStatus(current.activeRun?.status)) return;
      timer = window.setTimeout(() => void poll(), 80);
    };
    const poll = async () => {
      const before = runStore.getSnapshot();
      if (cancelled || before.activeRun?.run_id !== runId || before.connection === "idle" || isTerminalStatus(before.activeRun?.status)) return;
      try {
        const frame = await api.getFrame(runId, before.frameSequence);
        const current = runStore.getSnapshot();
        if (!cancelled && current.activeRun?.run_id === runId && !isTerminalStatus(current.activeRun.status)) runStore.acceptFrame(frame);
      } catch (error: unknown) {
        const current = runStore.getSnapshot();
        if (!cancelled && current.activeRun?.run_id === runId && (error as { status?: number }).status !== 404) {
          runStore.setError({ kind: "frame", message: error instanceof Error ? error.message : "Frame unavailable" });
        }
      } finally {
        schedule();
      }
    };
    void poll();
    return () => {
      cancelled = true;
      if (timer !== null) window.clearTimeout(timer);
    };
  }, [snapshot.activeRun?.run_id, snapshot.activeRun?.status, snapshot.connection]);

  const onEvent = (runId: string, event: RunEvent) => {
    if (event.run_id !== runId || runStore.getSnapshot().activeRun?.run_id !== runId) return;
    runStore.addEvent(event);
    if (event.type === "metrics" && isRecord(event.metrics)) runStore.setMetrics(event.metrics);
    if (event.type === "safety") {
      const current = runStore.getSnapshot().safety ?? {
        collision: 0,
        red_light: 0,
        illegal_transition: 0,
        harsh_braking: 0,
        teleport: 0,
        potential_conflict: 0,
      };
      const keyByEvent: Record<string, keyof SafetyCounters> = {
        collision: "collision",
        red_light: "red_light",
        illegal_transition: "illegal_transition",
        harsh_braking: "harsh_braking",
        teleport: "teleport",
        potential_conflict: "potential_conflict",
      };
      const key = keyByEvent[String(event.event_type)];
      if (key) runStore.setSafety({ ...current, [key]: current[key] + 1 });
      if (isRecord(event.safety)) runStore.setSafety(event.safety as unknown as SafetyCounters);
    }
    if (event.type === "status" && typeof event.status === "string") {
      runStore.setRunStatus(event.status as RunStatus);
      if (isTerminalStatus(event.status)) {
        const waiter = terminalWaiters.current.get(runId);
        if (waiter) {
          window.clearTimeout(waiter.timer);
          terminalWaiters.current.delete(runId);
          waiter.resolve();
        }
        closeSubscription(runId);
        void loadResults();
        void api.getSafety(runId).then((safety) => runStore.setSafety(safety)).catch(() => undefined);
      }
    }
  };

  const connectEvents = (runId: string) => {
    closeSubscription(runId);
    const subscription: EventSubscription = { runId, close: () => undefined, intentional: false };
    subscription.close = api.subscribeEvents(
      runId,
      (event) => onEvent(runId, event),
      () => {
        if (
          subscriptionRef.current !== subscription
          || subscription.intentional
          || runStore.getSnapshot().activeRun?.run_id !== runId
        ) return;
        subscriptionRef.current = null;
        const current = runStore.getSnapshot();
        if (!isTerminalStatus(current.activeRun?.status)) {
          runStore.setConnection("disconnected");
          runStore.setError({ kind: "disconnected", message: "Realtime connection closed" });
          const waiter = terminalWaiters.current.get(runId);
          if (waiter) {
            window.clearTimeout(waiter.timer);
            terminalWaiters.current.delete(runId);
            waiter.reject(new Error("Realtime connection closed before the demo completed"));
          }
        }
      },
      () => {
        if (
          subscriptionRef.current === subscription
          && !subscription.intentional
          && runStore.getSnapshot().activeRun?.run_id === runId
        ) {
          runStore.setConnection("connected");
          if (runStore.getSnapshot().error?.kind === "disconnected") runStore.setError(null);
        }
      },
    );
    subscriptionRef.current = subscription;
  };

  const submitDemo = async (algorithm: AlgorithmKey, waitForTerminal = false) => {
    closeSubscription();
    runStore.resetRun();
    runStore.setSelection({ selectedAlgorithm: algorithm });
    const selection = runStore.getSnapshot();
    const durationSeconds = boundedNumber(selection.selectedDuration, 5, 3600, 30);
    const warmupSeconds = boundedNumber(selection.selectedWarmup, 0, Math.max(0, durationSeconds - 1), 0);
    const flowMultiplier = boundedNumber(selection.selectedLoad, 0.5, 2, 1);
    const scene = scenes.find((candidate) => candidate.intersection_id === selection.selectedScene);
    const laneTarget = scene?.lane_ids[0] ?? "lane-1";
    const edgeTarget = laneTarget.includes("_")
      ? laneTarget.slice(0, laneTarget.lastIndexOf("_"))
      : laneTarget;
    const disturbance = selection.selectedDisturbance === "none"
      ? null
      : {
          kind: selection.selectedDisturbance,
          begin_seconds: warmupSeconds,
          end_seconds: durationSeconds,
          target: selection.selectedDisturbance === "event_demand" ? edgeTarget : laneTarget,
          intensity: selection.selectedDisturbance === "event_demand" ? 1 : 0.5,
        };
    runStore.setSafety({ collision: 0, red_light: 0, illegal_transition: 0, harsh_braking: 0, teleport: 0, potential_conflict: 0 });
    try {
      const run = await api.startRun({
        intersection_id: selection.selectedScene,
        algorithm,
        flow_multiplier: flowMultiplier,
        seed: boundedNumber(selection.selectedSeed, 0, 2147483647, 42),
        duration_seconds: durationSeconds,
        warmup_seconds: warmupSeconds,
        disturbance,
      });
      if (!mounted.current) return;
      runStore.setActiveRun(run);
      const terminalPromise = waitForTerminal
        ? new Promise<void>((resolve, reject) => {
            const timer = window.setTimeout(() => {
              terminalWaiters.current.delete(run.run_id);
              reject(new Error("Judge demo timed out before terminal status"));
            }, 180_000);
            terminalWaiters.current.set(run.run_id, { resolve, reject, timer });
          })
        : Promise.resolve();
      connectEvents(run.run_id);
      await terminalPromise;
    } catch (error: unknown) {
      runStore.setError({ kind: "network", message: error instanceof Error ? error.message : "Unable to start demo" });
      throw error;
    }
  };

  const startQuickDemo = async () => {
    if (startPendingRef.current) return;
    startPendingRef.current = true;
    setStartPending(true);
    try {
      await submitDemo(runStore.getSnapshot().selectedAlgorithm);
    } catch {
      // submitDemo already exposes the actionable error in the console.
    } finally {
      startPendingRef.current = false;
      if (mounted.current) setStartPending(false);
    }
  };

  const runJudgeSequence = async () => {
    if (startPendingRef.current) return;
    startPendingRef.current = true;
    setStartPending(true);
    try {
      await submitDemo("fixed_time", true);
      await submitDemo("capacity_aware_maxpressure", true);
      await loadResults();
      if (mounted.current) setView("comparison");
    } catch {
      // submitDemo already exposes the actionable error in the console.
    } finally {
      startPendingRef.current = false;
      if (mounted.current) setStartPending(false);
    }
  };

  const reconnectEvents = () => {
    const runId = runStore.getSnapshot().activeRun?.run_id;
    if (runId && !isTerminalStatus(runStore.getSnapshot().activeRun?.status)) connectEvents(runId);
  };

  const stopRun = async () => {
    const runId = runStore.getSnapshot().activeRun?.run_id;
    if (!runId) return;
    try {
      const result = await api.stopRun(runId);
      const waiter = terminalWaiters.current.get(runId);
      if (waiter) {
        window.clearTimeout(waiter.timer);
        terminalWaiters.current.delete(runId);
        waiter.reject(new Error("Judge sequence stopped by the user"));
      }
      closeSubscription(runId);
      runStore.setActiveRun(result);
      runStore.setConnection("idle");
      void loadResults();
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

  const openResult = async (runId: string) => {
    try {
      setOpenedResult(await api.getResult(runId));
    } catch (error: unknown) {
      setResultsError(error instanceof Error ? error.message : "Unable to load sealed summary");
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
          startPending={startPending}
          onStart={() => void startQuickDemo()}
          onSequence={() => void runJudgeSequence()}
          onStop={() => void stopRun()}
          onNativeGui={() => void showNativeGui()}
          onSceneChange={(selectedScene) => runStore.setSelection({ selectedScene })}
          onAlgorithmChange={(selectedAlgorithm) => runStore.setSelection({ selectedAlgorithm: selectedAlgorithm as RunStoreSnapshot["selectedAlgorithm"] })}
          onSelectionChange={(selection) => runStore.setSelection(selection)}
          onReconnect={reconnectEvents}
          onDismissError={() => runStore.setError(null)}
        />
      ) : view === "comparison" ? (
        <ComparisonView results={results} loading={resultsLoading} error={resultsError} />
      ) : view === "history" ? (
        <>
          <HistoryView results={results} loading={resultsLoading} error={resultsError} onOpenResult={(runId) => void openResult(runId)} />
          {openedResult && <pre className="result-detail" aria-label="Sealed result detail">{JSON.stringify(openedResult, null, 2)}</pre>}
        </>
      ) : (
        <SceneView scenes={scenes} loading={scenesLoading} error={sceneError} />
      )}
    </div>
  );
}
