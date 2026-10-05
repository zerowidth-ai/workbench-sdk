/**
 * Memory: reads the agent's memory into a block for the system prompt.
 * Only MEMORY.md and the current person's notes ride along in full;
 * every other file is named so the agent can read it when it matters.
 * The store comes from the host as config.integrations.memory.
 */

const INDEX = "MEMORY.md";
const INDEX_BYTE_CAP = 25000;
const PERSON_BYTE_CAP = 8000;

const cap = (content, maxBytes, maxLines) => {
  let out = content;
  if (maxLines) {
    const lines = out.split("\n");
    if (lines.length > maxLines) out = lines.slice(0, maxLines).join("\n");
  }
  if (Buffer.byteLength(out, "utf8") > maxBytes) {
    out = Buffer.from(out, "utf8").subarray(0, maxBytes).toString("utf8");
  }
  return out.length < content.length
    ? `${out}\n\n(Cut here: the rest is still in the file. Read the file for it.)`
    : out;
};

// A memory line must never read as a prompt {{variable}} downstream.
const inert = (text) => text.replace(/\{\{/g, "{ {");

const fileBlock = (path, content) =>
  `<memory-file path="${path}">\n${inert(content)}\n</memory-file>`;

export default async ({ settings, config }) => {
  const memory = config.integrations?.memory;
  if (!memory) {
    throw new Error("No memory is available. Pass config.memory to the engine.");
  }

  const variableName = settings?.variable_name || "MEMORY";
  const guidance = settings?.guidance ?? "";
  const indexLines = Number(settings?.index_lines) || 200;

  const files = await memory.list();
  const paths = new Set(files.map((f) => f.path));
  const person = memory.person ?? null;
  const personPath = person?.id ? `people/${person.id}.md` : null;

  const sections = ["# Your memory"];
  if (guidance.trim()) sections.push(guidance.trim());

  const index = paths.has(INDEX) ? await memory.read(INDEX) : null;
  sections.push(
    index
      ? `## ${INDEX}\n${fileBlock(INDEX, cap(index, INDEX_BYTE_CAP, indexLines))}`
      : `## ${INDEX}\nEmpty. Nothing has been written down yet.`,
  );

  if (personPath) {
    const name = person.name || person.id;
    const notes = paths.has(personPath) ? await memory.read(personPath) : null;
    sections.push(
      notes
        ? `## About ${name}, who you're talking to\n${fileBlock(personPath, cap(notes, PERSON_BYTE_CAP))}`
        : `## About ${name}, who you're talking to\nNo notes yet. How ${name} likes to work with you goes in ${personPath}.`,
    );
  }

  const others = files.map((f) => f.path).filter((p) => p !== INDEX && p !== personPath);
  if (others.length > 0) {
    sections.push(`## Other files\n${others.map((p) => `- ${p}`).join("\n")}`);
  }

  if (memory.held) {
    const waiting = await memory.pending();
    sections.push(
      `Changes you make to memory wait for a person to approve them before they take effect.${
        waiting > 0 ? ` ${waiting} of your earlier changes are waiting now.` : ""
      }`,
    );
  }

  const content = sections.join("\n\n");
  return {
    variables: { [variableName]: content },
    content,
    files: files.map((f) => ({ path: f.path, size: f.size })),
  };
};
