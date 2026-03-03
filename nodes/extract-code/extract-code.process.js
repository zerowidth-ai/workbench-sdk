export default async ({ inputs, settings, config }) => {
  const text = inputs.text;
  const returnAll = inputs.return_all ?? false;
  const languageFilter = inputs.language_filter?.toLowerCase()?.trim() || null;

  if (typeof text !== "string" || text.trim() === "") {
    return { code: null, language: null, found: false, blocks: [] };
  }

  const blocks = [];

  // Match markdown code blocks with optional language
  // Captures: (language)? and (code content)
  const codeBlockRegex = /```(\w*)\n?([\s\S]*?)```/g;

  let match;
  while ((match = codeBlockRegex.exec(text)) !== null) {
    const language = match[1]?.trim()?.toLowerCase() || null;
    const code = match[2];

    // Apply language filter if specified
    if (languageFilter) {
      if (language !== languageFilter) {
        continue;
      }
    }

    blocks.push({
      code: code,
      language: language,
    });
  }

  if (blocks.length === 0) {
    return { code: null, language: null, found: false, blocks: [] };
  }

  if (returnAll) {
    return {
      code: blocks.map((b) => b.code),
      language: blocks[0].language,
      found: true,
      blocks: blocks,
    };
  }

  return {
    code: blocks[0].code,
    language: blocks[0].language,
    found: true,
    blocks: blocks,
  };
};
