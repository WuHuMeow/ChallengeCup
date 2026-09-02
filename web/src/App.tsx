import { useCallback, useEffect, useRef, useState } from "react";
import { createApiClient, type AlgorithmKey, type AlgorithmSpec, type RunEvent, type RunStatus, type SafetyCounters, type SceneManifest } from "./api/client";
import { SimulationView } from "./components/SimulationView";
import { ComparisonView } from "./components/ComparisonView";
import { HistoryView } from "./components/HistoryView";
import { SceneView } from "./components/SceneView";
import { localizeMessage } from "./localization";
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
  const [guiDelayPending, setGuiDelayPending] = useState(false);
  const mounted = useRef(true);
  const resultsRequest = useRef(0);
  const startPendingRef = useRef(false);
  const subscriptionRef = useRef<EventSubscription | null>(null);
  const nativeGuiAutofocusRun = useRef<string | null>(null);

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
      setResultsError(localizeMessage(error instanceof Error ? error.message : "无法加载封存运行结果"));
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

  const updateActiveRun = (runId: string, update: () => void) => {
    if (mounted.current && runStore.getSnapshot().activeRun?.run_id === runId) update();
  };

  useEffect(() => {
    let cancelled = false;
    void Promise.all([api.listScenes(), api.listAlgorithms()])
      .then(([sceneRows, algorithmRows]) => {
        if (cancelled) return;
        setScenes(sceneRows);
        setAlgorithms(
          [...algorithmRows.formal, ...algorithmRows.optional].filter(
            (algorithm) => algorithm.available,
          ),
        );
      })
      .catch((error: unknown) => {
        if (cancelled) return;
        const message = localizeMessage(error instanceof Error ? error.message : "无法加载评审元数据");
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
      nativeGuiAutofocusRun.current = null;
      closeSubscription();
    };
  }, []);

  useEffect(() => {
    if (view === "comparison" || view === "history") void loadResults();
  }, [loadResults, view]);

  const focusNativeGuiWhenReady = async (runId: string) => {
    const maxAttempts = 8;
    for (let attempt = 1; attempt <= maxAttempts; attempt += 1) {
      const current = runStore.getSnapshot();
      if (
        !mounted.current
        || nativeGuiAutofocusRun.current !== runId
        || current.activeRun?.run_id !== runId
        || isTerminalStatus(current.activeRun.status)
      ) return;
      try {
        await api.openNativeGui(runId);
        if (nativeGuiAutofocusRun.current === runId) nativeGuiAutofocusRun.current = null;
        return;
      } catch (error: unknown) {
        const typed = error as { message?: string; status?: number };
        if (typed.status === 409 && attempt < maxAttempts) {
          await new Promise<void>((resolve) => window.setTimeout(resolve, 250));
          continue;
        }
        if (runStore.getSnapshot().activeRun?.run_id === runId) {
          runStore.setError({
            kind: "http",
            message: localizeMessage(typed.message ?? "Native SUMO GUI unavailable"),
            status: typed.status,
          });
        }
        if (nativeGuiAutofocusRun.current === runId) nativeGuiAutofocusRun.current = null;
        return;
      }
    }
  };

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
      if (event.status === "running" && nativeGuiAutofocusRun.current === runId) {
        void focusNativeGuiWhenReady(runId);
      }
      if (isTerminalStatus(event.status)) {
        if (nativeGuiAutofocusRun.current === runId) nativeGuiAutofocusRun.current = null;
        closeSubscription(runId);
        void loadResults();
        if (event.status === "completed" || event.status === "ended_early") {
          void api.getMetrics(runId)
            .then((metrics) => updateActiveRun(runId, () => runStore.setMetrics(metrics)))
            .catch(() => undefined);
          void api.getSafety(runId)
            .then((safety) => updateActiveRun(runId, () => runStore.setSafety(safety)))
            .catch(() => undefined);
        }
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
          runStore.setError({ kind: "disconnected", message: "实时连接已关闭" });
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

  const submitDemo = async (algorithm: AlgorithmKey) => {
    closeSubscription();
    nativeGuiAutofocusRun.current = null;
    runStore.resetRun();
    runStore.setSelection({ selectedAlgorithm: algorithm });
    const selection = runStore.getSnapshot();
    const durationSeconds = boundedNumber(selection.selectedDuration, 5, 3600, 300);
    const warmupSeconds = boundedNumber(selection.selectedWarmup, 0, Math.max(0, durationSeconds - 1), 0);
    const guiDelayMs = Math.round(boundedNumber(selection.selectedGuiDelayMs, 0, 2000, 100));
    const flowMultiplier = boundedNumber(selection.selectedLoad, 0.5, 2, 1);
    const scene = scenes.find((candidate) => candidate.intersection_id === selection.selectedScene);
    const sceneStepLength = scene?.step_length && scene.step_length > 0 ? scene.step_length : 1;
    const stepLength = Number.isFinite(selection.selectedStepLength) && selection.selectedStepLength > 0
      ? selection.selectedStepLength
      : sceneStepLength;
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
        gui_delay_ms: guiDelayMs,
        step_length_override: stepLength,
        disturbance,
      });
      if (!mounted.current) return;
      runStore.setActiveRun(run);
      nativeGuiAutofocusRun.current = run.run_id;
      connectEvents(run.run_id);
    } catch (error: unknown) {
      runStore.setError({ kind: "network", message: localizeMessage(error instanceof Error ? error.message : "无法启动演示") });
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

  const reconnectEvents = () => {
    const runId = runStore.getSnapshot().activeRun?.run_id;
    if (runId && !isTerminalStatus(runStore.getSnapshot().activeRun?.status)) connectEvents(runId);
  };

  const stopRun = async () => {
    const runId = runStore.getSnapshot().activeRun?.run_id;
    if (!runId) return;
    try {
      const result = await api.stopRun(runId);
      if (nativeGuiAutofocusRun.current === runId) nativeGuiAutofocusRun.current = null;
      closeSubscription(runId);
      runStore.setActiveRun(result);
      runStore.setConnection("idle");
      void loadResults();
    } catch (error: unknown) {
      runStore.setError({ kind: "http", message: localizeMessage(error instanceof Error ? error.message : "无法停止运行") });
    }
  };

  const showNativeGui = async () => {
    const runId = runStore.getSnapshot().activeRun?.run_id;
    if (!runId) return;
    try {
      await api.openNativeGui(runId);
    } catch (error: unknown) {
      const typed = error as { message?: string; status?: number };
      runStore.setError({ kind: "http", message: localizeMessage(typed.message ?? "Native SUMO GUI unavailable"), status: typed.status });
    }
  };

  const changeGuiDelay = async (requestedDelayMs: number) => {
    if (guiDelayPending) return;
    const delayMs = Math.round(boundedNumber(requestedDelayMs, 0, 2000, 100));
    const current = runStore.getSnapshot().activeRun;
    if (current?.status !== "running") {
      runStore.setSelection({ selectedGuiDelayMs: delayMs });
      return;
    }
    setGuiDelayPending(true);
    try {
      const confirmed = await api.setGuiDelay(current.run_id, delayMs);
      if (
        mounted.current
        && runStore.getSnapshot().activeRun?.run_id === current.run_id
      ) {
        runStore.setSelection({ selectedGuiDelayMs: confirmed.delay_ms });
        runStore.setError(null);
      }
    } catch (error: unknown) {
      const typed = error as { message?: string; status?: number };
      runStore.setError({
        kind: "http",
        message: localizeMessage(typed.message ?? "无法调整 GUI 步进延迟"),
        status: typed.status,
      });
    } finally {
      if (mounted.current) setGuiDelayPending(false);
    }
  };

  const openResult = async (runId: string) => {
    try {
      setOpenedResult(await api.getResult(runId));
    } catch (error: unknown) {
      setResultsError(localizeMessage(error instanceof Error ? error.message : "无法加载封存摘要"));
    }
  };

  return (
    <div className="app-shell">
      <header className="app-header">
        <div>
          <p className="eyebrow">XH-202613 · 评审版本</p>
          <h1>交通信号控制仿真评审台</h1>
        </div>
        <nav aria-label="主导航">
          {Object.entries({ simulation: "实时仿真", comparison: "算法对比", history: "运行历史", scene: "场景清单" }).map(([key, label]) => (
            <button key={key} type="button" onClick={() => setView(key)} aria-current={view === key ? "page" : undefined}>
              {label}
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
          guiDelayPending={guiDelayPending}
          onStart={() => void startQuickDemo()}
          onStop={() => void stopRun()}
          onNativeGui={() => void showNativeGui()}
          onGuiDelayChange={(delayMs) => void changeGuiDelay(delayMs)}
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
          {openedResult && <pre className="result-detail" aria-label="封存结果详情">{JSON.stringify(openedResult, null, 2)}</pre>}
        </>
      ) : (
        <SceneView scenes={scenes} loading={scenesLoading} error={sceneError} />
      )}
    </div>
  );
}
