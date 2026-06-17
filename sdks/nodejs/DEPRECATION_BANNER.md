<!-- ─────────────────────────────────────────────────────────────────────
     DRAFT — prepend this block to the TOP of sdks/nodejs/README.md
     when publishing the deprecating release of `zv1` (e.g. 1.0.2).
     Don't commit this `DEPRECATION_BANNER.md` file to main; it's a
     review artifact only.
     ────────────────────────────────────────────────────────────────── -->

> ## ⚠️ This package has moved
>
> `zv1` is now **[`@zerowidth/workbench-sdk`](https://www.npmjs.com/package/@zerowidth/workbench-sdk)**.
> Same engine, same flow JSON, scoped npm name + a fixed MCP client
> (the `remote-mcp-tool` node now speaks the JSON-RPC 2.0 / Streamable
> HTTP wire shape correctly).
>
> ### Migrate
>
> ```bash
> npm uninstall zv1
> npm install @zerowidth/workbench-sdk
> ```
>
> ```diff
> - import zv1 from "zv1"
> + import workbenchSdk from "@zerowidth/workbench-sdk"
>
> - const engine = await zv1.create(flow, config)
> + const engine = await workbenchSdk.create(flow, config)
> ```
>
> Public API is identical — `create(flow, config)`, `engine.run(inputs, timeout)`,
> `engine.cleanup()`, `engine.timeline`. Same event handlers
> (`onNodeStart` / `onNodeComplete` / `onNodeUpdate` / `onError`), same
> cost summary, same timeline shape.
>
> ### Why
>
> - **Scoped name.** `@zerowidth/workbench-sdk` reflects that the SDK is
>   the runtime for Workbench, ZeroWidth's flow-authoring surface. Pairs
>   with future companions (`@zerowidth/panel-sdk`, …).
> - **MCP wire fix.** `zv1`'s `remote-mcp-tool` client omitted the
>   JSON-RPC 2.0 envelope, didn't set `Accept: text/event-stream`, and
>   couldn't parse SSE responses — so it failed against every
>   spec-compliant MCP server (including reference implementations
>   from Anthropic's `@modelcontextprotocol/sdk`). Fixed in
>   `@zerowidth/workbench-sdk` ≥ 2.0.0.
>
> ### What about `zv1@1.x`?
>
> Still installable, still works for flows that don't use
> `remote-mcp-tool`. **No new features land here.** Bug fixes only,
> and only on a best-effort basis. We recommend migrating at your
> next convenient release boundary.
>
> Documentation, releases, and the issue tracker now live under the
> new package name. See
> [`@zerowidth/workbench-sdk`](https://www.npmjs.com/package/@zerowidth/workbench-sdk)
> on npm and [the repo](https://github.com/zerowidth-ai/workbench-sdk) for the
> source.

<!-- end of deprecation banner — existing README content follows below this line -->
