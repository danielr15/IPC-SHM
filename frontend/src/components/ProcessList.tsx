import type { ProcessInfo } from "../api/client";
import { processColor } from "../utils";

interface Props {
  processes: ProcessInfo[];
}

export function ProcessList({ processes }: Props) {
  return (
    <div className="process-list">
      <h3>Processos</h3>
      {processes.length === 0 && <p className="muted">Nenhum processo carregado.</p>}
      {processes.map((p) => (
        <div key={p.pid} className={`process-card ${p.state}`}>
          <div
            className="process-dot"
            style={{ backgroundColor: processColor(p.state) }}
          />
          <div className="process-info">
            <strong>P{p.pid}</strong>
            <span className="process-state">{p.state}</span>
            {p.target_address !== null && (
              <span className="process-target">
                → @{p.target_address} ({p.op})
              </span>
            )}
            {p.state === "waiting" && (
              <span className="process-wait">espera: {p.wait_ticks} ticks</span>
            )}
            {p.held_locks.length > 0 && (
              <span className="process-locks">
                locks: [{p.held_locks.join(", ")}]
              </span>
            )}
          </div>
        </div>
      ))}
    </div>
  );
}
