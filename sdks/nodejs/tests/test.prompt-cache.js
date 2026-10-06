// Prompt caching: what the provider read from and wrote to its prompt
// cache is kept on a model call's usage and its cost breakdown, so a
// host can see whether caching is working and what it saved.
//
// The upstream call is faked by patching the integration's OpenAI
// client (same approach as test.custom-inference.js).

import assert from "assert";
import OpenRouterIntegration, { readCacheUsage } from "../src/integrations/openrouter.js";

let failures = 0;
function check(name, fn) {
  return fn().then(
    () => console.log(`  ✓ ${name}`),
    (err) => {
      failures++;
      console.error(`  ✗ ${name}\n    ${err.message}`);
    },
  );
}

function fakeStream(chunks) {
  return (async function* () {
    for (const c of chunks) yield c;
  })();
}

const pricing = {
  items: [
    { key: "input_cost_per_million", cost: 3 },
    { key: "output_cost_per_million", cost: 15 },
  ],
};

console.log("prompt-cache:");

await check("reads cached and written tokens from a usage block", async () => {
  assert.deepEqual(readCacheUsage({ prompt_tokens_details: { cached_tokens: 900, cache_write_tokens: 100 } }), {
    cached_tokens: 900,
    cache_write_tokens: 100,
  });
  assert.deepEqual(readCacheUsage({ prompt_tokens: 5 }), { cached_tokens: 0, cache_write_tokens: 0 });
  assert.deepEqual(readCacheUsage(undefined), { cached_tokens: 0, cache_write_tokens: 0 });
});

await check("a streamed call keeps the cache counts on usage and on the input cost line", async () => {
  const i = new OpenRouterIntegration("k");
  i.client.chat.completions.create = async () =>
    fakeStream([
      { object: "chat.completion.chunk", choices: [{ delta: { role: "assistant", content: "Hi" }, finish_reason: null }] },
      {
        object: "chat.completion.chunk",
        choices: [{ delta: {}, finish_reason: "stop" }],
        usage: {
          prompt_tokens: 1000,
          completion_tokens: 10,
          total_tokens: 1010,
          cost: 0.0012,
          prompt_tokens_details: { cached_tokens: 800, cache_write_tokens: 150 },
        },
      },
    ]);
  const res = await i.chatCompletion(
    { model: "anthropic/claude-sonnet-4.6", messages: [{ role: "user", content: "hi" }] },
    { type: "anthropic-claude-sonnet-4-6", id: "llm", pricing },
    {},
  );
  assert.equal(res.usage.cached_tokens, 800);
  assert.equal(res.usage.cache_write_tokens, 150);
  assert.equal(res.cost_total, 0.0012, "the provider's total (already reflecting the cache) stays the total");
  const input = res.cost_itemized.find((c) => c.label === "Input Tokens");
  assert.equal(input.tokens, 1000);
  assert.equal(input.cached_tokens, 800);
  assert.equal(input.cache_write_tokens, 150);
});

await check("a call with no cache reports zeros and leaves the cost lines as they were", async () => {
  const i = new OpenRouterIntegration("k");
  i.client.chat.completions.create = async () =>
    fakeStream([
      { object: "chat.completion.chunk", choices: [{ delta: { role: "assistant", content: "Hi" }, finish_reason: "stop" }], usage: { prompt_tokens: 5, completion_tokens: 2, total_tokens: 7 } },
    ]);
  const res = await i.chatCompletion(
    { model: "x", messages: [{ role: "user", content: "hi" }] },
    { type: "x", id: "llm", pricing },
    {},
  );
  assert.equal(res.usage.cached_tokens, 0);
  assert.equal(res.usage.cache_write_tokens, 0);
  const input = res.cost_itemized.find((c) => c.label === "Input Tokens");
  assert.ok(!("cached_tokens" in input), "no cache keys when nothing was cached");
});

if (failures > 0) {
  console.error(`\n${failures} prompt-cache test(s) failed`);
  process.exit(1);
}
console.log("prompt-cache: all passed");
