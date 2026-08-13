"""P2: file_lock serializes concurrent read-modify-write sections so parallel
`apply` runs can't race on shared state."""

import sys
import threading
from pathlib import Path

import pytest

from code_agnostic.core.repository import CoreRepository
from code_agnostic.executor import SyncExecutor
from code_agnostic.models import SyncPlan
from code_agnostic.utils import file_lock


def test_file_lock_acquire_release_roundtrip(tmp_path: Path) -> None:
    lock = tmp_path / ".sync.lock"
    # Acquire/release must not raise and must be re-acquirable once released.
    # (On non-POSIX the lock degrades to a no-op, so the lock file may not exist.)
    with file_lock(lock):
        pass
    with file_lock(lock):
        pass


@pytest.mark.skipif(sys.platform.startswith("win"), reason="POSIX flock semantics")
def test_file_lock_serializes_concurrent_writers(tmp_path: Path) -> None:
    lock = tmp_path / ".sync.lock"
    counter_file = tmp_path / "counter.txt"
    counter_file.write_text("0", encoding="utf-8")
    overlaps = 0
    active = 0
    active_guard = threading.Lock()

    def worker() -> None:
        nonlocal overlaps, active
        with file_lock(lock):
            with active_guard:
                active += 1
                if active > 1:
                    overlaps += 1
            # Non-atomic read-modify-write of a shared file: only safe if the
            # file lock truly serializes the section.
            value = int(counter_file.read_text(encoding="utf-8"))
            counter_file.write_text(str(value + 1), encoding="utf-8")
            with active_guard:
                active -= 1

    threads = [threading.Thread(target=worker) for _ in range(20)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    assert overlaps == 0, "lock holders overlapped"
    assert int(counter_file.read_text(encoding="utf-8")) == 20


@pytest.mark.skipif(sys.platform.startswith("win"), reason="POSIX flock semantics")
def test_executors_with_independent_sources_share_target_lock(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(Path, "home", classmethod(lambda cls: tmp_path))
    active = 0
    overlaps = 0
    guard = threading.Lock()

    class ProbeExecutor(SyncExecutor):
        def _execute(self, plan: SyncPlan, persist_state: bool = True):
            nonlocal active, overlaps
            with guard:
                active += 1
                if active > 1:
                    overlaps += 1
            threading.Event().wait(0.02)
            with guard:
                active -= 1
            return 0, 0, []

    executors = [
        ProbeExecutor(CoreRepository(tmp_path / "source-a")),
        ProbeExecutor(CoreRepository(tmp_path / "source-b")),
    ]
    threads = [
        threading.Thread(target=executor.execute, args=(SyncPlan([], [], []),))
        for executor in executors
    ]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()

    assert overlaps == 0
