#!/usr/bin/env python3
"""
Test suite for brainstorm-mode.
Uses only stdlib. Run from any directory:
    python3 tests/run_tests.py

Tests call main() functions directly (mocking stdin/stdout) so coverage
tools can instrument every line. A small set of subprocess smoke tests
at the bottom verify the scripts actually work as standalone CLI programs.
"""
import builtins
import importlib
import importlib.util
import io
import json
import os
import subprocess
import sys
import tempfile
import unittest
from contextlib import redirect_stdout
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import patch

# ── Paths ─────────────────────────────────────────────────────────────────────
REPO_ROOT = Path(__file__).parent.parent
CORE = REPO_ROOT / "core"
HOOKS = REPO_ROOT / "agents" / "claude-code" / "hooks_scripts"
OPENCODE_HOOKS = REPO_ROOT / "agents" / "opencode" / "hooks_scripts"

# Put core and hooks on sys.path so imports inside the modules resolve.
for p in (str(CORE), str(HOOKS)):
    if p not in sys.path:
        sys.path.insert(0, p)

import brainstorm_state as bs

# Import hook modules — their module-level sys.path.insert runs once here.
import on_pre_tool_use
import on_session_start
import on_user_prompt
import activate as activate_mod
import deactivate as deactivate_mod


def _load(name, path):
    """Import a module from an explicit file path under a unique name.

    The opencode adapters share filenames with the claude-code ones, so they are
    loaded under distinct module names to avoid colliding in sys.modules while
    still being measured by coverage (which tracks files, not module names).
    """
    spec = importlib.util.spec_from_file_location(name, str(path))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


# OpenCode adapters (thin shims with their own stdin/stdout contract).
oc_pre_tool_use = _load("oc_on_pre_tool_use", OPENCODE_HOOKS / "on_pre_tool_use.py")
oc_user_prompt = _load("oc_on_user_prompt", OPENCODE_HOOKS / "on_user_prompt.py")
oc_session_start = _load("oc_on_session_start", OPENCODE_HOOKS / "on_session_start.py")

# ── Shared helpers ────────────────────────────────────────────────────────────

def _now_utc():
    return datetime.now(timezone.utc)


def _locks_dir(cwd):
    return Path(cwd) / ".claude" / "brainstorm" / "locks"


def _make_lock(cwd, session_id, topic, hours_ago=0, ttl_hours=8):
    d = _locks_dir(cwd)
    d.mkdir(parents=True, exist_ok=True)
    created = _now_utc() - timedelta(hours=hours_ago)
    data = {
        "session_id": session_id,
        "topic": topic,
        "created_at": created.isoformat(),
        "ttl_hours": ttl_hours,
    }
    path = d / f"{session_id}.json"
    path.write_text(json.dumps(data))
    return path


def _call_hook(module, input_dict):
    """Call module.main() with input_dict as stdin JSON. Returns stdout string."""
    buf = io.StringIO()
    with patch("sys.stdin", io.StringIO(json.dumps(input_dict))):
        with redirect_stdout(buf):
            module.main()
    return buf.getvalue()


def _call_hook_raw(module, raw_input):
    """Call module.main() with raw string as stdin. Returns stdout string."""
    buf = io.StringIO()
    with patch("sys.stdin", io.StringIO(raw_input)):
        with redirect_stdout(buf):
            module.main()
    return buf.getvalue()


# ── Tests: on_pre_tool_use ────────────────────────────────────────────────────

class TestPreToolUse(unittest.TestCase):

    def _run(self, cwd, session_id, tool_name):
        return _call_hook(on_pre_tool_use, {
            "session_id": session_id, "cwd": str(cwd), "tool_name": tool_name,
        })

    def test_edit_blocked_when_active(self):
        with tempfile.TemporaryDirectory() as cwd:
            _make_lock(cwd, "s1", "my topic")
            out = self._run(cwd, "s1", "Edit")
            decision = json.loads(out)
            self.assertEqual(decision["hookSpecificOutput"]["permissionDecision"], "deny")
            self.assertIn("my topic", decision["hookSpecificOutput"]["denyReason"])

    def test_multiedit_blocked_when_active(self):
        with tempfile.TemporaryDirectory() as cwd:
            _make_lock(cwd, "s1", "topic")
            out = self._run(cwd, "s1", "MultiEdit")
            self.assertEqual(json.loads(out)["hookSpecificOutput"]["permissionDecision"], "deny")

    def test_notebookedit_blocked_when_active(self):
        with tempfile.TemporaryDirectory() as cwd:
            _make_lock(cwd, "s1", "topic")
            out = self._run(cwd, "s1", "NotebookEdit")
            self.assertEqual(json.loads(out)["hookSpecificOutput"]["permissionDecision"], "deny")

    def test_edit_allowed_when_no_lock(self):
        with tempfile.TemporaryDirectory() as cwd:
            self.assertEqual(self._run(cwd, "s-none", "Edit").strip(), "")

    def test_bash_allowed_even_when_active(self):
        with tempfile.TemporaryDirectory() as cwd:
            _make_lock(cwd, "s1", "topic")
            self.assertEqual(self._run(cwd, "s1", "Bash").strip(), "")

    def test_write_allowed_even_when_active(self):
        with tempfile.TemporaryDirectory() as cwd:
            _make_lock(cwd, "s1", "topic")
            self.assertEqual(self._run(cwd, "s1", "Write").strip(), "")

    def test_read_allowed_even_when_active(self):
        with tempfile.TemporaryDirectory() as cwd:
            _make_lock(cwd, "s1", "topic")
            self.assertEqual(self._run(cwd, "s1", "Read").strip(), "")

    def test_expired_lock_allows_edit(self):
        with tempfile.TemporaryDirectory() as cwd:
            _make_lock(cwd, "s-exp", "topic", hours_ago=9)
            self.assertEqual(self._run(cwd, "s-exp", "Edit").strip(), "")

    def test_expired_lock_file_removed(self):
        with tempfile.TemporaryDirectory() as cwd:
            p = _make_lock(cwd, "s-exp", "topic", hours_ago=9)
            self._run(cwd, "s-exp", "Edit")
            self.assertFalse(p.exists())

    def test_drift_log_appended_on_deny(self):
        with tempfile.TemporaryDirectory() as cwd:
            _make_lock(cwd, "s1", "log topic")
            self._run(cwd, "s1", "Edit")
            log = Path(cwd) / ".claude" / "brainstorm" / "drift-log.jsonl"
            self.assertTrue(log.exists())
            record = json.loads(log.read_text().strip())
            self.assertEqual(record["tool_name"], "Edit")
            self.assertEqual(record["topic"], "log topic")
            self.assertFalse(record["post_compaction"])

    def test_drift_log_post_compaction_flag(self):
        with tempfile.TemporaryDirectory() as cwd:
            _make_lock(cwd, "s1", "topic")
            bs.set_compact_flag(cwd, "s1")
            self._run(cwd, "s1", "Edit")
            log = Path(cwd) / ".claude" / "brainstorm" / "drift-log.jsonl"
            record = json.loads(log.read_text().strip())
            self.assertTrue(record["post_compaction"])

    def test_corrupt_lock_treated_as_absent(self):
        with tempfile.TemporaryDirectory() as cwd:
            d = _locks_dir(cwd)
            d.mkdir(parents=True, exist_ok=True)
            (d / "s1.json").write_text("{broken")
            self.assertEqual(self._run(cwd, "s1", "Edit").strip(), "")

    def test_empty_session_id_allows_through(self):
        with tempfile.TemporaryDirectory() as cwd:
            out = _call_hook(on_pre_tool_use, {
                "session_id": "", "cwd": str(cwd), "tool_name": "Edit",
            })
            self.assertEqual(out.strip(), "")

    def test_garbage_stdin_exits_clean(self):
        self.assertEqual(_call_hook_raw(on_pre_tool_use, "not json {{").strip(), "")

    def test_empty_stdin_exits_clean(self):
        self.assertEqual(_call_hook_raw(on_pre_tool_use, "").strip(), "")


# ── Tests: on_user_prompt ─────────────────────────────────────────────────────

class TestUserPrompt(unittest.TestCase):

    def _run(self, cwd, session_id):
        return _call_hook(on_user_prompt, {
            "session_id": session_id, "cwd": str(cwd),
        })

    def test_reminder_injected_when_active(self):
        with tempfile.TemporaryDirectory() as cwd:
            _make_lock(cwd, "s1", "cool topic")
            out = self._run(cwd, "s1")
            self.assertIn("BRAINSTORM MODE ACTIVE", out)
            self.assertIn("cool topic", out)

    def test_no_output_when_inactive(self):
        with tempfile.TemporaryDirectory() as cwd:
            self.assertEqual(self._run(cwd, "s-none").strip(), "")

    def test_expired_lock_announces_expiry(self):
        with tempfile.TemporaryDirectory() as cwd:
            _make_lock(cwd, "s1", "old topic", hours_ago=9)
            out = self._run(cwd, "s1")
            self.assertIn("expired", out.lower())
            self.assertIn("old topic", out)

    def test_escalated_reminder_after_threshold(self):
        with tempfile.TemporaryDirectory() as cwd:
            lock = bs.write_lock(cwd, "s1", "topic")
            for _ in range(bs.ESCALATION_THRESHOLD):
                bs.append_drift_log(cwd, "s1", "topic", "Edit", lock["created_at"], False)
            out = self._run(cwd, "s1")
            self.assertIn("ATTENTION", out)
            self.assertIn("BRAINSTORM MODE ACTIVE", out)

    def test_actionable_lock_shows_actionable_reminder(self):
        with tempfile.TemporaryDirectory() as cwd:
            bs.write_lock(cwd, "s1", "ship it", "actionable")
            out = self._run(cwd, "s1")
            self.assertIn("(actionable)", out)
            self.assertIn("ship it", out)

    def test_pending_lock_claimed_and_reminder_shown(self):
        with tempfile.TemporaryDirectory() as cwd:
            bs.write_pending_lock(cwd, "pending topic")
            out = self._run(cwd, "real-session")
            self.assertIn("BRAINSTORM MODE ACTIVE", out)
            self.assertIn("pending topic", out)
            self.assertFalse((_locks_dir(cwd) / "_pending.json").exists())
            self.assertTrue((_locks_dir(cwd) / "real-session.json").exists())

    def test_empty_session_id_no_output(self):
        with tempfile.TemporaryDirectory() as cwd:
            out = _call_hook(on_user_prompt, {"session_id": "", "cwd": str(cwd)})
            self.assertEqual(out.strip(), "")

    def test_garbage_stdin_exits_clean(self):
        self.assertEqual(_call_hook_raw(on_user_prompt, "not json").strip(), "")

    def test_empty_stdin_exits_clean(self):
        self.assertEqual(_call_hook_raw(on_user_prompt, "").strip(), "")


# ── Tests: on_session_start ───────────────────────────────────────────────────

class TestSessionStart(unittest.TestCase):

    def _run(self, cwd, session_id, source):
        return _call_hook(on_session_start, {
            "session_id": session_id, "cwd": str(cwd), "source": source,
        })

    def test_compact_reinjects_anchor(self):
        with tempfile.TemporaryDirectory() as cwd:
            _make_lock(cwd, "s1", "compact topic")
            out = self._run(cwd, "s1", "compact")
            self.assertIn("still active", out)
            self.assertIn("compact topic", out)

    def test_compact_sets_flag(self):
        with tempfile.TemporaryDirectory() as cwd:
            _make_lock(cwd, "s1", "topic")
            self._run(cwd, "s1", "compact")
            self.assertTrue((_locks_dir(cwd) / "s1.compact").exists())

    def test_compact_no_output_when_inactive(self):
        with tempfile.TemporaryDirectory() as cwd:
            self.assertEqual(self._run(cwd, "s1", "compact").strip(), "")

    def test_resume_informs_about_old_session(self):
        with tempfile.TemporaryDirectory() as cwd:
            _make_lock(cwd, "old-session", "old topic")
            out = self._run(cwd, "new-session", "resume")
            self.assertIn("old topic", out)
            self.assertIn("NOT currently active", out)

    def test_resume_silent_when_no_old_lock(self):
        with tempfile.TemporaryDirectory() as cwd:
            self.assertEqual(self._run(cwd, "new-session", "resume").strip(), "")

    def test_resume_silent_when_same_session_id(self):
        with tempfile.TemporaryDirectory() as cwd:
            _make_lock(cwd, "s1", "topic")
            # If the found lock has the same session_id as the resume, don't report.
            out = self._run(cwd, "s1", "resume")
            self.assertEqual(out.strip(), "")

    def test_empty_session_id_no_output(self):
        with tempfile.TemporaryDirectory() as cwd:
            out = _call_hook(on_session_start, {
                "session_id": "", "cwd": str(cwd), "source": "compact",
            })
            self.assertEqual(out.strip(), "")

    def test_unknown_source_no_output(self):
        with tempfile.TemporaryDirectory() as cwd:
            _make_lock(cwd, "s1", "topic")
            out = self._run(cwd, "s1", "unknown-source")
            self.assertEqual(out.strip(), "")

    def test_garbage_stdin_exits_clean(self):
        self.assertEqual(_call_hook_raw(on_session_start, "not json").strip(), "")


# ── Tests: activate.py ────────────────────────────────────────────────────────

class TestActivate(unittest.TestCase):

    def _run(self, cwd, session_id, topic_args):
        buf = io.StringIO()
        env = {"CLAUDE_CWD": str(cwd), "CLAUDE_SESSION_ID": session_id}
        with redirect_stdout(buf):
            rc = activate_mod.main(argv=["activate.py"] + topic_args, env=env)
        return buf.getvalue(), rc

    def test_creates_lock_with_session_id(self):
        with tempfile.TemporaryDirectory() as cwd:
            out, rc = self._run(cwd, "sess-abc", ["my topic"])
            self.assertEqual(rc, 0)
            data = json.loads((_locks_dir(cwd) / "sess-abc.json").read_text())
            self.assertEqual(data["topic"], "my topic")
            self.assertIn("activated", out.lower())

    def test_multi_word_topic(self):
        with tempfile.TemporaryDirectory() as cwd:
            _, rc = self._run(cwd, "s1", ["word1", "word2", "word3"])
            self.assertEqual(rc, 0)
            data = json.loads((_locks_dir(cwd) / "s1.json").read_text())
            self.assertEqual(data["topic"], "word1 word2 word3")

    def test_overwrite_updates_topic(self):
        with tempfile.TemporaryDirectory() as cwd:
            _make_lock(cwd, "s1", "old topic")
            out, rc = self._run(cwd, "s1", ["new topic"])
            self.assertEqual(rc, 0)
            data = json.loads((_locks_dir(cwd) / "s1.json").read_text())
            self.assertEqual(data["topic"], "new topic")
            self.assertIn("updated", out.lower())

    def test_pending_lock_when_no_session_id(self):
        with tempfile.TemporaryDirectory() as cwd:
            buf = io.StringIO()
            env = {"CLAUDE_CWD": str(cwd)}
            with redirect_stdout(buf):
                rc = activate_mod.main(argv=["activate.py", "pending topic"], env=env)
            self.assertEqual(rc, 0)
            data = json.loads((_locks_dir(cwd) / "_pending.json").read_text())
            self.assertEqual(data["topic"], "pending topic")

    def test_no_args_returns_error(self):
        buf = io.StringIO()
        with redirect_stdout(buf):
            rc = activate_mod.main(argv=["activate.py"])
        self.assertEqual(rc, 1)

    # ── --mode flag (actionable brainstorming) ────────────────────────────────

    def test_mode_actionable_creates_lock_with_mode(self):
        with tempfile.TemporaryDirectory() as cwd:
            out, rc = self._run(cwd, "s1", ["--mode", "actionable", "my topic"])
            self.assertEqual(rc, 0)
            data = json.loads((_locks_dir(cwd) / "s1.json").read_text())
            self.assertEqual(data["mode"], "actionable")
            self.assertEqual(data["topic"], "my topic")
            self.assertIn("actionable", out.lower())

    def test_default_mode_is_divergent(self):
        with tempfile.TemporaryDirectory() as cwd:
            _, rc = self._run(cwd, "s1", ["my topic"])
            self.assertEqual(rc, 0)
            data = json.loads((_locks_dir(cwd) / "s1.json").read_text())
            self.assertEqual(data["mode"], "divergent")

    def test_mode_flag_missing_value_errors(self):
        buf = io.StringIO()
        with redirect_stdout(buf):
            rc = activate_mod.main(argv=["activate.py", "--mode"])
        self.assertEqual(rc, 1)

    def test_mode_flag_invalid_value_errors(self):
        buf = io.StringIO()
        with redirect_stdout(buf):
            rc = activate_mod.main(argv=["activate.py", "--mode", "bogus", "topic"])
        self.assertEqual(rc, 1)

    def test_mode_flag_without_topic_errors(self):
        buf = io.StringIO()
        with redirect_stdout(buf):
            rc = activate_mod.main(argv=["activate.py", "--mode", "actionable"])
        self.assertEqual(rc, 1)

    def test_pending_lock_carries_mode(self):
        with tempfile.TemporaryDirectory() as cwd:
            buf = io.StringIO()
            env = {"BRAINSTORM_CWD": str(cwd)}
            with redirect_stdout(buf):
                rc = activate_mod.main(
                    argv=["activate.py", "--mode", "actionable", "pending topic"], env=env)
            self.assertEqual(rc, 0)
            data = json.loads((_locks_dir(cwd) / "_pending.json").read_text())
            self.assertEqual(data["mode"], "actionable")


# ── Tests: deactivate.py ──────────────────────────────────────────────────────

class TestDeactivate(unittest.TestCase):

    def _run(self, cwd, session_id):
        buf = io.StringIO()
        env = {"CLAUDE_CWD": str(cwd), "CLAUDE_SESSION_ID": session_id}
        with redirect_stdout(buf):
            rc = deactivate_mod.main(env=env, handoff="")
        return buf.getvalue(), rc

    def test_removes_active_lock(self):
        with tempfile.TemporaryDirectory() as cwd:
            _make_lock(cwd, "s1", "topic")
            out, rc = self._run(cwd, "s1")
            self.assertEqual(rc, 0)
            self.assertFalse((_locks_dir(cwd) / "s1.json").exists())
            self.assertIn("deactivated", out.lower())

    def test_graceful_when_no_lock(self):
        with tempfile.TemporaryDirectory() as cwd:
            out, rc = self._run(cwd, "s1")
            self.assertEqual(rc, 0)
            self.assertIn("not active", out.lower())

    def test_graceful_when_no_session_id(self):
        with tempfile.TemporaryDirectory() as cwd:
            buf = io.StringIO()
            env = {"CLAUDE_CWD": str(cwd)}
            with redirect_stdout(buf):
                rc = deactivate_mod.main(env=env)
            self.assertEqual(rc, 0)
            self.assertIn("not active", buf.getvalue().lower())


# ── Tests: brainstorm_state core ──────────────────────────────────────────────

class TestBrainstormState(unittest.TestCase):

    def test_write_and_read_lock(self):
        with tempfile.TemporaryDirectory() as cwd:
            bs.write_lock(cwd, "s1", "topic A")
            lock = bs.read_lock(cwd, "s1")
            self.assertIsNotNone(lock)
            self.assertEqual(lock["topic"], "topic A")

    def test_expired_lock_returns_none(self):
        with tempfile.TemporaryDirectory() as cwd:
            _make_lock(cwd, "s2", "old", hours_ago=9)
            self.assertIsNone(bs.read_lock(cwd, "s2"))

    def test_wrong_session_returns_none(self):
        with tempfile.TemporaryDirectory() as cwd:
            bs.write_lock(cwd, "s3", "topic")
            self.assertIsNone(bs.read_lock(cwd, "different"))

    def test_corrupt_lock_returns_none_and_deleted(self):
        with tempfile.TemporaryDirectory() as cwd:
            d = _locks_dir(cwd)
            d.mkdir(parents=True, exist_ok=True)
            p = d / "s4.json"
            p.write_text("{broken")
            self.assertIsNone(bs.read_lock(cwd, "s4"))
            self.assertFalse(p.exists())

    def test_mismatched_session_id_in_file(self):
        with tempfile.TemporaryDirectory() as cwd:
            bs.write_lock(cwd, "s1", "topic")
            # Manually overwrite with wrong session_id
            p = _locks_dir(cwd) / "s1.json"
            data = json.loads(p.read_text())
            data["session_id"] = "other"
            p.write_text(json.dumps(data))
            self.assertIsNone(bs.read_lock(cwd, "s1"))

    def test_delete_lock(self):
        with tempfile.TemporaryDirectory() as cwd:
            bs.write_lock(cwd, "s5", "topic")
            bs.delete_lock(cwd, "s5")
            self.assertIsNone(bs.read_lock(cwd, "s5"))

    def test_delete_lock_also_removes_compact_flag(self):
        with tempfile.TemporaryDirectory() as cwd:
            bs.write_lock(cwd, "s1", "topic")
            bs.set_compact_flag(cwd, "s1")
            bs.delete_lock(cwd, "s1")
            self.assertFalse(bs.is_post_compact(cwd, "s1"))

    def test_delete_nonexistent_lock_is_silent(self):
        with tempfile.TemporaryDirectory() as cwd:
            bs.delete_lock(cwd, "no-such-session")  # should not raise

    def test_claim_pending_lock(self):
        with tempfile.TemporaryDirectory() as cwd:
            bs.write_pending_lock(cwd, "pending topic")
            topic = bs.claim_pending_lock(cwd, "real-session")
            self.assertEqual(topic, "pending topic")
            self.assertIsNotNone(bs.read_lock(cwd, "real-session"))
            self.assertFalse((_locks_dir(cwd) / "_pending.json").exists())

    def test_claim_pending_no_pending_returns_none(self):
        with tempfile.TemporaryDirectory() as cwd:
            self.assertIsNone(bs.claim_pending_lock(cwd, "s1"))

    def test_claim_pending_preserves_mode(self):
        with tempfile.TemporaryDirectory() as cwd:
            bs.write_pending_lock(cwd, "topic", "actionable")
            bs.claim_pending_lock(cwd, "s1")
            self.assertEqual(bs.read_lock(cwd, "s1")["mode"], "actionable")

    def test_write_lock_invalid_mode_falls_back(self):
        with tempfile.TemporaryDirectory() as cwd:
            bs.write_lock(cwd, "s1", "topic", "bogus")
            self.assertEqual(bs.read_lock(cwd, "s1")["mode"], "divergent")

    def test_write_pending_lock_invalid_mode_falls_back(self):
        with tempfile.TemporaryDirectory() as cwd:
            bs.write_pending_lock(cwd, "topic", "bogus")
            data = json.loads((_locks_dir(cwd) / "_pending.json").read_text())
            self.assertEqual(data["mode"], "divergent")

    def test_claim_corrupt_pending_returns_none(self):
        with tempfile.TemporaryDirectory() as cwd:
            d = _locks_dir(cwd)
            d.mkdir(parents=True, exist_ok=True)
            (d / "_pending.json").write_text("{broken")
            self.assertIsNone(bs.claim_pending_lock(cwd, "s1"))

    def test_find_recent_lock(self):
        with tempfile.TemporaryDirectory() as cwd:
            _make_lock(cwd, "sx", "findable")
            lock = bs.find_recent_lock(cwd)
            self.assertIsNotNone(lock)
            self.assertEqual(lock["topic"], "findable")

    def test_find_recent_lock_ignores_expired(self):
        with tempfile.TemporaryDirectory() as cwd:
            _make_lock(cwd, "sx", "old", hours_ago=9)
            self.assertIsNone(bs.find_recent_lock(cwd))

    def test_find_recent_lock_empty_dir(self):
        with tempfile.TemporaryDirectory() as cwd:
            self.assertIsNone(bs.find_recent_lock(cwd))

    def test_two_sessions_isolated(self):
        with tempfile.TemporaryDirectory() as cwd:
            bs.write_lock(cwd, "A", "topic A")
            bs.write_lock(cwd, "B", "topic B")
            self.assertEqual(bs.read_lock(cwd, "A")["topic"], "topic A")
            self.assertEqual(bs.read_lock(cwd, "B")["topic"], "topic B")
            bs.delete_lock(cwd, "A")
            self.assertIsNone(bs.read_lock(cwd, "A"))
            self.assertIsNotNone(bs.read_lock(cwd, "B"))

    def test_compact_flag_set_and_read(self):
        with tempfile.TemporaryDirectory() as cwd:
            bs.write_lock(cwd, "s1", "topic")
            self.assertFalse(bs.is_post_compact(cwd, "s1"))
            bs.set_compact_flag(cwd, "s1")
            self.assertTrue(bs.is_post_compact(cwd, "s1"))

    def test_cleanup_removes_old_files(self):
        with tempfile.TemporaryDirectory() as cwd:
            d = _locks_dir(cwd)
            d.mkdir(parents=True, exist_ok=True)
            old = d / "ancient.json"
            old.write_text("{}")
            ancient = (_now_utc() - timedelta(days=8)).timestamp()
            os.utime(old, (ancient, ancient))
            bs.cleanup_old_locks(cwd)
            self.assertFalse(old.exists())

    def test_cleanup_keeps_recent_files(self):
        with tempfile.TemporaryDirectory() as cwd:
            bs.write_lock(cwd, "recent", "topic")
            bs.cleanup_old_locks(cwd)
            self.assertIsNotNone(bs.read_lock(cwd, "recent"))

    def test_cleanup_nonexistent_dir_is_silent(self):
        with tempfile.TemporaryDirectory() as cwd:
            bs.cleanup_old_locks(cwd)  # no .claude/brainstorm/locks dir — should not raise

    def test_append_drift_log(self):
        with tempfile.TemporaryDirectory() as cwd:
            bs.write_lock(cwd, "s1", "topic")
            lock = bs.read_lock(cwd, "s1")
            bs.append_drift_log(cwd, "s1", "topic", "Edit", lock["created_at"], False)
            log = Path(cwd) / ".claude" / "brainstorm" / "drift-log.jsonl"
            record = json.loads(log.read_text().strip())
            self.assertEqual(record["tool_name"], "Edit")
            self.assertGreaterEqual(record["minutes_since_activation"], 0)

    def test_get_reminder_contains_topic(self):
        reminder = bs.get_reminder("my special topic")
        self.assertIn("BRAINSTORM MODE ACTIVE", reminder)
        self.assertIn("my special topic", reminder)


# ── Tests: exception / error-path branches ───────────────────────────────────

class TestExceptionPaths(unittest.TestCase):
    """Cover defensive except blocks that require mocking to trigger."""

    # ── brainstorm_state._atomic_write ────────────────────────────────────────

    def test_atomic_write_reraises_on_json_dump_failure(self):
        with tempfile.TemporaryDirectory() as cwd:
            bs._ensure_dirs(cwd)
            with patch("json.dump", side_effect=IOError("disk full")):
                with self.assertRaises(IOError):
                    bs.write_lock(cwd, "s1", "topic")

    def test_atomic_write_unlink_oserror_suppressed(self):
        # When json.dump fails AND the tmp-file cleanup also fails, the original
        # error is still re-raised (not swallowed).
        with tempfile.TemporaryDirectory() as cwd:
            bs._ensure_dirs(cwd)
            with patch("json.dump", side_effect=IOError("disk full")):
                with patch.object(bs.os, "unlink", side_effect=OSError("perm")):
                    with self.assertRaises(IOError):
                        bs.write_lock(cwd, "s1", "topic")

    # ── brainstorm_state.read_lock ────────────────────────────────────────────

    def test_read_lock_remove_oserror_suppressed(self):
        with tempfile.TemporaryDirectory() as cwd:
            d = _locks_dir(cwd)
            d.mkdir(parents=True, exist_ok=True)
            (d / "s1.json").write_text("{broken")
            with patch.object(bs.os, "remove", side_effect=OSError("perm")):
                result = bs.read_lock(cwd, "s1")
            self.assertIsNone(result)

    # ── brainstorm_state.claim_pending_lock ───────────────────────────────────

    def test_claim_pending_lock_remove_oserror_suppressed(self):
        with tempfile.TemporaryDirectory() as cwd:
            bs.write_pending_lock(cwd, "topic")
            with patch.object(bs.os, "remove", side_effect=OSError("perm")):
                result = bs.claim_pending_lock(cwd, "s1")
            self.assertIsNone(result)

    # ── brainstorm_state.cleanup_old_locks ────────────────────────────────────

    def test_cleanup_remove_oserror_suppressed(self):
        with tempfile.TemporaryDirectory() as cwd:
            d = _locks_dir(cwd)
            d.mkdir(parents=True, exist_ok=True)
            old = d / "ancient.json"
            old.write_text("{}")
            ancient = (_now_utc() - timedelta(days=8)).timestamp()
            os.utime(old, (ancient, ancient))
            with patch.object(bs.os, "remove", side_effect=OSError("perm")):
                bs.cleanup_old_locks(cwd)  # should not raise

    # ── brainstorm_state.set_compact_flag ─────────────────────────────────────

    def test_set_compact_flag_oserror_suppressed(self):
        with tempfile.TemporaryDirectory() as cwd:
            bs._ensure_dirs(cwd)
            flag = str(bs._compact_flag_path(cwd, "s1"))
            real_open = builtins.open
            def fake_open(f, *a, **kw):
                if str(f) == flag:
                    raise OSError("perm")
                return real_open(f, *a, **kw)
            with patch("builtins.open", side_effect=fake_open):
                bs.set_compact_flag(cwd, "s1")  # should not raise

    # ── brainstorm_state.append_drift_log ─────────────────────────────────────

    def test_append_drift_log_bad_iso_suppressed(self):
        with tempfile.TemporaryDirectory() as cwd:
            bs.append_drift_log(cwd, "s1", "topic", "Edit", "not-a-date", False)
            # _parse_iso raises ValueError → caught by except Exception: pass

    # ── brainstorm_state.find_recent_lock ─────────────────────────────────────

    def test_find_recent_lock_skips_non_json_and_pending_files(self):
        with tempfile.TemporaryDirectory() as cwd:
            d = _locks_dir(cwd)
            d.mkdir(parents=True, exist_ok=True)
            (d / "s1.compact").write_text("")     # not .json → continue
            (d / "_pending.json").write_text("{}")  # starts with _ → continue
            self.assertIsNone(bs.find_recent_lock(cwd))

    def test_find_recent_lock_skips_corrupt_json(self):
        with tempfile.TemporaryDirectory() as cwd:
            d = _locks_dir(cwd)
            d.mkdir(parents=True, exist_ok=True)
            (d / "s1.json").write_text("{broken")  # json.load raises → continue
            self.assertIsNone(bs.find_recent_lock(cwd))

    # ── Hook scripts: outer except Exception: pass ────────────────────────────

    def test_pre_tool_use_inner_exception_suppressed(self):
        with tempfile.TemporaryDirectory() as cwd:
            _make_lock(cwd, "s1", "topic")
            with patch("on_pre_tool_use.read_lock", side_effect=RuntimeError("boom")):
                out = _call_hook(on_pre_tool_use, {
                    "session_id": "s1", "cwd": str(cwd), "tool_name": "Edit",
                })
            self.assertEqual(out.strip(), "")  # fail open — no output

    def test_user_prompt_inner_exception_suppressed(self):
        with tempfile.TemporaryDirectory() as cwd:
            _make_lock(cwd, "s1", "topic")
            with patch("on_user_prompt.read_lock", side_effect=RuntimeError("boom")):
                out = _call_hook(on_user_prompt, {
                    "session_id": "s1", "cwd": str(cwd),
                })
            self.assertEqual(out.strip(), "")

    def test_session_start_inner_exception_suppressed(self):
        with tempfile.TemporaryDirectory() as cwd:
            _make_lock(cwd, "s1", "topic")
            with patch("on_session_start.read_lock", side_effect=RuntimeError("boom")):
                out = _call_hook(on_session_start, {
                    "session_id": "s1", "cwd": str(cwd), "source": "compact",
                })
            self.assertEqual(out.strip(), "")

    # ── activate / deactivate: except Exception paths ─────────────────────────

    def test_activate_exception_returns_error_code(self):
        with tempfile.TemporaryDirectory() as cwd:
            buf = io.StringIO()
            env = {"CLAUDE_CWD": str(cwd), "CLAUDE_SESSION_ID": "s1"}
            with patch("activate.write_lock", side_effect=RuntimeError("boom")):
                with redirect_stdout(buf):
                    rc = activate_mod.main(argv=["activate.py", "topic"], env=env)
            self.assertEqual(rc, 1)

    def test_deactivate_exception_returns_error_code(self):
        with tempfile.TemporaryDirectory() as cwd:
            _make_lock(cwd, "s1", "topic")
            buf = io.StringIO()
            env = {"CLAUDE_CWD": str(cwd), "CLAUDE_SESSION_ID": "s1"}
            with patch("deactivate.read_lock", side_effect=RuntimeError("boom")):
                with redirect_stdout(buf):
                    rc = deactivate_mod.main(env=env, handoff="")
            self.assertEqual(rc, 1)


# ── Tests: opencode on_pre_tool_use ───────────────────────────────────────────

class TestOpenCodePreToolUse(unittest.TestCase):
    """OpenCode adapter: plain-text deny reason on stdout (non-empty = block)."""

    def _run(self, cwd, session_id, tool_name):
        return _call_hook(oc_pre_tool_use, {
            "session_id": session_id, "cwd": str(cwd), "tool_name": tool_name,
        })

    def test_edit_blocked_when_active(self):
        with tempfile.TemporaryDirectory() as cwd:
            _make_lock(cwd, "s1", "my topic")
            out = self._run(cwd, "s1", "edit")
            self.assertIn("blocked", out.lower())
            self.assertIn("my topic", out)

    def test_patch_blocked_when_active(self):
        with tempfile.TemporaryDirectory() as cwd:
            _make_lock(cwd, "s1", "topic")
            self.assertIn("blocked", self._run(cwd, "s1", "patch").lower())

    def test_write_allowed_even_when_active(self):
        with tempfile.TemporaryDirectory() as cwd:
            _make_lock(cwd, "s1", "topic")
            self.assertEqual(self._run(cwd, "s1", "write").strip(), "")

    def test_bash_allowed_even_when_active(self):
        with tempfile.TemporaryDirectory() as cwd:
            _make_lock(cwd, "s1", "topic")
            self.assertEqual(self._run(cwd, "s1", "bash").strip(), "")

    def test_edit_allowed_when_no_lock(self):
        with tempfile.TemporaryDirectory() as cwd:
            self.assertEqual(self._run(cwd, "s-none", "edit").strip(), "")

    def test_expired_lock_allows_edit(self):
        with tempfile.TemporaryDirectory() as cwd:
            _make_lock(cwd, "s-exp", "topic", hours_ago=9)
            self.assertEqual(self._run(cwd, "s-exp", "edit").strip(), "")

    def test_drift_log_appended_on_deny(self):
        with tempfile.TemporaryDirectory() as cwd:
            _make_lock(cwd, "s1", "log topic")
            self._run(cwd, "s1", "edit")
            log = Path(cwd) / ".claude" / "brainstorm" / "drift-log.jsonl"
            record = json.loads(log.read_text().strip())
            self.assertEqual(record["tool_name"], "edit")
            self.assertEqual(record["topic"], "log topic")

    def test_drift_log_post_compaction_flag(self):
        with tempfile.TemporaryDirectory() as cwd:
            _make_lock(cwd, "s1", "topic")
            bs.set_compact_flag(cwd, "s1")
            self._run(cwd, "s1", "patch")
            log = Path(cwd) / ".claude" / "brainstorm" / "drift-log.jsonl"
            self.assertTrue(json.loads(log.read_text().strip())["post_compaction"])

    def test_corrupt_lock_treated_as_absent(self):
        with tempfile.TemporaryDirectory() as cwd:
            d = _locks_dir(cwd)
            d.mkdir(parents=True, exist_ok=True)
            (d / "s1.json").write_text("{broken")
            self.assertEqual(self._run(cwd, "s1", "edit").strip(), "")

    def test_empty_session_id_allows_through(self):
        with tempfile.TemporaryDirectory() as cwd:
            out = _call_hook(oc_pre_tool_use, {
                "session_id": "", "cwd": str(cwd), "tool_name": "edit",
            })
            self.assertEqual(out.strip(), "")

    def test_garbage_stdin_exits_clean(self):
        self.assertEqual(_call_hook_raw(oc_pre_tool_use, "not json {{").strip(), "")

    def test_inner_exception_suppressed(self):
        with tempfile.TemporaryDirectory() as cwd:
            _make_lock(cwd, "s1", "topic")
            with patch.object(oc_pre_tool_use, "read_lock", side_effect=RuntimeError("boom")):
                out = self._run(cwd, "s1", "edit")
            self.assertEqual(out.strip(), "")


# ── Tests: opencode on_user_prompt ────────────────────────────────────────────

class TestOpenCodeUserPrompt(unittest.TestCase):

    def _run(self, cwd, session_id):
        return _call_hook(oc_user_prompt, {"session_id": session_id, "cwd": str(cwd)})

    def test_reminder_injected_when_active(self):
        with tempfile.TemporaryDirectory() as cwd:
            _make_lock(cwd, "s1", "cool topic")
            out = self._run(cwd, "s1")
            self.assertIn("BRAINSTORM MODE ACTIVE", out)
            self.assertIn("cool topic", out)

    def test_no_output_when_inactive(self):
        with tempfile.TemporaryDirectory() as cwd:
            self.assertEqual(self._run(cwd, "s-none").strip(), "")

    def test_expired_lock_announces_expiry(self):
        with tempfile.TemporaryDirectory() as cwd:
            _make_lock(cwd, "s1", "old topic", hours_ago=9)
            out = self._run(cwd, "s1")
            self.assertIn("expired", out.lower())

    def test_escalated_reminder_after_threshold(self):
        with tempfile.TemporaryDirectory() as cwd:
            lock = bs.write_lock(cwd, "s1", "topic")
            for _ in range(bs.ESCALATION_THRESHOLD):
                bs.append_drift_log(cwd, "s1", "topic", "edit", lock["created_at"], False)
            self.assertIn("ATTENTION", self._run(cwd, "s1"))

    def test_actionable_lock_shows_actionable_reminder(self):
        with tempfile.TemporaryDirectory() as cwd:
            bs.write_lock(cwd, "s1", "ship it", "actionable")
            self.assertIn("(actionable)", self._run(cwd, "s1"))

    def test_pending_lock_claimed_and_reminder_shown(self):
        with tempfile.TemporaryDirectory() as cwd:
            bs.write_pending_lock(cwd, "pending topic")
            out = self._run(cwd, "real-session")
            self.assertIn("pending topic", out)
            self.assertTrue((_locks_dir(cwd) / "real-session.json").exists())

    def test_empty_session_id_no_output(self):
        with tempfile.TemporaryDirectory() as cwd:
            self.assertEqual(_call_hook(oc_user_prompt, {"session_id": "", "cwd": str(cwd)}).strip(), "")

    def test_garbage_stdin_exits_clean(self):
        self.assertEqual(_call_hook_raw(oc_user_prompt, "not json").strip(), "")

    def test_inner_exception_suppressed(self):
        with tempfile.TemporaryDirectory() as cwd:
            _make_lock(cwd, "s1", "topic")
            with patch.object(oc_user_prompt, "read_lock", side_effect=RuntimeError("boom")):
                self.assertEqual(self._run(cwd, "s1").strip(), "")


# ── Tests: opencode on_session_start ──────────────────────────────────────────

class TestOpenCodeSessionStart(unittest.TestCase):

    def _run(self, cwd, session_id, source):
        return _call_hook(oc_session_start, {
            "session_id": session_id, "cwd": str(cwd), "source": source,
        })

    def test_compact_reinjects_anchor(self):
        with tempfile.TemporaryDirectory() as cwd:
            _make_lock(cwd, "s1", "compact topic")
            out = self._run(cwd, "s1", "compact")
            self.assertIn("still active", out)
            self.assertIn("compact topic", out)

    def test_compact_sets_flag(self):
        with tempfile.TemporaryDirectory() as cwd:
            _make_lock(cwd, "s1", "topic")
            self._run(cwd, "s1", "compact")
            self.assertTrue((_locks_dir(cwd) / "s1.compact").exists())

    def test_compact_no_output_when_inactive(self):
        with tempfile.TemporaryDirectory() as cwd:
            self.assertEqual(self._run(cwd, "s1", "compact").strip(), "")

    def test_non_compact_source_no_output(self):
        with tempfile.TemporaryDirectory() as cwd:
            _make_lock(cwd, "s1", "topic")
            self.assertEqual(self._run(cwd, "s1", "other").strip(), "")

    def test_empty_session_id_no_output(self):
        with tempfile.TemporaryDirectory() as cwd:
            out = _call_hook(oc_session_start, {
                "session_id": "", "cwd": str(cwd), "source": "compact",
            })
            self.assertEqual(out.strip(), "")

    def test_garbage_stdin_exits_clean(self):
        self.assertEqual(_call_hook_raw(oc_session_start, "not json").strip(), "")

    def test_inner_exception_suppressed(self):
        with tempfile.TemporaryDirectory() as cwd:
            _make_lock(cwd, "s1", "topic")
            with patch.object(oc_session_start, "read_lock", side_effect=RuntimeError("boom")):
                self.assertEqual(self._run(cwd, "s1", "compact").strip(), "")


# ── Tests: agent-neutral env vars (BRAINSTORM_* takes precedence) ──────────────

class TestAgentNeutralEnv(unittest.TestCase):

    def test_activate_reads_brainstorm_env(self):
        with tempfile.TemporaryDirectory() as cwd:
            buf = io.StringIO()
            env = {"BRAINSTORM_CWD": str(cwd), "BRAINSTORM_SESSION_ID": "oc-sess"}
            with redirect_stdout(buf):
                rc = activate_mod.main(argv=["activate.py", "neutral topic"], env=env)
            self.assertEqual(rc, 0)
            data = json.loads((_locks_dir(cwd) / "oc-sess.json").read_text())
            self.assertEqual(data["topic"], "neutral topic")

    def test_deactivate_reads_brainstorm_env(self):
        with tempfile.TemporaryDirectory() as cwd:
            _make_lock(cwd, "oc-sess", "topic")
            buf = io.StringIO()
            env = {"BRAINSTORM_CWD": str(cwd), "BRAINSTORM_SESSION_ID": "oc-sess"}
            with redirect_stdout(buf):
                rc = deactivate_mod.main(env=env)
            self.assertEqual(rc, 0)
            self.assertFalse((_locks_dir(cwd) / "oc-sess.json").exists())


# ── Tests: reminder escalation ────────────────────────────────────────────────

class TestReminderEscalation(unittest.TestCase):

    def test_reminder_normal_below_threshold(self):
        out = bs.get_reminder("topic", bs.ESCALATION_THRESHOLD - 1)
        self.assertIn("BRAINSTORM MODE ACTIVE", out)
        self.assertNotIn("ATTENTION", out)

    def test_reminder_default_count_is_zero(self):
        self.assertNotIn("ATTENTION", bs.get_reminder("topic"))

    def test_reminder_escalates_at_threshold(self):
        out = bs.get_reminder("topic", bs.ESCALATION_THRESHOLD)
        self.assertIn("ATTENTION", out)
        self.assertIn(str(bs.ESCALATION_THRESHOLD), out)
        self.assertIn("BRAINSTORM MODE ACTIVE", out)  # full reminder still present

    def test_actionable_reminder_differs_from_divergent(self):
        out = bs.get_reminder("topic", mode="actionable")
        self.assertIn("(actionable)", out)
        self.assertIn("first", out.lower())  # smallest-first-step guidance
        self.assertNotEqual(out, bs.get_reminder("topic"))

    def test_actionable_reminder_escalates_too(self):
        out = bs.get_reminder("topic", bs.ESCALATION_THRESHOLD, "actionable")
        self.assertIn("ATTENTION", out)
        self.assertIn("(actionable)", out)

    def test_unknown_mode_falls_back_to_divergent_reminder(self):
        self.assertEqual(bs.get_reminder("topic", mode="bogus"), bs.get_reminder("topic"))

    def test_count_session_drift_no_log(self):
        with tempfile.TemporaryDirectory() as cwd:
            self.assertEqual(bs.count_session_drift(cwd, "s1"), 0)

    def test_count_session_drift_filters_by_session(self):
        with tempfile.TemporaryDirectory() as cwd:
            lock = bs.write_lock(cwd, "s1", "t")
            bs.append_drift_log(cwd, "s1", "t", "Edit", lock["created_at"], False)
            bs.append_drift_log(cwd, "s1", "t", "Edit", lock["created_at"], False)
            bs.append_drift_log(cwd, "other", "t", "Edit", lock["created_at"], False)
            self.assertEqual(bs.count_session_drift(cwd, "s1"), 2)

    def test_count_session_drift_skips_blank_and_corrupt(self):
        with tempfile.TemporaryDirectory() as cwd:
            bs._ensure_dirs(cwd)
            p = Path(bs._drift_log_path(cwd))
            p.write_text('\n{bad json\n{"session_id": "s1"}\n{"session_id": "z"}\n')
            self.assertEqual(bs.count_session_drift(cwd, "s1"), 1)

    def test_count_session_drift_oserror_suppressed(self):
        with tempfile.TemporaryDirectory() as cwd:
            bs._ensure_dirs(cwd)
            drift = str(bs._drift_log_path(cwd))
            Path(drift).write_text('{"session_id": "s1"}\n')
            real_open = builtins.open
            def fake_open(f, *a, **kw):
                if str(f) == drift:
                    raise OSError("perm")
                return real_open(f, *a, **kw)
            with patch("builtins.open", side_effect=fake_open):
                self.assertEqual(bs.count_session_drift(cwd, "s1"), 0)


# ── Tests: loud TTL expiry ────────────────────────────────────────────────────

class TestExpiryNotice(unittest.TestCase):

    def test_read_lock_writes_expiry_marker(self):
        with tempfile.TemporaryDirectory() as cwd:
            _make_lock(cwd, "s1", "old topic", hours_ago=9)
            self.assertIsNone(bs.read_lock(cwd, "s1"))
            marker = _locks_dir(cwd) / "s1.expired"
            self.assertTrue(marker.exists())
            self.assertEqual(marker.read_text(), "old topic")

    def test_pop_expiry_notice_returns_and_clears(self):
        with tempfile.TemporaryDirectory() as cwd:
            bs._ensure_dirs(cwd)
            bs._mark_expired(cwd, "s1", "the topic")
            self.assertEqual(bs.pop_expiry_notice(cwd, "s1"), "the topic")
            self.assertFalse((_locks_dir(cwd) / "s1.expired").exists())
            # one-shot: second pop returns None
            self.assertIsNone(bs.pop_expiry_notice(cwd, "s1"))

    def test_pop_expiry_notice_none_when_absent(self):
        with tempfile.TemporaryDirectory() as cwd:
            self.assertIsNone(bs.pop_expiry_notice(cwd, "nope"))

    def test_get_expiry_notice_contains_topic(self):
        notice = bs.get_expiry_notice("my topic")
        self.assertIn("expired", notice.lower())
        self.assertIn("my topic", notice)

    def test_mark_expired_oserror_suppressed(self):
        with tempfile.TemporaryDirectory() as cwd:
            bs._ensure_dirs(cwd)
            exp = str(bs._expiry_path(cwd, "s1"))
            real_open = builtins.open
            def fake_open(f, *a, **kw):
                if str(f) == exp:
                    raise OSError("perm")
                return real_open(f, *a, **kw)
            with patch("builtins.open", side_effect=fake_open):
                bs._mark_expired(cwd, "s1", "topic")  # must not raise

    def test_pop_expiry_read_oserror_yields_empty(self):
        with tempfile.TemporaryDirectory() as cwd:
            bs._ensure_dirs(cwd)
            exp = str(bs._expiry_path(cwd, "s1"))
            Path(exp).write_text("topic")
            real_open = builtins.open
            def fake_open(f, *a, **kw):
                if str(f) == exp:
                    raise OSError("perm")
                return real_open(f, *a, **kw)
            with patch("builtins.open", side_effect=fake_open):
                self.assertEqual(bs.pop_expiry_notice(cwd, "s1"), "")

    def test_pop_expiry_remove_oserror_suppressed(self):
        with tempfile.TemporaryDirectory() as cwd:
            bs._ensure_dirs(cwd)
            bs._mark_expired(cwd, "s1", "topic")
            with patch.object(bs.os, "remove", side_effect=OSError("perm")):
                self.assertEqual(bs.pop_expiry_notice(cwd, "s1"), "topic")


# ── Tests: session archive (transcript capture) ───────────────────────────────

class TestSessionArchive(unittest.TestCase):

    def _sessions(self, cwd):
        return Path(cwd) / ".claude" / "brainstorm" / "sessions"

    def test_slug(self):
        self.assertEqual(bs._slug("Caching Strategy!"), "caching-strategy")
        self.assertEqual(bs._slug(""), "session")
        self.assertEqual(bs._slug("@@@"), "session")
        self.assertLessEqual(len(bs._slug("x" * 200)), 60)

    def test_archive_writes_record_with_handoff_and_drift(self):
        with tempfile.TemporaryDirectory() as cwd:
            lock = bs.write_lock(cwd, "s1", "caching strategy")
            bs.append_drift_log(cwd, "s1", "caching strategy", "Edit", lock["created_at"], False)
            bs.append_drift_log(cwd, "s1", "caching strategy", "MultiEdit", lock["created_at"], True)
            path = bs.archive_session(cwd, "s1", "## Clusters\n- cluster A")
            self.assertIsNotNone(path)
            text = Path(path).read_text()
            self.assertIn("caching strategy", text)
            self.assertIn("cluster A", text)
            self.assertIn("Blocked edit attempts:** 2", text)
            self.assertIn("MultiEdit", text)
            self.assertIn("Duration:", text)
            self.assertTrue(Path(path).name.endswith("-caching-strategy.md"))

    def test_archive_no_handoff_uses_placeholder(self):
        with tempfile.TemporaryDirectory() as cwd:
            bs.write_lock(cwd, "s1", "topic")
            path = bs.archive_session(cwd, "s1", "")
            self.assertIn("no handoff text", Path(path).read_text())

    def test_archive_no_drift_shows_none(self):
        with tempfile.TemporaryDirectory() as cwd:
            bs.write_lock(cwd, "s1", "topic")
            path = bs.archive_session(cwd, "s1", "handoff")
            text = Path(path).read_text()
            self.assertIn("Blocked edit attempts:** 0", text)
            self.assertIn("no blocked edit attempts", text.lower())

    def test_archive_records_mode(self):
        with tempfile.TemporaryDirectory() as cwd:
            bs.write_lock(cwd, "s1", "topic", "actionable")
            path = bs.archive_session(cwd, "s1", "plan")
            self.assertIn("**Mode:** actionable", Path(path).read_text())

    def test_archive_no_lock_returns_none(self):
        with tempfile.TemporaryDirectory() as cwd:
            self.assertIsNone(bs.archive_session(cwd, "nope", "handoff"))

    def test_archive_exception_returns_none(self):
        with tempfile.TemporaryDirectory() as cwd:
            bs.write_lock(cwd, "s1", "topic")
            with patch.object(bs.os, "makedirs", side_effect=OSError("perm")):
                self.assertIsNone(bs.archive_session(cwd, "s1", "handoff"))


# ── Tests: deactivate archives the session ────────────────────────────────────

class TestDeactivateArchive(unittest.TestCase):

    def _sessions(self, cwd):
        return Path(cwd) / ".claude" / "brainstorm" / "sessions"

    def test_deactivate_archives_with_handoff(self):
        with tempfile.TemporaryDirectory() as cwd:
            bs.write_lock(cwd, "s1", "topic")
            env = {"BRAINSTORM_CWD": cwd, "BRAINSTORM_SESSION_ID": "s1"}
            buf = io.StringIO()
            with redirect_stdout(buf):
                rc = deactivate_mod.main(env=env, handoff="MY HANDOFF")
            self.assertEqual(rc, 0)
            self.assertIn("archived", buf.getvalue().lower())
            self.assertFalse((_locks_dir(cwd) / "s1.json").exists())
            files = list(self._sessions(cwd).glob("*.md"))
            self.assertEqual(len(files), 1)
            self.assertIn("MY HANDOFF", files[0].read_text())

    def test_deactivate_reads_handoff_from_stdin(self):
        with tempfile.TemporaryDirectory() as cwd:
            bs.write_lock(cwd, "s1", "topic")
            env = {"BRAINSTORM_CWD": cwd, "BRAINSTORM_SESSION_ID": "s1"}
            buf = io.StringIO()
            with patch.object(deactivate_mod.sys, "stdin", io.StringIO("piped handoff")):
                with redirect_stdout(buf):
                    rc = deactivate_mod.main(env=env)  # handoff=None → read stdin
            self.assertEqual(rc, 0)
            files = list(self._sessions(cwd).glob("*.md"))
            self.assertIn("piped handoff", files[0].read_text())

    def test_read_stdin_handoff_isatty_returns_empty(self):
        class _TTY:
            def isatty(self):
                return True
            def read(self):  # pragma: no cover - must not be called
                return "X"
        with patch.object(deactivate_mod.sys, "stdin", _TTY()):
            self.assertEqual(deactivate_mod._read_stdin_handoff(), "")

    def test_read_stdin_handoff_reads_content(self):
        with patch.object(deactivate_mod.sys, "stdin", io.StringIO("hello handoff")):
            self.assertEqual(deactivate_mod._read_stdin_handoff(), "hello handoff")

    def test_read_stdin_handoff_exception_returns_empty(self):
        class _Bad:
            def isatty(self):
                raise OSError("no stdin")
        with patch.object(deactivate_mod.sys, "stdin", _Bad()):
            self.assertEqual(deactivate_mod._read_stdin_handoff(), "")


# ── Subprocess smoke tests ────────────────────────────────────────────────────
# Verify scripts actually work as standalone CLI programs.

class TestSubprocessSmoke(unittest.TestCase):

    def _run_script(self, path, stdin_data, extra_env=None):
        env = {**os.environ}
        if extra_env:
            env.update(extra_env)
        r = subprocess.run(
            [sys.executable, str(path)],
            input=json.dumps(stdin_data) if isinstance(stdin_data, dict) else stdin_data,
            capture_output=True, text=True, env=env,
        )
        return r.stdout, r.returncode

    def test_pre_tool_use_blocks_edit_subprocess(self):
        with tempfile.TemporaryDirectory() as cwd:
            _make_lock(cwd, "s1", "smoke topic")
            out, rc = self._run_script(
                HOOKS / "on_pre_tool_use.py",
                {"session_id": "s1", "cwd": cwd, "tool_name": "Edit"},
            )
            self.assertEqual(rc, 0)
            self.assertEqual(json.loads(out)["hookSpecificOutput"]["permissionDecision"], "deny")

    def test_user_prompt_subprocess(self):
        with tempfile.TemporaryDirectory() as cwd:
            _make_lock(cwd, "s1", "smoke")
            out, rc = self._run_script(
                HOOKS / "on_user_prompt.py",
                {"session_id": "s1", "cwd": cwd},
            )
            self.assertEqual(rc, 0)
            self.assertIn("BRAINSTORM MODE ACTIVE", out)

    def test_garbage_stdin_subprocess_exits_zero(self):
        for script in [HOOKS / "on_pre_tool_use.py",
                       HOOKS / "on_user_prompt.py",
                       HOOKS / "on_session_start.py"]:
            out, rc = self._run_script(script, "garbage {{ not json")
            self.assertEqual(rc, 0, f"{script.name} should exit 0 on garbage input")
            self.assertEqual(out.strip(), "")

    def test_activate_subprocess(self):
        with tempfile.TemporaryDirectory() as cwd:
            r = subprocess.run(
                [sys.executable, str(CORE / "activate.py"), "smoke topic"],
                capture_output=True, text=True,
                env={**os.environ, "CLAUDE_CWD": cwd, "CLAUDE_SESSION_ID": "s1"},
            )
            self.assertEqual(r.returncode, 0)
            data = json.loads((_locks_dir(cwd) / "s1.json").read_text())
            self.assertEqual(data["topic"], "smoke topic")

    def test_opencode_pre_tool_use_blocks_edit_subprocess(self):
        with tempfile.TemporaryDirectory() as cwd:
            _make_lock(cwd, "s1", "smoke topic")
            out, rc = self._run_script(
                OPENCODE_HOOKS / "on_pre_tool_use.py",
                {"session_id": "s1", "cwd": cwd, "tool_name": "edit"},
            )
            self.assertEqual(rc, 0)
            self.assertIn("blocked", out.lower())

    def test_opencode_user_prompt_subprocess(self):
        with tempfile.TemporaryDirectory() as cwd:
            _make_lock(cwd, "s1", "smoke")
            out, rc = self._run_script(
                OPENCODE_HOOKS / "on_user_prompt.py",
                {"session_id": "s1", "cwd": cwd},
            )
            self.assertEqual(rc, 0)
            self.assertIn("BRAINSTORM MODE ACTIVE", out)


# ── Entry point ───────────────────────────────────────────────────────────────

if __name__ == "__main__":
    unittest.main(verbosity=2)
