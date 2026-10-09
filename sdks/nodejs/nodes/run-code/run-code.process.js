/**
 * Run Code: the model writes code, a sandbox runs it. The sandbox comes
 * from the host as config.integrations.codeExecutor, scoped to this run:
 * the first call opens a session and every later call reuses it.
 *
 * A failure in the code itself is a result, not an error: the traceback
 * is in stderr and the model's next move is to fix it. Only the sandbox
 * failing (time limit, lost session, unreachable) throws.
 */

const IMAGE = /^image\/(png|jpeg|gif|webp)$/;

export default async ({ inputs, settings, config }) => {
  const executor = config.integrations?.codeExecutor;
  if (!executor) {
    throw new Error("No sandbox is available to run code. Pass config.codeExecutor to the engine.");
  }
  const code = typeof inputs.code === "string" ? inputs.code : "";
  if (!code.trim()) throw new Error("There's no code to run.");
  const language = inputs.language || "python";
  const timeoutMs = Math.max(1, Number(settings?.timeout_seconds) || 60) * 1000;

  const out = await executor.run({ language, code, timeoutMs });

  if (out.error && out.error.kind !== "runtime") {
    const reason =
      out.error.kind === "timeout"
        ? `The code ran past the ${timeoutMs / 1000}s limit and was stopped.`
        : out.error.kind === "memory"
          ? "The code ran out of memory and was stopped."
          : out.error.message;
    const printed = out.stdout ? `\n\nPrinted before it stopped:\n${out.stdout}` : "";
    throw new Error(`${reason}${printed}`);
  }

  const produced = Array.isArray(out.files) ? out.files : [];
  const content = produced
    .filter((f) => typeof f.data === "string" && IMAGE.test(f.mimeType ?? ""))
    .map((f) => ({ type: "image", data: f.data, mimeType: f.mimeType }));
  // Bytes never ride in `files`: the listing is what the model and the
  // trace see, and images reach the model through `content` instead.
  const files = produced.map(({ data: _data, ...meta }) => meta);

  return {
    stdout: out.stdout ?? "",
    stderr: out.stderr ?? "",
    result: out.result ?? null,
    files,
    content,
  };
};
