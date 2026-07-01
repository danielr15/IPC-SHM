from __future__ import annotations

from abc import ABC, abstractmethod

from .models import ProcessOp, ProtectionMode
from .process import SimulatedProcess


class ProtectionStrategy(ABC):
    @abstractmethod
    def reset(self) -> None: ...

    @abstractmethod
    def request_access(
        self, process: SimulatedProcess, op: ProcessOp, address: int
    ) -> bool: ...

    @abstractmethod
    def release_access(
        self, process: SimulatedProcess, op: ProcessOp, address: int
    ) -> None: ...

    @abstractmethod
    def detect_deadlock(self, processes: list[SimulatedProcess]) -> bool: ...


class NoProtection(ProtectionStrategy):
    def reset(self) -> None:
        pass

    def request_access(
        self, process: SimulatedProcess, op: ProcessOp, address: int
    ) -> bool:
        return True

    def release_access(
        self, process: SimulatedProcess, op: ProcessOp, address: int
    ) -> None:
        pass

    def detect_deadlock(self, processes: list[SimulatedProcess]) -> bool:
        return False


class MutexProtection(ProtectionStrategy):
    def __init__(self) -> None:
        self.holder: int | None = None
        self.wait_queue: list[int] = []

    def reset(self) -> None:
        self.holder = None
        self.wait_queue = []

    def request_access(
        self, process: SimulatedProcess, op: ProcessOp, address: int
    ) -> bool:
        if self.holder is None:
            self.holder = process.pid
            process.held_locks = [address]
            return True
        if self.holder == process.pid:
            return True
        if process.pid not in self.wait_queue:
            self.wait_queue.append(process.pid)
        return False

    def release_access(
        self, process: SimulatedProcess, op: ProcessOp, address: int
    ) -> None:
        if self.holder == process.pid:
            self.holder = None
            process.held_locks = []
            if self.wait_queue:
                self.holder = self.wait_queue.pop(0)

    def detect_deadlock(self, processes: list[SimulatedProcess]) -> bool:
        return False


class SemaphoreProtection(ProtectionStrategy):
    def __init__(self, k: int = 3) -> None:
        self.k = k
        self.available = k
        self.holders: set[int] = set()
        self.wait_queue: list[int] = []

    def reset(self) -> None:
        self.available = self.k
        self.holders = set()
        self.wait_queue = []

    def set_k(self, k: int) -> None:
        self.k = k
        self.available = k

    def request_access(
        self, process: SimulatedProcess, op: ProcessOp, address: int
    ) -> bool:
        if process.pid in self.holders:
            return True
        if self.available > 0:
            self.available -= 1
            self.holders.add(process.pid)
            process.held_locks = [address]
            return True
        if process.pid not in self.wait_queue:
            self.wait_queue.append(process.pid)
        return False

    def release_access(
        self, process: SimulatedProcess, op: ProcessOp, address: int
    ) -> None:
        if process.pid in self.holders:
            self.holders.discard(process.pid)
            self.available += 1
            process.held_locks = []
            if self.wait_queue and self.available > 0:
                next_pid = self.wait_queue.pop(0)
                self.available -= 1
                self.holders.add(next_pid)

    def detect_deadlock(self, processes: list[SimulatedProcess]) -> bool:
        return False


class RWLockProtection(ProtectionStrategy):
    def __init__(self) -> None:
        self.readers: dict[int, set[int]] = {}
        self.writer: dict[int, int | None] = {}
        self.read_wait: dict[int, list[int]] = {}
        self.write_wait: dict[int, list[int]] = {}

    def reset(self) -> None:
        self.readers = {}
        self.writer = {}
        self.read_wait = {}
        self.write_wait = {}

    def _ensure(self, address: int) -> None:
        if address not in self.readers:
            self.readers[address] = set()
            self.writer[address] = None
            self.read_wait[address] = []
            self.write_wait[address] = []

    @staticmethod
    def _remove_from_queue(queue: list[int], pid: int) -> None:
        while pid in queue:
            queue.remove(pid)

    def request_access(
        self, process: SimulatedProcess, op: ProcessOp, address: int
    ) -> bool:
        self._ensure(address)
        if op == ProcessOp.READ:
            if process.pid in self.readers[address]:
                process.held_locks = [address]
                return True
            if self.writer[address] is None:
                self.readers[address].add(process.pid)
                self._remove_from_queue(self.read_wait[address], process.pid)
                process.held_locks = [address]
                return True
            if process.pid not in self.read_wait[address]:
                self.read_wait[address].append(process.pid)
            return False
        if self.writer[address] == process.pid:
            process.held_locks = [address]
            return True
        if self.writer[address] is None and not self.readers[address]:
            self.writer[address] = process.pid
            self._remove_from_queue(self.write_wait[address], process.pid)
            process.held_locks = [address]
            return True
        if process.pid not in self.write_wait[address]:
            self.write_wait[address].append(process.pid)
        return False

    def release_access(
        self, process: SimulatedProcess, op: ProcessOp, address: int
    ) -> None:
        self._ensure(address)
        if op == ProcessOp.READ:
            self.readers[address].discard(process.pid)
            process.held_locks = []
        elif self.writer[address] == process.pid:
            self.writer[address] = None
            process.held_locks = []

    def detect_deadlock(self, processes: list[SimulatedProcess]) -> bool:
        return False


class GlobalRWLockProtection(ProtectionStrategy):
    """RW-lock global com preferência por leitores (reader preference).

    Vários leitores ou um escritor no segmento inteiro. Escritores só entram
    quando não há leitores ativos nem leitores aguardando na fila.
    """

    def __init__(self, reader_preference: bool = True) -> None:
        self.reader_preference = reader_preference
        self.readers: set[int] = set()
        self.writer: int | None = None
        self.read_wait: list[int] = []
        self.write_wait: list[int] = []

    def reset(self) -> None:
        self.readers = set()
        self.writer = None
        self.read_wait = []
        self.write_wait = []

    def _writers_may_proceed(self) -> bool:
        if self.writer is not None or self.readers:
            return False
        if self.reader_preference and self.read_wait:
            return False
        return True

    def request_access(
        self, process: SimulatedProcess, op: ProcessOp, address: int
    ) -> bool:
        if op == ProcessOp.READ:
            if process.pid in self.readers:
                process.held_locks = [address]
                return True
            if self.writer is None:
                self.readers.add(process.pid)
                RWLockProtection._remove_from_queue(self.read_wait, process.pid)
                process.held_locks = [address]
                return True
            if process.pid not in self.read_wait:
                self.read_wait.append(process.pid)
            return False
        if self.writer == process.pid:
            process.held_locks = [address]
            return True
        if self._writers_may_proceed():
            self.writer = process.pid
            RWLockProtection._remove_from_queue(self.write_wait, process.pid)
            process.held_locks = [address]
            return True
        if process.pid not in self.write_wait:
            self.write_wait.append(process.pid)
        return False

    def release_access(
        self, process: SimulatedProcess, op: ProcessOp, address: int
    ) -> None:
        if op == ProcessOp.READ:
            self.readers.discard(process.pid)
            process.held_locks = []
        elif self.writer == process.pid:
            self.writer = None
            process.held_locks = []

    def detect_deadlock(self, processes: list[SimulatedProcess]) -> bool:
        return False


class PerCellMutexProtection(ProtectionStrategy):
    """Mutex independente por endereço — usado para demonstrar deadlock."""

    def __init__(self) -> None:
        self.holders: dict[int, int] = {}
        self.wait_queues: dict[int, list[int]] = {}

    def reset(self) -> None:
        self.holders = {}
        self.wait_queues = {}

    def request_access(
        self, process: SimulatedProcess, op: ProcessOp, address: int
    ) -> bool:
        if self.holders.get(address) == process.pid:
            return True
        if address not in self.holders:
            self.holders[address] = process.pid
            if address not in process.held_locks:
                process.held_locks.append(address)
            return True
        q = self.wait_queues.setdefault(address, [])
        if process.pid not in q:
            q.append(process.pid)
        return False

    def release_access(
        self, process: SimulatedProcess, op: ProcessOp, address: int
    ) -> None:
        if self.holders.get(address) == process.pid:
            del self.holders[address]
            if address in process.held_locks:
                process.held_locks.remove(address)
            q = self.wait_queues.get(address, [])
            if q:
                self.holders[address] = q.pop(0)

    def detect_deadlock(self, processes: list[SimulatedProcess]) -> bool:
        from .models import ProcessState

        wait_for: dict[int, int] = {}
        for proc in processes:
            if proc.state != ProcessState.WAITING or not proc.pending_step:
                continue
            addr = proc.pending_step.address
            holder = self.holders.get(addr)
            if holder is not None and holder != proc.pid:
                wait_for[proc.pid] = holder

        if len(wait_for) < 2:
            return False

        def in_cycle(start: int) -> bool:
            seen: set[int] = set()
            cur: int | None = start
            while cur is not None and cur in wait_for:
                if cur in seen:
                    return True
                seen.add(cur)
                cur = wait_for.get(cur)
            return False

        return any(in_cycle(pid) for pid in wait_for)


def create_protection(
    mode: ProtectionMode, k: int = 3, *, reader_preference: bool = True
) -> ProtectionStrategy:
    if mode == ProtectionMode.NONE:
        return NoProtection()
    if mode == ProtectionMode.MUTEX:
        return MutexProtection()
    if mode == ProtectionMode.SEMAPHORE:
        return SemaphoreProtection(k)
    if mode == ProtectionMode.RWLOCK:
        return RWLockProtection()
    if mode == ProtectionMode.RWLOCK_GLOBAL:
        return GlobalRWLockProtection(reader_preference=reader_preference)
    if mode == ProtectionMode.CELL_MUTEX:
        return PerCellMutexProtection()
    raise ValueError(f"Unknown protection mode: {mode}")
