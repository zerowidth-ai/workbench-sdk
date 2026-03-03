export default async ({ inputs, settings, config }) => {
  const messages = inputs.messages;

  if (!Array.isArray(messages)) {
    throw new Error("Messages input must be an array");
  }

  const result = [];
  let insertedCount = 0;
  let pendingToolCalls = []; // Array of { id, index } to track order

  for (const message of messages) {
    if (!message || typeof message !== "object") {
      result.push(message);
      continue;
    }

    const role = message.role;

    // If this is an assistant message with tool_calls, track them
    if (role === "assistant" && Array.isArray(message.tool_calls) && message.tool_calls.length > 0) {
      // First, handle any previously pending tool calls (shouldn't happen in valid convos, but be safe)
      if (pendingToolCalls.length > 0) {
        for (const pending of pendingToolCalls) {
          result.push({
            role: "tool",
            tool_call_id: pending.id,
            content: "Tool call was not executed",
          });
          insertedCount++;
        }
        pendingToolCalls = [];
      }

      result.push(message);

      // Track the new tool calls in order
      for (const toolCall of message.tool_calls) {
        if (toolCall && toolCall.id) {
          pendingToolCalls.push({ id: toolCall.id });
        }
      }
      continue;
    }

    // If this is a tool response, mark that tool_call_id as handled
    if (role === "tool" && message.tool_call_id) {
      const pendingIndex = pendingToolCalls.findIndex((p) => p.id === message.tool_call_id);
      if (pendingIndex !== -1) {
        // Insert synthetic responses for any tool calls that come before this one in the original order
        for (let i = 0; i < pendingIndex; i++) {
          result.push({
            role: "tool",
            tool_call_id: pendingToolCalls[i].id,
            content: "Tool call was not executed",
          });
          insertedCount++;
        }
        // Remove handled tool calls (the ones we just backfilled + the current one)
        pendingToolCalls.splice(0, pendingIndex + 1);
      }
      result.push(message);
      continue;
    }

    // If this is a user message, we need to backfill any pending tool calls first
    if (role === "user") {
      for (const pending of pendingToolCalls) {
        result.push({
          role: "tool",
          tool_call_id: pending.id,
          content: "Tool call was not executed",
        });
        insertedCount++;
      }
      pendingToolCalls = [];
      result.push(message);
      continue;
    }

    // For any other message type, just pass through
    result.push(message);
  }

  // Handle any remaining pending tool calls at the end of the conversation
  for (const pending of pendingToolCalls) {
    result.push({
      role: "tool",
      tool_call_id: pending.id,
      content: "Tool call was not executed",
    });
    insertedCount++;
  }

  return {
    messages: result,
    inserted_count: insertedCount,
  };
};
