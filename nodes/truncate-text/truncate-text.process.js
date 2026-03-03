export default async ({ inputs, settings, config }) => {
  const text = inputs.text;
  const maxLength = inputs.max_length;
  const position = inputs.position ?? "end";
  const suffix = inputs.suffix ?? "...";
  const wordBoundary = inputs.word_boundary ?? false;

  if (typeof text !== "string") {
    return { text: "", was_truncated: false, original_length: 0 };
  }

  const originalLength = text.length;

  if (originalLength <= maxLength) {
    return { text, was_truncated: false, original_length: originalLength };
  }

  const suffixLength = suffix.length;
  const availableLength = maxLength - suffixLength;

  if (availableLength <= 0) {
    return { text: suffix.slice(0, maxLength), was_truncated: true, original_length: originalLength };
  }

  let result;

  if (position === "end") {
    let truncated = text.slice(0, availableLength);

    if (wordBoundary) {
      const lastSpace = truncated.lastIndexOf(" ");
      if (lastSpace > availableLength * 0.5) {
        truncated = truncated.slice(0, lastSpace);
      }
    }

    result = truncated + suffix;
  } else if (position === "start") {
    let truncated = text.slice(-availableLength);

    if (wordBoundary) {
      const firstSpace = truncated.indexOf(" ");
      if (firstSpace > 0 && firstSpace < availableLength * 0.5) {
        truncated = truncated.slice(firstSpace + 1);
      }
    }

    result = suffix + truncated;
  } else if (position === "middle") {
    const halfLength = Math.floor((availableLength - suffixLength) / 2);
    let startPart = text.slice(0, halfLength);
    let endPart = text.slice(-halfLength);

    if (wordBoundary) {
      const startLastSpace = startPart.lastIndexOf(" ");
      if (startLastSpace > halfLength * 0.5) {
        startPart = startPart.slice(0, startLastSpace);
      }

      const endFirstSpace = endPart.indexOf(" ");
      if (endFirstSpace > 0 && endFirstSpace < halfLength * 0.5) {
        endPart = endPart.slice(endFirstSpace + 1);
      }
    }

    result = startPart + suffix + endPart;
  } else {
    result = text.slice(0, availableLength) + suffix;
  }

  // Ensure we don't exceed max length
  if (result.length > maxLength) {
    result = result.slice(0, maxLength);
  }

  return { text: result, was_truncated: true, original_length: originalLength };
};
