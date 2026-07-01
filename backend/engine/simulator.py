from __future__ import annotations

import json
from pathlib import Path

from .memory import SharedMemory
from .models import (
    CellState,
    EventDTO,
    EventOutcome,
    ProcessOp,
    ProcessState,
    ProtectionMode,
    ScenarioConfig,
    SimulationStateDTO,
    metrics_to_dto,
)
from .process import SimulatedProcess
from .randomizer import build_random_processes, initial_think, make_rng
from .protection import (
    GlobalRWLockProtection,
    MutexProtection,
    PerCellMutexProtection,
    ProtectionStrategy,
    RWLockProtection,
    SemaphoreProtection,
    create_protection,
)

SCENARIOS_DIR = Path(__file__).resolve().parent.parent / "scenarios"


class SimulationEngine:
    def __init__(self) -> None:
        self.memory = SharedMemory(4)
        self.processes: list[SimulatedProcess] = []
        self.protection_mode = ProtectionMode.NONE
        self.semaphore_k = 3
        self.rwlock_reader_preference = True
        self.protection: ProtectionStrategy = create_protection(ProtectionMode.NONE)
        self.running = False
        self.tick_count = 0
        self.scenario_name: str | None = None
        self.loop_script = False
        self.retain_locks = False
        self.events: list[EventDTO] = []
        self.max_events = 100
        self._metrics: dict[str, int] = self._empty_metrics()
        self._random_profile = None
        self._grid_size = 4
        self._rng = make_rng(None)
        self.process_count = 0
        self.random_mode = False
        self.custom_mode = False

    def _default_custom_profile(self):
        from .models import RandomProfile

        return RandomProfile(process_count=max(1, self.process_count or 4))

    def _sync_profile_with_protection(self) -> None:
        if not self._random_profile:
            return
        profile = self._random_profile.model_copy(deep=True)
        cell_mutex = self.protection_mode == ProtectionMode.CELL_MUTEX
        profile.hold_lock_after_op = cell_mutex
        profile.prefer_different_cell_when_holding = cell_mutex
        self._random_profile = profile
        for proc in self.processes:
            proc.random_profile = profile

    def _rebuild_random_processes(self) -> None:
        if not self._random_profile:
            return
        profile = self._profile_with_count(self._random_profile, self.process_count)
        self.processes = self._build_random_processes(profile)

    def _empty_metrics(self) -> dict[str, int]:
        return {
            "corruption_count": 0,
            "crash_count": 0,
            "completed_ops": 0,
            "blocked_count": 0,
            "deadlock_count": 0,
            "total_wait_ticks": 0,
            "wait_episode_ticks": 0,
            "wait_episodes": 0,
            "reader_parallelism_max": 0,
        }

    def reset_metrics(self) -> None:
        self._metrics = self._empty_metrics()

    def set_protection(
        self,
        mode: ProtectionMode,
        k: int = 3,
        *,
        reader_preference: bool | None = None,
    ) -> None:
        if reader_preference is not None:
            self.rwlock_reader_preference = reader_preference

        recreate = mode != self.protection_mode or (
            mode == ProtectionMode.SEMAPHORE and k != self.semaphore_k
        )

        self.protection_mode = mode
        self.semaphore_k = k

        if recreate:
            self.protection = create_protection(
                mode, k, reader_preference=self.rwlock_reader_preference
            )
            self.protection.reset()
        elif (
            mode == ProtectionMode.RWLOCK_GLOBAL
            and isinstance(self.protection, GlobalRWLockProtection)
        ):
            self.protection.reader_preference = self.rwlock_reader_preference

        self.retain_locks = mode == ProtectionMode.CELL_MUTEX
        self._sync_profile_with_protection()
        policy = ""
        if mode == ProtectionMode.RWLOCK_GLOBAL:
            policy = (
                " (preferência leitores)"
                if self.rwlock_reader_preference
                else " (justo)"
            )
        self._log_event(
            None,
            "protection",
            None,
            EventOutcome.OK,
            f"Modo alterado para {mode.value}{policy}",
        )

    def clear_scenario(self) -> None:
        self.running = False
        self.scenario_name = None
        self.custom_mode = True
        self.random_mode = True
        self.loop_script = True
        count = self.process_count if self.process_count > 0 else 4
        self.process_count = count
        self._random_profile = self._default_custom_profile()
        self._sync_profile_with_protection()
        self.tick_count = 0
        self.events = []
        self.reset_metrics()
        self.memory.reset(self._grid_size)
        self.protection.reset()
        self._rng = make_rng(None)
        self._rebuild_random_processes()
        self._log_event(
            None,
            "scenario",
            None,
            EventOutcome.OK,
            "Customizavel",
        )

    def load_scenario(self, name: str, seed: int | None = None) -> ScenarioConfig | None:
        if not name:
            self.clear_scenario()
            return None
        path = SCENARIOS_DIR / f"{name}.json"
        if not path.exists():
            raise FileNotFoundError(f"Cenário '{name}' não encontrado")
        data = json.loads(path.read_text(encoding="utf-8"))
        config = ScenarioConfig(**data)
        self.custom_mode = False
        self.scenario_name = name
        self.loop_script = config.loop_script
        self.memory.reset(config.grid_size)
        self.set_protection(config.protection, config.semaphore_k)

        rng_seed = seed
        if rng_seed is None and config.random:
            rng_seed = config.random.seed
        rng = make_rng(rng_seed)

        if config.random:
            profile = config.random
            self._random_profile = profile
            self.random_mode = True
            self.process_count = profile.process_count
            self._grid_size = config.grid_size
            self._rng = rng
            self.processes = self._build_random_processes(profile)
            mode_label = "aleatório"
        else:
            self._random_profile = None
            self.random_mode = False
            self.process_count = len(config.processes)
            self.processes = [
                SimulatedProcess(p, loop_script=config.loop_script)
                for p in config.processes
            ]
            mode_label = "script"

        self.tick_count = 0
        self.running = False
        self.events = []
        self.reset_metrics()
        self._log_event(
            None,
            "scenario",
            None,
            EventOutcome.OK,
            f"Cenário carregado: {config.name} ({mode_label})",
        )
        return config

    def _profile_with_count(self, profile, count: int):
        from .models import RandomProfile

        p = profile.model_copy(deep=True)
        p.process_count = max(1, min(16, count))
        if p.writer_pids:
            p.reader_pids = list(range(2, p.process_count + 1))
        return p

    def _build_random_processes(self, profile) -> list[SimulatedProcess]:
        process_configs = build_random_processes(
            profile, self._grid_size, self._rng
        )
        processes: list[SimulatedProcess] = []
        for pc in process_configs:
            proc = SimulatedProcess(
                pc,
                loop_script=self.loop_script,
                random_profile=profile,
                random_rng=self._rng,
                grid_size=self._grid_size,
                initial_think=initial_think(profile, pc.pid, self._rng),
            )
            processes.append(proc)
        return processes

    def set_process_count(self, count: int) -> None:
        if not self.random_mode or not self._random_profile:
            raise ValueError(
                "Cenário scriptado não permite alterar a quantidade de processos"
            )
        was_running = self.running
        self.running = False
        self.process_count = max(1, min(16, count))
        self._rebuild_random_processes()
        self.tick_count = 0
        self.reset_metrics()
        self.events = []
        self.running = was_running
        self._log_event(
            None,
            "processes",
            None,
            EventOutcome.OK,
            f"Processos ajustados para {self.process_count}",
        )

    def list_scenarios(self) -> list[dict[str, str]]:
        result = []
        for path in sorted(SCENARIOS_DIR.glob("*.json")):
            data = json.loads(path.read_text(encoding="utf-8"))
            result.append(
                {
                    "id": path.stem,
                    "name": data.get("name", path.stem),
                    "description": data.get("description", ""),
                }
            )
        return result

    def start(self) -> None:
        self.running = True

    def stop(self) -> None:
        self.running = False

    def reset_simulation(self) -> None:
        if self.scenario_name:
            saved_count = self.process_count
            name = self.scenario_name
            self.load_scenario(name)
            if self.random_mode and saved_count > 0:
                self.set_process_count(saved_count)
        elif self.custom_mode:
            saved_count = self.process_count
            mode = self.protection_mode
            k = self.semaphore_k
            self.clear_scenario()
            self.set_protection(
                mode, k, reader_preference=self.rwlock_reader_preference
            )
            if saved_count != self.process_count:
                self.set_process_count(saved_count)
        else:
            self.memory.reset()
            self.processes = []
            self.tick_count = 0
            self.running = False
            self.events = []
            self.reset_metrics()
            self.protection.reset()

    def step(self) -> SimulationStateDTO:
        self.tick_count += 1
        self.memory.clear_access_states()
        active_access: dict[int, list[tuple[int, ProcessOp]]] = {}

        for proc in self.processes:
            if proc.crashed or proc.done:
                continue

            if proc.state == ProcessState.WAITING:
                proc.wait_ticks += 1
                self._metrics["total_wait_ticks"] += 1
                step = proc.pending_step or self._next_step(proc)
                if step and step.op != ProcessOp.IDLE:
                    if self._try_grant(proc, step):
                        proc.pending_step = None
                        active_access.setdefault(step.address, []).append(
                            (proc.pid, step.op)
                        )
                        self._paint_cell(step.address, step.op)
                continue

            if proc.remaining_duration > 0:
                proc.remaining_duration -= 1
                if proc.current_step and proc.target_address is not None:
                    addr = proc.target_address
                    op = proc.current_step.op
                    active_access.setdefault(addr, []).append((proc.pid, op))
                    self._paint_cell(addr, op)
                if proc.remaining_duration == 0:
                    self._complete_operation(proc)
                continue

            if proc.uses_random_behavior() and proc.think_remaining > 0:
                proc.think_remaining -= 1
                continue

            step = self._next_step(proc)
            if step is None:
                proc.state = ProcessState.DONE
                proc.done = True
                self._release_all_locks(proc)
                continue

            if step.op == ProcessOp.IDLE:
                proc.start_step(step)
                continue

            if self._try_grant(proc, step):
                proc.pending_step = None
                active_access.setdefault(step.address, []).append(
                    (proc.pid, step.op)
                )
                self._paint_cell(step.address, step.op)
            else:
                proc.pending_step = step
                proc.set_waiting()
                self._metrics["blocked_count"] += 1
                self._log_event(
                    proc.pid,
                    step.op.value,
                    step.address,
                    EventOutcome.BLOCKED,
                    f"P{proc.pid} bloqueado aguardando lock",
                )

        if self.protection_mode == ProtectionMode.NONE:
            self._detect_races(active_access)

        if self.protection_mode in (
            ProtectionMode.RWLOCK,
            ProtectionMode.RWLOCK_GLOBAL,
        ):
            self._update_reader_parallelism()

        if self.retain_locks and isinstance(self.protection, PerCellMutexProtection):
            if self.protection.detect_deadlock(self.processes):
                if self._metrics["deadlock_count"] == 0:
                    self._metrics["deadlock_count"] += 1
                    self.running = False
                    self._log_event(
                        None,
                        "deadlock",
                        None,
                        EventOutcome.DEADLOCK,
                        "Deadlock detectado: locks cruzados",
                    )

        return self.get_state()

    def _next_step(self, proc: SimulatedProcess):
        if proc.uses_random_behavior():
            return proc.next_random_step()
        return proc.current_script_step()

    def _try_grant(self, proc: SimulatedProcess, step) -> bool:
        was_waiting = proc.state == ProcessState.WAITING
        if self.protection.request_access(proc, step.op, step.address):
            if was_waiting:
                self._metrics["wait_episode_ticks"] += proc.wait_ticks
                self._metrics["wait_episodes"] += 1
                proc.wait_ticks = 0
            proc.start_step(step)
            self._log_event(
                proc.pid,
                step.op.value,
                step.address,
                EventOutcome.OK,
                f"P{proc.pid} iniciou {step.op.value} @ {step.address}",
            )
            return True
        return False

    def _complete_operation(self, proc: SimulatedProcess) -> None:
        step = proc.current_step
        if not step or step.op == ProcessOp.IDLE:
            proc.finish_current_step()
            return

        addr = step.address
        op = step.op
        if op == ProcessOp.WRITE:
            if self.memory.states[addr] != CellState.CORRUPTED:
                self.memory.values[addr] = step.value

        if not self.retain_locks:
            self.protection.release_access(proc, op, addr)
        elif proc.uses_random_behavior() and proc.random_profile and proc.random_profile.hold_lock_after_op:
            for held in list(proc.held_locks):
                if held != addr:
                    self.protection.release_access(proc, op, held)
        elif proc.current_script_step() is None and not proc.uses_random_behavior():
            self._release_all_locks(proc)

        self._metrics["completed_ops"] += 1
        proc.finish_current_step()
        if proc.uses_random_behavior() and proc.loop_script:
            proc.schedule_think_after_op()
        self._log_event(
            proc.pid,
            op.value,
            addr,
            EventOutcome.OK,
            f"P{proc.pid} concluiu {op.value} @ {addr}",
        )

        if proc.state == ProcessState.WAITING:
            return

        self._wake_waiters()

    def _release_all_locks(self, proc: SimulatedProcess) -> None:
        for addr in list(proc.held_locks):
            self.protection.release_access(proc, ProcessOp.WRITE, addr)

    def _wake_waiters(self) -> None:
        if isinstance(self.protection, MutexProtection):
            prot = self.protection
            if prot.holder is not None:
                return
            while prot.wait_queue:
                pid = prot.wait_queue[0]
                proc = self._get_process(pid)
                if not proc or proc.crashed or proc.done:
                    prot.wait_queue.pop(0)
                    continue
                step = proc.pending_step or self._next_step(proc)
                if step and step.op != ProcessOp.IDLE:
                    if self._try_grant(proc, step):
                        prot.wait_queue.pop(0)
                        proc.state = ProcessState.READING if step.op == ProcessOp.READ else ProcessState.WRITING
                        if step.op == ProcessOp.WRITE:
                            proc.state = ProcessState.WRITING
                        break
                else:
                    prot.wait_queue.pop(0)

        if isinstance(self.protection, SemaphoreProtection):
            prot = self.protection
            while prot.wait_queue and prot.available > 0:
                pid = prot.wait_queue[0]
                proc = self._get_process(pid)
                if not proc or proc.crashed or proc.done:
                    prot.wait_queue.pop(0)
                    continue
                step = proc.pending_step or self._next_step(proc)
                if step and step.op != ProcessOp.IDLE and self._try_grant(proc, step):
                    prot.wait_queue.pop(0)
                    proc.pending_step = None
                else:
                    break

        if isinstance(self.protection, RWLockProtection):
            self._wake_rwlock_waiters()

        if isinstance(self.protection, GlobalRWLockProtection):
            self._wake_global_rwlock_waiters()

        if isinstance(self.protection, PerCellMutexProtection):
            for proc in self.processes:
                if proc.state == ProcessState.WAITING:
                    step = proc.pending_step or self._next_step(proc)
                    if step and step.op != ProcessOp.IDLE:
                        self._try_grant(proc, step)

    def _wake_rwlock_waiters(self) -> None:
        prot = self.protection
        if not isinstance(prot, RWLockProtection):
            return
        addresses = set(prot.readers) | set(prot.writer) | set(prot.read_wait) | set(
            prot.write_wait
        )
        for address in addresses:
            prot._ensure(address)
            if prot.writer[address] is None:
                read_q = prot.read_wait.get(address, [])
                still_waiting: list[int] = []
                for pid in read_q:
                    proc = self._get_process(pid)
                    if not proc or proc.state != ProcessState.WAITING:
                        continue
                    step = proc.pending_step
                    if step and step.op == ProcessOp.READ and step.address == address:
                        if self._try_grant(proc, step):
                            proc.pending_step = None
                        else:
                            still_waiting.append(pid)
                    else:
                        still_waiting.append(pid)
                prot.read_wait[address] = still_waiting

            if prot.writer[address] is None and not prot.readers[address]:
                write_q = prot.write_wait.get(address, [])
                if write_q:
                    pid = write_q[0]
                    proc = self._get_process(pid)
                    if proc and proc.state == ProcessState.WAITING:
                        step = proc.pending_step
                        if (
                            step
                            and step.op == ProcessOp.WRITE
                            and step.address == address
                            and self._try_grant(proc, step)
                        ):
                            prot.write_wait[address] = write_q[1:]
                            proc.pending_step = None

    def _wake_global_rwlock_waiters(self) -> None:
        prot = self.protection
        if not isinstance(prot, GlobalRWLockProtection):
            return
        if prot.writer is None:
            still_waiting: list[int] = []
            for pid in prot.read_wait:
                proc = self._get_process(pid)
                if not proc or proc.state != ProcessState.WAITING:
                    continue
                step = proc.pending_step
                if step and step.op == ProcessOp.READ:
                    if self._try_grant(proc, step):
                        proc.pending_step = None
                    else:
                        still_waiting.append(pid)
                else:
                    still_waiting.append(pid)
            prot.read_wait = still_waiting

        if prot._writers_may_proceed() and prot.write_wait:
            pid = prot.write_wait[0]
            proc = self._get_process(pid)
            if proc and proc.state == ProcessState.WAITING:
                step = proc.pending_step
                if (
                    step
                    and step.op == ProcessOp.WRITE
                    and self._try_grant(proc, step)
                ):
                    prot.write_wait = prot.write_wait[1:]
                    proc.pending_step = None

    def _paint_cell(self, address: int, op: ProcessOp) -> None:
        if self.memory.states[address] == CellState.CORRUPTED:
            return
        if op == ProcessOp.READ:
            self.memory.states[address] = CellState.READING
        elif op == ProcessOp.WRITE:
            self.memory.states[address] = CellState.WRITING

    def _detect_races(
        self, active_access: dict[int, list[tuple[int, ProcessOp]]]
    ) -> None:
        for address, accessors in active_access.items():
            if len(accessors) < 2:
                continue
            ops = [op for _, op in accessors]
            if ProcessOp.WRITE in ops:
                self.memory.mark_corrupted(address)
                self._metrics["corruption_count"] += 1
                for pid, _ in accessors:
                    proc = self._get_process(pid)
                    if proc and not proc.crashed:
                        proc.crash()
                        self._metrics["crash_count"] += 1
                self._log_event(
                    None,
                    "race",
                    address,
                    EventOutcome.CORRUPTED,
                    f"Corrupção em @{address}: acesso concorrente",
                )

    def _update_reader_parallelism(self) -> None:
        if isinstance(self.protection, GlobalRWLockProtection):
            n = len(self.protection.readers)
            if n > self._metrics["reader_parallelism_max"]:
                self._metrics["reader_parallelism_max"] = n
            return
        if isinstance(self.protection, RWLockProtection):
            for readers in self.protection.readers.values():
                n = len(readers)
                if n > self._metrics["reader_parallelism_max"]:
                    self._metrics["reader_parallelism_max"] = n

    def _get_process(self, pid: int) -> SimulatedProcess | None:
        for p in self.processes:
            if p.pid == pid:
                return p
        return None

    def _log_event(
        self,
        pid: int | None,
        op: str,
        address: int | None,
        outcome: EventOutcome,
        message: str,
    ) -> None:
        event = EventDTO(
            tick=self.tick_count,
            pid=pid,
            op=op,
            address=address,
            outcome=outcome,
            message=message,
        )
        self.events.append(event)
        if len(self.events) > self.max_events:
            self.events = self.events[-self.max_events :]

    def get_state(self) -> SimulationStateDTO:
        return SimulationStateDTO(
            running=self.running,
            protection=self.protection_mode,
            semaphore_k=self.semaphore_k,
            rwlock_reader_preference=self.rwlock_reader_preference,
            grid_size=self.memory.grid_size,
            process_count=self.process_count,
            random_mode=self.random_mode,
            custom_mode=self.custom_mode,
            cells=self.memory.to_dto_list(),
            processes=[p.to_dto() for p in self.processes],
            events=list(self.events),
            metrics=metrics_to_dto(self._metrics, self.tick_count),
            scenario_name=self.scenario_name,
        )


engine = SimulationEngine()
