"""Шлюз LLM: OpenAI-совместимые API + Anthropic, цепочка фолбэков, маскирование ПДн, работа без LLM.
Ключи — в data/secrets.json (chmod 600) или в переменных окружения <PROVIDER>_API_KEY; в UI не возвращаются."""
from __future__ import annotations
import json, os, re, time
import httpx
from .store import DATA

SECRETS = DATA / "secrets.json"
PRESETS = {
    "openai": {"label": "OpenAI", "kind": "openai", "base_url": "https://api.openai.com/v1"},
    "anthropic": {"label": "Anthropic Claude", "kind": "anthropic", "base_url": "https://api.anthropic.com/v1"},
    "gemini": {"label": "Google Gemini", "kind": "openai", "base_url": "https://generativelanguage.googleapis.com/v1beta/openai"},
    "deepseek": {"label": "DeepSeek", "kind": "openai", "base_url": "https://api.deepseek.com"},
    "mistral": {"label": "Mistral", "kind": "openai", "base_url": "https://api.mistral.ai/v1"},
    "openrouter": {"label": "OpenRouter", "kind": "openai", "base_url": "https://openrouter.ai/api/v1"},
    "custom": {"label": "Свой OpenAI-совместимый (в т.ч. локальный)", "kind": "openai", "base_url": "http://127.0.0.1:11434/v1"},
}
LOCAL = r"https?://(127\.0\.0\.1|localhost)"


def _load() -> dict:
    d = {"providers": {k: {"enabled": False, "model": "", "key": "", "base_url": v["base_url"], "priority": i} for i, (k, v) in enumerate(PRESETS.items())},
         "telegram_token": "", "graph_token": "", "mask_pii": True, "allow_cloud": True}
    if SECRETS.exists():
        s = json.loads(SECRETS.read_text(encoding="utf-8"))
        for k, v in s.get("providers", {}).items():
            if k in d["providers"]: d["providers"][k].update(v)
        for k in ("telegram_token", "graph_token", "mask_pii", "allow_cloud"):
            if k in s: d[k] = s[k]
    for k in d["providers"]:
        env = os.getenv(f"{k.upper()}_API_KEY")
        if env and not d["providers"][k]["key"]: d["providers"][k]["key"] = env
    return d


def settings() -> dict: return _load()


def save_settings(patch: dict) -> None:
    d = _load()
    for k, v in (patch.get("providers") or {}).items():
        if k not in d["providers"]: continue
        for f in ("enabled", "model", "base_url", "priority"):
            if f in v: d["providers"][k][f] = v[f]
        if v.get("key"): d["providers"][k]["key"] = v["key"].strip()
        if v.get("clear_key"): d["providers"][k]["key"] = ""
    for k in ("telegram_token", "graph_token"):
        if patch.get(k): d[k] = patch[k].strip()
        if patch.get("clear_" + k): d[k] = ""
    for k in ("mask_pii", "allow_cloud"):
        if k in patch: d[k] = bool(patch[k])
    SECRETS.write_text(json.dumps(d, ensure_ascii=False, indent=1), encoding="utf-8")
    try: SECRETS.chmod(0o600)
    except OSError: pass


def public_settings() -> dict:
    d = _load()
    out = {"mask_pii": d["mask_pii"], "allow_cloud": d["allow_cloud"], "telegram_set": bool(d["telegram_token"]), "graph_set": bool(d["graph_token"]), "providers": []}
    for k, v in d["providers"].items():
        out["providers"].append({"id": k, "label": PRESETS[k]["label"], "enabled": v["enabled"], "model": v["model"], "base_url": v["base_url"],
                                 "has_key": bool(v["key"]), "key_hint": ("…" + v["key"][-4:]) if v["key"] else "", "priority": v["priority"]})
    out["providers"].sort(key=lambda x: x["priority"])
    return out


def mask(text: str) -> str:
    text = re.sub(r"[\w.+-]+@[\w-]+\.[\w.-]+", "[email]", text)
    return re.sub(r"(?<!\d)(?:\+7|8)[\s(-]*\d{3}[\s)-]*\d{3}[\s-]*\d{2}[\s-]*\d{2}(?!\d)", "[phone]", text)


class LLMError(Exception): pass


def _chain() -> list[tuple[str, dict]]:
    d = _load(); items = [(k, v) for k, v in d["providers"].items() if v["enabled"] and v["model"] and (v["key"] or k == "custom")]
    if not d["allow_cloud"]: items = [(k, v) for k, v in items if re.match(LOCAL, v["base_url"])]
    return sorted(items, key=lambda kv: kv[1]["priority"])


def available() -> bool: return bool(_chain())


def _post(k: str, v: dict, messages: list[dict], max_tokens: int, json_mode: bool, timeout: float) -> str:
    base = v["base_url"].rstrip("/")
    if PRESETS[k]["kind"] == "anthropic":
        sys_ = "\n".join(m["content"] for m in messages if m["role"] == "system")
        body = {"model": v["model"], "max_tokens": max_tokens, "messages": [m for m in messages if m["role"] != "system"]}
        if sys_: body["system"] = sys_
        r = httpx.post(base + "/messages", json=body, timeout=timeout, headers={"x-api-key": v["key"], "anthropic-version": "2023-06-01"})
        r.raise_for_status(); return "".join(b.get("text", "") for b in r.json()["content"])
    body = {"model": v["model"], "messages": messages}
    body["max_completion_tokens" if k == "openai" else "max_tokens"] = max_tokens
    if k != "openai": body["temperature"] = 0.2
    if json_mode and k in ("openai", "deepseek", "mistral"): body["response_format"] = {"type": "json_object"}
    h = {"Authorization": f"Bearer {v['key']}"} if v["key"] else {}
    r = httpx.post(base + "/chat/completions", json=body, headers=h, timeout=timeout)
    r.raise_for_status(); return r.json()["choices"][0]["message"]["content"] or ""


def chat(system: str, user: str, max_tokens: int = 1500, json_mode: bool = False, timeout: float = 90) -> tuple[str, str]:
    chain = _chain()
    if not chain: raise LLMError("LLM не подключён")
    pii = _load()["mask_pii"]; errs = []
    for k, v in chain:
        u = mask(user) if pii and not re.match(LOCAL, v["base_url"]) else user
        try: return _post(k, v, [{"role": "system", "content": system}, {"role": "user", "content": u}], max_tokens, json_mode, timeout), k
        except Exception as e: errs.append(f"{k}: {str(e)[:120]}")
    raise LLMError("; ".join(errs))


def chat_json(system: str, user: str, **kw):
    try: txt, _ = chat(system + "\nОтвечай только валидным JSON без пояснений.", user, json_mode=True, **kw)
    except LLMError: return None
    m = re.search(r"[\[{].*[\]}]", txt, re.S)
    try: return json.loads(m.group(0)) if m else None
    except json.JSONDecodeError: return None


def list_models(pid: str) -> list[str]:
    d = _load()["providers"][pid]; base = d["base_url"].rstrip("/")
    h = {"x-api-key": d["key"], "anthropic-version": "2023-06-01"} if PRESETS[pid]["kind"] == "anthropic" else ({"Authorization": f"Bearer {d['key']}"} if d["key"] else {})
    r = httpx.get(base + "/models", headers=h, timeout=20); r.raise_for_status()
    data = r.json(); items = data.get("data") or data.get("models") or []
    return sorted({(x.get("id") or x.get("name", "")).replace("models/", "") for x in items if isinstance(x, dict)})


def probe(pid: str) -> dict:
    d = _load()["providers"][pid]
    if not d["key"] and pid != "custom": return {"ok": False, "error": "ключ не задан"}
    if not d["model"]: return {"ok": False, "error": "не выбрана модель"}
    t = time.time()
    try: return {"ok": True, "ms": int((time.time() - t) * 1000) or 1, "reply": _post(pid, d, [{"role": "user", "content": "Ответь одним словом: ок"}], 30, False, 30)[:40]}
    except Exception as e: return {"ok": False, "error": str(e)[:200]}


class Facade:
    def available(self) -> bool: return available()

    def classify_email(self, m: dict, cats: list[str]):
        r = chat_json("Ты классифицируешь деловые письма. Категории: " + ", ".join(cats) + '. Верни {"category":"...","reason":"кратко"}.',
                      f"От: {m['from_name']} ({m['sender_role']})\nТема: {m['subject']}\n{m['body']}", max_tokens=200)
        return r if isinstance(r, dict) else None


llm = Facade()
