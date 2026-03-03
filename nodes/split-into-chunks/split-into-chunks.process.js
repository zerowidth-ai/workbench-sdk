export default async ({ inputs, settings, config }) => {
  const text = inputs.text;
  const chunkSize = Math.max(1, Math.floor(inputs.chunk_size || 1));
  const chunkBy = inputs.chunk_by ?? "characters";
  const overlap = Math.max(0, Math.floor(inputs.overlap || 0));

  if (typeof text !== "string" || text === "") {
    return { chunks: [], chunk_count: 0 };
  }

  const chunks = [];

  if (chunkBy === "characters") {
    const step = Math.max(1, chunkSize - overlap);
    for (let i = 0; i < text.length; i += step) {
      chunks.push(text.slice(i, i + chunkSize));
    }
  } else if (chunkBy === "words") {
    const words = text.split(/\s+/).filter((w) => w.length > 0);
    const step = Math.max(1, chunkSize - overlap);
    for (let i = 0; i < words.length; i += step) {
      const chunk = words.slice(i, i + chunkSize);
      if (i > 0 && chunk.length <= overlap) break;
      chunks.push(chunk.join(" "));
    }
  } else if (chunkBy === "sentences") {
    const sentences = (text.match(/[^.!?]+[.!?]+/g) || [text]).map((s) =>
      s.trim()
    );
    const step = Math.max(1, chunkSize - overlap);
    for (let i = 0; i < sentences.length; i += step) {
      const chunk = sentences.slice(i, i + chunkSize);
      if (i > 0 && chunk.length <= overlap) break;
      chunks.push(chunk.join(" "));
    }
  }

  return {
    chunks,
    chunk_count: chunks.length,
  };
};
