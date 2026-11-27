"""Профиль руководителя = markdown-файл. Парсится в настройки; код не меняется при подключении нового руководителя."""
from __future__ import annotations
import re, csv, shutil
from pathlib import Path
from .store import DATA

DEMO = DATA / "demo"
PROFILES = DATA / "profiles"
PROFILES.mkdir(parents=True, exist_ok=True)
ACTIONS = ["спросить_руководителя", "делегировать", "авто", "в_сводку", "игнорировать"]
DEFAULT_RULES = {
    "деньги": ("спросить_руководителя", ""), "кадры": ("спросить_руководителя", ""),
    "обязательства_клиентам": ("спросить_руководителя", ""), "руководство": ("спросить_руководителя", ""),
    "приглашение": ("спросить_руководителя", ""), "продажи": ("делегировать", "Директор по продажам"),
    "клиенты": ("делегировать", "клиентского сервиса"), "доступы": ("делегировать", "Ассистент"),
    "календарь": ("авто", ""), "отчёт": ("в_сводку", ""), "статус": ("в_сводку", ""), "рассылка": ("игнорировать", ""),
}
NEVER_AUTO = {"деньги", "кадры", "обязательства_клиентам", "руководство"}
DEFAULT_BLOCKS = [("Стратегия", [2], "11:00", "13:00"), ("Один на один с командой", [3], "16:00", "18:00")]
DAYS = {"пн": 0, "вт": 1, "ср": 2, "чт": 3, "пт": 4, "сб": 5, "вс": 6}
TEMPLATE = """# Профиль руководителя
Имя: Новый Руководитель
Должность: Руководитель направления
Email: leader@company.example
Telegram chat_id:
Утренний план: 08:30
Итог недели: пт 17:00

## Цели на квартал
1. Цель 1
2. Цель 2

## Никогда без подтверждения руководителя
- деньги и бюджеты
- кадры
- обязательства клиентам
- письма руководству

## Правила разбора
- деньги → спросить_руководителя
- кадры → спросить_руководителя
- обязательства_клиентам → спросить_руководителя
- руководство → спросить_руководителя
- приглашение → спросить_руководителя
- продажи → делегировать → Директор по продажам
- клиенты → делегировать → клиентского сервиса
- доступы → делегировать → Ассистент
- календарь → авто
- отчёт → в_сводку
- статус → в_сводку
- рассылка → игнорировать

## Защищённые блоки
- Стратегия | ср | 11:00-13:00
- Один на один с командой | чт | 16:00-18:00

## Стиль общения
Коротко, по делу, с конкретным следующим шагом и сроком.
"""


def pdir(pid: str) -> Path:
    if not re.fullmatch(r"[a-z0-9_-]{1,32}", pid): raise KeyError(pid)
    p = PROFILES / pid
    if not p.exists():
        if (DEMO / pid).exists(): shutil.copytree(DEMO / pid, p)
        else: raise KeyError(pid)
    return p


def md_path(pid: str) -> Path:
    d = pdir(pid)
    return d / "profile.md" if (d / "profile.md").exists() else d / "leader_profile.md"


def read_md(pid: str) -> str: return md_path(pid).read_text(encoding="utf-8")


def write_md(pid: str, text: str) -> None: (pdir(pid) / "profile.md").write_text(text, encoding="utf-8")


def list_profiles() -> list[dict]:
    for d in DEMO.iterdir():
        if d.is_dir() and not (PROFILES / d.name).exists(): shutil.copytree(d, PROFILES / d.name)
    out = []
    for d in sorted(PROFILES.iterdir()):
        if (d / "profile.md").exists() or (d / "leader_profile.md").exists():
            pr = parse(read_md(d.name)); out.append({"id": d.name, "name": pr["name"], "position": pr["position"]})
    return out


def create(pid: str, name: str, position: str, base: str = "ivan") -> None:
    if not re.fullmatch(r"[a-z0-9_-]{1,32}", pid): raise ValueError("id: латиница/цифры")
    if (PROFILES / pid).exists(): raise ValueError("профиль уже есть")
    shutil.copytree(pdir(base), PROFILES / pid)
    for f in ("profile.md", "leader_profile.md"): (PROFILES / pid / f).unlink(missing_ok=True)
    (PROFILES / pid / "profile.md").write_text(TEMPLATE.replace("Новый Руководитель", name).replace("Руководитель направления", position), encoding="utf-8")


def sections(md: str) -> dict[str, str]:
    out, cur = {"_head": ""}, "_head"
    for ln in md.splitlines():
        m = re.match(r"^##\s+(.*)", ln)
        if m: cur = m.group(1).strip().lower(); out[cur] = ""
        else: out[cur] += ln + "\n"
    return out


def _bullets(t: str) -> list[str]:
    return [re.sub(r"^\s*(?:[-*]|\d+[.)])\s*", "", x).strip() for x in t.splitlines() if re.match(r"^\s*(?:[-*]|\d+[.)])\s+", x)]


def _find(sec: dict, *keys) -> str:
    for k, v in sec.items():
        if any(x in k for x in keys): return v
    return ""


def parse(md: str) -> dict:
    sec = sections(md); head = sec["_head"]
    def field(n, d=""):
        m = re.search(rf"^{n}\s*:\s*(.*)$", head, re.M | re.I)
        return m.group(1).strip() if m else d
    name = field("Имя"); pos = field("Должность")
    if not name:
        m = re.search(r"^([А-ЯЁ][а-яё]+ [А-ЯЁ][а-яё]+)\s+—\s+([^.\n]+)", head, re.M)
        name, pos = (m.group(1), m.group(2)) if m else ("Руководитель", "")
    never_txt = " ".join(_bullets(_find(sec, "никогда"))).lower(); never = set()
    for cat, keys in {"деньги": ["деньг", "бюджет"], "кадры": ["кадр", "найм"], "обязательства_клиентам": ["обязательств"], "руководство": ["руковод"]}.items():
        if any(k in never_txt for k in keys): never.add(cat)
    if not never: never = set(NEVER_AUTO)
    rules = {k: {"action": v[0], "to": v[1]} for k, v in DEFAULT_RULES.items()}
    for b in _bullets(_find(sec, "правила разбора")):
        p = [x.strip() for x in re.split(r"→|->", b)]
        if len(p) >= 2 and p[1] in ACTIONS: rules[p[0]] = {"action": p[1], "to": p[2] if len(p) > 2 else ""}
    for c in never:
        if rules.get(c, {}).get("action") != "спросить_руководителя": rules[c] = {"action": "спросить_руководителя", "to": ""}
    blocks = []
    for b in _bullets(_find(sec, "защищённые", "защищенные")):
        m = re.match(r"(.+?)\s*\|\s*([^|]+)\|\s*(\d{1,2}:\d{2})\s*-\s*(\d{1,2}:\d{2})", b)
        if m:
            days = [DAYS[d[:2].lower()] for d in re.split(r"[,\s]+", m.group(2).strip()) if d[:2].lower() in DAYS]
            blocks.append({"title": m.group(1).strip(), "days": days, "start": m.group(3).zfill(5), "end": m.group(4).zfill(5)})
    if not blocks: blocks = [{"title": t, "days": d, "start": s, "end": e} for t, d, s, e in DEFAULT_BLOCKS]
    return {"name": name, "position": pos, "email": field("Email"), "chat_id": field("Telegram chat_id"), "briefing_time": field("Утренний план", "08:30"),
            "goals": _bullets(_find(sec, "цели")), "style": _find(sec, "стиль").strip(), "never": sorted(never), "rules": rules, "blocks": blocks}


def get(pid: str) -> dict: return parse(read_md(pid))


def rd_csv(pid: str, name: str) -> list[dict]:
    f = pdir(pid) / name
    if not f.exists(): return []
    with open(f, encoding="utf-8-sig", newline="") as fh: return list(csv.DictReader(fh))


def org(pid: str) -> list[dict]: return rd_csv(pid, "org_structure.csv")
