"""Расширения без правки server.py: токены из окружения, ключ администратора, проверка и привязка Telegram.
Подключаются в app/main.py. Переменные: TELEGRAM_BOT_TOKEN, GRAPH_TOKEN, AVATAR_ADMIN_KEY,
AVATAR_LLM_PROVIDER, AVATAR_LLM_MODEL (+ <PROVIDER>_API_KEY, читается самим llm.py)."""
import hmac, os, re, threading, time
from collections import deque
import httpx
from . import llm as L, channels as CH, profile as P

SEEN: deque = deque(maxlen=8)
_lock = threading.Lock()
ENV_TOKENS = (("telegram_token", "TELEGRAM_BOT_TOKEN"), ("graph_token", "GRAPH_TOKEN"))
CHAT_RE = re.compile(r"^-?\d{4,20}$")
UNLINKED = "Чат не привязан к профилю"


def _env(name: str) -> str: return (os.getenv(name) or "").strip()


def admin_key() -> str: return _env("AVATAR_ADMIN_KEY")


def needs_admin(path: str) -> bool:
    return path.startswith("/api/telegram") or bool(re.match(r"^/api/[^/]+/telegram(/|$)", path))


def guarded(method: str, path: str) -> bool:
    """Нужен ли ключ администратора для запроса (только если AVATAR_ADMIN_KEY задан)."""
    if not admin_key(): return False
    if needs_admin(path): return True
    return path.startswith("/api/settings") and method not in ("GET", "HEAD", "OPTIONS")


def key_ok(given: str) -> bool:
    return hmac.compare_digest((given or "").encode(), admin_key().encode())


def clean(text: str) -> str:
    """Убирает токены из текста ошибок, чтобы они не попали в ответ API или лог."""
    s = L.settings()
    for k in ("telegram_token", "graph_token"):
        if s.get(k): text = text.replace(s[k], "***")
    return re.sub(r"bot\d+:[\w-]{20,}", "bot***", text)


def patch_settings() -> None:
    """Токены и провайдер LLM из переменных окружения (удобно для Render: диск там не сохраняется)."""
    orig = L._load
    if getattr(orig, "_ext", False): return

    def _load() -> dict:
        d = orig()
        for key, env in ENV_TOKENS:
            if _env(env): d[key] = _env(env)
        prov = _env("AVATAR_LLM_PROVIDER").lower()
        if prov in d["providers"] and d["providers"][prov].get("key"):
            d["providers"][prov]["enabled"] = True
            if _env("AVATAR_LLM_MODEL"): d["providers"][prov]["model"] = _env("AVATAR_LLM_MODEL")
            d["providers"][prov]["priority"] = -1
        return d
    _load._ext = True
    L._load = _load
    save = L.save_settings

    def save_settings(patch: dict) -> None:
        save(patch)
        # не оставляем секреты из окружения в data/secrets.json
        try:
            import json
            raw = json.loads(L.SECRETS.read_text(encoding="utf-8"))
            for key, env in ENV_TOKENS:
                if _env(env) and raw.get(key) == _env(env) and not patch.get(key): raw[key] = ""
            L.SECRETS.write_text(json.dumps(raw, ensure_ascii=False, indent=1), encoding="utf-8")
        except (OSError, ValueError): pass
    L.save_settings = save_settings


def patch_poller() -> None:
    """Запоминает, кто писал боту, и подсказывает chat_id, пока чат не привязан."""
    orig = CH.TgPoller
    if getattr(orig, "_ext", False): return

    class Poller(orig):
        _ext = True

        def __init__(self, handler):
            def wrapped(chat, data, cb):
                with _lock: SEEN.appendleft({"chat_id": str(chat), "text": "" if cb else (data or "")[:60], "ts": time.strftime("%H:%M:%S")})
                rep = handler(chat, data, cb)
                if rep == UNLINKED and not cb:
                    return f"Это бот «Цифровой аватар». Ваш chat_id: {chat}. Откройте на сайте «Подключения → Telegram → Привязать» и укажите его."
                return rep
            super().__init__(wrapped)
    CH.TgPoller = Poller


def link_chat(pid: str, chat_id: str) -> dict:
    """Записывает chat_id в profile.md руководителя."""
    chat_id = str(chat_id).strip()
    if not CHAT_RE.match(chat_id): raise ValueError("chat_id — число, для групп с минусом")
    md = P.read_md(pid)
    if re.search(r"^Telegram chat_id\s*:.*$", md, re.M | re.I): md = re.sub(r"^(Telegram chat_id\s*:).*$", lambda m: f"{m.group(1)} {chat_id}", md, count=1, flags=re.M | re.I)
    else: md = re.sub(r"^(Email\s*:.*)$", lambda m: f"{m.group(1)}\nTelegram chat_id: {chat_id}", md, count=1, flags=re.M | re.I) if re.search(r"^Email\s*:", md, re.M | re.I) else f"Telegram chat_id: {chat_id}\n" + md
    P.write_md(pid, md)
    return P.get(pid)


def tg_check() -> dict:
    tok = L.settings()["telegram_token"]
    if not tok: return {"ok": False, "error": "Токен не задан: добавьте его в «Подключения» или переменную TELEGRAM_BOT_TOKEN"}
    try:
        r = httpx.get(f"https://api.telegram.org/bot{tok}/getMe", timeout=15)
        j = r.json()
    except Exception as e: return {"ok": False, "error": clean(f"Нет связи с Telegram: {e}")[:200]}
    if r.status_code == 200 and j.get("ok"): return {"ok": True, "username": j["result"].get("username", ""), "name": j["result"].get("first_name", "")}
    return {"ok": False, "error": "Telegram отклонил токен (проверьте, что скопировали его целиком)" if r.status_code in (401, 404) else clean(str(j))[:200]}


def install(app) -> None:
    from fastapi import HTTPException
    from fastapi.responses import JSONResponse
    from pydantic import BaseModel

    class LinkIn(BaseModel): chat_id: str

    patch_settings(); patch_poller()

    @app.middleware("http")
    async def admin_guard(req, nxt):
        if guarded(req.method, req.url.path) and not key_ok(req.headers.get("x-admin-key", "")):
            return JSONResponse({"detail": "Нужен ключ администратора (AVATAR_ADMIN_KEY)"}, status_code=401)
        return await nxt(req)

    @app.get("/api/extras")
    def extras(): return {"admin_protected": bool(admin_key()), "telegram_env": bool(_env("TELEGRAM_BOT_TOKEN")), "llm_env": bool(_env("AVATAR_LLM_PROVIDER")), "version": 2}

    @app.get("/api/telegram/status")
    def tg_status():
        with _lock: seen = list(SEEN)
        return {"configured": bool(L.settings()["telegram_token"]), "seen": seen}

    @app.post("/api/telegram/test")
    def tg_test(): return tg_check()

    @app.post("/api/{pid}/telegram/link")
    def tg_link(pid: str, b: LinkIn):
        try: P.get(pid)
        except KeyError: raise HTTPException(404, "нет такого профиля")
        try: prof = link_chat(pid, b.chat_id)
        except ValueError as e: raise HTTPException(400, str(e))
        r = CH.tg_send(prof["chat_id"], f"Чат привязан к профилю: {CH.esc(prof['name'])}. Утренний план придёт сюда, команда /plan покажет его сразу.")
        return {"ok": True, "profile": prof, "telegram": r}

    @app.post("/api/{pid}/telegram/test-send")
    def tg_test_send(pid: str):
        try: prof = P.get(pid)
        except KeyError: raise HTTPException(404, "нет такого профиля")
        return CH.tg_send(prof["chat_id"], "Проверка связи: сообщение от «Цифрового аватара».")
