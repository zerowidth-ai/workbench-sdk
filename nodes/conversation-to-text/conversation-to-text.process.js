export default async ({ inputs, settings, config }) => {
  const messages = inputs.messages;
  const includeSystem = inputs.include_system ?? false;
  const separator = inputs.separator ?? "\n\n";
  const roleFormat = inputs.role_format ?? "capitalized";

  if (!Array.isArray(messages)) {
    throw new Error("Messages input must be an array");
  }

  const formatRole = (role) => {
    if (roleFormat === "none") return "";
    if (roleFormat === "uppercase") return role.toUpperCase();
    if (roleFormat === "lowercase") return role.toLowerCase();
    // capitalized (default)
    return role.charAt(0).toUpperCase() + role.slice(1).toLowerCase();
  };

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

  const lines = [];

  for (const message of messages) {
    if (!message || typeof message !== "object") continue;

    const role = message.role;
    if (!role) continue;

    // Skip system messages if not included
    if (role === "system" && !includeSystem) continue;

    // Skip tool messages (they don't make sense in text transcript)
    if (role === "tool") continue;

    const content = getContent(message);
    const formattedRole = formatRole(role);

    if (roleFormat === "none") {
      lines.push(content);
    } else {
      lines.push(`${formattedRole}: ${content}`);
    }
  }

  return {
    text: lines.join(separator),
    message_count: lines.length,
  };
};
