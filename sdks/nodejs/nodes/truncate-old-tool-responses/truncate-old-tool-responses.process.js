export default async ({ inputs, settings, config }) => {
  const messages = inputs.messages;
  const keepRecent = Math.max(0, Math.floor(Number(inputs.keep_recent ?? 20)));
  const step = Math.max(1, Math.floor(Number(inputs.step ?? 1)) || 1);
  const placeholder = inputs.placeholder ?? "[Truncated]";

  if (!Array.isArray(messages)) {
    throw new Error("Messages input must be an array");
  }

  // The cutoff moves in whole steps, so between steps the earlier
  // messages are byte-for-byte what they were last turn (cacheable).
  const total = messages.length;
  const cutoffIndex = Math.floor(Math.max(0, total - keepRecent) / step) * step;

  const result = [];
  let truncatedCount = 0;

  for (let i = 0; i < messages.length; i++) {
    const message = messages[i];

    if (!message || typeof message !== "object") {
      result.push(message);
      continue;
    }

    // Check if this is an old tool message that should be truncated
    if (message.role === "tool" && i < cutoffIndex) {
      result.push({
        ...message,
        content: placeholder,
      });
      truncatedCount++;
    } else {
      result.push({ ...message });
    }
  }

  return {
    messages: result,
    truncated_count: truncatedCount,
  };
};
