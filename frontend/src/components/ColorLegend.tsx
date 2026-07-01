import { cellColor } from "../utils";

const CELL_LEGEND = [
  { state: "idle" as const, label: "Livre", desc: "Nenhum acesso em andamento" },
  { state: "reading" as const, label: "Leitura", desc: "Processo lendo a célula" },
  { state: "writing" as const, label: "Escrita", desc: "Processo escrevendo na célula" },
  { state: "corrupted" as const, label: "Corrupção", desc: "Race condition detectada" },
];

const EXTRA_LEGEND = [
  {
    color: "transparent",
    border: "#fbbf24",
    label: "Acesso ativo",
    desc: "Processo conectado neste tick",
    className: "legend-swatch-active",
  },
];

export function ColorLegend() {
  return (
    <aside className="color-legend">
      <h3>Legenda</h3>
      <ul className="legend-list">
        {CELL_LEGEND.map((item) => (
          <li key={item.state} className="legend-item">
            <span
              className="legend-swatch"
              style={{ backgroundColor: cellColor(item.state) }}
            />
            <div className="legend-text">
              <strong>{item.label}</strong>
              <span>{item.desc}</span>
            </div>
          </li>
        ))}
        {EXTRA_LEGEND.map((item) => (
          <li key={item.label} className="legend-item">
            <span className={`legend-swatch ${item.className}`} />
            <div className="legend-text">
              <strong>{item.label}</strong>
              <span>{item.desc}</span>
            </div>
          </li>
        ))}
      </ul>
    </aside>
  );
}
