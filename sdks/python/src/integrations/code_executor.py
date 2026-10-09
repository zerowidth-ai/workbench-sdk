"""
Code execution: the contract an executor fulfils, a client for an
executor reached over HTTP, and the per-run wrapper the engine hands to
the Run Code tool. Mirrors sdks/nodejs/src/integrations/code-executor.js.

The engine never runs code itself and never learns which sandbox does.
The host passes ``config["code_executor"]`` (``codeExecutor`` also works):

    {"instance": <CodeExecutorInterface>}        its own executor object
    {"url": ..., "api_key"?: ..., "headers"?: ...} an executor speaking the
                                                   HTTP contract below

HTTP contract (all JSON):

    POST   {url}/sessions        -> {"id"}
    POST   {url}/run             <- RunRequest  -> RunResult
    DELETE {url}/sessions/{id}   -> 204
"""

from __future__ import annotations

import asyncio
import inspect
import json
from typing import Any, Callable, Optional
from urllib.parse import quote

OUTPUT_CAP = 20000


class CodeSessionLostError(Exception):
    """The executor no longer has the session's state; run setup again."""

    def __init__(self) -> None:
        super().__init__(
            "The sandbox restarted, so variables and files from earlier calls are gone. "
            "Run the setup code again before continuing."
        )


class CodeExecutorInterface:
    """The contract. Implement it over any sandbox and pass it as
    ``config["code_executor"]["instance"]``. Request and result use the
    same camelCase keys as the HTTP contract (``timeoutMs``, ``mimeType``)."""

    async def capabilities(self) -> dict[str, Any]:
        raise NotImplementedError

    async def run(self, request: dict[str, Any]) -> dict[str, Any]:
        raise NotImplementedError

    async def open_session(self) -> str:
        raise NotImplementedError

    async def close_session(self, session_id: str) -> None:
        return None


class HttpCodeExecutor(CodeExecutorInterface):
    """An executor reached over HTTP."""

    def __init__(
        self,
        url: str,
        api_key: Optional[str] = None,
        headers: Optional[dict[str, str]] = None,
        get_headers: Optional[Callable[[], Any]] = None,
        capabilities: Optional[dict[str, Any]] = None,
        timeout: float = 30.0,
    ) -> None:
        if not url:
            raise ValueError("A code executor needs a url.")
        self.url = url.rstrip("/")
        self.api_key = api_key
        self.headers = headers or {}
        self.get_headers = get_headers
        self.declared = capabilities
        self.timeout = timeout

    async def capabilities(self) -> dict[str, Any]:
        return self.declared or {"languages": ["python", "javascript"], "sessions": True, "files": True}

    async def _request(self, method: str, path: str, body: Any = None, timeout: Optional[float] = None) -> Any:
        import httpx

        headers = {"content-type": "application/json", **self.headers}
        if self.get_headers:
            extra = self.get_headers()
            if inspect.isawaitable(extra):
                extra = await extra
            headers.update(extra or {})
        if self.api_key:
            headers["authorization"] = f"Bearer {self.api_key}"
        async with httpx.AsyncClient(timeout=timeout or self.timeout) as client:
            res = await client.request(method, f"{self.url}{path}", headers=headers, json=body)
        if res.status_code == 204:
            return None
        try:
            data = res.json() if res.content else None
        except ValueError:
            data = None
        if res.status_code >= 400:
            error = data.get("error") if isinstance(data, dict) else None
            if res.status_code == 410 or (isinstance(error, dict) and error.get("kind") == "session_lost"):
                raise CodeSessionLostError()
            message = (error.get("message") if isinstance(error, dict) else error) or res.text[:300]
            raise RuntimeError(f"The code executor refused the request ({res.status_code}): {message}")
        return data

    async def run(self, request: dict[str, Any]) -> dict[str, Any]:
        # Wait a little past the sandbox's own limit so its timeout answer
        # arrives instead of a dropped connection.
        timeout_ms = request.get("timeoutMs")
        timeout = timeout_ms / 1000 + 15 if isinstance(timeout_ms, (int, float)) else None
        return await self._request("POST", "/run", request, timeout=timeout)

    async def open_session(self) -> str:
        data = await self._request("POST", "/sessions", {})
        if not isinstance(data, dict) or not data.get("id"):
            raise RuntimeError("The code executor did not return a session id.")
        return data["id"]

    async def close_session(self, session_id: str) -> None:
        await self._request("DELETE", f"/sessions/{quote(session_id, safe='')}")


def _cap(text: Any) -> str:
    value = text if isinstance(text, str) else ""
    if len(value) > OUTPUT_CAP:
        return f"{value[:OUTPUT_CAP]}\n… (cut: {len(value) - OUTPUT_CAP} more characters)"
    return value


def _cap_result(value: Any) -> Any:
    """``result`` is whatever the sandbox reports for the last expression;
    a big one (a DataFrame, a long list) is capped like printed output."""
    if value is None:
        return None
    if isinstance(value, str):
        return _cap(value)
    try:
        dumped = json.dumps(value)
    except (TypeError, ValueError):
        return _cap(str(value))
    return _cap(dumped) if len(dumped) > OUTPUT_CAP else value


class RunScopedCodeExecutor:
    """One run's view of an executor: opens a session on first use when
    the executor supports them, reuses it, and closes it when the run
    ends. Output is capped here whatever the executor allows.

    Every engine owns one of these. A sub-engine (an import or a macro)
    gets its own through ``for_sub_engine()``, so its session never shares
    state with its caller's and closing it leaves the caller's open."""

    def __init__(self, executor: CodeExecutorInterface) -> None:
        self.executor = executor
        self.session_id: Optional[str] = None
        self._lock = asyncio.Lock()

    async def capabilities(self) -> dict[str, Any]:
        return await self.executor.capabilities()

    def for_sub_engine(self) -> "RunScopedCodeExecutor":
        """A fresh scope over the same executor, for a sub-engine."""
        return RunScopedCodeExecutor(self.executor)

    async def _session(self) -> Optional[str]:
        caps = await self.executor.capabilities()
        if not caps.get("sessions"):
            return None
        async with self._lock:
            if not self.session_id:
                self.session_id = await self.executor.open_session()
            return self.session_id

    async def run(
        self,
        *,
        language: str,
        code: str,
        timeout_ms: int,
        input: Any = None,
        files: Optional[list[dict[str, Any]]] = None,
    ) -> dict[str, Any]:
        caps = await self.executor.capabilities()
        languages = caps.get("languages") or []
        if language not in languages:
            raise ValueError(f"This sandbox runs {' and '.join(languages)}, not {language}.")
        session = await self._session()
        request: dict[str, Any] = {"language": language, "code": code, "timeoutMs": timeout_ms}
        if input is not None:
            request["input"] = input
        if files:
            request["files"] = files
        if session:
            request["session"] = session
        try:
            result = await self.executor.run(request) or {}
        except CodeSessionLostError:
            self.session_id = None
            raise
        error = result.get("error")
        if isinstance(error, dict) and error.get("kind") == "session_lost":
            self.session_id = None
            raise CodeSessionLostError()
        return {
            **result,
            "stdout": _cap(result.get("stdout")),
            "stderr": _cap(result.get("stderr")),
            "result": _cap_result(result.get("result")),
        }

    async def close(self) -> None:
        session_id, self.session_id = self.session_id, None
        if session_id:
            await self.executor.close_session(session_id)


def with_own_code_session(integrations: Optional[dict[str, Any]]) -> Optional[dict[str, Any]]:
    """The integrations a sub-engine runs with: the caller's, except that
    code runs in a session of its own. Returns the same dict when there is
    no code executor."""
    executor = (integrations or {}).get("code_executor")
    if not hasattr(executor, "for_sub_engine"):
        return integrations
    return {**integrations, "code_executor": executor.for_sub_engine()}


def create_code_executor(code_executor_config: dict[str, Any]) -> RunScopedCodeExecutor:
    """From the host's ``config["code_executor"]`` to the run-scoped executor."""
    if code_executor_config.get("instance") is not None:
        return RunScopedCodeExecutor(code_executor_config["instance"])
    if code_executor_config.get("url"):
        return RunScopedCodeExecutor(
            HttpCodeExecutor(
                url=code_executor_config["url"],
                api_key=code_executor_config.get("api_key") or code_executor_config.get("apiKey"),
                headers=code_executor_config.get("headers"),
                get_headers=code_executor_config.get("get_headers") or code_executor_config.get("getHeaders"),
                capabilities=code_executor_config.get("capabilities"),
            )
        )
    raise ValueError("config['code_executor'] needs either an instance or a url.")
