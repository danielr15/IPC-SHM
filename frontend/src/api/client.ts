export type ProtectionMode =
  | "none"
  | "mutex"
  | "semaphore"
  | "rwlock"
  | "rwlock_global"
  | "cell_mutex";

export type CellState = "idle" | "reading" | "writing" | "corrupted";
export type ProcessState =
  | "idle"
  | "reading"
  | "writing"
  | "waiting"
  | "crashed"
  | "done";

export interface Cell {
  address: number;
  value: number;
  state: CellState;
}

export interface ProcessInfo {
  pid: number;
  state: ProcessState;
  op: string | null;
  target_address: number | null;
  script_index: number;
  wait_ticks: number;
  held_locks: number[];
}

export interface SimEvent {
  tick: number;
  pid: number | null;
  op: string;
  address: number | null;
  outcome: string;
  message: string;
}

export interface Metrics {
  tick: number;
  corruption_count: number;
  crash_count: number;
  completed_ops: number;
  blocked_count: number;
  deadlock_count: number;
  total_wait_ticks: number;
  avg_wait_time: number;
  throughput: number;
  reader_parallelism_max: number;
}

export interface SimulationState {
  running: boolean;
  protection: ProtectionMode;
  semaphore_k: number;
  rwlock_reader_preference: boolean;
  grid_size: number;
  process_count: number;
  random_mode: boolean;
  custom_mode: boolean;
  cells: Cell[];
  processes: ProcessInfo[];
  events: SimEvent[];
  metrics: Metrics;
  scenario_name: string | null;
}

export interface ScenarioInfo {
  id: string;
  name: string;
  description: string;
}

const API = "/api";

async function request<T>(path: string, options?: RequestInit): Promise<T> {
  const res = await fetch(`${API}${path}`, {
    headers: { "Content-Type": "application/json" },
    ...options,
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: res.statusText }));
    throw new Error(err.detail || res.statusText);
  }
  return res.json();
}

export const api = {
  getState: () => request<SimulationState>("/state"),
  listScenarios: () => request<ScenarioInfo[]>("/scenarios"),
  setProtection: (
    mode: ProtectionMode,
    k = 3,
    readerPreference?: boolean
  ) =>
    request<SimulationState>("/protection", {
      method: "POST",
      body: JSON.stringify({
        mode,
        k,
        ...(readerPreference !== undefined
          ? { reader_preference: readerPreference }
          : {}),
      }),
    }),
  setProcessCount: (count: number) =>
    request<SimulationState>("/processes", {
      method: "POST",
      body: JSON.stringify({ count }),
    }),
  loadScenario: (name: string) =>
    request<SimulationState>("/scenario", {
      method: "POST",
      body: JSON.stringify({ name }),
    }),
  start: () => request<SimulationState>("/start", { method: "POST" }),
  stop: () => request<SimulationState>("/stop", { method: "POST" }),
  step: () => request<SimulationState>("/step", { method: "POST" }),
  reset: () => request<SimulationState>("/reset", { method: "POST" }),
};

export function connectWebSocket(
  onMessage: (state: SimulationState) => void
): WebSocket {
  const protocol = window.location.protocol === "https:" ? "wss:" : "ws:";
  const host = window.location.host;
  const ws = new WebSocket(`${protocol}//${host}/ws/events`);
  ws.onmessage = (ev) => {
    onMessage(JSON.parse(ev.data) as SimulationState);
  };
  return ws;
}
