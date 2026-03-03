export default async ({ inputs, settings, config }) => {
  const messages = inputs.messages;
  const separator = inputs.separator ?? "\n\n";

  if (!Array.isArray(messages)) {
    throw new Error("Messages input must be an array");
  }

  if (messages.length === 0) {
    return {
      messages: [],
      merged_count: 0,
    };
  }

  // Check if a message can be merged
  const canMerge = (message) => {
    if (!message || typeof message !== "object") return false;
    // Tool messages are never merged
    if (message.role === "tool") return false;
    // Assistant messages with tool_calls are never merged
    if (message.role === "assistant" && Array.isArray(message.tool_calls) && message.tool_calls.length > 0) {
      return false;
    }
    return true;
  };

  // Extract string content from a message
  const getContent = (message) => {
    if (typeof message.content === "string") return message.content;
    if (Array.isArray(message.content)) {
      return message.content
        .filter((item) => item && item.type === "text" && item.text)
        .map((item) => item.text)
        .join(" ");
    }
    return String(message.content ?? "");
  };

  const result = [];
  let mergedCount = 0;

  for (const message of messages) {
    if (!message || typeof message !== "object") {
      result.push(message);
      continue;
    }

    const lastMessage = result[result.length - 1];
    const currentCanMerge = canMerge(message);
    const lastCanMerge = lastMessage && canMerge(lastMessage);

    // Check if we should merge with the previous message
    if (
      lastMessage &&
      lastCanMerge &&
      currentCanMerge &&
      message.role === lastMessage.role
    ) {
      // Merge content
      const lastContent = getContent(lastMessage);
      const currentContent = getContent(message);
      lastMessage.content = lastContent + separator + currentContent;
      mergedCount++;
    } else {
      // Clone the message to avoid mutating input
      result.push({ ...message });
    }
  }

  return {
    messages: result,
    merged_count: mergedCount,
  };
};
