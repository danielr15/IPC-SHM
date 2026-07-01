import type { Cell } from "../api/client";
import { cellColor, formatCellValue } from "../utils";

interface Props {
  cells: Cell[];
  gridSize: number;
  activeTargets: Map<number, number[]>;
}

export function MemoryGrid({ cells, gridSize, activeTargets }: Props) {
  return (
    <div className="memory-grid" style={{ gridTemplateColumns: `repeat(${gridSize}, 1fr)` }}>
      {cells.map((cell) => {
        const pids = activeTargets.get(cell.address) ?? [];
        const isActive = pids.length > 0;
        return (
          <div
            key={cell.address}
            className={`memory-cell ${cell.state} ${isActive ? "active" : ""}`}
            style={{ backgroundColor: cellColor(cell.state) }}
            title={`@${cell.address} = ${formatCellValue(cell)}`}
          >
            <span className="cell-addr">@{cell.address}</span>
            <span className="cell-val">{formatCellValue(cell)}</span>
            {pids.length > 0 && (
              <span className="cell-pids">P{pids.join(", P")}</span>
            )}
          </div>
        );
      })}
    </div>
  );
}
