import type { SimEvent } from "../api/client";
import { outcomeClass } from "../utils";

interface Props {
  events: SimEvent[];
}

export function EventLog({ events }: Props) {
  const recent = [...events].reverse().slice(0, 30);

  return (
    <div className="event-log">
      <h3>Log de eventos</h3>
      <div className="event-list">
        {recent.length === 0 && <p className="muted">Aguardando eventos...</p>}
        {recent.map((ev, i) => (
          <div key={`${ev.tick}-${i}`} className={`event-row ${outcomeClass(ev.outcome)}`}>
            <span className="event-tick">T{ev.tick}</span>
            <span className="event-msg">{ev.message}</span>
          </div>
        ))}
      </div>
    </div>
  );
}
