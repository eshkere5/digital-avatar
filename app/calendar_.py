from __future__ import annotations
import re
from datetime import datetime, date, timedelta
from . import profile as P

CAT_AVATAR = {"операционная"}
WORK = ("09:00", "18:00")
SENSITIVE = r"кандидат|интервью|договор|бюджет|увольн|оффер|отпуск|согласование кп|скидк"


def _t(s): return datetime.strptime(s, "%Y%m%dT%H%M%S")


def events(pid: str, moved: dict | None = None) -> list[dict]:
    f = P.pdir(pid) / "calendar.ics"
    if not f.exists(): return []
    txt = f.read_text(encoding="utf-8").replace("\r\n", "\n"); out = []
    for blk in re.findall(r"BEGIN:VEVENT(.*?)END:VEVENT", txt, re.S):
        g = lambda k: (re.search(rf"^{k}[^:\n]*:(.*)$", blk, re.M) or [None, ""])[1].strip()
        e = {"id": g("UID").split("@")[0], "start": _t(g("DTSTART")), "end": _t(g("DTEND")), "title": g("SUMMARY"), "category": g("CATEGORIES"),
             "attendees": re.findall(r"ATTENDEE;CN=([^:]*):", blk)}
        if moved and e["id"] in moved:
            e["start"] = datetime.fromisoformat(moved[e["id"]]["start"]); e["end"] = datetime.fromisoformat(moved[e["id"]]["end"]); e["moved"] = True
        e["avatar_ok"] = e["category"] in CAT_AVATAR and not re.search(SENSITIVE, e["title"].lower())
        out.append(e)
    return sorted(out, key=lambda e: e["start"])


def ser(e: dict) -> dict:
    return {**e, "start": e["start"].isoformat(), "end": e["end"].isoformat(), "minutes": int((e["end"] - e["start"]).total_seconds() // 60)}


def _hm(d: date, s: str) -> datetime:
    h, m = map(int, s.split(":")); return datetime(d.year, d.month, d.day, h, m)


def block_instances(blocks, d0: date, d1: date) -> list[dict]:
    out, d = [], d0
    while d <= d1:
        out += [{"title": b["title"], "start": _hm(d, b["start"]), "end": _hm(d, b["end"])} for b in blocks if d.weekday() in b["days"]]
        d += timedelta(days=1)
    return out


def conflicts(evs, blocks) -> list[dict]:
    if not evs: return []
    bl = block_instances(blocks, evs[0]["start"].date(), evs[-1]["end"].date())
    return [{"event": e, "block": b} for e in evs for b in bl if e["start"] < b["end"] and b["start"] < e["end"]]


def free_slot(evs, blocks, day: date, minutes: int, not_before: datetime | None = None):
    busy = [(e["start"], e["end"]) for e in evs if e["start"].date() == day] + [(b["start"], b["end"]) for b in block_instances(blocks, day, day)]
    cur = max(_hm(day, WORK[0]), not_before or _hm(day, WORK[0])); end = _hm(day, WORK[1])
    if cur.minute % 15: cur = cur.replace(minute=0) + timedelta(minutes=(cur.minute // 15 + 1) * 15)
    while cur + timedelta(minutes=minutes) <= end:
        s, e = cur, cur + timedelta(minutes=minutes)
        if not any(s < b1 and b0 < e for b0, b1 in busy): return s, e
        cur += timedelta(minutes=15)
    return None


def propose_moves(pid: str, moved: dict | None = None) -> list[dict]:
    prof = P.get(pid); evs = events(pid, moved); out = []
    for c in conflicts(evs, prof["blocks"]):
        e = c["event"]; mins = int((e["end"] - e["start"]).total_seconds() // 60); movable = e["category"] in CAT_AVATAR
        others = [x for x in evs if x["id"] != e["id"]]; slot = None
        if movable:
            for k in range(4):
                d = e["start"].date() + timedelta(days=k)
                if d.weekday() > 4: continue
                slot = free_slot(others, prof["blocks"], d, mins, e["end"] if k == 0 else None)
                if slot: break
        out.append({"event": ser(e), "block": c["block"]["title"], "movable": movable,
                    "proposal": {"start": slot[0].isoformat(), "end": slot[1].isoformat()} if slot else None,
                    "note": "внутренняя операционная встреча — можно перенести" if movable else f"категория «{e['category']}» — решает руководитель"})
    return out


def week_bounds(d: date): s = d - timedelta(days=d.weekday()); return s, s + timedelta(days=6)


def freed_hours(pid: str, d: date, rows: list[dict], moved=None, mins_email=3.0, mins_protocol=25.0, mins_review=5.0) -> dict:
    s, e = week_bounds(d); evs = [x for x in events(pid, moved) if s <= x["start"].date() <= e]; av = [x for x in evs if x["avatar_ok"]]
    meet_h = sum((x["end"] - x["start"]).total_seconds() for x in av) / 3600; proto_h = len(av) * (mins_protocol - mins_review) / 60
    uniq = [r for r in rows if not r["duplicate_of"]]; handled = [r for r in uniq if not r["needs_confirmation"]]; dups = sum(1 for r in rows if r["duplicate_of"])
    mail_h = (len(handled) * mins_email + dups * 1) / 60
    return {"week": [s.isoformat(), e.isoformat()], "meetings_total": len(evs), "meetings_avatar": len(av), "meetings_h": round(meet_h, 1), "protocol_h": round(proto_h, 1),
            "mail_h": round(mail_h, 1), "total_h": round(meet_h + proto_h + mail_h, 1), "conservative_h": round(meet_h + mail_h, 1),
            "emails_total": len(rows), "emails_unique": len(uniq), "emails_no_leader": len(handled) + dups,
            "share_no_leader": round((len(handled) + dups) / max(1, len(rows)), 3), "share_no_leader_unique": round(len(handled) / max(1, len(uniq)), 3),
            "assumptions": f"встречи «операционная» без кадров/денег/договоров, 100% длительности; {mins_protocol:.0f} мин на протокол минус {mins_review:.0f} мин на проверку; {mins_email:.0f} мин на письмо без руководителя (дубль — 1 мин). Консервативно = встречи + почта."}
