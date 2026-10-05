/**
 * Agent memory: a small folder of markdown an agent reads and writes
 * between conversations.
 *
 *   MEMORY.md            a short index, read into the prompt every turn
 *   memory/<topic>.md    detail, read when the agent decides it needs it
 *   people/<id>.md       optional: one person's private page in a shared
 *                        memory, read in only when they're talking
 *
 * A memory store is four operations over those paths. The SDK ships a
 * folder store and an in-memory store; a host keeping many agents'
 * memories implements the same four over whatever it has (SQL rows,
 * bucket objects, Redis) and passes it as `config.memory.instance`.
 * Each store instance is one memory: the host decides whose (an
 * agent's own, one end user's) before handing it to the engine.
 *
 * The memory nodes (Memory, memory_list/read/write/edit/delete) only
 * ever talk to `config.integrations.memory`, which is the host's store
 * wrapped in `ScopedMemory` so every store gets the same path rules
 * and size limits.
 */

import fs from "node:fs/promises";
import path from "node:path";

export const MEMORY_INDEX = "MEMORY.md";
export const MAX_FILE_BYTES = 100_000;
export const MAX_FILES = 200;

const SEGMENT = /^[a-z0-9][a-z0-9._-]*$/i;

/** The node types that read or write an agent's memory. */
export const MEMORY_NODE_TYPES = new Set([
  "memory",
  "memory-list",
  "memory-read",
  "memory-write",
  "memory-edit",
  "memory-delete",
]);

export function flowUsesMemory(flow) {
  return Array.isArray(flow?.nodes) && flow.nodes.some((n) => MEMORY_NODE_TYPES.has(n.type));
}

export class MemoryPathError extends Error {
  constructor(message) {
    super(message);
    this.name = "MemoryPathError";
  }
}

/**
 * Normalize and check a memory path. Accepts `MEMORY.md`,
 * `memory/<name>.md` and `people/<id>.md`, adding `.md` when missing.
 * Nothing nests deeper than one folder.
 */
export function normalizeMemoryPath(raw) {
  const trimmed = String(raw ?? "").trim().replace(/^\.?\/+/, "");
  const withExt = /\.md$/i.test(trimmed) ? trimmed : `${trimmed}.md`;
  const parts = withExt.split("/");
  const ok =
    (parts.length === 1 && parts[0] === MEMORY_INDEX) ||
    (parts.length === 2 &&
      (parts[0] === "memory" || parts[0] === "people") &&
      SEGMENT.test(parts[1]) &&
      !parts[1].includes(".."));
  if (!ok) {
    throw new MemoryPathError(
      `"${raw}" isn't a memory file. Use MEMORY.md, memory/<topic>.md, or people/<id>.md.`,
    );
  }
  return withExt;
}

/**
 * The contract every memory store implements. Paths arrive already
 * normalized. `origin` says which node made the change, for stores
 * that keep a history.
 *
 * Optional members a host store may add:
 *   held     true when changes wait for a person to approve them;
 *            write/delete then return { status: "held" }.
 *   pending()  how many changes are waiting, for the prompt.
 */
export class MemoryStoreInterface {
  /** @returns {Promise<Array<{path: string, size: number, updated_at?: string}>>} */
  async list() {
    throw new Error("list() must be implemented by a memory store");
  }

  /** @returns {Promise<string|null>} the file's content, or null when it doesn't exist */
  async read(_path) {
    throw new Error("read() must be implemented by a memory store");
  }

  /** @returns {Promise<{status: "applied"|"held"}>} */
  async write(_path, _content, _origin) {
    throw new Error("write() must be implemented by a memory store");
  }

  /** @returns {Promise<{status: "applied"|"held"}>} */
  async delete(_path, _origin) {
    throw new Error("delete() must be implemented by a memory store");
  }
}

/** Memory that lasts as long as the process. For tests and trials. */
export class InMemoryMemoryStore extends MemoryStoreInterface {
  constructor(files = {}) {
    super();
    this.files = new Map(Object.entries(files));
  }

  async list() {
    return [...this.files.entries()]
      .sort(([a], [b]) => a.localeCompare(b))
      .map(([p, content]) => ({ path: p, size: Buffer.byteLength(content, "utf8") }));
  }

  async read(p) {
    return this.files.has(p) ? this.files.get(p) : null;
  }

  async write(p, content) {
    this.files.set(p, content);
    return { status: "applied" };
  }

  async delete(p) {
    this.files.delete(p);
    return { status: "applied" };
  }
}

/** Memory as real files under a folder: `<root>/MEMORY.md`, … */
export class FolderMemoryStore extends MemoryStoreInterface {
  constructor(root) {
    super();
    if (!root) throw new Error("FolderMemoryStore needs a folder path.");
    this.root = path.resolve(root);
  }

  async list() {
    const out = [];
    const visit = async (rel) => {
      let entries;
      try {
        entries = await fs.readdir(path.join(this.root, rel), { withFileTypes: true });
      } catch (err) {
        if (err.code === "ENOENT") return;
        throw err;
      }
      for (const entry of entries) {
        const p = rel ? `${rel}/${entry.name}` : entry.name;
        if (entry.isDirectory() && !rel && (entry.name === "memory" || entry.name === "people")) {
          await visit(p);
        } else if (entry.isFile() && entry.name.endsWith(".md")) {
          try {
            normalizeMemoryPath(p);
          } catch {
            continue;
          }
          const stat = await fs.stat(path.join(this.root, p));
          out.push({ path: p, size: stat.size, updated_at: stat.mtime.toISOString() });
        }
      }
    };
    await visit("");
    return out.sort((a, b) => a.path.localeCompare(b.path));
  }

  async read(p) {
    try {
      return await fs.readFile(path.join(this.root, p), "utf8");
    } catch (err) {
      if (err.code === "ENOENT") return null;
      throw err;
    }
  }

  async write(p, content) {
    const full = path.join(this.root, p);
    await fs.mkdir(path.dirname(full), { recursive: true });
    await fs.writeFile(full, content, "utf8");
    return { status: "applied" };
  }

  async delete(p) {
    await fs.rm(path.join(this.root, p), { force: true });
    return { status: "applied" };
  }
}

/**
 * The store the memory nodes see: path rules and size limits in front
 * of whatever store the host passed, so a custom store can't be handed
 * `../../etc/passwd` and doesn't have to re-implement the limits.
 *
 * People pages (`people: true`, a shared memory with a page per person):
 * the agent sees and changes only the page of whoever is talking
 * (`person`), so one person's notes never reach another conversation.
 * With nobody talking it sees no pages at all. Without `people`, the
 * `people/` folder isn't part of the memory.
 */
export class ScopedMemory {
  constructor(store, { people = false, person = null } = {}) {
    this.store = store;
    this.people = people === true;
    this.talking = this.people && person?.id ? { id: String(person.id), name: person.name || String(person.id) } : null;
    // The id becomes a file name; an id that can't be one would leave
    // the agent pointed at a page it isn't allowed to write.
    if (this.talking && (!SEGMENT.test(`${this.talking.id}.md`) || this.talking.id.includes(".."))) {
      throw new MemoryPathError(
        `memory.person.id "${this.talking.id}" can't name a page: use letters, digits, ".", "_" and "-" (hash or slug an email first).`,
      );
    }
  }

  /** Whoever is talking, when this memory keeps a page per person. */
  get person() {
    return this.talking;
  }

  get held() {
    return this.store.held === true;
  }

  /** The canonical form of a path the agent may use, or a MemoryPathError. */
  normalize(raw) {
    const p = normalizeMemoryPath(raw);
    if (!p.startsWith("people/")) return p;
    if (!this.people) {
      throw new MemoryPathError(`"${raw}" isn't a memory file. Use MEMORY.md or memory/<topic>.md.`);
    }
    if (!this.talking || p !== `people/${this.talking.id}.md`) {
      throw new MemoryPathError(
        this.talking
          ? `You can only use the page of the person you're talking to: people/${this.talking.id}.md.`
          : "Nobody is named in this conversation, so there's no person's page to use.",
      );
    }
    return p;
  }

  async pending() {
    return typeof this.store.pending === "function" ? await this.store.pending() : 0;
  }

  async list() {
    const own = this.talking ? `people/${this.talking.id}.md` : null;
    return (await this.store.list()).filter((f) => !f.path.startsWith("people/") || f.path === own);
  }

  async read(raw) {
    return this.store.read(this.normalize(raw));
  }

  async write(raw, content, origin = {}) {
    const p = this.normalize(raw);
    const text = String(content ?? "");
    if (Buffer.byteLength(text, "utf8") > MAX_FILE_BYTES) {
      throw new MemoryPathError(
        `${p} would be over ${MAX_FILE_BYTES / 1000}KB. Keep memory files short; split detail into another topic file.`,
      );
    }
    const existing = await this.store.list();
    if (!existing.some((f) => f.path === p) && existing.length >= MAX_FILES) {
      throw new MemoryPathError(
        `Memory already holds ${MAX_FILES} files. Fold some together or delete ones that no longer matter.`,
      );
    }
    return this.store.write(p, text, origin);
  }

  async delete(raw, origin = {}) {
    return this.store.delete(this.normalize(raw), origin);
  }
}

/**
 * Pick the memory for a run from `config.memory`:
 *   { instance }  a host store (wins)
 *   { path }      a FolderMemoryStore at that folder
 *   neither       an in-memory store, gone when the process exits
 * plus `people: true` and `person: { id, name }` for a shared memory
 * with a page per person.
 */
export function createMemory(memoryConfig = {}) {
  const options = { people: memoryConfig.people, person: memoryConfig.person };
  if (memoryConfig.instance) return new ScopedMemory(memoryConfig.instance, options);
  if (memoryConfig.path) return new ScopedMemory(new FolderMemoryStore(memoryConfig.path), options);
  return new ScopedMemory(new InMemoryMemoryStore(), options);
}
