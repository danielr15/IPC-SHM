import { useCallback, useEffect, useState } from "react";
import {
  api,
  connectWebSocket,
  type ProtectionMode,
  type ScenarioInfo,
  type SimulationState,
} from "./api/client";
import { MemoryGrid } from "./components/MemoryGrid";
import { ColorLegend } from "./components/ColorLegend";
import { ProcessList } from "./components/ProcessList";
import { MetricsPanel } from "./components/MetricsPanel";
import { EventLog } from "./components/EventLog";
import { getActiveTargets, protectionLabel } from "./utils";
import "./App.css";

const PROTECTION_MODES: ProtectionMode[] = [
  "none",
  "mutex",
  "semaphore",
  "rwlock",
  "rwlock_global",
  "cell_mutex",
];

export default function App() {
  const [state, setState] = useState<SimulationState | null>(null);
  const [scenarios, setScenarios] = useState<ScenarioInfo[]>([]);
  const [semaphoreK, setSemaphoreK] = useState(3);
  const [processCount, setProcessCount] = useState(6);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  const refresh = useCallback(async () => {
    try {
      const s = await api.getState();
      setState(s);
      setSemaphoreK(s.semaphore_k);
      setProcessCount(s.process_count);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Erro ao conectar");
    }
  }, []);

  useEffect(() => {
    refresh();
    api.listScenarios().then(setScenarios).catch(console.error);
    const ws = connectWebSocket(setState);
    const interval = setInterval(refresh, 2000);
    return () => {
      ws.close();
      clearInterval(interval);
    };
  }, [refresh]);

  const run = async (fn: () => Promise<SimulationState>) => {
    setLoading(true);
    setError(null);
    try {
      const s = await fn();
      setState(s);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Erro");
    } finally {
      setLoading(false);
    }
  };

  if (!state) {
    return (
      <div className="app loading-screen">
        <p>Conectando ao simulador...</p>
        {error && <p className="error">{error}</p>}
      </div>
    );
  }

  const activeTargets = getActiveTargets(state.processes);

  return (
    <div className="app">
      <header className="header">
        <div>
          <h1>Simulador IPC — Memória Compartilhada Protegida</h1>
          <p className="subtitle">
            IFCE · Sistemas Operacionais · SHM + Sincronização
          </p>
        </div>
        <div className={`status-badge ${state.running ? "running" : "paused"}`}>
          {state.running ? "▶ Executando" : "⏸ Pausado"}
        </div>
      </header>

      {error && <div className="error-banner">{error}</div>}

      <section className="toolbar">
        <div className="toolbar-left">
          <div className="toolbar-group">
            <label>Proteção</label>
            <select
              value={state.protection}
              onChange={(e) =>
                run(() =>
                  api.setProtection(
                    e.target.value as ProtectionMode,
                    semaphoreK,
                    state.rwlock_reader_preference
                  )
                )
              }
              disabled={loading}
            >
              {PROTECTION_MODES.map((m) => (
                <option key={m} value={m}>
                  {protectionLabel(m)}
                </option>
              ))}
            </select>
          </div>

          <div className="toolbar-group">
            <label>Processos</label>
            <input
              type="number"
              min={1}
              max={16}
              value={processCount}
              disabled={loading || !state.random_mode}
              title="Quantidade de processos simulados"
              onChange={(e) => setProcessCount(Number(e.target.value))}
              onBlur={() => {
                if (state.random_mode) {
                  run(() => api.setProcessCount(processCount));
                }
              }}
              onKeyDown={(e) => {
                if (e.key === "Enter" && state.random_mode) {
                  run(() => api.setProcessCount(processCount));
                }
              }}
            />
          </div>

          {state.protection === "rwlock_global" && (
            <div className="toolbar-group toolbar-checkbox">
              <label className="checkbox-label">
                <input
                  type="checkbox"
                  checked={state.rwlock_reader_preference}
                  disabled={loading}
                  onChange={(e) =>
                    run(() =>
                      api.setProtection(
                        "rwlock_global",
                        semaphoreK,
                        e.target.checked
                      )
                    )
                  }
                />
                Preferência por leitores
              </label>
              <p className="scenario-hint">
                {state.rwlock_reader_preference
                  ? "Escritores aguardam leitores na fila."
                  : "Justo: escritor entra sem leitores ativos."}
              </p>
            </div>
          )}

          {state.protection === "semaphore" && (
            <div className="toolbar-group">
              <label>K (semáforo)</label>
              <input
                type="number"
                min={1}
                max={16}
                value={semaphoreK}
                onChange={(e) => setSemaphoreK(Number(e.target.value))}
                onBlur={() =>
                  run(() => api.setProtection("semaphore", semaphoreK))
                }
              />
            </div>
          )}
        </div>

        <div className="toolbar-scenario">
          <div className="toolbar-group">
            <label>Cenário</label>
            <select
              value={state.scenario_name ?? ""}
              onChange={(e) => run(() => api.loadScenario(e.target.value))}
              disabled={loading}
            >
              <option value="">— Selecione um cenário —</option>
              {scenarios.map((s) => (
                <option key={s.id} value={s.id}>
                  {s.name}
                </option>
              ))}
            </select>
            {state.scenario_name ? (
              scenarios.find((s) => s.id === state.scenario_name)?.description && (
                <p className="scenario-hint">
                  {scenarios.find((s) => s.id === state.scenario_name)?.description}
                </p>
              )
            ) : (
              <p className="scenario-hint">
                Customizavel.
              </p>
            )}
          </div>
        </div>

        <div className="toolbar-actions">
          <button
            onClick={() => run(api.start)}
            disabled={loading || state.running || state.process_count < 1}
          >
            Play
          </button>
          <button onClick={() => run(api.stop)} disabled={loading || !state.running}>
            Pause
          </button>
          <button onClick={() => run(api.step)} disabled={loading}>
            Step
          </button>
          <button onClick={() => run(api.reset)} disabled={loading}>
            Reset
          </button>
        </div>
      </section>

      <main className="main-layout">
        <div className="left-panel">
          <h2>Segmento de Memória Compartilhada ({state.grid_size}×{state.grid_size})</h2>
          <div className="memory-section">
            <MemoryGrid
              cells={state.cells}
              gridSize={state.grid_size}
              activeTargets={activeTargets}
            />
            <ColorLegend />
          </div>
          <ProcessList processes={state.processes} />
        </div>
        <div className="right-panel">
          <MetricsPanel
            metrics={state.metrics}
            protection={protectionLabel(state.protection)}
            semaphoreK={state.semaphore_k}
          />
          <EventLog events={state.events} />
        </div>
      </main>
    </div>
  );
}
