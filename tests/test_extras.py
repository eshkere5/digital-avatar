import os, sys, tempfile, shutil, unittest
from pathlib import Path
ROOT = Path(__file__).resolve().parent.parent
if "AVATAR_HOME" not in os.environ:
    TMP = tempfile.mkdtemp(); shutil.copytree(ROOT / "data", Path(TMP) / "data", ignore=shutil.ignore_patterns("state", "profiles", "outbox", "secrets.json")); os.environ["AVATAR_HOME"] = TMP
sys.path.insert(0, str(ROOT))
from app import extras as X, llm as L, profile as P  # noqa


class Extras(unittest.TestCase):
    def setUp(self):
        X.patch_settings(); self.md = P.read_md("ivan")
        for k in ("TELEGRAM_BOT_TOKEN", "AVATAR_ADMIN_KEY", "AVATAR_LLM_PROVIDER", "AVATAR_LLM_MODEL", "DEEPSEEK_API_KEY"): os.environ.pop(k, None)

    def tearDown(self):
        P.write_md("ivan", self.md)
        for k in ("TELEGRAM_BOT_TOKEN", "AVATAR_ADMIN_KEY", "AVATAR_LLM_PROVIDER", "AVATAR_LLM_MODEL", "DEEPSEEK_API_KEY"): os.environ.pop(k, None)

    def test_telegram_token_from_env(self):
        self.assertFalse(L.public_settings()["telegram_set"])
        os.environ["TELEGRAM_BOT_TOKEN"] = "123456:ABCDEFGHIJKLMNOPQRSTUVWXYZ012345"
        self.assertTrue(L.public_settings()["telegram_set"]); self.assertEqual(L.settings()["telegram_token"], os.environ["TELEGRAM_BOT_TOKEN"])

    def test_env_never_leaks_into_error_text(self):
        os.environ["TELEGRAM_BOT_TOKEN"] = "123456:ABCDEFGHIJKLMNOPQRSTUVWXYZ012345"
        self.assertNotIn("ABCDEFGHIJ", X.clean("ошибка https://api.telegram.org/bot123456:ABCDEFGHIJKLMNOPQRSTUVWXYZ012345/getMe"))

    def test_llm_from_env(self):
        os.environ.update({"DEEPSEEK_API_KEY": "sk-test", "AVATAR_LLM_PROVIDER": "deepseek", "AVATAR_LLM_MODEL": "deepseek-chat"})
        p = L.settings()["providers"]["deepseek"]; self.assertTrue(p["enabled"]); self.assertEqual(p["model"], "deepseek-chat"); self.assertTrue(L.available())

    def test_link_chat_updates_profile(self):
        self.assertEqual(X.link_chat("ivan", "123456789")["chat_id"], "123456789"); self.assertEqual(X.link_chat("ivan", "-1001234567")["chat_id"], "-1001234567")
        for bad in ("abc", "12", "1; drop"):
            with self.assertRaises(ValueError): X.link_chat("ivan", bad)

    def test_admin_guard_rules(self):
        self.assertFalse(X.guarded("PUT", "/api/settings"))
        os.environ["AVATAR_ADMIN_KEY"] = "secret"
        self.assertTrue(X.guarded("PUT", "/api/settings")); self.assertFalse(X.guarded("GET", "/api/settings"))
        self.assertTrue(X.guarded("GET", "/api/telegram/status")); self.assertTrue(X.guarded("POST", "/api/ivan/telegram/link")); self.assertFalse(X.guarded("POST", "/api/ivan/meeting/say"))
        self.assertTrue(X.key_ok("secret")); self.assertFalse(X.key_ok("")); self.assertFalse(X.key_ok("Secret"))


if __name__ == "__main__": unittest.main()
