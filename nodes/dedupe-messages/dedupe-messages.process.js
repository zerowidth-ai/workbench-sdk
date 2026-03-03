export default async ({ inputs, settings, config }) => {
  const messages = inputs.messages;

  if (!Array.isArray(messages)) {
    throw new Error("Messages input must be an array");
  }

  if (messages.length === 0) {
    return {
      messages: [],
      removed_count: 0,
    };
  }

  const result = [];
  let removedCount = 0;

  for (const message of messages) {
    if (!message || typeof message !== "object") {
      result.push(message);
      continue;
    }

    const lastMessage = result[result.length - 1];

    // Check if this is a duplicate of the previous message
    if (lastMessage && typeof lastMessage === "object") {
      const sameRole = message.role === lastMessage.role;
      const sameContent = JSON.stringify(message.content) === JSON.stringify(lastMessage.content);

      if (sameRole && sameContent) {
        removedCount++;
        continue;
      }
    }

    result.push(message);
  }

  return {
    messages: result,
    removed_count: removedCount,
  };
};
