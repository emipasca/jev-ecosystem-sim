"""Web UI backend: stdlib-only HTTP server that runs the sim and serves JSON.

The backend advances the simulation on a background thread; the page polls
/api/state and renders the grid on a <canvas>. No third-party dependencies.

Endpoints:
  GET /                 -> the UI (web/index.html)
  GET /api/world        -> static world description (terrain, size, colours)
  GET /api/state        -> latest tick state (animals, veg, carcasses, pops)
  GET /api/control?cmd= -> play | pause | step | speed&value=<ticks/s>
"""

import json
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

from . import config as C
from .engine import Simulation

WEB_DIR = Path(__file__).resolve().parent.parent / "web"


class SimRunner:
    """Owns the simulation and advances it on a background thread."""

    def __init__(self, seed: int = C.WORLD_SEED):
        self.sim = Simulation(seed=seed)
        self.lock = threading.Lock()
        self.playing = False
        self.ticks_per_sec = 10.0
        self._state_cache = self.sim.to_state()
        self._world_cache = self.sim.world_static()
        thread = threading.Thread(target=self._loop, daemon=True)
        thread.start()

    def _loop(self):
        while True:
            if self.playing:
                start = time.time()
                self.step()
                # keep to the requested pace, but never spin
                delay = max(0.0, 1.0 / self.ticks_per_sec - (time.time() - start))
                time.sleep(delay if delay > 0 else 0.001)
            else:
                time.sleep(0.05)

    def step(self):
        with self.lock:
            self.sim.step()
            self._state_cache = self.sim.to_state()

    def state(self) -> dict:
        with self.lock:
            return self._state_cache

    def world(self) -> dict:
        return self._world_cache

    def control(self, cmd: str, value=None) -> dict:
        if cmd == "play":
            self.playing = True
        elif cmd == "pause":
            self.playing = False
        elif cmd == "step":
            self.playing = False
            self.step()
        elif cmd == "speed" and value:
            self.ticks_per_sec = max(0.5, min(60.0, float(value)))
        return {"playing": self.playing, "ticks_per_sec": self.ticks_per_sec}


def make_handler(runner: SimRunner):
    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *args):  # keep the console quiet
            pass

        def _send(self, body: bytes, content_type: str, status: int = 200):
            self.send_response(status)
            self.send_header("Content-Type", content_type)
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def _send_json(self, obj):
            self._send(json.dumps(obj).encode(), "application/json")

        def do_GET(self):
            url = urlparse(self.path)
            try:
                if url.path in ("/", "/index.html"):
                    self._send((WEB_DIR / "index.html").read_bytes(),
                               "text/html; charset=utf-8")
                elif url.path == "/api/world":
                    self._send_json(runner.world())
                elif url.path == "/api/state":
                    self._send_json(runner.state())
                elif url.path == "/api/control":
                    q = parse_qs(url.query)
                    cmd = q.get("cmd", [""])[0]
                    value = q.get("value", [None])[0]
                    self._send_json(runner.control(cmd, value))
                else:
                    self._send(b"not found", "text/plain", 404)
            except BrokenPipeError:
                pass

    return Handler


def serve(host: str = "127.0.0.1", port: int = 8000, seed: int = C.WORLD_SEED):
    runner = SimRunner(seed=seed)
    httpd = ThreadingHTTPServer((host, port), make_handler(runner))
    print(f"ecosystem sim running at http://{host}:{port}  (Ctrl-C to stop)")
    httpd.serve_forever()
