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
 * Where marks go, for a model that takes them:
 *   - the end of the system prompt's fixed part. The System Prompt node
 *     records it as `cache_prefix_length` on its text block (the text
 *     before the first variable it fills in); the block is split there
 *     and the first part marked, so a value that changes per run (the
 *     time, memory, search results) doesn't spoil the cache;
 *   - marks the caller placed itself (`cache_control` on a block);
 *   - the last message, whatever its role, so everything so far
 *     (earlier turns, and this turn's tool calls and results) is reused
 *     by the next call.
 * At most four: the earliest three are kept, then the last message.
 * A mark that comes before a one-hour mark gets the one-hour lifetime
 * too, since Anthropic needs longer-lived marks to come first.
 *
 * For any other model, or with caching off, the hint and every mark are
 * removed, and the system prompt goes out exactly as it was written.
 */

const MAX_MARKS = 4;
const MARK = { type: "ephemeral" };

/** Models that cache only where they're told to. */
export function takesCacheMarks(model) {
  return typeof model === "string" && model.startsWith("anthropic/");
}

const isText = (b) => b && typeof b === "object" && b.type === "text" && typeof b.text === "string";

function strip(block) {
  if (!block || typeof block !== "object") return block;
  if (!("cache_control" in block) && !("cache_prefix_length" in block)) return block;
  const { cache_control, cache_prefix_length, ...rest } = block;
  return rest;
}

/** One message's blocks, with the System Prompt node's hint turned into
 *  a split and a mark. */
function splitAtPrefix(blocks) {
  return blocks.flatMap((b) => {
    if (!isText(b) || typeof b.cache_prefix_length !== "number") return [b];
    const { cache_prefix_length: at, ...block } = b;
    if (at <= 0 || !b.text.slice(0, at).trim()) return [block];
    if (at >= b.text.length) return [{ ...block, cache_control: block.cache_control ?? MARK }];
    return [
      { type: "text", text: b.text.slice(0, at), cache_control: MARK },
      { ...block, text: b.text.slice(at) },
    ];
  });
}

const stripMessage = (m) =>
  m && typeof m === "object" && Array.isArray(m.content) ? { ...m, content: m.content.map(strip) } : m;

/**
 * A message or conversation with every cache mark and hint removed, for
 * anything that sends one somewhere other than a chat model (a decision
 * model's `state`). Anything else passes through. Never mutates the input.
 */
export function stripCacheHints(value) {
  return Array.isArray(value) ? value.map(stripMessage) : stripMessage(value);
}

/**
 * The messages to send, with cache marks placed for a model that takes
 * them and removed for any other. Never mutates the input.
 */
export function applyPromptCache(messages, { model, enabled = true } = {}) {
  if (!Array.isArray(messages)) return messages;
  const marking = enabled && takesCacheMarks(model);

  if (!marking) {
    return messages.map(stripMessage);
  }

  // Split the hinted blocks, then keep the earliest three marks.
  let kept = 0;
  const out = messages.map((m) => {
    if (!m || !Array.isArray(m.content)) return m;
    const blocks = splitAtPrefix(m.content).map((b) => {
      if (!b || !b.cache_control) return b;
      // A mark on an empty block is refused by the provider.
      if (kept < MAX_MARKS - 1 && !(isText(b) && !b.text)) {
        kept++;
        return b;
      }
      return strip(b);
    });
    return { ...m, content: blocks };
  });

  // The last message's last text block.
  const last = out.length - 1;
  const m = out[last];
  if (m && m.role !== "system") {
    const blocks =
      typeof m.content === "string"
        ? [{ type: "text", text: m.content }]
        : Array.isArray(m.content)
          ? [...m.content]
          : null;
    if (blocks && !blocks.some((b) => b && b.cache_control)) {
      for (let j = blocks.length - 1; j >= 0; j--) {
        if (isText(blocks[j]) && blocks[j].text) {
          blocks[j] = { ...blocks[j], cache_control: MARK };
          out[last] = { ...m, content: blocks };
          break;
        }
      }
    }
  }

  // Longer-lived marks must come first: anything before a one-hour mark
  // lives an hour too.
  let lastHourAt = -1;
  out.forEach((msg, i) => {
    if (Array.isArray(msg?.content) && msg.content.some((b) => b?.cache_control?.ttl === "1h")) lastHourAt = i;
  });
  if (lastHourAt > 0) {
    for (let i = 0; i < lastHourAt; i++) {
      const msg = out[i];
      if (!Array.isArray(msg?.content)) continue;
      if (!msg.content.some((b) => b?.cache_control && b.cache_control.ttl !== "1h")) continue;
      out[i] = {
        ...msg,
        content: msg.content.map((b) =>
          b?.cache_control && b.cache_control.ttl !== "1h" ? { ...b, cache_control: { ...b.cache_control, ttl: "1h" } } : b,
        ),
      };
    }
  }
  return out;
}
