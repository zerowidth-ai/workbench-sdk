"""
Regression test for preemptive flow timeout (Python engine).

Mirrors sdks/nodejs/tests/test.preemptive-timeout.js. Before, the flow timeout
only set a flag checked between nodes, so a hung node parked the launch loop.
After, run() sets an abort asyncio.Event on timeout and _race_abort cancels the
in-flight node task (cancellation propagates into httpx/SDK calls), so a hung
node is cut loose at ~timeout. Normal runs are unaffected.

Deterministic & offline: we stub a node's process to hang — no network, no keys.

Run with: python tests/test_preemptive_timeout.py
"""

from __future__ import annotations

import asyncio
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.engine import Zv1  # noqa: E402

FLOW = {
    "nodes": [
        {"id": "in", "type": "input-data", "settings": {"key": "x"}},
        {"id": "out", "type": "output-data", "settings": {"key": "out"}},
    ],
    "links": [
        {"from": {"node_id": "in", "port_name": "value"},
         "to": {"node_id": "out", "port_name": "value"}},
    ],
}


async def test_normal_run_unaffected() -> None:
    print("\n--- normal run completes, signal not aborted ---")
    engine = await Zv1.create(FLOW, {"keys": {}})
    res = await engine.run({"x": 42}, 5000)
    assert res is not None, "run should return a result"
    assert engine._abort_event is not None and not engine._abort_event.is_set(), \
        "signal should NOT be set on a normal run"
    print("  ok completed normally, abort signal clean")


async def test_hung_node_is_preempted() -> None:
    print("\n--- hung node is preempted at ~timeout (not parked forever) ---")
    engine = await Zv1.create(FLOW, {"keys": {}})

    async def hang(**_kwargs):
        await asyncio.Event().wait()  # never resolves

    engine.nodes["output-data"]["process"] = hang

    timeout_ms = 600
    t0 = time.time()
    raised = False
    message = ""
    try:
        await engine.run({"x": 1}, timeout_ms)
    except Exception as e:  # noqa: BLE001
        raised = True
        message = str(e)
    elapsed = (time.time() - t0) * 1000

    assert raised, "run should raise when a node hangs past the timeout"
    assert elapsed < 3000, f"run should abort near the timeout, took {elapsed:.0f}ms"
    assert engine._abort_event.is_set(), "abort signal should have fired"
    print(f"  ok aborted in {elapsed:.0f}ms (timeout {timeout_ms}ms): {message!r}")


async def main() -> None:
    print("Testing preemptive flow timeout (python)...")
    await test_normal_run_unaffected()
    await test_hung_node_is_preempted()
    print("\nAll preemptive-timeout tests passed.")


if __name__ == "__main__":
    asyncio.run(main())
