from __future__ import annotations
import base64, time, uuid
from contextlib import asynccontextmanager
from datetime import date, datetime
from pathlib import Path
from typing import Literal
from fastapi import FastAPI, HTTPException, Request, Query
from fastapi.responses import FileResponse, JSONResponse, PlainTextResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field
from . import profile as P, service as S, calendar_ as C, memory as M, protocol as PR, channels as CH, llm as L, triage as T
from .store import Tx, load, audit, DATA

WEB = Path(__file__).parent / "web"
DEMO_TODAY = "2026-12-07"
OLGA = """# Профиль руководителя
Имя: Ольга Смирнова
Должность: Директор по продажам SMB
Email: p02@company.example
Telegram chat_id:
Утренний план: 08:45

## Цели на квартал
1. Довести конверсию КП в сделку до 28%.
2. Закрыть 2 ключевых сделки с «ТехноСтрой» и «Ромашка-Ритейл».
3. Нанять аккаунт-менеджера до конца января.

## Никогда без подтверждения руководителя
- деньги и бюджеты (скидки)
- кадры
- обязательства клиентам
- письма руководству

## Правила разбора
- продажи → спросить_руководителя
- клиенты → спросить_руководителя
- доступы → делегировать → Ассистент
- статус → в_сводку

## Защищённые блоки
- Работа с ключевыми клиентами | пн, вт | 14:00-16:00
- Один на один | пт | 10:00-12:00

## Стиль общения
Тепло, но конкретно: решение, ответственный, срок. Обращение на «вы».
"""


class DecisionIn(BaseModel): decision: Literal["approve", "reject", "clarify"]; note: str = Field("", max_length=1000)
class SendIn(BaseModel): text: str = Field(min_length=1, max_length=6000)
class ProfileIn(BaseModel): markdown: str = Field(min_length=10, max_length=20000)
class NewProfile(BaseModel): id: str; name: str; position: str = "Руководитель направления"; base: str = "ivan"
class DraftIn(BaseModel): title: str = Field(max_length=200); transcript: str = Field(min_length=10, max_length=400000); previous: str = ""; library_prev: str = ""; library_transcript: str = ""
class ProtoEdit(BaseModel): text: str = Field(min_length=1, max_length=20000)
class RejectIn(BaseModel): reason: str = ""
class SayIn(BaseModel): text: str = Field(min_length=1, max_length=1000)
class MoveIn(BaseModel): event_id: str; start: str; end: str
class SettingsIn(BaseModel): providers: dict = {}; telegram_token: str = ""; graph_token: str = ""; clear_telegram_token: bool = False; clear_graph_token: bool = False; mask_pii: bool | None = None; allow_cloud: bool | None = None
class PhotoIn(BaseModel): data_url: str
class RuleToggle(BaseModel): on: bool


def D(s: str) -> date:
    try: return date.fromisoformat(s)
    except ValueError: raise HTTPException(400, "дата YYYY-MM-DD")


def create_app() -> FastAPI:
    def tg_handler(chat: str, data: str, cb: bool):
        for pr in P.list_profiles():
            prof = P.get(pr["id"])
            if prof["chat_id"] and prof["chat_id"] == chat:
                today = date.fromisoformat(DEMO_TODAY)
                if not cb: return S.briefing(pr["id"], today)["text_html"] if data.startswith("/plan") else "Команды: /plan"
                kind, _, pid_ = data.partition(":")
                try:
                    if kind == "ok": _approve(pr["id"], pid_, today); return "Утверждено, рассылаю"
                    if kind == "no": _reject(pr["id"], pid_, "из Telegram"); return "Отклонено"
                except Exception as e: return str(e)[:100]
        return "Чат не привязан к профилю"

    @asynccontextmanager
    async def lifespan(app):
        if not (P.PROFILES / "olga").exists():
            P.create("olga", "Ольга Смирнова", "Директор по продажам SMB"); P.write_md("olga", OLGA)
        P.list_profiles(); CH.TgPoller(tg_handler).start(); yield

    app = FastAPI(title="Digital Avatar", version="1.0", lifespan=lifespan)

    @app.middleware("http")
    async def guard(req: Request, nxt):
        host = (req.headers.get("host") or "").split(":")[0]
        if host not in ("127.0.0.1", "localhost", "testserver") and not host.endswith(".onrender.com"): return PlainTextResponse("forbidden", 403)
        r = await nxt(req); r.headers["Cache-Control"] = "no-store"; return r

    def prof_or_404(pid):
        try: return P.get(pid)
        except KeyError: raise HTTPException(404, "нет такого профиля")

    @app.get("/api/profiles")
    def profiles(): return {"profiles": P.list_profiles(), "demo_today": DEMO_TODAY}

    @app.post("/api/profiles")
    def new_profile(b: NewProfile):
        try: P.create(b.id, b.name, b.position, b.base)
        except (ValueError, KeyError) as e: raise HTTPException(400, str(e))
        return {"ok": True}

    @app.get("/api/{pid}/profile")
    def get_profile(pid: str): return {"markdown": P.read_md(pid), "parsed": prof_or_404(pid), "org": P.org(pid)}

    @app.put("/api/{pid}/profile")
    def put_profile(pid: str, b: ProfileIn):
        prof_or_404(pid); P.write_md(pid, b.markdown)
        with Tx(pid) as st: audit(st, "leader", "profile.updated")
        return {"parsed": P.get(pid)}

    @app.get("/api/{pid}/briefing")
    def briefing(pid: str, today: str = DEMO_TODAY): prof_or_404(pid); return S.briefing(pid, D(today))

    @app.post("/api/{pid}/briefing/send")
    def briefing_send(pid: str, today: str = DEMO_TODAY):
        prof = prof_or_404(pid); b = S.briefing(pid, D(today)); r = CH.tg_send(prof["chat_id"], b["text_html"])
        with Tx(pid) as st: st["briefings"].append({"ts": time.strftime("%Y-%m-%d %H:%M"), "ok": r["ok"]}); audit(st, "avatar", "briefing.telegram", today, r)
        return {"telegram": r, "text": b["text_html"]}

    @app.get("/api/{pid}/inbox")
    def inbox(pid: str, today: str = DEMO_TODAY): prof_or_404(pid); return S.inbox(pid, D(today))

    @app.post("/api/{pid}/inbox/run-auto")
    def run_auto(pid: str, today: str = DEMO_TODAY): prof_or_404(pid); return S.run_auto(pid, D(today))

    @app.post("/api/{pid}/emails/{eid}/decision")
    def decision(pid: str, eid: str, b: DecisionIn, today: str = DEMO_TODAY):
        prof_or_404(pid)
        try: return S.make_draft(pid, eid, b.decision, b.note, D(today))
        except StopIteration: raise HTTPException(404, "письмо не найдено")

    @app.post("/api/{pid}/emails/{eid}/send")
    def send(pid: str, eid: str, b: SendIn):
        prof_or_404(pid)
        try: return S.send_draft(pid, eid, b.text)
        except ValueError as e: raise HTTPException(409, str(e))

    @app.get("/api/{pid}/calendar")
    def calendar(pid: str, today: str = DEMO_TODAY):
        prof = prof_or_404(pid); st = load(pid); d = D(today); s, e = C.week_bounds(d)
        evs = [C.ser(x) for x in C.events(pid, st["moved"]) if s <= x["start"].date() <= e + (e - s) + C.timedelta(days=1)]
        bl = [{"title": b["title"], "start": b["start"].isoformat(), "end": b["end"].isoformat()} for b in C.block_instances(prof["blocks"], s, e + (e - s) + C.timedelta(days=1))]
        return {"events": evs, "blocks": bl, "proposals": C.propose_moves(pid, st["moved"]), "freed": C.freed_hours(pid, d, S.inbox(pid, d)["rows"], st["moved"])}

    @app.post("/api/{pid}/calendar/move")
    def move(pid: str, b: MoveIn):
        prof_or_404(pid)
        with Tx(pid) as st:
            st["moved"][b.event_id] = {"start": b.start, "end": b.end}; audit(st, "leader", "calendar.move", b.event_id, {"to": b.start})
        CH.event_create(pid, "Перенос: " + b.event_id, b.start, b.end, []); return {"ok": True}

    @app.get("/api/{pid}/tasks")
    def tasks(pid: str, today: str = DEMO_TODAY): prof_or_404(pid); return {"tasks": S.tasks_all(pid, D(today))}

    @app.get("/api/{pid}/prep")
    def prep(pid: str, name: str, today: str = DEMO_TODAY): prof_or_404(pid); return S.prep_brief(pid, name, D(today))

    @app.get("/api/library")
    def library(): return {"items": PR.list_library()}

    @app.post("/api/{pid}/protocols/draft")
    def proto_draft(pid: str, b: DraftIn, today: str = DEMO_TODAY):
        prof_or_404(pid); st = load(pid)
        tr = PR.read_lib(b.library_transcript, "transcript") if b.library_transcript else b.transcript
        prev = PR.read_lib(b.library_prev, "summary") if b.library_prev else b.previous
        p = PR.draft(tr, b.title, prev, [o["name"] for o in P.org(pid)], D(today), P.get(pid)["style"], st)
        with Tx(pid) as st2: st2["protocols"][p["id"]] = p; audit(st2, "avatar", "protocol.draft", p["id"], {"engine": p["data"].get("engine")})
        prof = P.get(pid); CH.tg_send(prof["chat_id"], f"<b>Протокол на утверждение:</b> {CH.esc(p['title'])}\nЗадач: {len(PR.tasks_from_text(p['text']))}", [[("Утвердить", f"ok:{p['id']}"), ("Отклонить", f"no:{p['id']}")]])
        return p

    @app.get("/api/{pid}/protocols")
    def protos(pid: str): prof_or_404(pid); return {"items": sorted(load(pid)["protocols"].values(), key=lambda p: p["created"], reverse=True)}

    def _approve(pid, proto_id, today, text=None):
        with Tx(pid) as st:
            p = st["protocols"].get(proto_id)
            if not p: raise ValueError("нет протокола")
            if text is not None and text != p["text"]:
                M.learn(st, "protocol", p["title"], p["text"], text); p["text"] = text
            if p["status"] == "draft": p["status"] = "approved"; audit(st, "leader", "protocol.approved", proto_id)
        org = P.org(pid); rec = [f"{o['id']}@company.example" for o in org if o["role_for_leader"] in ("подчинённый",)]
        return S.finalize_protocol(pid, proto_id, today, rec)

    def _reject(pid, proto_id, reason):
        with Tx(pid) as st:
            p = st["protocols"][proto_id]
            if p["status"] == "draft": p["status"] = "rejected"; p["reason"] = reason; audit(st, "leader", "protocol.rejected", proto_id)

    @app.post("/api/{pid}/protocols/{proto_id}/approve")
    def approve(pid: str, proto_id: str, b: ProtoEdit, today: str = DEMO_TODAY):
        prof_or_404(pid)
        try: return _approve(pid, proto_id, D(today), b.text)
        except (ValueError, KeyError) as e: raise HTTPException(409, str(e))

    @app.post("/api/{pid}/protocols/{proto_id}/reject")
    def reject(pid: str, proto_id: str, b: RejectIn): prof_or_404(pid); _reject(pid, proto_id, b.reason); return {"ok": True}

    @app.get("/api/transcript")
    def transcript(name: str):
        try: u = PR.parse_transcript(PR.read_lib(name, "transcript"))
        except ValueError: raise HTTPException(400, "bad name")
        return {"lines": [x["text"] for x in u]}

    @app.get("/api/{pid}/meeting/script")
    def meeting_script(pid: str, prev: str = "", platform: str = "browser"):
        prof = prof_or_404(pid); qs = PR.questions_from_previous(PR.read_lib(prev, "summary")) if prev else []
        return {"intro": f"Здравствуйте! Я ИИ-помощник руководителя, {prof['name']}. Присутствую вместо него, веду запись и подготовлю протокол на его утверждение. Решения по деньгам, кадрам и обязательствам клиентам принимает только руководитель.",
                "questions": qs, "outro": "Спасибо. Протокол подготовлю и отправлю руководителю на утверждение. После утверждения разошлю участникам и поставлю задачи."}

    @app.post("/api/{pid}/meeting/say")
    def meeting_say(pid: str, b: SayIn, today: str = DEMO_TODAY):
        prof = prof_or_404(pid); st = load(pid); a = PR.answer(b.text, prof, S.tasks_all(pid, D(today), st), st)
        with Tx(pid) as st2:
            if a["escalate"]: st2["escalations"].append({"ts": time.strftime("%H:%M"), "q": b.text})
            audit(st2, "avatar", "meeting.answer", "", {"escalate": a["escalate"], "src": a["source"]})
        return a

    @app.get("/api/{pid}/escalations")
    def esc_(pid: str): prof_or_404(pid); return {"items": load(pid)["escalations"]}

    @app.get("/api/{pid}/memory")
    def memory(pid: str): prof_or_404(pid); st = load(pid); return {"rules": st["rules"], "edits": st["edits"][-20:][::-1]}

    @app.post("/api/{pid}/memory/{rid}")
    def toggle(pid: str, rid: str, b: RuleToggle):
        prof_or_404(pid)
        with Tx(pid) as st:
            for r in st["rules"]:
                if r["id"] == rid: r["on"] = b.on
        return {"ok": True}

    @app.delete("/api/{pid}/memory/{rid}")
    def del_rule(pid: str, rid: str):
        prof_or_404(pid)
        with Tx(pid) as st: st["rules"] = [r for r in st["rules"] if r["id"] != rid]
        return {"ok": True}

    @app.post("/api/{pid}/memory/distill")
    def distill(pid: str):
        prof_or_404(pid)
        with Tx(pid) as st: return {"added": M.distill(st), "llm": L.available()}

    @app.get("/api/{pid}/audit")
    def audit_(pid: str): prof_or_404(pid); return {"items": load(pid)["audit"][-100:][::-1]}

    @app.get("/api/{pid}/metrics")
    def metrics(pid: str, today: str = DEMO_TODAY):
        prof_or_404(pid); d = D(today); st = load(pid); inbx = S.inbox(pid, d); fr = C.freed_hours(pid, d, inbx["rows"], st["moved"]); tks = S.tasks_all(pid, d, st)
        sent = [p for p in st["protocols"].values() if p["status"] == "sent"]
        return {"freed": fr, "eval": inbx["eval"], "learned_rules": len([r for r in st["rules"] if r.get("on", True)]), "edits": len(st["edits"]),
                "protocols": {"total": len(st["protocols"]), "sent": len(sent)}, "tasks": {"total": len(tks), "overdue": sum(t["overdue"] for t in tks)}, "escalations": len(st["escalations"])}

    @app.get("/api/settings")
    def get_settings(): return L.public_settings()

    @app.put("/api/settings")
    def put_settings(b: SettingsIn):
        patch = b.model_dump(exclude_none=True); L.save_settings(patch); return L.public_settings()

    @app.get("/api/settings/{prov}/models")
    def models(prov: str):
        if prov not in L.PRESETS: raise HTTPException(404)
        try: return {"models": L.list_models(prov)}
        except Exception as e: raise HTTPException(502, str(e)[:200])

    @app.post("/api/settings/{prov}/test")
    def test(prov: str):
        if prov not in L.PRESETS: raise HTTPException(404)
        return L.probe(prov)

    @app.get("/api/status")
    def status(): return {"llm": L.available(), "telegram": L.public_settings()["telegram_set"], "outlook": "graph" if L.public_settings()["graph_set"] else "stub"}

    @app.put("/api/{pid}/avatar-photo")
    def photo(pid: str, b: PhotoIn):
        prof_or_404(pid)
        if not b.data_url.startswith("data:image/") or len(b.data_url) > 4_000_000: raise HTTPException(400, "нужно изображение до 3 МБ")
        (DATA / "state" / f"{pid}.photo").write_text(b.data_url); return {"ok": True}

    @app.get("/api/{pid}/avatar-photo")
    def get_photo(pid: str):
        prof_or_404(pid); f = DATA / "state" / f"{pid}.photo"
        return {"data_url": f.read_text() if f.exists() else ""}

    @app.get("/")
    def index(): return FileResponse(WEB / "index.html")

    app.mount("/static", StaticFiles(directory=WEB), name="static")
    return app


app = create_app()
