import type { Cell, CellState, ProcessInfo, ProcessState } from "./api/client";

export function cellColor(state: CellState): string {
  switch (state) {
    case "reading":
      return "#3b82f6";
    case "writing":
      return "#f97316";
    case "corrupted":
      return "#ef4444";
    default:
      return "#374151";
  }
}

export function processColor(state: ProcessState): string {
  switch (state) {
    case "reading":
      return "#60a5fa";
    case "writing":
      return "#fb923c";
    case "waiting":
      return "#eab308";
    case "crashed":
      return "#6b7280";
    case "done":
      return "#22c55e";
    default:
      return "#a78bfa";
  }
}

export function protectionLabel(mode: string): string {
  const labels: Record<string, string> = {
    none: "Sem proteção",
    mutex: "Mutex",
    semaphore: "Semáforo",
    rwlock: "RW-Lock (por célula)",
    rwlock_global: "RW-Lock global",
    cell_mutex: "Mutex por célula",
  };
  return labels[mode] ?? mode;
}

export function outcomeClass(outcome: string): string {
  switch (outcome) {
    case "corrupted":
      return "event-corrupted";
    case "blocked":
      return "event-blocked";
    case "deadlock":
      return "event-deadlock";
    default:
      return "event-ok";
  }
}

export function getActiveTargets(processes: ProcessInfo[]): Map<number, number[]> {
  const map = new Map<number, number[]>();
  for (const p of processes) {
    if (p.target_address !== null && p.state !== "crashed" && p.state !== "done") {
      const list = map.get(p.target_address) ?? [];
      list.push(p.pid);
      map.set(p.target_address, list);
    }
  }
  return map;
}

export function formatCellValue(cell: Cell): string {
  if (cell.state === "corrupted") return "ERR";
  return String(cell.value);
}
