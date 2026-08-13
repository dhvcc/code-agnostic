"""P2: file_lock serializes concurrent read-modify-write sections so parallel
`apply` runs can't race on shared state."""

import json
import sys
import threading
from pathlib import Path

import pytest

from code_agnostic.apps.apps_service import AppsService
from code_agnostic.core.repository import CoreRepository
from code_agnostic.executor import SyncExecutor
from code_agnostic.models import SyncPlan
from code_agnostic.utils import file_lock


def _write_source_root(root: Path, server_name: str) -> None:
    (root / "config").mkdir(parents=True)
    (root / "config" / "apps.json").write_text(
        json.dumps({"cursor": True}), encoding="utf-8"
    )
    (root / "config" / "mcp.base.json").write_text(
        json.dumps({"mcpServers": {server_name: {"command": server_name, "args": []}}}),
        encoding="utf-8",
    )


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
        def _execute(
            self, plan: SyncPlan, persist_state: bool = True
        ) -> tuple[int, int, list[str]]:
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


@pytest.mark.skipif(sys.platform.startswith("win"), reason="POSIX flock semantics")
def test_apply_serializes_plan_and_execute_across_source_roots(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(Path, "home", classmethod(lambda cls: tmp_path))
    source_a = tmp_path / "source-a"
    source_b = tmp_path / "source-b"
    _write_source_root(source_a, "from-a")
    _write_source_root(source_b, "from-b")
    services = [
        AppsService(CoreRepository(source_a)),
        AppsService(CoreRepository(source_b)),
    ]

    first_plan_started = threading.Event()
    release_first_plan = threading.Event()
    second_plan_entered = threading.Event()
    original_plan = AppsService.plan_for_target

    def gated_plan(
        self: AppsService, target: str, *, apply_excludes: bool = False
    ) -> SyncPlan:
        if self.core_repository.root == source_a:
            first_plan_started.set()
            assert release_first_plan.wait(5)
        elif self.core_repository.root == source_b:
            second_plan_entered.set()
        return original_plan(self, target, apply_excludes=apply_excludes)

    monkeypatch.setattr(AppsService, "plan_for_target", gated_plan)
    failures: list[BaseException] = []

    def apply(service: AppsService) -> None:
        try:
            service.apply_target("cursor")
        except (
            BaseException
        ) as exc:  # pragma: no cover - assertion below reports failures
            failures.append(exc)

    first = threading.Thread(target=apply, args=(services[0],))
    second = threading.Thread(target=apply, args=(services[1],))
    first.start()
    assert first_plan_started.wait(5)
    second.start()
    assert not second_plan_entered.wait(
        0.2
    ), "second source planned before first source applied"
    release_first_plan.set()
    first.join(5)
    second.join(5)

    assert not first.is_alive()
    assert not second.is_alive()
    assert failures == []
    target = json.loads((tmp_path / ".cursor" / "mcp.json").read_text(encoding="utf-8"))
    assert set(target["mcpServers"]) == {"from-a", "from-b"}
    assert CoreRepository(source_a).load_state().managed_mcp["app:cursor:mcp"] == [
        "from-a"
    ]
    assert CoreRepository(source_b).load_state().managed_mcp["app:cursor:mcp"] == [
        "from-b"
    ]
