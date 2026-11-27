from __future__ import annotations
import json, threading, time, hashlib, os
from pathlib import Path

ROOT = Path(os.getenv("AVATAR_HOME", Path(__file__).resolve().parent.parent))
DATA = ROOT / "data"
STATE = DATA / "state"
STATE.mkdir(parents=True, exist_ok=True)
_lock = threading.RLock()
EMPTY = {"decisions": {}, "drafts": {}, "protocols": {}, "tasks_extra": [], "edits": [], "rules": [],
         "moved": {}, "audit": [], "meetings": [], "escalations": [], "briefings": []}


def load(pid: str) -> dict:
    f = STATE / f"{pid}.json"
    with _lock:
        d = json.loads(f.read_text(encoding="utf-8")) if f.exists() else {}
    for k, v in EMPTY.items():
        d.setdefault(k, json.loads(json.dumps(v)))
    return d


def save(pid: str, st: dict) -> None:
    with _lock:
        tmp = STATE / f"{pid}.json.tmp"
        tmp.write_text(json.dumps(st, ensure_ascii=False, indent=1), encoding="utf-8")
        tmp.replace(STATE / f"{pid}.json")


class Tx:
    """with Tx(pid) as st: ... — изменения сохраняются при выходе без ошибки"""
    def __init__(self, pid): self.pid = pid
    def __enter__(self): _lock.acquire(); self.st = load(self.pid); return self.st
    def __exit__(self, et, *_):
        try:
            if et is None: save(self.pid, self.st)
        finally: _lock.release()


def audit(st: dict, actor: str, action: str, target: str = "", meta: dict | None = None) -> None:
    prev = st["audit"][-1]["hash"] if st["audit"] else ""
    e = {"ts": time.strftime("%Y-%m-%d %H:%M:%S"), "actor": actor, "action": action, "target": target, "meta": meta or {}}
    e["hash"] = hashlib.sha256((prev + json.dumps(e, ensure_ascii=False, sort_keys=True)).encode()).hexdigest()[:16]
    st["audit"].append(e)
    del st["audit"][:-500]
