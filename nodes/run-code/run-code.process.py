"""
Run Code Node - the model writes code, a sandbox runs it.

The sandbox comes from the host as config["integrations"]["code_executor"],
scoped to this run. A failure in the code itself is a result (the
traceback is in stderr); only the sandbox failing raises.
"""

import re
from typing import Any

IMAGE = re.compile(r"^image/(png|jpeg|gif|webp)$")


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
    timeout_ms = int(max(1.0, seconds) * 1000)

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
    content = [
        {"type": "image", "data": f["data"], "mimeType": f.get("mimeType")}
        for f in produced
        if isinstance(f.get("data"), str) and IMAGE.match(f.get("mimeType") or "")
    ]
    files = [{k: v for k, v in f.items() if k != "data"} for f in produced]

    return {
        "stdout": out.get("stdout") or "",
        "stderr": out.get("stderr") or "",
        "result": out.get("result"),
        "files": files,
        "content": content,
    }
