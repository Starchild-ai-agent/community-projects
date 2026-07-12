#!/usr/bin/env python3
"""Deterministic tests for Starchild Live background bridge state."""
from __future__ import annotations

import importlib.util
import json
import threading
import time
import unittest
from http.server import ThreadingHTTPServer
from pathlib import Path
from unittest.mock import patch
from urllib.error import HTTPError
from urllib.request import Request, urlopen

SPEC = importlib.util.spec_from_file_location("live_server", Path(__file__).with_name("server.py"))
server = importlib.util.module_from_spec(SPEC)
assert SPEC and SPEC.loader
SPEC.loader.exec_module(server)


class BackgroundJobsTest(unittest.TestCase):
    def setUp(self):
        with server.JOB_REGISTRY_LOCK:
            server.JOB_REGISTRY.clear()
            server.JOB_ACTIVE_PER_THREAD.clear()
        with server.BRIDGE_COORD_LOCK:
            server.BRIDGE_RESULT_CACHE.clear()
        with server.BRIDGE_CONFIG_LOCK:
            server.BRIDGE_CONFIG.update({
                "agent_id": "main", "model": None,
                "thread_mode": "isolated", "thread_id": None,
                "system_prompt": "",
            })

    def wait_terminal(self, run_id, timeout=2):
        end = time.time() + timeout
        while time.time() < end:
            job = server._get_job(run_id)
            if job and job["status"] in server.TERMINAL_STATUSES:
                return job
            time.sleep(0.01)
        self.fail("job did not become terminal")

    def test_mode_selection(self):
        self.assertEqual(server._decide_execution_mode("wait", "long" * 500), "wait")
        self.assertEqual(server._decide_execution_mode("background", "hi"), "background")
        self.assertEqual(server._decide_execution_mode("auto", "quick status"), "wait")
        self.assertEqual(server._decide_execution_mode("auto", "继续后台处理这个任务"), "background")
        self.assertEqual(server._decide_execution_mode("auto", "x" * 481), "background")

    def test_temporary_route_is_safe_default(self):
        thread, temporary, mode = server._resolve_effective_thread(server._safe_bridge_config())
        self.assertEqual((thread, temporary, mode), ("voice-realtime", True, "isolated"))

    def test_start_complete_and_sanitize(self):
        result = {"result": "done", "model": "m", "usage": {"secret": 1}}
        with patch.object(server, "_dispatch_chat_call", return_value=result):
            accepted = server.start_background_bridge_job("work")
            job = self.wait_terminal(accepted["run_id"])
        self.assertEqual(job["status"], "completed")
        self.assertEqual(job["result"], "done")
        self.assertNotIn("question", job)
        self.assertNotIn("usage", job)
        self.assertTrue(job["is_temporary"])

    def test_same_question_deduplicates(self):
        release = threading.Event()
        def slow(*args):
            release.wait(1)
            return {"result": "ok", "model": None}
        with patch.object(server, "_dispatch_chat_call", side_effect=slow):
            first = server.start_background_bridge_job("same")
            second = server.start_background_bridge_job("same")
            self.assertEqual(first["run_id"], second["run_id"])
            self.assertTrue(second.get("deduplicated"))
            release.set()
            self.wait_terminal(first["run_id"])

    def test_different_active_job_same_thread_rejected(self):
        release = threading.Event()
        def slow(*args):
            release.wait(1)
            return {"result": "ok", "model": None}
        with patch.object(server, "_dispatch_chat_call", side_effect=slow):
            first = server.start_background_bridge_job("one")
            with self.assertRaisesRegex(ValueError, "active background job"):
                server.start_background_bridge_job("two")
            release.set()
            self.wait_terminal(first["run_id"])

    def test_failure_is_terminal_and_sanitized(self):
        with patch.object(server, "_dispatch_chat_call", side_effect=RuntimeError("boom")):
            accepted = server.start_background_bridge_job("fail")
            job = self.wait_terminal(accepted["run_id"])
        self.assertEqual(job["status"], "failed")
        self.assertEqual(job["error"], "boom")
        self.assertNotIn("question", job)

    def test_cancel_request_never_claims_early_cancel(self):
        release = threading.Event()
        def slow(*args):
            release.wait(1)
            return {"result": "late", "model": None}
        with patch.object(server, "_dispatch_chat_call", side_effect=slow), patch.object(server, "urlopen", side_effect=OSError("no runtime")):
            accepted = server.start_background_bridge_job("cancel")
            end = time.time() + 1
            while server._get_job(accepted["run_id"])["status"] == "queued" and time.time() < end:
                time.sleep(0.005)
            requested = server.request_job_cancel(accepted["run_id"])
            self.assertEqual(requested["status"], "cancel_requested")
            release.set()
            terminal = self.wait_terminal(accepted["run_id"])
        self.assertEqual(terminal["status"], "cancelled")

    def test_unknown_run(self):
        self.assertIsNone(server._get_job("run_missing"))
        self.assertIsNone(server.request_job_cancel("run_missing"))

    def test_http_wait_returns_completed_result_within_budget(self):
        httpd = ThreadingHTTPServer(("127.0.0.1", 0), server.Handler)
        worker = threading.Thread(target=httpd.serve_forever, daemon=True)
        worker.start()
        base = "http://127.0.0.1:" + str(httpd.server_address[1])
        try:
            with patch.object(server, "_dispatch_chat_call", return_value={"result": "quick", "model": "m"}):
                req = Request(
                    base + "/agent_bridge",
                    data=json.dumps({"question": "quick work", "execution_mode": "wait"}).encode(),
                    headers={"Content-Type": "application/json"},
                    method="POST",
                )
                with urlopen(req, timeout=2) as resp:
                    self.assertEqual(resp.status, 200)
                    body = json.loads(resp.read())
            self.assertEqual(body["result"], "quick")
            self.assertFalse(body["deferred"])
        finally:
            httpd.shutdown()
            httpd.server_close()

    def test_http_wait_auto_defers_before_gateway_timeout(self):
        release = threading.Event()
        def slow(*args):
            release.wait(1)
            return {"result": "late", "model": "m"}
        httpd = ThreadingHTTPServer(("127.0.0.1", 0), server.Handler)
        worker = threading.Thread(target=httpd.serve_forever, daemon=True)
        worker.start()
        base = "http://127.0.0.1:" + str(httpd.server_address[1])
        try:
            with patch.object(server, "_dispatch_chat_call", side_effect=slow), patch.object(server, "SYNC_WAIT_BUDGET_SECONDS", 0.05):
                req = Request(
                    base + "/agent_bridge",
                    data=json.dumps({"question": "slow work", "execution_mode": "wait"}).encode(),
                    headers={"Content-Type": "application/json"},
                    method="POST",
                )
                with urlopen(req, timeout=2) as resp:
                    self.assertEqual(resp.status, 202)
                    body = json.loads(resp.read())
                self.assertTrue(body["accepted"])
                self.assertTrue(body["deferred"])
                self.assertTrue(body["run_id"].startswith("run_"))
                release.set()
                terminal = self.wait_terminal(body["run_id"])
                self.assertEqual(terminal["result"], "late")
        finally:
            release.set()
            httpd.shutdown()
            httpd.server_close()

    def test_voice_source_marker_is_written_into_user_message(self):
        captured = {}
        class FakeResponse:
            def __enter__(self): return self
            def __exit__(self, *args): return False
            def read(self): return json.dumps({"success": True, "reply": "ok"}).encode()
        def fake_urlopen(req, timeout=None):
            captured.update(json.loads(req.data.decode()))
            return FakeResponse()
        cfg = {"agent_id": "main", "model": None, "thread_mode": "selected", "system_prompt": ""}
        with patch.object(server, "urlopen", side_effect=fake_urlopen):
            server._dispatch_chat_call("thread-test", False, "spoken request", cfg)
        self.assertIn("[Starchild Live Voice Agent]", captured["message"])
        self.assertIn("[Spoken user request]\nspoken request", captured["message"])

    def test_http_background_lifecycle_and_unknown_404(self):
        httpd = ThreadingHTTPServer(("127.0.0.1", 0), server.Handler)
        worker = threading.Thread(target=httpd.serve_forever, daemon=True)
        worker.start()
        base = "http://127.0.0.1:" + str(httpd.server_address[1])
        try:
            with patch.object(server, "_dispatch_chat_call", return_value={"result": "http done", "model": "m"}):
                req = Request(
                    base + "/agent_bridge",
                    data=json.dumps({"question": "http work", "execution_mode": "background"}).encode(),
                    headers={"Content-Type": "application/json"},
                    method="POST",
                )
                with urlopen(req, timeout=2) as resp:
                    self.assertEqual(resp.status, 202)
                    accepted = json.loads(resp.read())
                job = self.wait_terminal(accepted["run_id"])
                with urlopen(base + "/agent_jobs?run_id=" + accepted["run_id"], timeout=2) as resp:
                    wire = json.loads(resp.read())
                self.assertEqual(wire["status"], "completed")
                self.assertEqual(wire["result"], "http done")
                self.assertNotIn("question", wire)
            with self.assertRaises(HTTPError) as cm:
                urlopen(base + "/agent_jobs?run_id=run_missing", timeout=2)
            self.assertEqual(cm.exception.code, 404)
        finally:
            httpd.shutdown()
            httpd.server_close()


    # ----- Rolling voice context (temporary follow-up disambiguation) -----

    def test_format_recent_context_handles_empty_and_malformed(self):
        self.assertEqual(server._format_recent_context(None), "")
        self.assertEqual(server._format_recent_context([]), "")
        self.assertEqual(server._format_recent_context("nope"), "")
        self.assertEqual(server._format_recent_context([{"role": "user", "text": "  "}]), "")
        self.assertEqual(server._format_recent_context(["x", 5, {"no": "text"}]), "")

    def test_format_recent_context_caps_to_last_six_turns(self):
        turns = [{"role": "user", "text": f"m{i}"} for i in range(10)]
        block = server._format_recent_context(turns)
        self.assertIn("m9", block)
        self.assertIn("m4", block)
        self.assertNotIn("m3", block)  # only last 6 kept (m4..m9)

    def test_context_injected_only_in_temporary_mode(self):
        captured = {}
        class FakeResponse:
            def __enter__(self): return self
            def __exit__(self, *args): return False
            def read(self): return json.dumps({"success": True, "reply": "ok"}).encode()
        def fake_urlopen(req, timeout=None):
            captured.update(json.loads(req.data.decode()))
            return FakeResponse()
        cfg = {"agent_id": "main", "model": None, "thread_mode": "isolated", "system_prompt": ""}
        ctx = [{"role": "user", "text": "去做线程标题预览"}, {"role": "assistant", "text": "好的"}]

        # Temporary → context block present
        with patch.object(server, "urlopen", side_effect=fake_urlopen):
            server._dispatch_chat_call("voice-realtime", True, "可以去做了吗", cfg, ctx)
        self.assertIn("Recent voice conversation", captured["message"])
        self.assertIn("去做线程标题预览", captured["message"])
        self.assertIn("[Spoken user request]\n可以去做了吗", captured["message"])

        # Selected/persistent thread → no injected context (runtime has history)
        captured.clear()
        with patch.object(server, "urlopen", side_effect=fake_urlopen):
            server._dispatch_chat_call("thread-real", False, "可以去做了吗", cfg, ctx)
        self.assertNotIn("Recent voice conversation", captured["message"])
        self.assertNotIn("去做线程标题预览", captured["message"])

    def test_http_bridge_forwards_context_end_to_end(self):
        captured = {}
        class FakeResponse:
            def __enter__(self): return self
            def __exit__(self, *args): return False
            def read(self): return json.dumps({"success": True, "reply": "ok"}).encode()
        def fake_urlopen(req, timeout=None):
            captured.update(json.loads(req.data.decode()))
            return FakeResponse()
        httpd = ThreadingHTTPServer(("127.0.0.1", 0), server.Handler)
        worker = threading.Thread(target=httpd.serve_forever, daemon=True)
        worker.start()
        base = "http://127.0.0.1:" + str(httpd.server_address[1])
        try:
            with patch.object(server, "urlopen", side_effect=fake_urlopen):
                req = Request(
                    base + "/agent_bridge",
                    data=json.dumps({
                        "question": "可以去做了吗",
                        "execution_mode": "wait",
                        "context": [{"role": "user", "text": "先做线程标题预览"}],
                    }).encode(),
                    headers={"Content-Type": "application/json"},
                    method="POST",
                )
                with urlopen(req, timeout=2) as resp:
                    self.assertEqual(resp.status, 200)
            self.assertIn("先做线程标题预览", captured["message"])
        finally:
            httpd.shutdown()
            httpd.server_close()


if __name__ == "__main__":
    unittest.main(verbosity=2)
