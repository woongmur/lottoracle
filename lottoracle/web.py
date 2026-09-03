"""브라우저 GUI — 표준 라이브러리 http.server 만으로 동작한다 (설치 불필요).

    python -m lottoracle gui            # http://127.0.0.1:8765 를 열어 준다
"""

from __future__ import annotations

import json
import os
import sys
import threading
import webbrowser
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any
from urllib.parse import parse_qs, urlparse

from .engine import Engine, Options

GUI_HTML = os.path.join(os.path.dirname(os.path.abspath(__file__)), "gui.html")


def _json_bytes(payload: Any) -> bytes:
    return json.dumps(payload, ensure_ascii=False).encode("utf-8")


class Handler(BaseHTTPRequestHandler):
    engine: Engine  # 서버 생성 시 주입
    _lock = threading.Lock()  # 백테스트 같은 무거운 작업은 한 번에 하나만

    # ------------------------------------------------------------ 공통
    def _send(self, status: int, body: bytes, content_type: str) -> None:
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def _json(self, payload: Any, status: int = HTTPStatus.OK) -> None:
        self._send(status, _json_bytes(payload), "application/json; charset=utf-8")

    def _error(self, message: str, status: int = HTTPStatus.BAD_REQUEST) -> None:
        self._json({"error": message}, status)

    def _body(self) -> dict[str, Any]:
        length = int(self.headers.get("Content-Length") or 0)
        if not length:
            return {}
        raw = self.rfile.read(length)
        parsed = json.loads(raw.decode("utf-8"))
        return parsed if isinstance(parsed, dict) else {}

    def log_message(self, fmt: str, *args: Any) -> None:  # 콘솔을 조용히
        if os.environ.get("LOTTORACLE_DEBUG"):
            super().log_message(fmt, *args)

    # ------------------------------------------------------------ 라우팅
    def do_GET(self) -> None:
        url = urlparse(self.path)
        query = {k: v[-1] for k, v in parse_qs(url.query).items()}
        try:
            if url.path in ("/", "/index.html"):
                with open(GUI_HTML, "rb") as fp:
                    self._send(HTTPStatus.OK, fp.read(), "text/html; charset=utf-8")
            elif url.path == "/api/meta":
                prev = self.engine.previous
                self._json({
                    "draws_used": len(self.engine.draws),
                    "previous": self.engine.draw_payload(prev) if prev else None,
                    "strategies": [
                        {"key": s.key, "name": s.name, "concept": s.concept}
                        for s in __import__("lottoracle.strategies", fromlist=["DEFAULT_STRATEGIES"]).DEFAULT_STRATEGIES
                    ],
                })
            elif url.path == "/api/stats":
                self._json(self.engine.stats_payload(
                    recent_window=int(query.get("recent_window", 30)),
                    coverage=float(query.get("coverage", 0.8)),
                ))
            elif url.path == "/api/draws":
                self._json(self.engine.draws_payload(limit=int(query.get("limit", 20))))
            else:
                self._error("not found", HTTPStatus.NOT_FOUND)
        except Exception as exc:  # 사용자 입력 오류를 화면에 그대로 보여준다
            self._error(str(exc))

    def do_POST(self) -> None:
        url = urlparse(self.path)
        try:
            body = self._body()
            if url.path == "/api/recommend":
                self._json(self.engine.recommend_payload(Options.from_dict(body)))
            elif url.path == "/api/grade":
                lines = [[int(n) for n in row] for row in body.get("lines", [])]
                for row in lines:
                    if len(row) != 6 or len(set(row)) != 6 or not all(1 <= n <= 45 for n in row):
                        raise ValueError(f"조합은 1~45 사이 서로 다른 번호 6개여야 합니다: {row}")
                no = body.get("draw_no")
                self._json(self.engine.grade_payload(lines, int(no) if no not in (None, "") else None))
            elif url.path == "/api/backtest":
                with self._lock:
                    opts = Options.from_dict(body.get("options", {}))
                    rounds = max(5, min(300, int(body.get("rounds", 52) or 52)))
                    seed = body.get("seed")
                    self._json(self.engine.backtest_payload(
                        opts, rounds=rounds, seed=int(seed) if seed not in (None, "") else None
                    ))
            else:
                self._error("not found", HTTPStatus.NOT_FOUND)
        except Exception as exc:
            self._error(str(exc))


def make_server(engine: Engine, host: str = "127.0.0.1", port: int = 8765) -> ThreadingHTTPServer:
    handler = type("BoundHandler", (Handler,), {"engine": engine})
    return ThreadingHTTPServer((host, port), handler)


def serve(engine: Engine, host: str = "127.0.0.1", port: int = 8765, open_browser: bool = True) -> int:
    server = make_server(engine, host, port)
    url = f"http://{host}:{server.server_address[1]}/"
    print(f"lottoracle GUI → {url}   (종료: Ctrl+C)")
    if open_browser:
        threading.Timer(0.6, lambda: webbrowser.open(url)).start()
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\n서버를 종료합니다.", file=sys.stderr)
    finally:
        server.server_close()
    return 0
