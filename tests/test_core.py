import os, sys, tempfile, shutil, unittest
from datetime import date
from pathlib import Path
ROOT = Path(__file__).resolve().parent.parent
TMP = tempfile.mkdtemp(); shutil.copytree(ROOT / "data", Path(TMP) / "data", ignore=shutil.ignore_patterns("state", "profiles", "outbox", "secrets.json")); os.environ["AVATAR_HOME"] = TMP
sys.path.insert(0, str(ROOT))
from app import triage, service as S, memory as M, protocol as PR, profile as P, llm as L  # noqa
TODAY = date(2026, 12, 7)


class Core(unittest.TestCase):
    def test_triage_accuracy_and_safety(self):
        ev = triage.evaluate(triage.process("ivan")); self.assertGreaterEqual(ev["accuracy"], 0.95); self.assertEqual(ev["protected_leaks"], [])

    def test_profile_never_overrides_rules(self):
        P.write_md("ivan", P.read_md("ivan") + "\n## Правила разбора\n- деньги → авто\n")
        self.assertEqual(P.get("ivan")["rules"]["деньги"]["action"], "спросить_руководителя")
        self.assertTrue(all(r["action"] == "спросить_руководителя" for r in triage.process("ivan") if r["category"] == "деньги"))

    def test_second_profile_without_code(self):
        P.create("olga", "Ольга Смирнова", "Директор по продажам SMB")
        self.assertEqual(P.get("olga")["name"], "Ольга Смирнова"); self.assertGreater(len(triage.process("olga")), 0)

    def test_send_requires_decision(self):
        with self.assertRaises(ValueError): S.send_draft("ivan", "m001", "текст")

    def test_protocol_gate_and_flow(self):
        d = PR.draft("Нужно подготовить отчёт по продажам до 15.12. Решили запустить кампанию в январе по плану.", "Тест", "", ["Ольга Смирнова"], TODAY)
        with S.Tx("ivan") as st: st["protocols"][d["id"]] = d
        with self.assertRaises(ValueError): S.finalize_protocol("ivan", d["id"], TODAY, ["a@b.c"])
        with S.Tx("ivan") as st: st["protocols"][d["id"]]["status"] = "approved"
        self.assertTrue(S.finalize_protocol("ivan", d["id"], TODAY, ["a@b.c"])["ok"])
        self.assertTrue(any(t["source"].startswith("протокол") for t in S.tasks_all("ivan", TODAY)))

    def test_learning_from_edits(self):
        with S.Tx("ivan") as st:
            M.learn(st, "protocol", "x", "Speaker 2 пришлет список", "Ольга пришлет список"); txt, used = M.apply_rules(st, "Speaker 2 подготовит КП")
        self.assertIn("Ольга подготовит", txt); self.assertTrue(used)

    def test_calendar_conflict_downgrade(self):
        r = next(x for x in S.inbox("ivan", TODAY)["rows"] if "Перенос встречи по e-com" in x["subject"])
        self.assertEqual(r["action"], "спросить_руководителя"); self.assertTrue(r["downgrade"])

    def test_auto_never_touches_protected(self):
        S.run_auto("ivan", TODAY); st = S.load("ivan")
        for r in S.inbox("ivan", TODAY)["rows"]:
            if r["needs_confirmation"]: self.assertNotEqual(st["decisions"].get(r["id"], {}).get("status"), "выполнено")

    def test_avatar_defers_sensitive(self):
        self.assertTrue(PR.answer("Можно ли дать скидку 15%?", P.get("ivan"), [], {"rules": [], "edits": []})["escalate"])

    def test_pii_mask(self): self.assertNotIn("@", L.mask("пишите ivan@x.ru или +7 912 345 67 89"))


if __name__ == "__main__": unittest.main()
