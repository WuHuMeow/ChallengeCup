export type AlgorithmKey =
  | "fixed_time"
  | "classic_maxpressure"
  | "capacity_aware_maxpressure"
  | "actuated";

export type RunStatus =
  | "queued"
  | "starting"
  | "running"
  | "stopping"
  | "completed"
  | "stopped"
  | "ended_early"
  | "disconnected"
  | "interrupted"
  | "failed";

export interface SceneManifest {
  scene_id: string;
  intersection_id: string;
  name: string;
  description: string;
  source_files: Record<string, string>;
  sha256: Record<string, string>;
  step_length: number;
  tls_ids: string[];
  lane_ids: string[];
  movement_count: number;
  validation_status: string;
  warnings: string[];
}

export interface AlgorithmSpec {
  key: AlgorithmKey;
  display_name: string;
  formal: boolean;
  available: boolean;
  unavailable_reason: string | null;
}

export interface RunResult {
  run_id: string;
  status: RunStatus;
  reason: string;
  summary: Record<string, unknown> | null;
  algorithm: string;
}

interface RawRunResult extends RunResult {
  run_dir?: string;
}

export interface RunRequest {
  intersection_id: string;
  algorithm: AlgorithmKey;
  steps?: number;
  flow_multiplier: number;
  seed: number;
  duration_seconds: number;
  warmup_seconds: number;
  gui_delay_ms: number;
  step_length_override?: number;
  edge_delay_steps?: number;
  edge_directions?: string[];
  variant?: Record<string, unknown>;
  disturbance?: Record<string, unknown> | null;
  algorithm_params?: Record<string, number>;
}

export interface FrameResponse {
  runId: string;
  sequence: number;
  simulationTime: number;
  blob: Blob;
}

export interface SafetyCounters {
  collision: number;
  red_light: number;
  illegal_transition: number;
  harsh_braking: number;
  teleport: number;
  potential_conflict: number;
}

export interface RunEvent {
  run_id: string;
  type: "status" | "metrics" | "action" | "safety" | "frame" | "terminal" | string;
  status?: RunStatus | string;
  simulation_time?: number;
  [key: string]: unknown;
}

export interface ResultListItem extends RunResult {
  scene_id: string;
  summary: Record<string, unknown>;
  run_dir?: never;
}

export interface ResultList {
  items: ResultListItem[];
  count: number;
}

export class ApiError extends Error {
  readonly status: number;
  readonly kind: "http" | "network";

  constructor(message: string, status = 0, kind: "http" | "network" = "http") {
    super(message);
    this.name = "ApiError";
    this.status = status;
    this.kind = kind;
  }
}

export interface JudgeApiClient {
  listScenes(): Promise<SceneManifest[]>;
  listAlgorithms(): Promise<{ formal: AlgorithmSpec[]; optional: AlgorithmSpec[] }>;
  startRun(request: RunRequest): Promise<RunResult>;
  getRun(runId: string): Promise<RunResult>;
  stopRun(runId: string): Promise<RunResult>;
  getMetrics(runId: string): Promise<Record<string, unknown>>;
  getFrame(runId: string, afterSequence: number | null): Promise<FrameResponse>;
  listResults(): Promise<ResultList>;
  getResult(runId: string): Promise<ResultListItem>;
  getSafety(runId: string): Promise<SafetyCounters>;
  setGuiDelay(runId: string, delayMs: number): Promise<{ delay_ms: number }>;
  openNativeGui(runId: string): Promise<{ status: "shown" }>;
  subscribeEvents(
    runId: string,
    onMessage: (event: RunEvent) => void,
    onClose: () => void,
    onOpen?: () => void,
  ): () => void;
}

function sanitizeResultItem(result: ResultListItem & { run_dir?: string }): ResultListItem {
  const { run_dir: _runDir, ...safe } = result;
  return safe;
}

async function parseError(response: Response): Promise<string> {
  try {
    const payload = (await response.json()) as { detail?: unknown };
    if (typeof payload.detail === "string") return payload.detail;
  } catch {
    // A non-JSON error still gets a stable message below.
  }
  return `${response.status} ${response.statusText || "request failed"}`;
}

function sanitizeRunResult(result: RawRunResult): RunResult {
  const { run_dir: _runDir, ...safe } = result;
  return safe;
}

function websocketUrl(baseUrl: string, runId: string): string {
  const base = new URL(baseUrl || window.location.origin, window.location.href);
  base.protocol = base.protocol === "https:" ? "wss:" : "ws:";
  base.pathname = `/api/runs/${encodeURIComponent(runId)}/events`;
  base.search = "";
  return base.toString();
}

export function createApiClient(baseUrl = ""): JudgeApiClient {
  async function request<T>(path: string, init?: RequestInit): Promise<T> {
    try {
      const response = await fetch(`${baseUrl}${path}`, {
        headers: { Accept: "application/json", ...(init?.headers ?? {}) },
        ...init,
      });
      if (!response.ok) {
        throw new ApiError(await parseError(response), response.status);
      }
      return (await response.json()) as T;
    } catch (error) {
      if (error instanceof ApiError) throw error;
      throw new ApiError(error instanceof Error ? error.message : "network request failed", 0, "network");
    }
  }

  return {
    listScenes: () => request<SceneManifest[]>("/api/scenes"),
    listAlgorithms: () =>
      request<{ formal: AlgorithmSpec[]; optional: AlgorithmSpec[] }>("/api/algorithms"),
    startRun: async (payload) => {
      const result = await request<RawRunResult>("/api/runs", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload),
      });
      return sanitizeRunResult(result);
    },
    getRun: async (runId) => sanitizeRunResult(await request<RawRunResult>(`/api/runs/${encodeURIComponent(runId)}`)),
    stopRun: async (runId) => sanitizeRunResult(await request<RawRunResult>(`/api/runs/${encodeURIComponent(runId)}/stop`, { method: "POST" })),
    getMetrics: (runId) => request<Record<string, unknown>>(`/api/runs/${encodeURIComponent(runId)}/metrics`),
    getFrame: async (runId, afterSequence) => {
      const query = afterSequence === null ? "" : `?sequence=${afterSequence}`;
      try {
        const response = await fetch(`/api/runs/${encodeURIComponent(runId)}/frame${query}`, {
          headers: { Accept: "image/png" },
        });
        if (!response.ok) throw new ApiError(await parseError(response), response.status);
        const sequence = Number(response.headers.get("X-Frame-Sequence"));
        const simulationTime = Number(response.headers.get("X-Simulation-Time"));
        const responseRunId = response.headers.get("X-Run-Id") ?? runId;
        if (!Number.isFinite(sequence) || !Number.isFinite(simulationTime)) {
          throw new ApiError("frame response is missing sequence metadata", 502);
        }
        return { runId: responseRunId, sequence, simulationTime, blob: await response.blob() };
      } catch (error) {
        if (error instanceof ApiError) throw error;
        throw new ApiError(error instanceof Error ? error.message : "frame request failed", 0, "network");
      }
    },
    listResults: async () => {
      const result = await request<ResultList & { items: Array<ResultListItem & { run_dir?: string }> }>("/api/results");
      return { ...result, items: result.items.map(sanitizeResultItem) };
    },
    getResult: async (runId) => sanitizeResultItem(await request<ResultListItem & { run_dir?: string }>(`/api/results/${encodeURIComponent(runId)}`)),
    getSafety: (runId) => request<SafetyCounters>(`/api/runs/${encodeURIComponent(runId)}/safety`),
    setGuiDelay: (runId, delayMs) =>
      request<{ delay_ms: number }>(`/api/runs/${encodeURIComponent(runId)}/gui-delay`, {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ delay_ms: delayMs }),
      }),
    openNativeGui: (runId) =>
      request<{ status: "shown" }>(`/api/runs/${encodeURIComponent(runId)}/native-gui`, { method: "POST" }),
    subscribeEvents: (runId, onMessage, onClose, onOpen) => {
      const socket = new WebSocket(websocketUrl(baseUrl, runId));
      socket.addEventListener("open", () => onOpen?.());
      socket.addEventListener("message", (message) => {
        try {
          onMessage(JSON.parse(String(message.data)) as RunEvent);
        } catch {
          // Ignore malformed messages; the REST state remains authoritative.
        }
      });
      socket.addEventListener("close", onClose);
      socket.addEventListener("error", onClose);
      return () => socket.close();
    },
  };
}
