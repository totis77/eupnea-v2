"""Real-time WebSocket bridge for the web viewer.

Runs the headless sim at its fixed tick rate and broadcasts JSON snapshots to
connected browsers. A tiny stdlib HTTP server serves the static viewer so the
page can be opened over http:// (not file://).

    uv run python -m simsy.server
    -> open http://localhost:8000

The snapshot stream is currently full keyframes every tick. Delta encoding and
a decoupled (lower) snapshot rate (architecture doc 2A) are a later optimization;
for a handful of agents the bandwidth is trivial and the client already
interpolates between frames.
"""

from __future__ import annotations

import asyncio
import functools
import http.server
import json
import threading
from pathlib import Path

import websockets

from .config import load_config
from .sim import build_coffee_shop

_cfg = load_config()
HTTP_PORT = _cfg.server.http_port
WS_PORT = _cfg.server.ws_port
VIEWER_DIR = Path(__file__).resolve().parent.parent / "viewer"

_clients: set = set()


async def _ws_handler(ws) -> None:
    _clients.add(ws)
    try:
        await ws.wait_closed()
    finally:
        _clients.discard(ws)


async def _sim_loop() -> None:
    sim = build_coffee_shop(config=_cfg)
    dt = sim.ctx.dt
    # Decouple broadcast rate from the tick rate (architecture doc 2A): emit a
    # snapshot every Nth tick so a 100Hz sim can still stream at, say, 10Hz.
    every = max(1, round(_cfg.simulation.tick_rate_hz / _cfg.server.snapshot_hz))
    loop = asyncio.get_running_loop()
    next_tick = loop.time()
    print(f"[sim] {1 / dt:.0f} ticks/s, broadcast every {every} tick(s) (seed {sim.ctx.seed})")
    while True:
        sim.step()
        if _clients and sim.ctx.tick % every == 0:
            websockets.broadcast(_clients, json.dumps(sim.snapshot()))
        next_tick += dt
        await asyncio.sleep(max(0.0, next_tick - loop.time()))


def _serve_http() -> None:
    handler = functools.partial(
        http.server.SimpleHTTPRequestHandler, directory=str(VIEWER_DIR)
    )
    httpd = http.server.ThreadingHTTPServer(("localhost", HTTP_PORT), handler)
    print(f"[http] viewer at http://localhost:{HTTP_PORT}")
    httpd.serve_forever()


async def main() -> None:
    threading.Thread(target=_serve_http, daemon=True).start()
    async with websockets.serve(_ws_handler, "localhost", WS_PORT):
        print(f"[ws]   streaming snapshots on ws://localhost:{WS_PORT}")
        await _sim_loop()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n[server] stopped")
