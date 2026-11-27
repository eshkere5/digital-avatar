"""Каналы: Telegram (утверждения) и Outlook (MS Graph или заглушка .eml/.ics — допустима по ТЗ)."""
from __future__ import annotations
import re, time, threading, uuid
from email.message import EmailMessage
from email.utils import formatdate
import httpx
from . import llm as L
from .store import DATA

OUTBOX = DATA / "outbox"


def esc(s) -> str: return str(s).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def tg_send(chat_id: str, text: str, buttons=None) -> dict:
    tok = L.settings()["telegram_token"]
    if not tok or not chat_id: return {"ok": False, "stub": True, "reason": "Telegram не настроен (токен бота — в «Подключениях», chat_id — в профиле)"}
    body = {"chat_id": chat_id, "text": text[:4000], "parse_mode": "HTML", "disable_web_page_preview": True}
    if buttons: body["reply_markup"] = {"inline_keyboard": [[{"text": t, "callback_data": d} for t, d in row] for row in buttons]}
    try:
        r = httpx.post(f"https://api.telegram.org/bot{tok}/sendMessage", json=body, timeout=20)
        return {"ok": r.status_code == 200, "reason": "" if r.status_code == 200 else r.text[:200]}
    except Exception as e: return {"ok": False, "reason": str(e)[:200]}


class TgPoller(threading.Thread):
    """Кнопки «Утвердить/Отклонить» и команда /plan. handler(chat_id, data, is_callback) -> текст ответа"""
    def __init__(self, handler): super().__init__(daemon=True); self.handler = handler; self.offset = 0
    def run(self):
        while True:
            tok = L.settings()["telegram_token"]
            if not tok: time.sleep(5); continue
            try:
                r = httpx.get(f"https://api.telegram.org/bot{tok}/getUpdates", params={"timeout": 25, "offset": self.offset}, timeout=35).json()
                for u in r.get("result", []):
                    self.offset = u["update_id"] + 1
                    if "callback_query" in u:
                        cq = u["callback_query"]; rep = self.handler(str(cq["message"]["chat"]["id"]), cq["data"], True)
                        httpx.post(f"https://api.telegram.org/bot{tok}/answerCallbackQuery", json={"callback_query_id": cq["id"], "text": (rep or "ок")[:150]}, timeout=10)
                    elif u.get("message", {}).get("text"):
                        chat = str(u["message"]["chat"]["id"]); rep = self.handler(chat, u["message"]["text"], False)
                        if rep: tg_send(chat, rep)
            except Exception: time.sleep(5)


def mail_send(pid: str, to: list[str], subject: str, body: str, sender: str, cc=None) -> dict:
    tok = L.settings()["graph_token"]
    if tok:
        p = {"message": {"subject": subject, "body": {"contentType": "Text", "content": body}, "toRecipients": [{"emailAddress": {"address": a}} for a in to]}, "saveToSentItems": True}
        try:
            r = httpx.post("https://graph.microsoft.com/v1.0/me/sendMail", json=p, headers={"Authorization": f"Bearer {tok}"}, timeout=30)
            return {"mode": "graph", "ok": r.status_code in (200, 202), "error": "" if r.status_code in (200, 202) else r.text[:200]}
        except Exception as e: return {"mode": "graph", "ok": False, "error": str(e)[:200]}
    d = OUTBOX / pid; d.mkdir(parents=True, exist_ok=True)
    m = EmailMessage(); m["From"] = sender or "assistant@company.example"; m["To"] = ", ".join(to); m["Subject"] = subject; m["Date"] = formatdate(localtime=True); m.set_content(body)
    fn = d / f"{time.strftime('%Y%m%d-%H%M%S')}-{uuid.uuid4().hex[:4]}.eml"; fn.write_bytes(bytes(m))
    return {"mode": "stub", "ok": True, "file": f"data/outbox/{pid}/{fn.name}"}


def event_create(pid: str, title: str, start: str, end: str, attendees: list[str]) -> dict:
    tok = L.settings()["graph_token"]
    if tok:
        p = {"subject": title, "start": {"dateTime": start, "timeZone": "Europe/Moscow"}, "end": {"dateTime": end, "timeZone": "Europe/Moscow"}, "attendees": [{"emailAddress": {"address": a}, "type": "required"} for a in attendees]}
        try:
            r = httpx.post("https://graph.microsoft.com/v1.0/me/events", json=p, headers={"Authorization": f"Bearer {tok}"}, timeout=30)
            return {"mode": "graph", "ok": r.status_code in (200, 201)}
        except Exception as e: return {"mode": "graph", "ok": False, "error": str(e)[:200]}
    d = OUTBOX / pid; d.mkdir(parents=True, exist_ok=True); f = lambda s: re.sub(r"[-:]", "", s)[:15]
    fn = d / f"{time.strftime('%Y%m%d-%H%M%S')}-{uuid.uuid4().hex[:4]}.ics"
    fn.write_text(f"BEGIN:VCALENDAR\nVERSION:2.0\nBEGIN:VEVENT\nUID:{uuid.uuid4().hex}@avatar\nDTSTART:{f(start)}\nDTEND:{f(end)}\nSUMMARY:{title}\nEND:VEVENT\nEND:VCALENDAR\n", encoding="utf-8")
    return {"mode": "stub", "ok": True, "file": f"data/outbox/{pid}/{fn.name}"}
