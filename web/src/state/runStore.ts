import type {
  AlgorithmKey,
  FrameResponse,
  ResultListItem,
  RunEvent,
  RunResult,
  RunStatus,
  SafetyCounters,
} from "../api/client";

export interface RunError {
  kind: "http" | "network" | "disconnected" | "frame" | "unknown";
  message: string;
  status?: number;
}

export interface RunStoreSnapshot {
  selectedScene: string;
  selectedAlgorithm: AlgorithmKey;
  selectedLoad: number;
  selectedSeed: number;
  selectedDuration: number;
  selectedWarmup: number;
  selectedDisturbance: "none" | "construction" | "event_demand" | "vehicle_failure";
  activeRun: RunResult | null;
  metrics: Record<string, unknown>;
  events: RunEvent[];
  frameSequence: number | null;
  frameUrl: string | null;
  simulationTime: number | null;
  safety: SafetyCounters | null;
  formalEvidence: ResultListItem | null;
  error: RunError | null;
  connection: "idle" | "connecting" | "connected" | "disconnected";
}

export interface RunStore {
  getSnapshot(): RunStoreSnapshot;
  subscribe(listener: () => void): () => void;
  setSelection(selection: Partial<Pick<RunStoreSnapshot, "selectedScene" | "selectedAlgorithm" | "selectedLoad" | "selectedSeed" | "selectedDuration" | "selectedWarmup" | "selectedDisturbance">>): void;
  setActiveRun(run: RunResult): void;
  setRunStatus(status: RunStatus): void;
  setMetrics(metrics: Record<string, unknown>): void;
  setSafety(safety: SafetyCounters): void;
  addEvent(event: RunEvent): void;
  setError(error: RunError | null): void;
  setConnection(connection: RunStoreSnapshot["connection"]): void;
  acceptFrame(frame: FrameResponse): boolean;
  setFormalEvidence(result: ResultListItem | null): void;
  resetRun(): void;
}

const initialSnapshot: RunStoreSnapshot = {
  selectedScene: "1",
  selectedAlgorithm: "fixed_time",
  selectedLoad: 1,
  selectedSeed: 42,
  selectedDuration: 30,
  selectedWarmup: 0,
  selectedDisturbance: "none",
  activeRun: null,
  metrics: {},
  events: [],
  frameSequence: null,
  frameUrl: null,
  simulationTime: null,
  safety: null,
  formalEvidence: null,
  error: null,
  connection: "idle",
};

function revokeObjectUrl(url: string | null): void {
  if (url && typeof URL !== "undefined" && url.startsWith("blob:")) {
    URL.revokeObjectURL(url);
  }
}

export function createRunStore(): RunStore {
  let snapshot = { ...initialSnapshot };
  const listeners = new Set<() => void>();
  const publish = (next: RunStoreSnapshot) => {
    snapshot = next;
    listeners.forEach((listener) => listener());
  };
  const update = (patch: Partial<RunStoreSnapshot>) => publish({ ...snapshot, ...patch });

  return {
    getSnapshot: () => snapshot,
    subscribe: (listener) => {
      listeners.add(listener);
      return () => listeners.delete(listener);
    },
    setSelection: (selection) => update(selection),
    setActiveRun: (activeRun) => update({
      activeRun,
      error: null,
      connection: ["completed", "stopped", "ended_early", "disconnected", "interrupted", "failed"].includes(activeRun.status) ? "idle" : "connecting",
    }),
    setRunStatus: (status) => {
      if (snapshot.activeRun) {
        const terminal = ["completed", "stopped", "ended_early", "disconnected", "interrupted", "failed"].includes(status);
        update({ activeRun: { ...snapshot.activeRun, status }, ...(terminal ? { connection: "idle" } : {}) });
      }
    },
    setMetrics: (metrics) => update({ metrics }),
    setSafety: (safety) => update({ safety }),
    addEvent: (event) => update({ events: [...snapshot.events.slice(-99), event] }),
    setError: (error) => update({ error }),
    setConnection: (connection) => update({ connection }),
    acceptFrame: (frame) => {
      const currentRunId = snapshot.activeRun?.run_id;
      const currentSequence = snapshot.frameSequence ?? -1;
      if (frame.runId !== currentRunId || frame.sequence <= currentSequence) return false;
      const frameUrl = URL.createObjectURL(frame.blob);
      revokeObjectUrl(snapshot.frameUrl);
      update({ frameSequence: frame.sequence, simulationTime: frame.simulationTime, frameUrl });
      return true;
    },
    setFormalEvidence: (formalEvidence) => update({ formalEvidence }),
    resetRun: () => {
      revokeObjectUrl(snapshot.frameUrl);
      update({
        activeRun: null,
        metrics: {},
        events: [],
        frameSequence: null,
        frameUrl: null,
        simulationTime: null,
        safety: null,
        formalEvidence: null,
        error: null,
        connection: "idle",
      });
    },
  };
}

export const runStore = createRunStore();
