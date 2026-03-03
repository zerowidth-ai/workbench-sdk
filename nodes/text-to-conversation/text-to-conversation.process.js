export default async ({ inputs, settings, config }) => {
  const text = inputs.text;
  const separator = inputs.separator ?? "\\n\\n";
  const defaultRole = inputs.default_role ?? "user";

  if (typeof text !== "string" || text.trim() === "") {
    return { messages: [], message_count: 0 };
  }

  // Split by separator
  const separatorRegex = new RegExp(separator);
  const chunks = text.split(separatorRegex).filter((chunk) => chunk.trim() !== "");

  // Role detection pattern - matches "Role:" or "ROLE:" at start of text
  const rolePattern = /^(user|assistant|system|human|ai|bot):\s*/i;

  const messages = [];

  for (const chunk of chunks) {
    const trimmed = chunk.trim();
    if (!trimmed) continue;

    const match = trimmed.match(rolePattern);

    let role = defaultRole;
    let content = trimmed;

    if (match) {
      const detectedRole = match[1].toLowerCase();
      // Normalize role names
      if (detectedRole === "human") {
        role = "user";
      } else if (detectedRole === "ai" || detectedRole === "bot") {
        role = "assistant";
      } else {
        role = detectedRole;
      }
      content = trimmed.slice(match[0].length).trim();
    }

    if (content) {
      messages.push({ role, content });
    }
  }

  return {
    messages,
    message_count: messages.length,
  };
};
