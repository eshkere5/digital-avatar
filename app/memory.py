"""Память правок: правка → diff → правило. Новые черновики сразу применяют правила; при LLM последние правки идут few-shot."""
from __future__ import annotations
import difflib, re, time
from .llm import chat_json, available


def _tok(s): return re.findall(r"\S+\s*|\n", s)


def diff_ops(before: str, after: str) -> list[dict]:
    a, b = _tok(before), _tok(after); ops = []
    for tag, i1, i2, j1, j2 in difflib.SequenceMatcher(None, a, b, autojunk=False).get_opcodes():
        if tag != "equal": ops.append({"op": tag, "from": "".join(a[i1:i2]).strip(), "to": "".join(b[j1:j2]).strip()})
    return ops


def _bump(st, r):
    for x in st["rules"]:
        if all(x.get(k) == v for k, v in r.items()): x["count"] += 1; return
    r.update({"id": f"r{int(time.time()*1000)%10**9}{len(st['rules'])}", "count": 1, "kind": "auto", "on": True}); st["rules"].append(r)


def learn(st: dict, kind: str, ctx: str, before: str, after: str):
    if before.strip() == after.strip(): return None
    ops = diff_ops(before, after)
    e = {"ts": time.strftime("%Y-%m-%d %H:%M"), "kind": kind, "ctx": ctx, "before": before, "after": after, "ops": ops}
    st["edits"].append(e); del st["edits"][:-200]
    for o in ops:
        if o["op"] == "replace" and o["from"] and o["to"] and len(o["from"].split()) <= 4 and len(o["to"].split()) <= 6: _bump(st, {"type": "replace", "from": o["from"], "to": o["to"]})
        elif o["op"] == "delete" and o["from"] and len(o["from"].split()) <= 8: _bump(st, {"type": "delete", "from": o["from"]})
    return e


def apply_rules(st: dict, text: str):
    used = []
    for r in st["rules"]:
        if not r.get("on", True): continue
        if r["type"] == "replace" and r["from"] in text: text = text.replace(r["from"], r["to"]); used.append(f"«{r['from']}» → «{r['to']}»")
        elif r["type"] == "delete" and r["from"] in text: text = re.sub(r"[ \t]{2,}", " ", text.replace(r["from"], "")); used.append(f"убрать «{r['from']}»")
    return text, used


def few_shot(st, kind, n=4) -> str:
    return "\n\n".join(f"Черновик:\n{e['before'][:600]}\nПравка руководителя:\n{e['after'][:600]}" for e in [e for e in st["edits"] if e["kind"] == kind][-n:])


def style_notes(st) -> str: return "\n".join(f"- {r['text']}" for r in st["rules"] if r["type"] == "style" and r.get("on", True))


def distill(st: dict) -> list[dict]:
    if not available() or not st["edits"]: return []
    ex = "\n\n".join(f"{e['kind']}: ДО: {e['before'][:400]}\nПОСЛЕ: {e['after'][:400]}" for e in st["edits"][-12:])
    r = chat_json('Выведи из правок руководителя 3–6 коротких правил стиля и содержания на русском. Формат: {"rules":["..."]}', ex, max_tokens=500)
    out = []
    for t in (r or {}).get("rules", [])[:6]:
        if not any(x.get("text") == t for x in st["rules"]):
            x = {"id": f"s{int(time.time()*1000)%10**9}{len(out)}", "type": "style", "text": t, "count": 1, "kind": "llm", "on": True}; st["rules"].append(x); out.append(x)
    return out
