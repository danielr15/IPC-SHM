from __future__ import annotations

from .models import CellDTO, CellState


class SharedMemory:
    def __init__(self, grid_size: int = 4) -> None:
        self.grid_size = grid_size
        self.total_cells = grid_size * grid_size
        self.values: list[int] = [0] * self.total_cells
        self.states: list[CellState] = [CellState.IDLE] * self.total_cells

    def reset(self, grid_size: int | None = None) -> None:
        if grid_size is not None:
            self.grid_size = grid_size
            self.total_cells = grid_size * grid_size
        self.values = [0] * self.total_cells
        self.states = [CellState.IDLE] * self.total_cells

    def clear_access_states(self) -> None:
        for i, state in enumerate(self.states):
            if state in (CellState.READING, CellState.WRITING):
                self.states[i] = CellState.IDLE

    def mark_corrupted(self, address: int) -> None:
        self.states[address] = CellState.CORRUPTED
        self.values[address] = -1

    def to_dto_list(self) -> list[CellDTO]:
        return [
            CellDTO(address=i, value=self.values[i], state=self.states[i])
            for i in range(self.total_cells)
        ]
