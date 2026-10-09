"""
Run Code Node - the model writes code, a sandbox runs it.

The sandbox comes from the host as config["integrations"]["code_executor"],
scoped to this run. A failure in the code itself is a result (the
traceback is in stderr); only the sandbox failing raises.
"""

import re
from typing import Any

IMAGE = re.compile(r"^image/(png|jpeg|gif|webp)$")
# Inside the node's own 150s timeout, so the sandbox's limit is the one
# that fires and the model is told which limit it hit.
MAX_SECONDS = 120.0
# What the model is shown per call. Larger or later images are still
# listed in `files`.
MAX_IMAGES = 4
MAX_IMAGE_BYTES = 5 * 1024 * 1024


async def process(
    *,
    inputs: dict[str, Any],
    settings: dict[str, Any],
    config: dict[str, Any],
    node_config: dict[str, Any],
) -> dict[str, Any]:
    executor = (config.get("integrations") or {}).get("code_executor")
    if not executor:
        raise ValueError("No sandbox is available to run code. Pass config['code_executor'] to the engine.")
    code = inputs.get("code") if isinstance(inputs.get("code"), str) else ""
    if not code.strip():
        raise ValueError("There's no code to run.")
    language = inputs.get("language") or "python"
    try:
        seconds = float((settings or {}).get("timeout_seconds") or 60)
    except (TypeError, ValueError):
        seconds = 60.0
    timeout_ms = int(min(MAX_SECONDS, max(1.0, seconds)) * 1000)

    out = await executor.run(language=language, code=code, timeout_ms=timeout_ms)

    error = out.get("error")
    if isinstance(error, dict) and error.get("kind") != "runtime":
        kind = error.get("kind")
        if kind == "timeout":
            reason = f"The code ran past the {timeout_ms // 1000}s limit and was stopped."
        elif kind == "memory":
            reason = "The code ran out of memory and was stopped."
        else:
            reason = error.get("message") or "The sandbox stopped the code."
        printed = f"\n\nPrinted before it stopped:\n{out['stdout']}" if out.get("stdout") else ""
        raise RuntimeError(f"{reason}{printed}")

    produced = out.get("files") if isinstance(out.get("files"), list) else []
    images = [
        f for f in produced
        if isinstance(f.get("data"), str) and IMAGE.match(f.get("mimeType") or "")
    ]
    shown = [f for f in images if len(f["data"]) * 0.75 <= MAX_IMAGE_BYTES][:MAX_IMAGES]
    content = [{"type": "image", "data": f["data"], "mimeType": f.get("mimeType")} for f in shown]
    not_shown = len(images) - len(shown)
    files = [{k: v for k, v in f.items() if k != "data"} for f in produced]

    stderr = out.get("stderr") or ""
    if not_shown:
        plural = "s" if not_shown > 1 else ""
        stderr += (
            f"{chr(10) if stderr else ''}{not_shown} image{plural} not shown: at most {MAX_IMAGES} "
            "per call, each up to 5 MB. They are still listed in files."
        )

    return {
        "stdout": out.get("stdout") or "",
        "stderr": stderr,
        "result": out.get("result"),
        "files": files,
        "content": content,
    }
