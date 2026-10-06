/**
 * Prompt caching for models that need to be told where to cache.
 *
 * Anthropic models cache a request's prefix only up to blocks marked
 * `cache_control: { type: "ephemeral" }`, at most four per request.
 * Everything before a mark (tools, then the system prompt, then the
 * messages) is reused by the next call that starts the same way, read
 * at a fraction of the input price. Other providers OpenRouter serves
 * cache a repeated prefix on their own.
 *
 * Marks come from two places:
 *   - the System Prompt node marks the end of the prompt's fixed part,
 *     before the first variable it fills in, so values that change per
 *     run (the time, memory, search results) don't spoil the cache;
 *   - this adds one on the last user message, so earlier turns are
 *     cached for the next call.
 * Marks a caller placed itself count too. Past four, the latest are
 * dropped. For a model that doesn't take marks, or with caching off,
 * every mark is removed so no provider sees a field it doesn't expect.
 */

const MAX_MARKS = 4;
const MARK = { type: "ephemeral" };

/** Models that cache only where they're told to. */
export function takesCacheMarks(model) {
  return typeof model === "string" && model.startsWith("anthropic/");
}

function withoutMark(block) {
  if (!block || typeof block !== "object" || !("cache_control" in block)) return block;
  const { cache_control, ...rest } = block;
  return rest;
}

/**
 * The messages to send, with cache marks placed for a model that takes
 * them and removed for any other. Never mutates the input.
 */
export function applyPromptCache(messages, { model, enabled = true } = {}) {
  if (!Array.isArray(messages)) return messages;
  const marking = enabled && takesCacheMarks(model);

  // Keep the earliest marks, up to the limit (none when not marking).
  let kept = 0;
  const out = messages.map((m) => {
    if (!m || !Array.isArray(m.content)) return m;
    if (!m.content.some((b) => b && b.cache_control)) return m;
    return {
      ...m,
      content: m.content.map((b) => {
        if (!b || !b.cache_control) return b;
        // A mark on an empty block is refused by the provider.
        if (marking && kept < MAX_MARKS && !(b.type === "text" && !b.text)) {
          kept++;
          return b;
        }
        return withoutMark(b);
      }),
    };
  });
  if (!marking || kept >= MAX_MARKS) return out;

  // The last user message's last text block, so the conversation so far
  // is cached for the next call.
  for (let i = out.length - 1; i >= 0; i--) {
    const m = out[i];
    if (m?.role !== "user") continue;
    const blocks =
      typeof m.content === "string"
        ? [{ type: "text", text: m.content }]
        : Array.isArray(m.content)
          ? [...m.content]
          : null;
    if (!blocks || blocks.some((b) => b && b.cache_control)) break;
    for (let j = blocks.length - 1; j >= 0; j--) {
      if (blocks[j]?.type === "text" && blocks[j].text) {
        blocks[j] = { ...blocks[j], cache_control: MARK };
        out[i] = { ...m, content: blocks };
        break;
      }
    }
    break;
  }
  return out;
}
