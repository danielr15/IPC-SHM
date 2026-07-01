from __future__ import annotations

import random

from .models import ProcessConfig, ProcessDTO, ProcessOp, ProcessState, RandomProfile, ScriptStep


class SimulatedProcess:
    def __init__(
        self,
        config: ProcessConfig,
        loop_script: bool = False,
        *,
        random_profile: RandomProfile | None = None,
        random_rng: random.Random | None = None,
        grid_size: int = 4,
        initial_think: int = 0,
    ) -> None:
        self.pid = config.pid
        self.script = list(config.script)
        self.loop_script = loop_script
        self.script_index = 0
        self.state = ProcessState.IDLE
        self.current_step: ScriptStep | None = None
        self.remaining_duration = 0
        self.target_address: int | None = None
        self.wait_ticks = 0
        self.held_locks: list[int] = []
        self.crashed = False
        self.done = False
        self.random_profile = random_profile
        self.random_rng = random_rng or random.Random()
        self.grid_size = grid_size
        self.think_remaining = initial_think
        self.pending_step: ScriptStep | None = None

    def uses_random_behavior(self) -> bool:
        return self.random_profile is not None

    def current_script_step(self) -> ScriptStep | None:
        if self.uses_random_behavior():
            return None
        if self.script_index >= len(self.script):
            if self.loop_script and self.script:
                self.script_index = 0
            else:
                return None
        return self.script[self.script_index]

    def next_random_step(self) -> ScriptStep | None:
        if not self.random_profile:
            return None
        from .randomizer import generate_access_step

        return generate_access_step(
            self.random_profile, self.pid, self.grid_size, self.random_rng, self.held_locks
        )

    def schedule_think_after_op(self) -> None:
        if not self.random_profile:
            return
        from .randomizer import schedule_think

        self.think_remaining = schedule_think(self.random_profile, self.random_rng)

    def advance_script(self) -> None:
        self.script_index += 1
        if self.script_index >= len(self.script):
            if self.loop_script and self.script:
                self.script_index = 0
            else:
                self.done = True
                self.state = ProcessState.DONE

    def start_step(self, step: ScriptStep) -> None:
        self.current_step = step
        self.remaining_duration = step.duration
        self.target_address = step.address if step.op != ProcessOp.IDLE else None
        if step.op == ProcessOp.READ:
            self.state = ProcessState.READING
        elif step.op == ProcessOp.WRITE:
            self.state = ProcessState.WRITING
        else:
            self.state = ProcessState.IDLE

    def finish_current_step(self) -> ScriptStep | None:
        finished = self.current_step
        self.current_step = None
        self.target_address = None
        self.state = ProcessState.IDLE
        if not self.uses_random_behavior():
            self.advance_script()
        return finished

    def crash(self) -> None:
        self.crashed = True
        self.state = ProcessState.CRASHED
        self.current_step = None
        self.remaining_duration = 0
        self.held_locks = []
        self.pending_step = None

    def set_waiting(self) -> None:
        self.state = ProcessState.WAITING
        self.wait_ticks = 0

    def to_dto(self) -> ProcessDTO:
        return ProcessDTO(
            pid=self.pid,
            state=self.state,
            op=self.current_step.op if self.current_step else None,
            target_address=self.target_address,
            script_index=self.script_index,
            wait_ticks=self.wait_ticks,
            held_locks=list(self.held_locks),
        )
