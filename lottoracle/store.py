"""사용자 데이터 저장소 — 프로필 · 내 번호 · 설정. 전부 이 기기의 data/ 폴더 JSON 파일이다.

서버로 보내지 않는다. 파일이 없으면 빈 값으로 시작한다.
"""

from __future__ import annotations

import json
import os
import threading
import uuid
from datetime import datetime
from typing import Any, Sequence

from .data import DEFAULT_CACHE
from .fortune import Profile
from .metrics import NUMBER_POOL

DEFAULT_DIR = os.path.dirname(DEFAULT_CACHE)
MAX_PICKS = 200


class UserStore:
    def __init__(self, directory: str | None = None) -> None:
        self.dir = directory or DEFAULT_DIR
        self._lock = threading.RLock()

    # ------------------------------------------------------------ 공통
    def _path(self, name: str) -> str:
        return os.path.join(self.dir, name)

    def _read(self, name: str, default: Any) -> Any:
        path = self._path(name)
        if not os.path.exists(path):
            return default
        with open(path, encoding="utf-8") as fp:
            try:
                return json.load(fp)
            except json.JSONDecodeError:
                return default

    def _write(self, name: str, payload: Any) -> None:
        os.makedirs(self.dir, exist_ok=True)
        tmp = self._path(name + ".tmp")
        with open(tmp, "w", encoding="utf-8") as fp:
            json.dump(payload, fp, ensure_ascii=False, indent=1)
        os.replace(tmp, self._path(name))

    # ------------------------------------------------------------ 프로필
    def load_profile(self) -> Profile:
        with self._lock:
            try:
                return Profile.from_dict(self._read("profile.json", {}))
            except ValueError:
                return Profile()

    def save_profile(self, profile: Profile) -> Profile:
        with self._lock:
            self._write("profile.json", profile.to_dict())
        return profile

    def clear_profile(self) -> None:
        with self._lock:
            path = self._path("profile.json")
            if os.path.exists(path):
                os.remove(path)

    # ------------------------------------------------------------ 내 번호
    def list_picks(self) -> list[dict[str, Any]]:
        with self._lock:
            raw = self._read("picks.json", [])
        return raw if isinstance(raw, list) else []

    def add_pick(self, lines: Sequence[Sequence[int]], target_draw: int, note: str = "") -> dict[str, Any]:
        clean: list[list[int]] = []
        for row in lines:
            nums = sorted(int(n) for n in row)
            if len(nums) != 6 or len(set(nums)) != 6 or any(n not in NUMBER_POOL for n in nums):
                raise ValueError(f"조합은 1~45 사이 서로 다른 번호 6개여야 합니다: {list(row)}")
            clean.append(nums)
        if not clean:
            raise ValueError("저장할 조합이 없습니다.")
        if len(clean) > 20:
            raise ValueError("한 번에 최대 20줄까지 저장할 수 있습니다.")
        record = {
            "id": uuid.uuid4().hex[:10],
            "saved_at": datetime.now().isoformat(timespec="seconds"),
            "target_draw": int(target_draw),
            "lines": clean,
            "note": str(note or "")[:60],
        }
        with self._lock:
            picks = self.list_picks()
            picks.append(record)
            self._write("picks.json", picks[-MAX_PICKS:])
        return record

    def delete_pick(self, pick_id: str) -> bool:
        with self._lock:
            picks = self.list_picks()
            kept = [p for p in picks if p.get("id") != pick_id]
            if len(kept) == len(picks):
                return False
            self._write("picks.json", kept)
            return True

    # ------------------------------------------------------------ 설정
    def load_settings(self) -> dict[str, Any]:
        with self._lock:
            raw = self._read("settings.json", {})
        return raw if isinstance(raw, dict) else {}

    def save_settings(self, patch: dict[str, Any]) -> dict[str, Any]:
        allowed = {"kakao_js_key", "auto_refresh"}
        with self._lock:
            current = self.load_settings()
            for k, v in patch.items():
                if k not in allowed:
                    continue
                if v in (None, ""):
                    current.pop(k, None)
                else:
                    current[k] = v
            self._write("settings.json", current)
            return current
