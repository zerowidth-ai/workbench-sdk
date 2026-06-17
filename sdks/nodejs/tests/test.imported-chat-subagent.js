/**
 * Regression test for processImportedChatNode (imported flow used as a chat
 * sub-agent / plugin).
 *
 * Pins two bugs that were fixed:
 *   1. The sub-agent's own assistant replies must be appended to the conversation
 *      history across turns (the output was previously read by bare node id and
 *      never matched, so replies were dropped).
 *   2. Custom chat-stream keys must be honored (the key was previously derived by
 *      a broken node-id lookup that always fell back to 'chat').
 *
 * Deterministic & offline: we stub processNodeWithArgs so the imported sub-flow
 * doesn't actually call an LLM — we only exercise the conversation-state logic.
 *
 * Run with: node tests/test.imported-chat-subagent.js
 */
import assert from 'assert';
import Zv1 from '../src/index.js';

function buildFlow(chatKey) {
  const importId = 'imported-subagent-test';
  const p = (s) => `${importId}-${s}`;
  const importDef = {
    display_name: 'Memory Agent',
    id: importId,
    imports: [],
    nodes: [
      { id: p('inchat'), type: 'input-chat', settings: { key: chatKey } },
      { id: p('llm'), type: 'openai-gpt-4o-mini', settings: {} },
      { id: p('outchat'), type: 'output-chat', settings: { key: chatKey } },
    ],
    links: [
      { from: { node_id: p('inchat'), port_name: 'messages' }, to: { node_id: p('llm'), port_name: 'messages' } },
      { from: { node_id: p('llm'), port_name: 'message' }, to: { node_id: p('outchat'), port_name: 'message' } },
    ],
  };
  return {
    nodes: [
      { id: 'parent-llm', type: 'openai-gpt-4o-mini' },
      { id: 'sub', type: importId },
      { id: 'pin', type: 'input-chat' },
      { id: 'pout', type: 'output-chat' },
    ],
    links: [
      { from: { node_id: 'sub' }, to: { node_id: 'parent-llm' }, type: 'plugin' },
      { from: { node_id: 'pin', port_name: 'messages' }, to: { node_id: 'parent-llm', port_name: 'messages' } },
      { from: { node_id: 'parent-llm', port_name: 'message' }, to: { node_id: 'pout', port_name: 'message' } },
    ],
    imports: [importDef],
  };
}

async function runCase(chatKey, label) {
  console.log(`\n--- ${label} (chat key = "${chatKey}") ---`);
  const engine = await Zv1.create(buildFlow(chatKey), { keys: {} });
  const subNode = engine.flow.nodes.find((n) => n.id === 'sub');
  assert.ok(subNode, 'import node "sub" should exist');

  // Stub the sub-flow execution: capture the history it receives, and return a
  // canned assistant reply keyed by the output-chat's key (how the real import
  // process emits chat output).
  const seenHistories = [];
  let turn = 0;
  engine.processNodeWithArgs = async (_node, transformedArgs) => {
    turn += 1;
    seenHistories.push(transformedArgs[chatKey]);
    return { [chatKey]: [{ role: 'assistant', content: `reply-${turn}` }] };
  };

  await engine.processImportedChatNode(subNode, { [chatKey]: 'turn 1 user' });
  await engine.processImportedChatNode(subNode, { [chatKey]: 'turn 2 user' });

  const expectedKey = `sub_${chatKey}`;
  const stateKeys = Object.keys(engine._conversationState || {});

  // Bug #2: the stream must be keyed by the real chat key, not collapsed to 'chat'
  assert.deepStrictEqual(stateKeys, [expectedKey],
    `conversation should live under "${expectedKey}", got: ${JSON.stringify(stateKeys)}`);

  // Bug #1: full alternating history with assistant replies persisted
  const hist = engine._conversationState[expectedKey];
  const shape = hist.map((m) => `${m.role}:${m.content}`);
  assert.deepStrictEqual(shape,
    ['user:turn 1 user', 'assistant:reply-1', 'user:turn 2 user', 'assistant:reply-2'],
    `history should alternate user/assistant, got: ${JSON.stringify(shape)}`);

  // The sub-flow on turn 2 must have received the assistant reply from turn 1
  const turn2Roles = seenHistories[1].map((m) => m.role);
  assert.deepStrictEqual(turn2Roles, ['user', 'assistant', 'user'],
    `turn-2 sub-flow input should include the prior assistant reply, got: ${JSON.stringify(turn2Roles)}`);

  await engine.cleanup?.();
  console.log(`  ✓ stream "${expectedKey}" accumulated:`, shape.join('  |  '));
}

async function main() {
  console.log('Testing imported chat sub-agent (processImportedChatNode)...');
  try {
    await runCase('chat', 'DEFAULT KEY');
    await runCase('history', 'CUSTOM KEY');
    console.log('\n✅ All imported-chat-subagent tests passed.');
    process.exit(0);
  } catch (err) {
    console.error('\n❌ Test failed:', err.message);
    process.exit(1);
  }
}

main();
