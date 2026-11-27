from __future__ import annotations
import re, uuid, time
from datetime import date, datetime, timedelta
from . import profile as P, triage as T, calendar_ as C, memory as M, protocol as PR, channels as CH, llm as L
from .store import Tx, load, audit

WD = {"понедельник": 0, "вторник": 1, "сред": 2, "четверг": 3, "пятниц": 4}
TPL = {
    "approve": "Здравствуйте, {n}.\nРешение положительное. Следующий шаг: {step}. Срок: {due}.\n{sig}",
    "reject": "Здравствуйте, {n}.\nК сожалению, в текущем виде согласовать не можем. Причина: {step}. Готовы вернуться к вопросу после уточнений.\n{sig}",
    "clarify": "Здравствуйте, {n}.\nНужны уточнения: {step}. Пришлите, пожалуйста, до {due}.\n{sig}",
}
esc = CH.esc


def person_email(org, name: str) -> str:
    return next((f"{p['id']}@company.example" for p in org if p["name"] == name), "")


def tasks_all(pid: str, today: date, st: dict | None = None) -> list[dict]:
    st = st or load(pid); out = []
    for t in P.rd_csv(pid, "tasks.csv") + st["tasks_extra"]:
        due = t.get("due") or ""; done = t.get("status") in ("готово", "done", "выполнена")
        od = bool(due) and not done and due < today.isoformat()
        out.append({"id": t["id"], "task": t["task"], "owner": t.get("owner") or "", "due": due, "status": "просрочена" if od else ("в работе" if t.get("status") == "просрочена" else t.get("status", "")),
                    "source": t.get("source", ""), "overdue": od, "days_left": (date.fromisoformat(due) - today).days if due else None})
    return out


def cal_request_conflict(prof: dict, text: str):
    t = text.lower(); hits = [(m.start(), v) for k, v in WD.items() for m in re.finditer(k, t)]
    m = re.search(r"(\d{1,2}):(\d{2})", t)
    if not hits or not m: return None
    wd = max(hits)[1]; mins = int(m.group(1)) * 60 + int(m.group(2))   # целевой день — последний упомянутый («с понедельника на среду»)
    for b in prof["blocks"]:
        if wd in b["days"] and int(b["start"][:2]) * 60 + int(b["start"][3:]) <= mins < int(b["end"][:2]) * 60 + int(b["end"][3:]):
            return f"время попадает в защищённый блок «{b['title']}» ({b['start']}–{b['end']})"
    return None


def inbox(pid: str, today: date) -> dict:
    st = load(pid); prof = P.get(pid); rows = T.process(pid, llm=L.llm)
    for r in rows:
        r["downgrade"] = None
        if r["action"] == "авто":
            why = cal_request_conflict(prof, r["subject"] + " " + r["body"])
            if why: r["action"], r["needs_confirmation"], r["downgrade"] = "спросить_руководителя", True, why
        d = st["decisions"].get(r["id"]) or (st["decisions"].get(r["duplicate_of"]) if r["duplicate_of"] else None)
        r["state"] = d["status"] if d else ("ожидает" if r["needs_confirmation"] and not r["duplicate_of"] else "новое")
        r["draft"] = st["drafts"].get(r["id"])
    return {"rows": rows, "eval": T.evaluate(rows)}


def run_auto(pid: str, today: date) -> dict:
    rows = inbox(pid, today)["rows"]; org = P.org(pid); prof = P.get(pid); done = {"авто": 0, "делегировать": 0, "в_сводку": 0, "игнорировать": 0}
    with Tx(pid) as st:
        for r in rows:
            if r["id"] in st["decisions"] or r["needs_confirmation"] or r["duplicate_of"]: continue
            a = r["action"]; res = {"status": "выполнено", "action": a, "ts": time.strftime("%H:%M")}
            if a == "делегировать":
                to = person_email(org, r["delegate_to"]) or "assistant@company.example"
                res["result"] = CH.mail_send(pid, [to], "Fwd: " + r["subject"], f"Передано от имени {prof['name']} (ИИ-помощник).\nОтправитель: {r['from_name']}\n\n{r['body']}\n\nПросьба: взять в работу и сообщить итог руководителю.", prof["email"])
                res["note"] = f"передано: {r['delegate_to']}"
            elif a == "авто":
                res["result"] = CH.mail_send(pid, [r["from_email"]], "Re: " + r["subject"], "Подтверждаю. Автоматический ответ ИИ-помощника руководителя по правилам календаря.", prof["email"]); res["note"] = "ответ по правилам календаря"
            elif a == "в_сводку": res["note"] = "включено в сводку"
            else: res["note"] = "архив"
            st["decisions"][r["id"]] = res; done[a] += 1; audit(st, "avatar", "auto." + a, r["id"], {"subject": r["subject"]})
    return done


def make_draft(pid: str, email_id: str, decision: str, note: str, today: date) -> dict:
    if decision not in TPL: raise ValueError("decision: approve|reject|clarify")
    row = next(r for r in inbox(pid, today)["rows"] if r["id"] == email_id); prof = P.get(pid); st = load(pid)
    name = row["from_name"].split()[0] if row["sender_role"] in ("подчинённый", "коллега", "руководитель руководителя") else "коллеги"
    sig = prof["name"].split()[0] if row["sender_role"] == "подчинённый" else f"С уважением,\n{prof['name']}"
    txt = None
    if L.available():
        sn, fs = M.style_notes(st), M.few_shot(st, "email")
        sys_ = (f"Ты пишешь письмо от имени руководителя {prof['name']}. Стиль: {prof['style'] or 'коротко, по делу'}. Структура: решение, следующий шаг, срок. "
                "Не добавляй обязательств, которых нет в решении руководителя. Только текст письма." + (f"\nПравила:\n{sn}" if sn else "") + (f"\nПримеры правок:\n{fs}" if fs else ""))
        try: txt, _ = L.chat(sys_, f"Письмо:\nОт: {row['from_name']}\nТема: {row['subject']}\n{row['body']}\n\nРешение: {decision}. Комментарий: {note or '—'}. Сегодня {today.isoformat()}", max_tokens=500)
        except L.LLMError: txt = None
    if not txt: txt = TPL[decision].format(n=name, step=note or "уточним и вернёмся", due=(today + timedelta(days=3)).isoformat(), sig=sig)
    txt, used = M.apply_rules(st, txt)
    with Tx(pid) as st:
        st["drafts"][email_id] = {"id": email_id, "to": row["from_email"], "subject": "Re: " + row["subject"], "text": txt, "orig": txt, "decision": decision, "note": note, "rules_applied": used, "sent": False}
        st["decisions"][email_id] = {"status": "черновик", "action": decision, "ts": time.strftime("%H:%M")}
        audit(st, "leader", "decision." + decision, email_id)
        return st["drafts"][email_id]


def send_draft(pid: str, email_id: str, text: str) -> dict:
    prof = P.get(pid)
    with Tx(pid) as st:
        d = st["drafts"].get(email_id)
        if not d: raise ValueError("нет решения руководителя по этому письму — отправка запрещена")
        if d["sent"]: return {"ok": True, "already": True}
        learned = M.learn(st, "email", d["subject"], d["orig"], text); d["text"] = text
        res = CH.mail_send(pid, [d["to"]], d["subject"], text, prof["email"])
        if res.get("ok"): d["sent"] = True; st["decisions"][email_id] = {"status": "отправлено", "action": d["decision"], "ts": time.strftime("%H:%M"), "result": res}
        audit(st, "leader", "email.sent", email_id, {"mode": res.get("mode"), "learned": bool(learned)})
        return {"ok": res.get("ok"), "result": res, "learned": bool(learned)}


def briefing(pid: str, today: date) -> dict:
    prof = P.get(pid); st = load(pid); inb = inbox(pid, today)["rows"]
    evs = [e for e in C.events(pid, st["moved"]) if e["start"].date() == today]
    ask = [r for r in inb if r["needs_confirmation"] and not r["duplicate_of"] and r["state"] in ("ожидает", "новое")]
    over = [t for t in tasks_all(pid, today, st) if t["overdue"]]
    deleg = [r for r in inb if r["action"] == "делегировать" and not r["duplicate_of"]]
    dig = [r for r in inb if r["action"] == "в_сводку" and not r["duplicate_of"]]
    risk = [r for r in dig if re.search(r"риск|просроч|срыв|задерж", r["body"].lower())]
    props = [m for m in C.propose_moves(pid, st["moved"]) if today <= datetime.fromisoformat(m["event"]["start"]).date() <= today + timedelta(days=4)]
    mine = [e for e in evs if not e["avatar_ok"]]; av = [e for e in evs if e["avatar_ok"]]
    wd = ["понедельник", "вторник", "среда", "четверг", "пятница", "суббота", "воскресенье"][today.weekday()]
    h = [f"<b>Доброе утро, {esc(prof['name'].split()[0])}.</b> План на {today.strftime('%d.%m')} ({wd})", ""]
    h.append(f"<b>Где нужны вы ({len(mine)}):</b>" if mine else "<b>Лично вас сегодня нигде не ждут.</b>")
    h += [f"• {e['start']:%H:%M} {esc(e['title'])}" for e in mine]
    if av: h += ["", f"<b>Аватар возьмёт ({len(av)}):</b> " + "; ".join(f"{e['start']:%H:%M} {esc(e['title'])}" for e in av[:6])]
    h += ["", f"<b>Ждут вашего решения ({len(ask)}):</b>"] + [f"• [{r['category']}] {esc(r['from_name'])}: {esc(r['subject'])}" for r in ask[:8]]
    if len(ask) > 8: h.append(f"… и ещё {len(ask) - 8}")
    if over: h += ["", f"<b>Просрочено ({len(over)}):</b>"] + [f"• {esc(t['task'])} — {esc(t['owner'])}, срок {t['due']}" for t in over[:5]]
    if risk: h += ["", "<b>Риски из отчётов:</b>"] + [f"• {esc(r['subject'])}: {esc(r['body'][:100])}" for r in risk]
    if deleg: h += ["", f"<b>Передано без вас ({len(deleg)}):</b> " + "; ".join(f"{esc(r['subject'])} → {esc(r['delegate_to'])}" for r in deleg[:4])]
    if props: h += ["", f"<b>Конфликты с защищёнными блоками:</b> {len(props)} — предложены переносы"]
    return {"date": today.isoformat(), "weekday": wd, "meetings_leader": [C.ser(e) for e in mine], "meetings_avatar": [C.ser(e) for e in av], "decisions": ask, "overdue": over,
            "delegated": deleg, "digest": dig, "risks": risk, "protect_proposals": props, "freed": C.freed_hours(pid, today, inb, st["moved"]), "text_html": "\n".join(h)}


def prep_brief(pid: str, name: str, today: date) -> dict:
    mail = [r for r in inbox(pid, today)["rows"] if r["from_name"] == name and not r["duplicate_of"]]
    tk = [t for t in tasks_all(pid, today) if t["owner"] == name and t["status"] != "готово"]
    pts = [f"Просрочено: {t['task']} (срок {t['due']})" for t in tk if t["overdue"]] + [f"В работе: {t['task']} — до {t['due']}" for t in tk if not t["overdue"]][:4] + [f"Письмо: {r['subject']} → {r['action']}" for r in mail[:3]]
    d = {"name": name, "tasks": tk, "talking_points": pts}
    if L.available() and pts:
        try: d["summary"], _ = L.chat("Подготовь руководителю сводку перед встречей один на один: 4–6 коротких пунктов: что обсудить, что просрочено, что отметить.", "\n".join(pts), max_tokens=400)
        except L.LLMError: pass
    return d


def finalize_protocol(pid: str, proto_id: str, today: date, recipients: list[str]) -> dict:
    prof = P.get(pid)
    with Tx(pid) as st:
        p = st["protocols"][proto_id]
        if p["status"] == "sent": return {"ok": True, "already": True}
        if p["status"] != "approved": raise ValueError("протокол не утверждён руководителем — рассылка запрещена")
        res = CH.mail_send(pid, recipients, f"Протокол: {p['title']}", p["text"], prof["email"]); added = []
        for t in PR.tasks_from_text(p["text"]):
            row = {"id": "p" + uuid.uuid4().hex[:5], "task": t["text"], "owner": t["owner"] or "", "due": t["due"] or "", "status": "новая", "source": "протокол " + p["id"]}
            st["tasks_extra"].append(row); added.append(row)
            if t["due"]: CH.event_create(pid, "Срок: " + t["text"][:80], t["due"] + "T09:00:00", t["due"] + "T09:30:00", [prof["email"]] if prof["email"] else [])
        p["status"] = "sent"; p["sent"] = {"mail": res, "tasks": added, "ts": time.strftime("%Y-%m-%d %H:%M")}
        audit(st, "avatar", "protocol.sent", proto_id, {"recipients": recipients, "tasks": len(added)})
        return {"ok": True, "mail": res, "tasks": added}
