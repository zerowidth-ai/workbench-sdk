export default async ({ inputs, settings, config }) => {
  const text = inputs.text;
  const returnAll = inputs.return_all ?? false;

  if (typeof text !== "string" || text.trim() === "") {
    return { json: null, found: false, raw_match: null };
  }

  const tryParse = (str) => {
    try {
      return { success: true, value: JSON.parse(str), raw: str };
    } catch {
      return { success: false };
    }
  };

  const results = [];

  // Strategy 1: Try parsing the entire text as JSON
  const direct = tryParse(text.trim());
  if (direct.success) {
    if (!returnAll) {
      return { json: direct.value, found: true, raw_match: direct.raw };
    }
    results.push(direct);
  }

  // Strategy 2: Extract from markdown code blocks (```json or ```)
  const codeBlockRegex = /```(?:json)?\s*([\s\S]*?)```/g;
  let match;
  while ((match = codeBlockRegex.exec(text)) !== null) {
    const content = match[1].trim();
    const parsed = tryParse(content);
    if (parsed.success) {
      if (!returnAll) {
        return { json: parsed.value, found: true, raw_match: parsed.raw };
      }
      // Avoid duplicates
      if (!results.some((r) => r.raw === parsed.raw)) {
        results.push(parsed);
      }
    }
  }

  // Strategy 3: Find JSON objects {...} and arrays [...] in text
  // Collect all candidates with their positions, then process in order
  const objectRegex = /\{(?:[^{}]|\{(?:[^{}]|\{[^{}]*\})*\})*\}/g;
  const arrayRegex = /\[(?:[^\[\]]|\[(?:[^\[\]]|\[[^\[\]]*\])*\])*\]/g;

  const candidates = [];

  while ((match = objectRegex.exec(text)) !== null) {
    candidates.push({ str: match[0], index: match.index });
  }
  while ((match = arrayRegex.exec(text)) !== null) {
    candidates.push({ str: match[0], index: match.index });
  }

  // Sort by position, then by length (longer first to prefer outer structures)
  candidates.sort((a, b) => {
    if (a.index !== b.index) return a.index - b.index;
    return b.str.length - a.str.length;
  });

  // Filter out candidates that are substrings of earlier valid matches
  const usedRanges = [];
  for (const candidate of candidates) {
    const start = candidate.index;
    const end = start + candidate.str.length;

    // Skip if this is inside a previously matched range
    const isInsidePrevious = usedRanges.some(
      (range) => start >= range.start && end <= range.end
    );
    if (isInsidePrevious) continue;

    const parsed = tryParse(candidate.str);
    if (parsed.success) {
      usedRanges.push({ start, end });
      if (!returnAll) {
        return { json: parsed.value, found: true, raw_match: parsed.raw };
      }
      if (!results.some((r) => r.raw === parsed.raw)) {
        results.push(parsed);
      }
    }
  }

  if (results.length === 0) {
    return { json: null, found: false, raw_match: null };
  }

  if (returnAll) {
    return {
      json: results.map((r) => r.value),
      found: true,
      raw_match: results[0].raw,
    };
  }

  return { json: results[0].value, found: true, raw_match: results[0].raw };
};
