import type { Metrics } from "../api/client";

interface Props {
  metrics: Metrics;
  protection: string;
  semaphoreK: number;
}

export function MetricsPanel({ metrics, protection, semaphoreK }: Props) {
  const corruptionRate =
    metrics.completed_ops + metrics.corruption_count > 0
      ? (
          (metrics.corruption_count /
            (metrics.completed_ops + metrics.corruption_count)) *
          100
        ).toFixed(1)
      : "0.0";

  return (
    <div className="metrics-panel">
      <h3>Métricas</h3>
      <div className="metrics-grid">
        <div className="metric">
          <span className="metric-label">Tick</span>
          <span className="metric-value">{metrics.tick}</span>
        </div>
        <div className="metric">
          <span className="metric-label">Proteção</span>
          <span className="metric-value">
            {protection}
            {protection === "semaphore" && ` (K=${semaphoreK})`}
          </span>
        </div>
        <div className="metric">
          <span className="metric-label">Ops concluídas</span>
          <span className="metric-value">{metrics.completed_ops}</span>
        </div>
        <div className="metric">
          <span className="metric-label">Throughput</span>
          <span className="metric-value">{metrics.throughput.toFixed(3)}</span>
        </div>
        <div className="metric">
          <span className="metric-label">Corrupções</span>
          <span className="metric-value danger">{metrics.corruption_count}</span>
        </div>
        <div className="metric">
          <span className="metric-label">Taxa corrupção</span>
          <span className="metric-value danger">{corruptionRate}%</span>
        </div>
        <div className="metric">
          <span className="metric-label">Crashes</span>
          <span className="metric-value danger">{metrics.crash_count}</span>
        </div>
        <div className="metric">
          <span className="metric-label">Bloqueios</span>
          <span className="metric-value warn">{metrics.blocked_count}</span>
        </div>
        <div className="metric">
          <span className="metric-label">Espera média</span>
          <span className="metric-value">{metrics.avg_wait_time.toFixed(2)}</span>
        </div>
        <div className="metric">
          <span className="metric-label">Deadlocks</span>
          <span className="metric-value danger">{metrics.deadlock_count}</span>
        </div>
        <div className="metric">
          <span className="metric-label">Paralelismo leitores</span>
          <span className="metric-value">{metrics.reader_parallelism_max}</span>
        </div>
      </div>
    </div>
  );
}
