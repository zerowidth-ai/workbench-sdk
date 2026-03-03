export default async ({ inputs, settings, config }) => {
  const messages = inputs.messages;
  const keepRecent = Math.max(0, Math.floor(Number(inputs.keep_recent ?? 20)));
  const placeholder = inputs.placeholder ?? "[Truncated]";

  if (!Array.isArray(messages)) {
    throw new Error("Messages input must be an array");
  }

  const total = messages.length;
  const cutoffIndex = total - keepRecent;

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
