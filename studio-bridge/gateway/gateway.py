"""Studio Bridge gateway.

Aggregates several local stdio MCP servers (Cinema 4D, Houdini, Fusion, ...)
into one Streamable HTTP MCP endpoint, so a single remote connector in
claude.ai can reach all of them through a tunnel.

    python gateway.py --config servers.json

The endpoint is served at  http://HOST:PORT/<token>/mcp  - the random token in
the path is the only thing protecting it once it is exposed through a tunnel,
so keep the URL private.

Tools of every downstream server are re-exported with a prefix:
    c4d__list_objects, houdini__create_node, fusion__fusion_status, ...
plus one built-in tool, `bridge_status`.
"""

from __future__ import annotations

import argparse
import contextlib
import json
import logging
import os
import sys
from pathlib import Path
from typing import Any

import anyio
import mcp.types as types
import uvicorn
from mcp.client.session import ClientSession
from mcp.client.stdio import StdioServerParameters, stdio_client
from mcp.server.lowlevel import Server
from mcp.shared.exceptions import McpError
from mcp.server.streamable_http_manager import StreamableHTTPSessionManager
from mcp.server.transport_security import TransportSecuritySettings

SEP = "__"
log = logging.getLogger("studio-bridge")


class Downstream:
    """One stdio MCP server, kept alive by its own supervisor task.

    The stdio/session contexts are entered and exited inside `run()` only,
    which keeps anyio's cancel scopes in a single task. Request handlers just
    use `self.session` and call `restart()` if it breaks.
    """

    def __init__(self, name: str, spec: dict[str, Any], base_dir: Path):
        self.name = name
        cwd = spec.get("cwd")
        if cwd and not Path(cwd).is_absolute():
            cwd = str((base_dir / cwd).resolve())
        self.params = StdioServerParameters(
            command=spec["command"],
            args=list(spec.get("args", [])),
            env={**os.environ, **{k: str(v) for k, v in spec.get("env", {}).items()}},
            cwd=cwd,
        )
        self.timeout = float(spec.get("timeout", 120))
        self.log_path = base_dir.parent / "logs" / f"{name}.log"
        self.session: ClientSession | None = None
        self.last_error: str | None = None
        self._ready = anyio.Event()
        self._restart = anyio.Event()

    async def run(self) -> None:
        delay = 3.0
        self.log_path.parent.mkdir(parents=True, exist_ok=True)
        while True:
            errlog = open(self.log_path, "a", encoding="utf-8", errors="replace")  # the app server's stderr
            try:
                async with stdio_client(self.params, errlog=errlog) as (read, write):
                    async with ClientSession(read, write) as session:
                        await session.initialize()
                        self.session, self.last_error = session, None
                        delay = 3.0
                        log.info("[%s] connected", self.name)
                        self._ready.set()
                        await self._restart.wait()
            except Exception as exc:  # noqa: BLE001 - keep supervising whatever happens
                self.last_error = f"{_root_cause(exc)} (see {self.log_path})"
                log.warning("[%s] down: %s", self.name, self.last_error)
                self._ready.set()  # wake waiters so they see the error instead of hanging
            errlog.close()
            self.session = None
            self._restart = anyio.Event()
            self._ready = anyio.Event()
            await anyio.sleep(delay)
            delay = min(delay * 2, 60.0)

    def restart(self) -> None:
        self.session = None
        self._restart.set()

    async def get_session(self) -> ClientSession | None:
        if self.session is None and self.last_error is not None:
            return None  # known to be down; don't stall the request, the supervisor keeps retrying
        with anyio.move_on_after(15):
            await self._ready.wait()
        return self.session

    async def list_tools(self) -> list[types.Tool]:
        session = await self.get_session()
        if session is None:
            return []
        try:
            with anyio.fail_after(20):
                return (await session.list_tools()).tools
        except Exception as exc:  # noqa: BLE001
            self.last_error = f"list_tools: {exc}"
            self.restart()
            return []

    async def call_tool(self, tool: str, arguments: dict[str, Any]) -> types.CallToolResult:
        session = await self.get_session()
        if session is None:
            return _error(f"{self.name} MCP server is not available: {self.last_error}")
        try:
            with anyio.fail_after(self.timeout):
                return await session.call_tool(tool, arguments)
        except TimeoutError:
            return _error(f"{self.name}: '{tool}' timed out after {self.timeout:.0f}s")
        except McpError as exc:  # the server answered with an error; the connection is fine
            return _error(f"{self.name}: {exc.error.message}")
        except Exception as exc:  # noqa: BLE001 - transport broke; reconnect in the background
            self.last_error = f"call_tool: {_root_cause(exc)}"
            self.restart()
            return _error(f"{self.name} connection lost ({exc}); reconnecting, retry in a few seconds")


def _root_cause(exc: BaseException) -> str:
    while isinstance(exc, BaseExceptionGroup) and len(exc.exceptions) == 1:
        exc = exc.exceptions[0]
    return f"{type(exc).__name__}: {exc}"


def _error(text: str) -> types.CallToolResult:
    return types.CallToolResult(content=[types.TextContent(type="text", text=text)], isError=True)


def build_server(downstreams: dict[str, Downstream]) -> Server:
    server = Server("studio-bridge")

    status_tool = types.Tool(
        name="bridge_status",
        description="Show which local apps (Cinema 4D, Houdini, Fusion ...) are connected "
        "to the Studio Bridge on the user's PC and how many tools each exposes.",
        inputSchema={"type": "object", "properties": {}},
    )

    @server.list_tools()
    async def list_tools() -> list[types.Tool]:
        tools = [status_tool]
        for name, ds in downstreams.items():
            for t in await ds.list_tools():
                tools.append(
                    t.model_copy(
                        update={
                            "name": f"{name}{SEP}{t.name}",
                            "description": f"[{name}] {t.description or ''}".strip(),
                        }
                    )
                )
        return tools

    @server.call_tool(validate_input=False)
    async def call_tool(name: str, arguments: dict[str, Any]) -> types.CallToolResult:
        if name == "bridge_status":
            lines = []
            for ds_name, ds in downstreams.items():
                tools = await ds.list_tools()
                state = f"ok, {len(tools)} tools" if ds.session else f"DOWN - {ds.last_error}"
                lines.append(f"{ds_name}: {state}")
            return types.CallToolResult(content=[types.TextContent(type="text", text="\n".join(lines))])
        prefix, sep, tool = name.partition(SEP)
        ds = downstreams.get(prefix)
        if not sep or ds is None:
            return _error(f"Unknown tool: {name}")
        return await ds.call_tool(tool, arguments or {})

    return server


def make_app(config: dict[str, Any], base_dir: Path):
    token = config["token"]
    if len(token) < 16:
        raise SystemExit("token in config must be at least 16 characters")
    downstreams = {
        name: Downstream(name, spec, base_dir)
        for name, spec in config["servers"].items()
        if spec.get("enabled", True)
    }
    manager = StreamableHTTPSessionManager(
        app=build_server(downstreams),
        stateless=False,
        # The Host header is the tunnel's hostname; the secret path is the protection.
        security_settings=TransportSecuritySettings(enable_dns_rebinding_protection=False),
    )
    mcp_path = f"/{token}/mcp"

    @contextlib.asynccontextmanager
    async def lifespan():
        async with anyio.create_task_group() as tg:
            for ds in downstreams.values():
                tg.start_soon(ds.run)
            async with manager.run():
                log.info("Serving %d app(s) at %s", len(downstreams), mcp_path)
                yield
            tg.cancel_scope.cancel()

    async def app(scope, receive, send):
        if scope["type"] == "lifespan":
            msg = await receive()
            ctx = lifespan()
            try:
                await ctx.__aenter__()
            except Exception as exc:  # noqa: BLE001
                await send({"type": "lifespan.startup.failed", "message": str(exc)})
                return
            await send({"type": "lifespan.startup.complete"})
            msg = await receive()
            assert msg["type"] == "lifespan.shutdown"
            await ctx.__aexit__(None, None, None)
            await send({"type": "lifespan.shutdown.complete"})
            return
        if scope["type"] == "http" and scope["path"].rstrip("/") == mcp_path:
            await manager.handle_request(scope, receive, send)
            return
        # Anything else (including wrong tokens) looks like an empty server.
        await send({"type": "http.response.start", "status": 404, "headers": [(b"content-type", b"text/plain")]})
        await send({"type": "http.response.body", "body": b"not found"})

    return app


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--config", default="servers.json")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8765)
    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(name)s %(levelname)s %(message)s", stream=sys.stderr)
    logging.getLogger("mcp").setLevel(logging.WARNING)
    config_path = Path(args.config).resolve()
    config = json.loads(config_path.read_text(encoding="utf-8-sig"))  # PowerShell 5 writes a BOM
    # servers.local.json (next to servers.json) survives install.cmd: its entries add to or replace
    # the generated ones, e.g. the user's own C4D bridge instead of the bundled one.
    local_path = config_path.with_name("servers.local.json")
    if local_path.is_file():
        local = json.loads(local_path.read_text(encoding="utf-8-sig"))
        config["servers"].update(local.get("servers", {}))
        log.info("servers.local.json applied: %s", ", ".join(local.get("servers", {})) or "(empty)")
    uvicorn.run(make_app(config, config_path.parent), host=args.host, port=args.port, log_level="warning")


if __name__ == "__main__":
    main()
