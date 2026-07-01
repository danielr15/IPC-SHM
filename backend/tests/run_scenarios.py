"""Casos de teste automatizados do motor de simulação."""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from engine.simulator import SimulationEngine


def run_scenario(
    name: str,
    ticks: int,
    *,
    seed: int = 42,
    expect_corruption: int | None = None,
    expect_deadlock: int | None = None,
    expect_no_corruption: bool = False,
) -> None:
    engine = SimulationEngine()
    engine.load_scenario(name, seed=seed)
    for _ in range(ticks):
        state = engine.step()
        if not engine.running and state.metrics.deadlock_count > 0:
            break

    m = state.metrics
    print(f"[{name}] ticks={m.tick} corruption={m.corruption_count} "
          f"crashes={m.crash_count} blocked={m.blocked_count} "
          f"completed={m.completed_ops} deadlocks={m.deadlock_count}")

    if expect_corruption is not None and m.corruption_count < expect_corruption:
        raise AssertionError(
            f"{name}: esperava >= {expect_corruption} corrupções, obteve {m.corruption_count}"
        )
    if expect_no_corruption and m.corruption_count > 0:
        raise AssertionError(f"{name}: corrupção inesperada ({m.corruption_count})")
    if expect_deadlock is not None and m.deadlock_count < expect_deadlock:
        raise AssertionError(
            f"{name}: esperava deadlock, obteve {m.deadlock_count}"
        )


def main() -> None:
    run_scenario("race_write", 80, expect_corruption=1)
    run_scenario("race_read_write", 80, expect_corruption=1)
    run_scenario("safe_mutex", 60, expect_no_corruption=True)
    run_scenario("parallel_read", 40, expect_no_corruption=True)
    run_scenario("global_parallel_read", 40, expect_no_corruption=True)
    run_scenario("global_writer_blocks", 40, expect_no_corruption=True)
    run_scenario("semaphore_pool", 50, expect_no_corruption=True)
    run_scenario("deadlock_demo", 30, expect_deadlock=1)

    # deadlock_random é estocástico — só verifica que executa sem erro
    engine = SimulationEngine()
    engine.load_scenario("deadlock_random", seed=42)
    for _ in range(100):
        engine.step()
    print("[deadlock_random] ticks=100 ok (deadlock opcional)")
    print("\nTodos os cenários passaram.")


if __name__ == "__main__":
    main()
