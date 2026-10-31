"""Offline integration tests; no provider calls or Codex installation needed."""
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import threading
import unittest
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
CLI = ROOT / "plugins/shunt/scripts/shunt.py"
HOOK = ROOT / "plugins/shunt/hooks/check-read.py"
spec = importlib.util.spec_from_file_location("shunt_hook", HOOK)
HOOK_MODULE = importlib.util.module_from_spec(spec)
spec.loader.exec_module(HOOK_MODULE)


class FakeHandler(BaseHTTPRequestHandler):
    requests = []
    answer = "output"
    status = 200
    redirect = None

    def do_POST(self):
        body = self.rfile.read(int(self.headers["Content-Length"]))
        self.__class__.requests.append((self.path, json.loads(body), self.headers.get("Authorization")))
        if self.__class__.redirect:
            self.send_response(307)
            self.send_header("Location", self.__class__.redirect)
            self.end_headers()
            return
        data = json.dumps({"choices": [{"message": {"content": self.__class__.answer}}]}).encode()
        self.send_response(self.__class__.status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def log_message(self, *args):
        pass


class ShuntTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.server = ThreadingHTTPServer(("127.0.0.1", 0), FakeHandler)
        cls.thread = threading.Thread(target=cls.server.serve_forever, daemon=True)
        cls.thread.start()

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()
        cls.server.server_close()
        cls.thread.join()

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.cwd = Path(self.tmp.name)
        self.src = self.cwd / "source.py"
        self.src.write_text("def hello():\n    return 3\n", encoding="utf-8")
        FakeHandler.requests = []
        FakeHandler.answer = "output"
        FakeHandler.status = 200
        FakeHandler.redirect = None
        self.env = {k: v for k, v in os.environ.items() if not k.startswith("SHUNT_")}
        self.env["HOME"] = str(self.cwd)
        self.write_config({"api_base": f"http://127.0.0.1:{self.server.server_port}/v1",
                           "model": "cheap-mock", "api_key": "test-only-key"})

    def write_config(self, values, mode=0o600):
        path = self.cwd / ".config/codex-shunt/config.json"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(values), encoding="utf-8")
        path.chmod(mode)
        return path

    def update_config(self, **values):
        path = self.cwd / ".config/codex-shunt/config.json"
        data = json.loads(path.read_text())
        data.update(values)
        return self.write_config(data)

    def run_cli(self, *args, env=None):
        return subprocess.run([sys.executable, str(CLI), *map(str, args)], cwd=self.cwd,
                              env=env or self.env, text=True, capture_output=True)

    def hook(self, command, **extra):
        payload = {"hook_event_name": "PreToolUse", "tool_input": {"command": command},
                   "cwd": str(self.cwd), **extra}
        settings = HOOK_MODULE.setting.__globals__
        with patch.dict(settings, CONFIG_PATH=self.cwd / ".config/codex-shunt/config.json"):
            settings["load_config"].cache_clear()
            try:
                return HOOK_MODULE.decision(payload)
            finally:
                settings["load_config"].cache_clear()

    def test_user_config_works_without_exports_for_both_commands(self):
        self.write_config({"api_base": f"http://127.0.0.1:{self.server.server_port}/v1",
                           "model": "configured-cheap", "api_key": "config-test-key",
                           "context_tokens": 3000, "reply_tokens": 500})
        env = self.env
        p = self.run_cli("bulk-read", "--question", "Describe", "--paths", self.src, env=env)
        self.assertEqual(p.returncode, 0, p.stderr)
        self.assertEqual(FakeHandler.requests[0][1]["model"], "configured-cheap")
        self.assertEqual(FakeHandler.requests[0][2], "Bearer config-test-key")
        target = self.cwd / "generated.py"
        p = self.run_cli("code-write", "--spec", "Make test", "--reference", self.src,
                         "--target", target, env=env)
        self.assertEqual(p.returncode, 0, p.stderr)
        self.assertTrue(target.exists())

    def test_environment_variables_do_not_override_config(self):
        self.update_config(model="config-model", api_key="config-key")
        env = dict(self.env, SHUNT_MODEL="env-model", SHUNT_API_KEY="override-key",
                   SHUNT_API_BASE="http://invalid.example/v1", SHUNT_MAX_PAYLOAD_BYTES="16")
        p = self.run_cli("bulk-read", "--question", "hi", "--paths", self.src, env=env)
        self.assertEqual(p.returncode, 0, p.stderr)
        self.assertEqual(FakeHandler.requests[0][1]["model"], "config-model")
        self.assertEqual(FakeHandler.requests[0][2], "Bearer config-key")

    def test_missing_config_fails_instead_of_using_environment(self):
        (self.cwd / ".config/codex-shunt/config.json").unlink()
        env = dict(self.env, SHUNT_API_BASE=f"http://127.0.0.1:{self.server.server_port}/v1",
                   SHUNT_MODEL="cheap-mock", SHUNT_API_KEY="key")
        p = self.run_cli("bulk-read", "--question", "hi", "--paths", self.src, env=env)
        self.assertIn("config not found", p.stderr)
        self.assertFalse(FakeHandler.requests)

    def test_missing_config_does_not_block_hook(self):
        (self.cwd / ".config/codex-shunt/config.json").unlink()
        big = self.cwd / "big.py"
        big.write_text("x\n" * 500)
        event = {"tool_input": {"command": "cat big.py"}, "cwd": str(self.cwd)}
        p = subprocess.run([sys.executable, str(HOOK)], input=json.dumps(event),
                           text=True, capture_output=True, env=self.env)
        self.assertEqual(p.returncode, 0, p.stderr)
        self.assertEqual(json.loads(p.stdout), {})

    def test_config_rejects_insecure_permissions_and_malformed_json(self):
        config = self.write_config({"model": "example"}, mode=0o644)
        p = self.run_cli("bulk-read", "--question", "hi", "--paths", self.src,
                         env=self.env)
        if os.name != "nt":
            self.assertIn("chmod 600", p.stderr)
            self.assertFalse(FakeHandler.requests)
        config.chmod(0o600)
        config.write_text("{bad-json", encoding="utf-8")
        p = self.run_cli("bulk-read", "--question", "hi", "--paths", self.src,
                         env=self.env)
        self.assertIn("valid JSON", p.stderr)
        self.assertFalse(FakeHandler.requests)

    def test_config_rejects_symlinks_unknown_fields_and_wrong_types(self):
        target = self.cwd / "secret.json"
        target.write_text('{"api_key":"test"}')
        config = self.cwd / ".config/codex-shunt/config.json"
        config.parent.mkdir(parents=True, exist_ok=True)
        config.unlink()
        config.symlink_to(target)
        env = self.env
        p = self.run_cli("bulk-read", "--question", "hi", "--paths", self.src, env=env)
        self.assertIn("not a symlink", p.stderr)
        config.unlink()
        self.write_config({"unknown": "ignored"})
        p = self.run_cli("bulk-read", "--question", "hi", "--paths", self.src, env=env)
        self.assertIn("unknown config field", p.stderr)
        self.write_config({"context_tokens": True})
        p = self.run_cli("bulk-read", "--question", "hi", "--paths", self.src, env=env)
        self.assertIn("invalid config type", p.stderr)
        self.assertFalse(FakeHandler.requests)

    def test_shunt_config_file_cannot_be_delegated(self):
        path = self.write_config({"api_base": f"http://127.0.0.1:{self.server.server_port}/v1",
                                  "model": "config-model", "api_key": "secret-key"})
        p = self.run_cli("bulk-read", "--question", "hi", "--paths", path,
                         env=self.env)
        self.assertIn("refusing Shunt credential config", p.stderr)
        self.assertFalse(FakeHandler.requests)

    def test_hook_uses_user_config_without_exports(self):
        big = self.cwd / "medium.py"
        big.write_text("code\n" * 220)
        self.write_config({"min_lines": 200})
        event = {"tool_input": {"command": "cat medium.py"}, "cwd": str(self.cwd)}
        p = subprocess.run([sys.executable, str(HOOK)], input=json.dumps(event),
                           text=True, capture_output=True, env=self.env)
        self.assertEqual(p.returncode, 0, p.stderr)
        self.assertEqual(json.loads(p.stdout)["hookSpecificOutput"]["permissionDecision"], "deny")

    def test_bulk_reads_selected_files_and_extracts_only_worker_answer(self):
        p = self.run_cli("bulk-read", "--question", "What returns?", "--paths", self.src)
        self.assertEqual(p.returncode, 0, p.stderr)
        self.assertEqual(p.stdout.strip(), "output")
        path, body, auth = FakeHandler.requests[0]
        self.assertEqual(path, "/v1/chat/completions")
        self.assertEqual(body["model"], "cheap-mock")
        self.assertEqual(auth, "Bearer test-only-key")
        self.assertIn("def hello()", body["messages"][1]["content"])
        self.assertIn("What returns?", body["messages"][1]["content"])
        self.assertEqual(len(body["messages"]), 2)

    def test_generate_code_fence_and_create_new_target(self):
        FakeHandler.answer = "```python\nprint(42)\n```"
        target = self.cwd / "new.py"
        p = self.run_cli("code-write", "--spec", "add printing", "--reference", self.src,
                         "--target", target)
        self.assertEqual(p.returncode, 0, p.stderr)
        self.assertEqual(target.read_text(), "print(42)\n")
        self.assertEqual(len(FakeHandler.requests), 1)

    def test_existing_target_never_overwritten_and_no_billable_call(self):
        target = self.cwd / "existing.py"
        target.write_text("DO NOT REPLACE")
        p = self.run_cli("code-write", "--spec", "add tests", "--reference", self.src,
                         "--target", target)
        self.assertNotEqual(p.returncode, 0)
        self.assertIn("refusing to overwrite", p.stderr)
        self.assertEqual(target.read_text(), "DO NOT REPLACE")
        self.assertEqual(len(FakeHandler.requests), 0)

    def test_code_writer_keeps_previous_payload_cap(self):
        # Bulk-read context-budgeting must not break code-write callers.
        self.src.write_text("reference\n" * 2000)
        p = self.run_cli("code-write", "--spec", "write tests", "--reference", self.src)
        self.assertEqual(p.returncode, 0, p.stderr)
        self.assertEqual(len(FakeHandler.requests), 1)

    def test_unreadable_input_is_error_not_fake_context(self):
        p = self.run_cli("bulk-read", "--question", "hi", "--paths", "missing.py")
        self.assertNotEqual(p.returncode, 0)
        self.assertFalse(FakeHandler.requests)

    def test_secret_file_rejected_before_upload(self):
        secret = self.cwd / ".env"
        secret.write_text("TOKEN=abc")
        p = self.run_cli("bulk-read", "--question", "hi", "--paths", secret)
        self.assertNotEqual(p.returncode, 0)
        self.assertFalse(FakeHandler.requests)

    def test_symlink_to_secret_is_rejected(self):
        secret = self.cwd / ".env.private"
        secret.write_text("SECRET=topsecret")
        alias = self.cwd / "alias.py"
        alias.symlink_to(secret)
        p = self.run_cli("bulk-read", "--question", "hi", "--paths", alias)
        self.assertNotEqual(p.returncode, 0)
        self.assertFalse(FakeHandler.requests)

    def test_bounded_request(self):
        self.update_config(max_payload_bytes=16)
        p = self.run_cli("bulk-read", "--question", "hi", "--paths", self.src)
        self.assertNotEqual(p.returncode, 0)
        self.assertIn("too small", p.stderr)
        self.assertFalse(FakeHandler.requests)

    def test_reject_remote_http_and_missing_credentials(self):
        self.update_config(api_base="http://example.org/v1")
        p = self.run_cli("bulk-read", "--question", "hi", "--paths", self.src)
        self.assertIn("HTTPS", p.stderr)
        self.update_config(api_base="https://example.org/v1", api_key="")
        p = self.run_cli("bulk-read", "--question", "hi", "--paths", self.src)
        self.assertIn("api_key", p.stderr)
        self.assertFalse(FakeHandler.requests)

    def test_worker_http_failure_does_not_create_target(self):
        FakeHandler.status = 401
        target = self.cwd / "unwritten.py"
        p = self.run_cli("code-write", "--spec", "hi", "--reference", self.src,
                         "--target", target)
        self.assertIn("HTTP 401", p.stderr)
        self.assertFalse(target.exists())

    def test_refuses_redirect(self):
        FakeHandler.redirect = f"http://127.0.0.1:{self.server.server_port}/redirect"
        p = self.run_cli("bulk-read", "--question", "hi", "--paths", self.src)
        self.assertNotEqual(p.returncode, 0)
        self.assertEqual(len(FakeHandler.requests), 1)

    def test_loopback_without_key_is_valid(self):
        self.update_config(api_key="")
        p = self.run_cli("bulk-read", "--question", "hi", "--paths", self.src)
        self.assertEqual(p.returncode, 0, p.stderr)
        self.assertIsNone(FakeHandler.requests[0][2])

    def test_hook_blocks_bulk_cat_and_nl_but_allows_targeted_reads(self):
        big = self.cwd / "big file.py"
        big.write_text("x\n" * 351)
        self.assertEqual(self.hook(f"cat '{big.name}'")["hookSpecificOutput"]["permissionDecision"], "deny")
        self.assertEqual(self.hook(f"nl '{big.name}'")["hookSpecificOutput"]["permissionDecision"], "deny")
        self.assertEqual(self.hook(f"bash -lc \"cat '{big.name}'\"")["hookSpecificOutput"]["permissionDecision"], "deny")
        self.assertEqual(self.hook(f"cat '{big.name}' | grep x"), {})
        self.assertEqual(self.hook(f"head -n 10 '{big.name}'"), {})
        self.assertEqual(self.hook("cat source.py"), {})

    def test_hook_uses_event_cwd_and_threshold(self):
        big = self.cwd / "medium.txt"
        big.write_text("line\n" * 201)
        self.assertEqual(self.hook("cat medium.txt"), {})
        self.update_config(min_lines=200)
        payload = {"tool_input": {"command": "cat medium.txt"}, "cwd": str(self.cwd)}
        p = subprocess.run([sys.executable, str(HOOK)], input=json.dumps(payload),
                           text=True, capture_output=True, env=self.env)
        self.assertEqual(json.loads(p.stdout)["hookSpecificOutput"]["permissionDecision"], "deny")

    def test_large_file_is_chunked_and_reduced_without_losing_source_text(self):
        import re
        source = ("# 中文\n" + "result = 'hello\\\"world'\n" * 300 + "final = 7\n")
        self.src.write_text(source, encoding="utf-8")
        self.update_config(context_tokens=2100, reply_tokens=500)
        p = self.run_cli("bulk-read", "--question", "summarize", "--paths", self.src)
        self.assertEqual(p.returncode, 0, p.stderr)
        self.assertEqual(p.stdout.strip(), "output")
        requests = [body for _, body, _ in FakeHandler.requests]
        self.assertGreater(len(requests), 2)
        self.assertTrue(all(len(json.dumps(body, ensure_ascii=False).encode()) <= 1600 for body in requests))
        chunks = [body["messages"][1]["content"] for body in requests
                  if '<file path=' in body["messages"][1]["content"]]
        self.assertGreater(len(chunks), 1)
        self.assertEqual("".join(re.search(r"start_line=\"\d+\">\n(.*?)\n</file>", c, re.S).group(1)
                                 for c in chunks), source)
        self.assertIn("Synthesize them", requests[-1]["messages"][1]["content"])

    def test_very_long_single_line_splits_without_loss(self):
        import re
        source = "你好 🔧\\" * 3500  # includes non-ASCII, backslashes and JSON-escaped quotes
        self.src.write_text(source, encoding="utf-8")
        self.update_config(context_tokens=2300, reply_tokens=500)
        p = self.run_cli("bulk-read", "--question", "summarize", "--paths", self.src)
        self.assertEqual(p.returncode, 0, p.stderr)
        chunks = [body["messages"][1]["content"] for _, body, _ in FakeHandler.requests
                  if 'start_line=' in body["messages"][1]["content"]]
        self.assertGreater(len(chunks), 5)
        self.assertEqual("".join(re.search(r"start_line=\"\d+\">\n(.*?)\n</file>", c, re.S).group(1)
                                 for c in chunks), source)

    def test_many_chunks_use_bounded_multilevel_reduction(self):
        self.src.write_text("line = 1234\n" * 1500)
        FakeHandler.answer = "summary " * 45
        self.update_config(context_tokens=2000, reply_tokens=500)
        p = self.run_cli("bulk-read", "--question", "find all", "--paths", self.src)
        self.assertEqual(p.returncode, 0, p.stderr)
        calls = [body for _, body, _ in FakeHandler.requests]
        self.assertGreater(len(calls), 15)
        self.assertTrue(all(len(json.dumps(body, ensure_ascii=False).encode()) <= 1500 for body in calls))
        self.assertGreater(sum("Synthesize them" in b["messages"][1]["content"] for b in calls), 1)

    def test_later_unreadable_file_prevents_any_upload(self):
        big = self.cwd / "big.py"
        big.write_text("line\n" * 1000)
        p = self.run_cli("bulk-read", "--question", "hi", "--paths", big, self.cwd / ".env")
        self.assertNotEqual(p.returncode, 0)
        self.assertFalse(FakeHandler.requests)

    def test_worker_failure_mid_batch_does_not_print_partial_results(self):
        big = self.cwd / "big.py"
        big.write_text("line\n" * 400)
        FakeHandler.status = 400
        self.update_config(context_tokens=2100, reply_tokens=500)
        p = self.run_cli("bulk-read", "--question", "hi", "--paths", big)
        self.assertNotEqual(p.returncode, 0)
        self.assertEqual(p.stdout, "")
        self.assertIn("HTTP 400", p.stderr)

    def test_context_budget_rejects_invalid_reserve(self):
        self.update_config(context_tokens=500, reply_tokens=500)
        p = self.run_cli("bulk-read", "--question", "hi", "--paths", self.src)
        self.assertNotEqual(p.returncode, 0)
        self.assertIn("smaller", p.stderr)
        self.assertFalse(FakeHandler.requests)

    def test_hook_recognizes_common_read_patterns_not_writes(self):
        big = self.cwd / "big file.py"
        big.write_text("x\n" * 500)
        name = f"'{big.name}'"
        for command in (f"head -n 400 {name}", f"tail -400 {name}", f"tail -n +10 {name}",
                        f"sed -n '1,450p' {name}", f"sed -n '1,$p' {name}",
                        f"sed 's/x/y/' {name}", f"awk '1' {name}",
                        f"python3 -c \"print(open('{big.name}').read())\"",
                        f"python3 -c \"print(Path('{big.name}').read_text())\""):
            with self.subTest(command=command):
                self.assertEqual(self.hook(command)["hookSpecificOutput"]["permissionDecision"], "deny")
        for command in (f"head -n 20 {name}", f"tail {name}", f"tail -n -10 {name}",
                        f"sed -n '2,50p' {name}", f"sed -i 's/x/y/' {name}",
                        f"cat {name} | head -n 5", f"python3 -c \"open('{big.name}', 'w').write('x')\"",
                        f"grep -n 'x' {name}"):
            with self.subTest(command=command):
                self.assertEqual(self.hook(command), {})

    def test_hook_supports_exec_command_array_and_ignores_unknown_shell(self):
        big = self.cwd / "big.py"
        big.write_text("x\n" * 351)
        self.assertEqual(self.hook("", tool_input={"cmd": ["bash", "-lc", "cat big.py"]})
                         ["hookSpecificOutput"]["permissionDecision"], "deny")
        self.assertEqual(self.hook("cat big.py && echo side-effect"), {})

    def test_portable_manifest_and_skills(self):
        plugin = ROOT / "plugins/shunt"
        doc = json.loads((plugin / "plugin.json").read_text())
        marketplace = json.loads((ROOT / ".agents/plugins/marketplace.json").read_text())
        self.assertEqual(marketplace["plugins"][0]["source"]["path"], "./plugins/shunt")
        self.assertEqual(doc["extensions"]["com.openai"]["hooks"], "./hooks/hooks.json")
        self.assertTrue((plugin / "hooks/hooks.json").exists())
        for name in ("bulk-reader", "code-writer"):
            content = (plugin / "skills" / name / "SKILL.md").read_text()
            self.assertIn("name: shunt-", content)


if __name__ == "__main__":
    unittest.main()
