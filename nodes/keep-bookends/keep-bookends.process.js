export default async ({ inputs, settings, config }) => {
  const messages = inputs.messages;
  const keepFirst = Math.max(0, Math.floor(Number(inputs.keep_first) || 0));
  const keepLast = Math.max(0, Math.floor(Number(inputs.keep_last) || 0));

  if (!Array.isArray(messages)) {
    throw new Error("Messages input must be an array");
  }

  // Separate system messages from non-system messages
  const systemMessages = [];
  const nonSystemMessages = [];

  for (const message of messages) {
    if (message && typeof message === "object" && message.role === "system") {
      systemMessages.push(message);
    } else {
      nonSystemMessages.push(message);
    }
  }

  const totalNonSystem = nonSystemMessages.length;

  // If keepFirst + keepLast covers everything, keep all
  if (keepFirst + keepLast >= totalNonSystem) {
    return {
      messages: messages,
      removed_count: 0,
    };
  }

  // Get the first N and last M non-system messages
  const firstMessages = nonSystemMessages.slice(0, keepFirst);
  const lastMessages = nonSystemMessages.slice(totalNonSystem - keepLast);

  // Combine: system messages first, then first N, then last M
  const result = [...systemMessages, ...firstMessages, ...lastMessages];
  const removedCount = messages.length - result.length;

  return {
    messages: result,
    removed_count: removedCount,
  };
};
