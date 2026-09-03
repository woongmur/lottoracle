"""브라우저 GUI — 표준 라이브러리 http.server 만으로 동작한다 (설치 불필요).

    python -m lottoracle gui            # http://127.0.0.1:8765 를 열어 준다

보안 메모:
  * 쓰기 요청(POST)은 Origin 헤더가 있으면 Host 와 같아야 한다. 다른 사이트가 사용자의
    브라우저를 통해 이 로컬 서버를 호출하는 것(CSRF)을 막는다.
  * --host 0.0.0.0 으로 열면 같은 네트워크의 누구나 접속할 수 있다. 인증은 없다.
"""

from __future__ import annotations

import ipaddress
import json
import os
import sys
import threading
import webbrowser
from datetime import date
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any
from urllib.parse import parse_qs, urlparse

from . import __version__
from .engine import Engine, Options
from .fortune import DISCLAIMER, TAGLINE, Profile, branch_choices
from .strategies import DEFAULT_STRATEGIES

GUI_HTML = os.path.join(os.path.dirname(os.path.abspath(__file__)), "gui.html")

# 카카오맵 JavaScript 키. 페이지 소스에 드러나는 것이 정상인 키이며, 카카오 개발자 콘솔에
# 등록된 도메인(http://localhost:8765, http://127.0.0.1:8765)에서만 동작한다.
# 개발용으로 다른 키를 쓰려면 LOTTORACLE_KAKAO_JS_KEY 환경변수로 덮어쓴다.
DEFAULT_KAKAO_JS_KEY = "14d51c1614df122e68dbc7ca849d5d40"
DEFAULT_PORT = 8765


def kakao_js_key() -> tuple[str, str]:
    """(키, 출처). 환경변수가 있으면 그것, 없으면 내장 기본 키."""
    if os.environ.get("LOTTORACLE_KAKAO_JS_KEY"):
        return os.environ["LOTTORACLE_KAKAO_JS_KEY"], "env"
    return DEFAULT_KAKAO_JS_KEY, "default"


def _json_bytes(payload: Any) -> bytes:
    return json.dumps(payload, ensure_ascii=False).encode("utf-8")


def _is_loopback(host: str) -> bool:
    if host in ("localhost", ""):
        return True
    try:
        return ipaddress.ip_address(host).is_loopback
    except ValueError:
        return False


class Handler(BaseHTTPRequestHandler):
    engine: Engine  # 서버 생성 시 주입
    _lock = threading.Lock()  # 백테스트·갱신 같은 무거운 작업은 한 번에 하나만

    # ------------------------------------------------------------ 공통
    def _send(self, status: int, body: bytes, content_type: str) -> None:
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
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

    def _origin_ok(self) -> bool:
        """Origin 이 있으면 Host 와 같아야 한다. (curl 처럼 Origin 이 없는 요청은 통과)"""
        origin = self.headers.get("Origin")
        if not origin or origin == "null":
            return not origin  # 'null' 오리진(파일·샌드박스)은 거부
        host = self.headers.get("Host", "")
        return urlparse(origin).netloc.lower() == host.lower()

    def log_message(self, fmt: str, *args: Any) -> None:  # 콘솔을 조용히
        if os.environ.get("LOTTORACLE_DEBUG"):
            super().log_message(fmt, *args)

    # ------------------------------------------------------------ 라우팅
    def _meta(self) -> dict[str, Any]:
        eng = self.engine
        prev = eng.previous
        profile = eng.store.load_profile()
        settings = eng.store.load_settings()
        key, key_source = kakao_js_key()
        return {
            "version": __version__,
            "draws_used": len(eng.draws),
            "previous": eng.draw_payload(prev) if prev else None,
            "strategies": [{"key": s.key, "name": s.name, "concept": s.concept} for s in DEFAULT_STRATEGIES],
            "has_profile": not profile.is_empty,
            "profile_name": profile.name,
            "tagline": TAGLINE,
            "disclaimer": DISCLAIMER,
            "kakao_js_key": key,
            "kakao_key_source": key_source,
            "kakao_default_origins": [f"http://localhost:{DEFAULT_PORT}", f"http://127.0.0.1:{DEFAULT_PORT}"],
            "auto_refresh": bool(settings.get("auto_refresh", True)),
            "online_refresh": eng.path.lower().endswith(".json"),
            "today": date.today().isoformat(),
            "branch_choices": branch_choices(),
        }

    def do_GET(self) -> None:
        url = urlparse(self.path)
        query = {k: v[-1] for k, v in parse_qs(url.query).items()}
        eng = self.engine
        try:
            if url.path in ("/", "/index.html"):
                with open(GUI_HTML, "rb") as fp:
                    self._send(HTTPStatus.OK, fp.read(), "text/html; charset=utf-8")
            elif url.path == "/api/meta":
                self._json(self._meta())
            elif url.path == "/api/stats":
                self._json(eng.stats_payload(
                    recent_window=int(query.get("recent_window", 30)),
                    coverage=float(query.get("coverage", 0.8)),
                ))
            elif url.path == "/api/draws":
                self._json(eng.draws_payload(limit=int(query.get("limit", 20))))
            elif url.path == "/api/fortune":
                today = date.fromisoformat(query["date"]) if query.get("date") else None
                self._json(eng.fortune_payload(today=today))
            elif url.path == "/api/profile":
                self._json({"profile": eng.store.load_profile().to_dict()})
            elif url.path == "/api/picks":
                self._json({"picks": eng.picks_payload()})
            elif url.path == "/api/settings":
                self._json({"settings": eng.store.load_settings()})
            else:
                self._error("not found", HTTPStatus.NOT_FOUND)
        except Exception as exc:  # 사용자 입력 오류를 화면에 그대로 보여준다
            self._error(str(exc))

    def do_POST(self) -> None:
        url = urlparse(self.path)
        eng = self.engine
        if not self._origin_ok():
            self._error("다른 출처에서 온 요청은 받지 않습니다.", HTTPStatus.FORBIDDEN)
            return
        try:
            body = self._body()
            if url.path == "/api/recommend":
                self._json(eng.recommend_payload(Options.from_dict(body)))
            elif url.path == "/api/grade":
                lines = [[int(n) for n in row] for row in body.get("lines", [])]
                for row in lines:
                    if len(row) != 6 or len(set(row)) != 6 or not all(1 <= n <= 45 for n in row):
                        raise ValueError(f"조합은 1~45 사이 서로 다른 번호 6개여야 합니다: {row}")
                no = body.get("draw_no")
                self._json(eng.grade_payload(lines, int(no) if no not in (None, "") else None))
            elif url.path == "/api/backtest":
                with self._lock:
                    opts = Options.from_dict(body.get("options", {}))
                    rounds = max(5, min(300, int(body.get("rounds", 52) or 52)))
                    seed = body.get("seed")
                    self._json(eng.backtest_payload(
                        opts, rounds=rounds, seed=int(seed) if seed not in (None, "") else None
                    ))
            elif url.path == "/api/profile":
                profile = Profile.from_dict(body.get("profile", body))
                if profile.is_empty:
                    raise ValueError("생년월일을 입력하세요.")
                eng.store.save_profile(profile)
                self._json(eng.fortune_payload(profile))
            elif url.path == "/api/profile/delete":
                eng.store.clear_profile()
                self._json({"ok": True})
            elif url.path == "/api/picks":
                prev = eng.previous
                target = body.get("target_draw") or ((prev.no + 1) if prev else 1)
                rec = eng.store.add_pick(body.get("lines", []), int(target), body.get("note", ""))
                self._json({"saved": rec, "picks": eng.picks_payload()})
            elif url.path == "/api/picks/delete":
                ok = eng.store.delete_pick(str(body.get("id", "")))
                self._json({"ok": ok, "picks": eng.picks_payload()})
            elif url.path == "/api/refresh":
                with self._lock:
                    try:
                        self._json(eng.refresh(timeout=float(body.get("timeout", 10) or 10)))
                    except ValueError:
                        raise
                    except Exception as exc:  # 네트워크·파싱 실패는 502 로 구분
                        self._error(f"동행복권 연결 실패: {exc}", HTTPStatus.BAD_GATEWAY)
            elif url.path == "/api/settings":
                self._json({"settings": eng.store.save_settings(body.get("settings", body))})
            else:
                self._error("not found", HTTPStatus.NOT_FOUND)
        except Exception as exc:
            self._error(str(exc))


def make_server(engine: Engine, host: str = "127.0.0.1", port: int = DEFAULT_PORT) -> ThreadingHTTPServer:
    handler = type("BoundHandler", (Handler,), {"engine": engine})
    return ThreadingHTTPServer((host, port), handler)


def serve(engine: Engine, host: str = "127.0.0.1", port: int = DEFAULT_PORT, open_browser: bool = True) -> int:
    try:
        server = make_server(engine, host, port)
    except OSError as exc:
        print(f"포트 {port} 을(를) 열 수 없습니다 ({exc}). --port 로 다른 번호를 지정하세요.", file=sys.stderr)
        return 1
    real_port = server.server_address[1]
    browser_host = "localhost" if _is_loopback(host) or host == "0.0.0.0" else host
    url = f"http://{browser_host}:{real_port}/"
    print(f"lottoracle v{__version__} GUI → {url}   (종료: Ctrl+C)")
    if not _is_loopback(host):
        print(
            f"주의: {host} 에 바인딩했습니다. 같은 네트워크의 다른 기기에서도 접속할 수 있고 인증은 없습니다.\n"
            f"      프로필·내 번호 같은 개인 데이터가 있으니 신뢰하는 네트워크에서만 쓰세요.",
            file=sys.stderr,
        )
    if open_browser:
        threading.Timer(0.6, lambda: webbrowser.open(url)).start()
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\n서버를 종료합니다.", file=sys.stderr)
    finally:
        server.server_close()
    return 0
