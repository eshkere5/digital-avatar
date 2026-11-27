"""Протоколы: вопросы по прошлому протоколу, черновик нового, задачи со сроками, ответы аватара."""
from __future__ import annotations
import re, time, uuid
from datetime import date, timedelta
from . import llm as L, memory as M
from .store import DATA

PROTO_DIR = DATA / "protocols"
MARK_ACTION = r"нужно|надо|необходимо|давайте|подготов|пришл|отправ|сделаем|сделать|согласовать|проверить|уточнить|организ|запустить|составит|займ[её]тся|возьм[уё]"
MARK_DECISION = r"решили|договорились|принято|согласовали|утвердили|остановились"
SENSITIVE_Q = r"бюджет|скидк|цен[аыуе]\b|стоимост|оплат|гарант|обещ|увольн|найм|оффер|зарплат|отпуск|договор|подпис|срок.*клиент"


def list_library() -> list[dict]:
    out = {}
    for f in sorted(PROTO_DIR.glob("*.txt")):
        parts = f.name.rsplit(".", 2); out.setdefault(parts[0], {"name": parts[0], "summary": False, "transcript": False})[parts[1]] = True
    return list(out.values())


def read_lib(name: str, kind: str) -> str:
    f = (PROTO_DIR / f"{name}.{kind}.txt").resolve()
    if f.parent != PROTO_DIR.resolve(): raise ValueError("bad name")
    return f.read_text(encoding="utf-8") if f.exists() else ""


def parse_previous(text: str) -> dict:
    items, ai, sec = [], [], ""
    for ln in text.splitlines():
        if ln.startswith("#"): sec = ln.lower(); continue
        m = re.match(r"\s*- \[( |x)\]\s*(.+)", ln)
        if m: items.append({"done": m.group(1) == "x", "text": m.group(2).strip()}); continue
        m = re.match(r"\s*>?\s*\d+\.\s+(.+)", ln)
        if m and ("предложения ии" in sec or ln.strip().startswith(">")): ai.append(m.group(1).strip())
    return {"commitments": items, "open_ai": ai}


def questions_from_previous(prev: str, limit: int = 5) -> list[str]:
    p = parse_previous(prev)
    qs = [f"По прошлому протоколу: каков статус пункта «{i['text'].rstrip('.')}»?" for i in p["commitments"] if not i["done"]]
    qs += [f"Остался нерешённый вопрос: {t.rstrip('.')} Есть ли ясность?" for t in p["open_ai"]]
    return qs[:limit]


def parse_transcript(text: str) -> list[dict]:
    out, ts = [], None
    for ln in text.splitlines():
        ln = ln.strip()
        if not ln: continue
        if re.fullmatch(r"\d{1,2}:\d{2}(:\d{2})?", ln): ts = ln; continue
        m = re.match(r"^(?:\[?(\d{1,2}:\d{2}(?::\d{2})?)\]?\s+)?([^:]{2,30}):\s+(.+)", ln)
        out.append({"t": (m.group(1) or ts) if m else ts, "speaker": m.group(2) if m else None, "text": m.group(3) if m else ln})
    return out


def _due(s: str, base: date):
    s = s.lower(); m = re.search(r"до (\d{1,2})[.](\d{1,2})", s)
    if m:
        try: return date(base.year, int(m.group(2)), int(m.group(1))).isoformat()
        except ValueError: pass
    for k, wd in {"понедельник": 0, "вторник": 1, "сред": 2, "четверг": 3, "пятниц": 4}.items():
        if re.search(rf"(до|к|в) {k}", s):
            d = base + timedelta(days=1)
            while d.weekday() != wd: d += timedelta(days=1)
            return d.isoformat()
    if "завтра" in s: return (base + timedelta(days=1)).isoformat()
    if "следующей неделе" in s or "через неделю" in s: return (base + timedelta(days=7)).isoformat()
    return None


def _owner(s: str, names: list[str]):
    for n in names:
        first = n.split()[0]
        if re.search(rf"\b{first[:-1]}\w*", s): return n
    m = re.search(r"Speaker \d", s)
    return m.group(0) if m else None


def extractive(utts, names, base: date) -> dict:
    sents = [s.strip() for u in utts for s in re.split(r"(?<=[.!?])\s+", u["text"]) if 5 <= len(s.split()) <= 45]
    weak = r"наверное|не знаю|как-то|вроде|может быть|я бы|если вдруг|типа|короче"
    dec = [s for s in sents if re.search(MARK_DECISION, s, re.I) and len(s.split()) <= 35 and not re.search(weak, s, re.I)][:6]
    tasks, seen = [], set()
    for s in sents:
        if not (re.search(MARK_ACTION, s, re.I) and s not in dec and not s.endswith("?") and 6 <= len(s.split()) <= 26 and not re.search(weak, s, re.I)): continue
        if s.lower()[:40] in seen: continue
        seen.add(s.lower()[:40]); tasks.append({"text": s, "owner": _owner(s, names), "due": _due(s, base)})
        if len(tasks) >= 8: break
    words = {}
    for s in sents:
        for w in re.findall(r"[а-яёa-z]{6,}", s.lower()): words[w] = words.get(w, 0) + 1
    top = sorted(words, key=words.get, reverse=True)[:6]
    summ = [s for s in sents if sum(w in s.lower() for w in top) >= 2 and 10 <= len(s.split()) <= 30 and not re.search(r"наверное|не знаю|как-то", s, re.I)][:5]
    return {"summary": summ, "decisions": dec, "tasks": tasks, "open_questions": [s for s in sents if s.endswith("?") and len(s.split()) > 7][:4], "engine": "правила (без LLM) — подключите LLM для качества"}


def render(title: str, d: date, data: dict) -> str:
    li = lambda xs: "\n".join(f"- {x}" for x in xs) or "- —"
    tk = "\n".join("- [ ] %s — %s — %s" % (t["text"].rstrip("."), t.get("owner") or "не назначен", ("до " + t["due"]) if t.get("due") else "срок не указан") for t in data["tasks"]) or "- —"
    return f"# Протокол: {title}\nДата: {d.isoformat()}\nПодготовлен ИИ-помощником руководителя\n\n## Кратко\n{li(data['summary'])}\n\n## Решения\n{li(data['decisions'])}\n\n## Задачи\n{tk}\n\n## Открытые вопросы\n{li(data['open_questions'])}\n"


def tasks_from_text(text: str) -> list[dict]:
    out = []
    for ln in text.splitlines():
        m = re.match(r"\s*- \[ \]\s*(.+?)(?:\s+—\s+(.+?))?(?:\s+—\s+(?:до\s+(\d{4}-\d{2}-\d{2})|срок не указан))?\s*$", ln)
        if m:
            o = m.group(2); out.append({"text": m.group(1).strip(), "owner": None if (not o or o.startswith("не назначен")) else o, "due": m.group(3)})
    return out


def draft(transcript: str, title: str, prev: str, names: list[str], base: date, style: str = "", st: dict | None = None) -> dict:
    utts = parse_transcript(transcript); data = None
    if L.available():
        prompt = ('Составь протокол встречи по транскрипту. Ответ JSON: {"summary":[строки],"decisions":[строки],"tasks":[{"text":"","owner":"имя или null","due":"YYYY-MM-DD или null"}],"open_questions":[строки]}. '
                  f"Не выдумывай фактов. Сегодня {base.isoformat()}. Участники из оргструктуры: {', '.join(names)}. Стиль: {style}.")
        if st:
            sn, fs = M.style_notes(st), M.few_shot(st, "protocol")
            if sn: prompt += "\nПравила руководителя:\n" + sn
            if fs: prompt += "\nПримеры правок руководителя:\n" + fs
        txt = " ".join(u["text"] for u in utts)[:24000] + (("\nПрошлый протокол:\n" + prev[:3000]) if prev else "")
        data = L.chat_json(prompt, txt, max_tokens=2000, timeout=120)
        if isinstance(data, dict): data["engine"] = "LLM"
        else: data = None
    if not data: data = extractive(utts, names, base)
    for k in ("summary", "decisions", "tasks", "open_questions"): data.setdefault(k, [])
    text, used = render(title, base, data), []
    if st: text, used = M.apply_rules(st, text)
    return {"id": uuid.uuid4().hex[:8], "title": title, "date": base.isoformat(), "data": data, "text": text, "orig_text": text, "status": "draft",
            "rules_applied": used, "created": time.strftime("%Y-%m-%d %H:%M"), "prev_questions": questions_from_previous(prev) if prev else []}


def answer(question: str, prof: dict, tasks: list[dict], st: dict) -> dict:
    q = question.lower()
    if re.search(SENSITIVE_Q, q):
        return {"text": f"Это решает {prof['name']}. Я ИИ-помощник и не принимаю решений по деньгам, кадрам и обязательствам. Передам вопрос руководителю.", "escalate": True, "source": "policy"}
    if L.available():
        ctx = "Цели: " + "; ".join(prof["goals"]) + "\nЗадачи: " + "; ".join(f"{t['task']} ({t['owner']}, до {t['due']}, {t['status']})" for t in tasks[:25])
        try:
            txt, _ = L.chat(f"Ты — ИИ-помощник руководителя {prof['name']} на встрече. Отвечай коротко (1–3 предложения) только по контексту. Если ответа нет в контексте или нужно решение/обязательство — ответь ровно: ПЕРЕДАТЬ. Стиль: {prof['style']}\n{M.style_notes(st)}", f"{ctx}\n\nВопрос: {question}", max_tokens=300)
            if txt.strip().startswith("ПЕРЕДАТЬ"): return {"text": "Уточню у руководителя и вернусь с ответом после встречи.", "escalate": True, "source": "llm"}
            return {"text": txt.strip(), "escalate": False, "source": "llm"}
        except L.LLMError: pass
    ws = re.findall(r"[а-яё]{5,}", q)
    hit = next((t for t in tasks if any(w[:5] in (t["task"] + t["owner"]).lower() for w in ws)), None)
    if hit: return {"text": f"По задаче «{hit['task']}»: ответственный — {hit['owner']}, срок — {hit['due']}, статус — {hit['status']}.", "escalate": False, "source": "tasks"}
    return {"text": "Не хочу гадать: уточню у руководителя и вернусь с ответом после встречи.", "escalate": True, "source": "fallback"}
