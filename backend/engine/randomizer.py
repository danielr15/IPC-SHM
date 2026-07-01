from __future__ import annotations

import random

from .models import ProcessConfig, ProcessOp, RandomProfile, ScriptStep


def make_rng(seed: int | None) -> random.Random:
    if seed is not None:
        return random.Random(seed)
    return random.Random()


def build_random_processes(
    profile: RandomProfile, grid_size: int, rng: random.Random
) -> list[ProcessConfig]:
    return [
        ProcessConfig(pid=pid, script=[])
        for pid in range(1, profile.process_count + 1)
    ]


def initial_think(profile: RandomProfile, pid: int, rng: random.Random) -> int:
    return rng.randint(0, profile.start_delay_max)


def pick_address(
    rng: random.Random,
    grid_size: int,
    *,
    avoid: set[int] | None = None,
    prefer_different: bool = False,
) -> int:
    total = grid_size * grid_size
    if prefer_different and avoid:
        candidates = [a for a in range(total) if a not in avoid]
        if candidates:
            return rng.choice(candidates)
    return rng.randint(0, total - 1)


def pick_operation(profile: RandomProfile, pid: int, rng: random.Random) -> ProcessOp:
    if pid in profile.writer_pids:
        return ProcessOp.WRITE
    if pid in profile.reader_pids:
        return ProcessOp.READ
    if rng.random() < profile.read_probability:
        return ProcessOp.READ
    return ProcessOp.WRITE


def generate_access_step(
    profile: RandomProfile,
    pid: int,
    grid_size: int,
    rng: random.Random,
    held_locks: list[int] | None = None,
) -> ScriptStep:
    op = pick_operation(profile, pid, rng)
    held = set(held_locks or [])
    address = pick_address(
        rng,
        grid_size,
        avoid=held,
        prefer_different=profile.prefer_different_cell_when_holding and bool(held),
    )
    duration = rng.randint(profile.duration_min, profile.duration_max)
    value = rng.randint(1, 999) if op == ProcessOp.WRITE else 0
    return ScriptStep(op=op, address=address, value=value, duration=duration)


def schedule_think(profile: RandomProfile, rng: random.Random) -> int:
    return rng.randint(profile.think_min, profile.think_max)
