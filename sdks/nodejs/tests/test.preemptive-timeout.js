/**
 * Regression test for preemptive flow timeout (AbortController).
 *
 * Before: the flow timeout only set a flag checked *between* nodes, so a single
 * hung node (e.g. a stalled LLM/HTTP call) parked the execution loop and the
 * flow could run past its timeout indefinitely.
 *
 * After: run() aborts an AbortController on timeout; node execution is raced
 * against the signal, so a hung node is cut loose at ~timeout and the run
 * rejects promptly. Normal (fast) runs are unaffected.
 *
 * Deterministic & offline: we stub a node's process to hang — no network.
 *
 * Run with: node tests/test.preemptive-timeout.js
 */
import assert from 'assert';
import Zv1 from '../src/index.js';

const flow = {
  nodes: [
    { id: 'in', type: 'input-data', settings: { key: 'x' } },
    { id: 'out', type: 'output-data', settings: { key: 'out' } },
  ],
  links: [
    { from: { node_id: 'in', port_name: 'value' }, to: { node_id: 'out', port_name: 'value' } },
  ],
};

async function testNormalRunUnaffected() {
  console.log('\n--- normal run completes, signal not aborted ---');
  const engine = await Zv1.create(flow, { keys: {} });
  const res = await engine.run({ x: 42 }, 5000);
  assert.ok(res, 'run should return a result');
  assert.strictEqual(engine.abortController.signal.aborted, false, 'signal should NOT be aborted on a normal run');
  console.log('  ✓ completed normally, abort signal clean');
}

async function testHungNodeIsPreempted() {
  console.log('\n--- hung node is preempted at ~timeout (not parked forever) ---');
  const engine = await Zv1.create(flow, { keys: {} });

  // Force the terminal node to hang forever.
  engine.nodes['output-data'].process = () => new Promise(() => {});

  const timeout = 600;
  const t0 = Date.now();
  let threw = false;
  let message = '';
  try {
    await engine.run({ x: 1 }, timeout);
  } catch (e) {
    threw = true;
    message = e.message;
  }
  const elapsed = Date.now() - t0;

  assert.ok(threw, 'run should reject when a node hangs past the timeout');
  assert.ok(elapsed < 3000, `run should abort near the timeout, but took ${elapsed}ms (was it parked?)`);
  assert.strictEqual(engine.abortController.signal.aborted, true, 'abort signal should have fired');

  // #1 regression: after a timed-out run the inherited signal must be restored,
  // so a reused engine doesn't treat this run's aborted signal as an ancestor
  // (and instantly abort) on the next run().
  assert.strictEqual(engine._inheritedSignal, null, 'top-level engine has no inherited signal');
  assert.strictEqual(engine.config.signal, engine._inheritedSignal,
    'config.signal must be restored to the inherited signal after a run');

  console.log(`  ✓ aborted in ${elapsed}ms (timeout ${timeout}ms), error: "${message}"`);
}

async function main() {
  console.log('Testing preemptive flow timeout...');
  try {
    await testNormalRunUnaffected();
    await testHungNodeIsPreempted();
    console.log('\n✅ All preemptive-timeout tests passed.');
    process.exit(0);
  } catch (err) {
    console.error('\n❌ Test failed:', err.message);
    process.exit(1);
  }
}

main();
