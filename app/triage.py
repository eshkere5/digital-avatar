"""Разбор почты: детерминированные правила + LLM только для неоднозначных писем. Неизвестное → «спросить руководителя»."""
from __future__ import annotations
import re, hashlib
from . import profile as P

CAT_ORDER = ["деньги", "кадры", "руководство", "обязательства_клиентам", "приглашение", "рассылка", "календарь",
             "доступы", "продажи", "клиенты", "отчёт", "статус"]
KW = {
    "деньги": r"скидк|бюджет|закупк|перераспред|оплат|счёт на|счет на|платёж|платеж|компенсац|расход",
    "кадры": r"отпуск|кандидат|оффер|найм|увольн|повышени|зарплат|премир|вакан|штат",
    "обязательства_клиентам": r"срок|гаранти|подтвердите|обязуем|до \d{1,2} (?:января|февраля|марта|апреля|мая|июня|июля|августа|сентября|октября|ноября|декабря)|sla|неустойк",
    "приглашение": r"приглаша|выступить|спикер|конференц",
    "рассылка": r"рассылк|отписа|новости продуктов|вебинар|дайджест",
    "календарь": r"перенос|перенести|сдвинуть|подтвердите участие|переслать встречу|новое время встречи|подтвердить участие",
    "доступы": r"доступ|учётн|учетн|права на|vpn|crm для",
    "продажи": r"коммерческ|\bкп\b|запрос цен|тендер|лицензи",
    "клиенты": r"жалоб|претензи|недоволен|эскалац",
    "отчёт": r"отч[её]т|прогноз|дашборд|итоги недели|сводк",
    "статус": r"статус|апдейт|обновлени|ход работ|прогресс",
}
ROLE_CAT = {"руководитель руководителя": "руководство", "приглашение": "приглашение", "рассылка": "рассылка"}


def classify(m: dict) -> tuple[str, float, str]:
    role = (m.get("sender_role") or "").lower()
    text = f"{m.get('subject','')} {m.get('body','')}".lower(); subj = (m.get("subject") or "").lower()
    if role in ROLE_CAT: return ROLE_CAT[role], 0.95, f"отправитель: {role}"
    hits = []
    for cat in CAT_ORDER:
        rx = KW.get(cat)
        if not rx or (cat == "обязательства_клиентам" and role != "клиент"): continue
        if re.search(rx, subj): hits.append((cat, 0.9, "тема"))
        elif re.search(rx, text): hits.append((cat, 0.7, "текст"))
    if not hits: return "неизвестно", 0.0, "нет правил"
    b = sorted(hits, key=lambda h: (-h[1], CAT_ORDER.index(h[0])))[0]
    return b[0], b[1], f"ключевые слова ({b[2]})"


def _find_person(org: list[dict], hint: str) -> dict | None:
    hint = (hint or "").lower()
    if not hint: return None
    return next((p for p in org if hint in (p["position"] + " " + p["name"]).lower()), None)


def process(pid: str, llm=None) -> list[dict]:
    prof = P.get(pid); org = P.org(pid); seen: dict[str, str] = {}; out = []
    for m in P.rd_csv(pid, "inbox.csv"):
        key = hashlib.md5(f"{m['from_email']}|{m['subject']}|{m['body']}".encode()).hexdigest()
        cat, conf, why = classify(m); used = False
        if conf < 0.7 and llm is not None and llm.available():
            r = llm.classify_email(m, list(prof["rules"].keys()))
            if r and r.get("category") in prof["rules"]: cat, conf, why, used = r["category"], 0.65, "LLM: " + str(r.get("reason", "")), True
        rule = prof["rules"].get(cat)
        action, to = (rule["action"], rule["to"]) if rule else ("спросить_руководителя", "")
        if not rule: why += "; неизвестная категория → спросить руководителя"
        if cat in prof["never"]: action = "спросить_руководителя"
        who = _find_person(org, to) if action == "делегировать" else None
        out.append({"id": m["id"], "received": m["received"], "from_name": m["from_name"], "from_email": m["from_email"], "sender_role": m["sender_role"],
                    "subject": m["subject"], "body": m["body"], "category": cat, "action": action, "delegate_to": who["name"] if who else to,
                    "confidence": conf, "why": why, "llm": used, "duplicate_of": seen.get(key),
                    "needs_confirmation": action == "спросить_руководителя", "expected": m.get("expected_action"), "expected_category": m.get("category")})
        seen.setdefault(key, m["id"])
    return out


def evaluate(rows: list[dict]) -> dict:
    ex = [r for r in rows if r.get("expected")]
    if not ex: return {}
    ok = [r for r in ex if r["action"] == r["expected"]]
    leaked = [r["id"] for r in ex if r["expected_category"] in P.NEVER_AUTO and r["action"] != "спросить_руководителя"]
    return {"total": len(ex), "correct": len(ok), "accuracy": round(len(ok) / len(ex), 3), "protected_leaks": leaked,
            "mismatches": [{"id": r["id"], "subject": r["subject"], "got": r["action"], "expected": r["expected"]} for r in ex if r["action"] != r["expected"]]}
