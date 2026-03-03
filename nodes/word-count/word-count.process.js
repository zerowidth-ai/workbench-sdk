export default async ({ inputs, settings, config }) => {
  const text = inputs.text;

  if (typeof text !== "string" || text === "") {
    return {
      characters: 0,
      characters_no_spaces: 0,
      words: 0,
      sentences: 0,
      paragraphs: 0,
      lines: 0,
    };
  }

  // Character counts
  const characters = text.length;
  const charactersNoSpaces = text.replace(/\s/g, "").length;

  // Word count - split on whitespace and filter empty
  const words = text.trim().split(/\s+/).filter((w) => w.length > 0).length;

  // Sentence count - split on sentence-ending punctuation
  const sentenceMatches = text.match(/[.!?]+(?:\s|$)/g);
  const sentences = sentenceMatches ? sentenceMatches.length : (text.trim() ? 1 : 0);

  // Paragraph count - split on double newlines
  const paragraphs = text.split(/\n\s*\n/).filter((p) => p.trim().length > 0).length;

  // Line count
  const lines = text.split("\n").length;

  return {
    characters,
    characters_no_spaces: charactersNoSpaces,
    words,
    sentences,
    paragraphs,
    lines,
  };
};
