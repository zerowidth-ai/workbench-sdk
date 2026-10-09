/**
 * Code execution: the contract an executor fulfils, a client for an
 * executor reached over HTTP, and the per-run wrapper the engine hands to
 * the Run Code tool.
 *
 * The engine never runs code itself and never learns which sandbox does.
 * The host passes `config.codeExecutor`:
 *
 *   { instance: <CodeExecutorInterface> }   — its own executor object
 *   { url, apiKey?, headers?, getHeaders? } — an executor that speaks the
 *                                              HTTP contract below
 *
 * HTTP contract (all JSON):
 *
 *   POST   {url}/sessions        → { id }
 *   POST   {url}/run             ← RunRequest  → RunResult
 *   DELETE {url}/sessions/{id}   → 204
 *
 * A session holds variables and files between calls. Sessions are
 * optional: an executor that answers `capabilities.sessions = false`
 * runs every call fresh.
 */

const OUTPUT_CAP = 20000;

/**
 * Thrown when the executor no longer has the session's state (it was
 * restarted, or the call landed somewhere else). Distinct from a failure
 * in the code itself: the model's next step is to run its setup again.
 */
export class CodeSessionLostError extends Error {
  constructor() {
    super(
      "The sandbox restarted, so variables and files from earlier calls are gone. Run the setup code again before continuing."
    );
    this.name = "CodeSessionLostError";
  }
}

/**
 * The contract. Implement this over any sandbox and pass it as
 * `config.codeExecutor.instance`.
 */
export class CodeExecutorInterface {
  /** @returns {Promise<{ languages: string[], sessions: boolean, files: boolean }>} */
  async capabilities() {
    throw new Error("capabilities() not implemented");
  }

  /**
   * @param {{ language: string, code: string, input?: unknown,
   *   files?: { path: string, data: string }[], timeoutMs: number,
   *   session?: string }} _request  file `data` is base64
   * @param {{ signal?: AbortSignal }} [_options] aborted when the run is
   *   cancelled or the node times out; stop waiting on the sandbox then
   * @returns {Promise<{ stdout: string, stderr: string, result?: unknown,
   *   files?: { path: string, mimeType?: string, data?: string, url?: string, size?: number }[],
   *   error?: { kind: "timeout" | "memory" | "runtime" | "unsupported" | "session_lost", message: string },
   *   usage?: { wallMs: number, cpuMs?: number } }>}
   */
  async run(_request, _options) {
    throw new Error("run() not implemented");
  }

  /** @returns {Promise<string>} a session id */
  async openSession() {
    throw new Error("openSession() not implemented");
  }

  /** @param {string} _id */
  async closeSession(_id) {}
}

/** An executor reached over HTTP. */
export class HttpCodeExecutor extends CodeExecutorInterface {
  constructor({ url, apiKey, headers, getHeaders, fetch: fetchImpl, capabilities } = {}) {
    super();
    if (!url) throw new Error("A code executor needs a url.");
    this.url = url.replace(/\/+$/, "");
    this.apiKey = apiKey;
    this.headers = headers ?? {};
    this.getHeaders = getHeaders;
    this.fetch = fetchImpl ?? globalThis.fetch;
    this.declared = capabilities;
  }

  async capabilities() {
    return this.declared ?? { languages: ["python", "javascript"], sessions: true, files: true };
  }

  async request(method, path, body, signal) {
    const headers = {
      "content-type": "application/json",
      ...this.headers,
      ...(this.getHeaders ? await this.getHeaders() : {}),
      ...(this.apiKey ? { authorization: `Bearer ${this.apiKey}` } : {}),
    };
    const res = await this.fetch(`${this.url}${path}`, {
      method,
      headers,
      body: body === undefined ? undefined : JSON.stringify(body),
      signal,
    });
    if (res.status === 204) return null;
    const text = await res.text();
    let data = null;
    try {
      data = text ? JSON.parse(text) : null;
    } catch {
      // Fall through with the raw text for the error below.
    }
    if (!res.ok) {
      if (res.status === 410 || data?.error?.kind === "session_lost") throw new CodeSessionLostError();
      const message = data?.error?.message ?? data?.error ?? text.slice(0, 300);
      throw new Error(`The code executor refused the request (${res.status}): ${message}`);
    }
    return data;
  }

  async run(request, { signal } = {}) {
    return this.request("POST", "/run", request, signal);
  }

  async openSession() {
    const data = await this.request("POST", "/sessions", {});
    if (!data?.id) throw new Error("The code executor did not return a session id.");
    return data.id;
  }

  async closeSession(id) {
    await this.request("DELETE", `/sessions/${encodeURIComponent(id)}`);
  }
}

const cap = (text) => {
  const value = typeof text === "string" ? text : "";
  return value.length > OUTPUT_CAP
    ? `${value.slice(0, OUTPUT_CAP)}\n… (cut: ${value.length - OUTPUT_CAP} more characters)`
    : value;
};

// `result` is whatever the sandbox reports for the last expression; a
// big one (a DataFrame, a long list) is capped like printed output.
const capResult = (value) => {
  if (value === undefined || value === null) return null;
  if (typeof value === "string") return cap(value);
  let json;
  try {
    json = JSON.stringify(value);
  } catch {
    return cap(String(value));
  }
  return json && json.length > OUTPUT_CAP ? cap(json) : value;
};

/**
 * One run's view of an executor: opens a session on first use when the
 * executor supports them, reuses it for every later call in the run, and
 * closes it when the run ends. Output is capped here so a print loop
 * cannot flood the conversation, whatever the executor allows.
 *
 * Every engine owns one of these. A sub-engine (an import or a macro)
 * gets its own through forSubEngine(), so its session never shares
 * state with its caller's and closing it leaves the caller's open.
 */
export class RunScopedCodeExecutor {
  constructor(executor) {
    this.executor = executor;
    this.sessionId = null;
    this.opening = null;
  }

  async capabilities() {
    return this.executor.capabilities();
  }

  /** A fresh scope over the same executor, for a sub-engine. */
  forSubEngine() {
    return new RunScopedCodeExecutor(this.executor);
  }

  async session() {
    const caps = await this.executor.capabilities();
    if (!caps.sessions) return undefined;
    if (this.sessionId) return this.sessionId;
    this.opening ??= this.executor.openSession().then((id) => {
      this.sessionId = id;
      return id;
    });
    try {
      return await this.opening;
    } finally {
      this.opening = null;
    }
  }

  async run({ language, code, input, files, timeoutMs, signal }) {
    const caps = await this.executor.capabilities();
    if (!caps.languages.includes(language)) {
      throw new Error(
        `This sandbox runs ${caps.languages.join(" and ")}, not ${language}.`
      );
    }
    const session = await this.session();
    let result;
    try {
      result = await this.executor.run({ language, code, input, files, timeoutMs, session }, { signal });
    } catch (err) {
      if (err instanceof CodeSessionLostError) this.sessionId = null;
      throw err;
    }
    if (result?.error?.kind === "session_lost") {
      this.sessionId = null;
      throw new CodeSessionLostError();
    }
    return {
      ...result,
      stdout: cap(result?.stdout),
      stderr: cap(result?.stderr),
      result: capResult(result?.result),
    };
  }

  async close() {
    const id = this.sessionId;
    this.sessionId = null;
    if (id) await this.executor.closeSession(id);
  }
}

/**
 * The integrations a sub-engine runs with: the caller's, except that
 * code runs in a session of its own. Returns the same object when there
 * is no code executor.
 */
export function withOwnCodeSession(integrations) {
  if (!integrations?.codeExecutor?.forSubEngine) return integrations;
  return { ...integrations, codeExecutor: integrations.codeExecutor.forSubEngine() };
}

/** From the host's `config.codeExecutor` to the run-scoped executor. */
export function createCodeExecutor(codeExecutorConfig = {}) {
  if (codeExecutorConfig.instance) return new RunScopedCodeExecutor(codeExecutorConfig.instance);
  if (codeExecutorConfig.url) return new RunScopedCodeExecutor(new HttpCodeExecutor(codeExecutorConfig));
  throw new Error("config.codeExecutor needs either an instance or a url.");
}
