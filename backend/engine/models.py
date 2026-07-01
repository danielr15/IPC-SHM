from __future__ import annotations

from enum import Enum
from typing import Any

from pydantic import BaseModel, Field


class ProtectionMode(str, Enum):
    NONE = "none"
    MUTEX = "mutex"
    SEMAPHORE = "semaphore"
    RWLOCK = "rwlock"
    RWLOCK_GLOBAL = "rwlock_global"
    CELL_MUTEX = "cell_mutex"


class CellState(str, Enum):
    IDLE = "idle"
    READING = "reading"
    WRITING = "writing"
    CORRUPTED = "corrupted"


class ProcessOp(str, Enum):
    READ = "read"
    WRITE = "write"
    IDLE = "idle"


class ProcessState(str, Enum):
    IDLE = "idle"
    READING = "reading"
    WRITING = "writing"
    WAITING = "waiting"
    CRASHED = "crashed"
    DONE = "done"


class EventOutcome(str, Enum):
    OK = "ok"
    BLOCKED = "blocked"
    CORRUPTED = "corrupted"
    DEADLOCK = "deadlock"


class ScriptStep(BaseModel):
    op: ProcessOp
    address: int = 0
    value: int = 0
    duration: int = 2


class ProcessConfig(BaseModel):
    pid: int
    script: list[ScriptStep]


class RandomProfile(BaseModel):
    process_count: int = Field(default=6, ge=1, le=16)
    read_probability: float = Field(default=0.3, ge=0.0, le=1.0)
    writer_pids: list[int] = Field(default_factory=list)
    reader_pids: list[int] = Field(default_factory=list)
    duration_min: int = Field(default=2, ge=1, le=20)
    duration_max: int = Field(default=5, ge=1, le=20)
    think_min: int = Field(default=1, ge=0, le=30)
    think_max: int = Field(default=8, ge=0, le=30)
    start_delay_max: int = Field(default=10, ge=0, le=50)
    hold_lock_after_op: bool = False
    prefer_different_cell_when_holding: bool = False
    seed: int | None = None


class ScenarioConfig(BaseModel):
    name: str
    description: str = ""
    protection: ProtectionMode = ProtectionMode.NONE
    semaphore_k: int = 3
    grid_size: int = 4
    processes: list[ProcessConfig] = Field(default_factory=list)
    loop_script: bool = False
    random: RandomProfile | None = None


class ProtectionRequest(BaseModel):
    mode: ProtectionMode
    k: int = Field(default=3, ge=1, le=16)
    reader_preference: bool | None = None


class ScenarioRequest(BaseModel):
    name: str


class ProcessCountRequest(BaseModel):
    count: int = Field(ge=1, le=16)


class CellDTO(BaseModel):
    address: int
    value: int
    state: CellState


class ProcessDTO(BaseModel):
    pid: int
    state: ProcessState
    op: ProcessOp | None = None
    target_address: int | None = None
    script_index: int = 0
    wait_ticks: int = 0
    held_locks: list[int] = Field(default_factory=list)


class EventDTO(BaseModel):
    tick: int
    pid: int | None
    op: str
    address: int | None
    outcome: EventOutcome
    message: str


class MetricsDTO(BaseModel):
    tick: int
    corruption_count: int
    crash_count: int
    completed_ops: int
    blocked_count: int
    deadlock_count: int
    total_wait_ticks: int
    avg_wait_time: float
    throughput: float
    reader_parallelism_max: int


class SimulationStateDTO(BaseModel):
    running: bool
    protection: ProtectionMode
    semaphore_k: int
    rwlock_reader_preference: bool = True
    grid_size: int
    process_count: int
    random_mode: bool
    cells: list[CellDTO]
    processes: list[ProcessDTO]
    events: list[EventDTO]
    metrics: MetricsDTO
    scenario_name: str | None = None
    custom_mode: bool = False


def metrics_to_dto(m: dict[str, Any], tick: int) -> MetricsDTO:
    completed = m["completed_ops"]
    return MetricsDTO(
        tick=tick,
        corruption_count=m["corruption_count"],
        crash_count=m["crash_count"],
        completed_ops=completed,
        blocked_count=m["blocked_count"],
        deadlock_count=m["deadlock_count"],
        total_wait_ticks=m["total_wait_ticks"],
        avg_wait_time=(
            m["wait_episode_ticks"] / m["wait_episodes"]
            if m["wait_episodes"] > 0
            else 0.0
        ),
        throughput=completed / tick if tick > 0 else 0.0,
        reader_parallelism_max=m["reader_parallelism_max"],
    )
