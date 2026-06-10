"""
Shared state helpers for brainstorm-mode.
All constants live here; no config file in v1.
"""
import json
import os
import tempfile
from datetime import datetime, timedelta, timezone

# ── Constants ────────────────────────────────────────────────────────────────
TTL_HOURS = 8
CLEANUP_AGE_DAYS = 7

BLOCKED_TOOLS = frozenset({"Edit", "MultiEdit", "NotebookEdit"})

REMINDER_TEMPLATE = (
    'BRAINSTORM MODE ACTIVE — topic: "{topic}". Brainstorm as a conversation, not a report: '
    'offer a thought or two, then ask a question back — including open-ended ones. '
    'Do not dump a full structured list of framings/ideas at once. Diverge, don\'t converge; '
    'no code, no implementation detail. Use AskUserQuestion to let the user pick a direction. '
    'Editing tools (Edit, MultiEdit, NotebookEdit) are blocked; Bash and Write are allowed. '
    'Exit with /brainstorm-done.'
)

# ── Private path helpers ──────────────────────────────────────────────────────

def _locks_dir(cwd):
    return os.path.join(cwd, ".claude", "brainstorm", "locks")

def _lock_path(cwd, session_id):
    return os.path.join(_locks_dir(cwd), f"{session_id}.json")

def _pending_path(cwd):
    return os.path.join(_locks_dir(cwd), "_pending.json")

def _drift_log_path(cwd):
    return os.path.join(cwd, ".claude", "brainstorm", "drift-log.jsonl")

def _compact_flag_path(cwd, session_id):
    return os.path.join(_locks_dir(cwd), f"{session_id}.compact")

def _ensure_dirs(cwd):
    os.makedirs(_locks_dir(cwd), exist_ok=True)

def _now_utc():
    return datetime.now(timezone.utc)

def _parse_iso(s):
    return datetime.fromisoformat(s.replace("Z", "+00:00"))

def _atomic_write(path, data):
    dir_ = os.path.dirname(path)
    fd, tmp = tempfile.mkstemp(dir=dir_, suffix=".tmp")
    try:
        with os.fdopen(fd, "w") as f:
            json.dump(data, f)
        os.replace(tmp, path)
    except Exception:
        try:
            os.unlink(tmp)
        except OSError:
            pass
        raise

# ── Public API ────────────────────────────────────────────────────────────────

def write_lock(cwd, session_id, topic):
    """Write a session lock atomically. Returns the lock dict."""
    _ensure_dirs(cwd)
    data = {
        "session_id": session_id,
        "topic": topic,
        "created_at": _now_utc().isoformat(),
        "ttl_hours": TTL_HOURS,
    }
    _atomic_write(_lock_path(cwd, session_id), data)
    return data


def read_lock(cwd, session_id):
    """Return the lock dict if the session is active, else None.

    Deletes the file if expired or corrupt (opportunistic cleanup).
    """
    path = _lock_path(cwd, session_id)
    if not os.path.exists(path):
        return None
    try:
        with open(path) as f:
            data = json.load(f)
        if data.get("session_id") != session_id:
            os.remove(path)
            return None
        created = _parse_iso(data["created_at"])
        if _now_utc() > created + timedelta(hours=data.get("ttl_hours", TTL_HOURS)):
            os.remove(path)
            return None
        return data
    except (json.JSONDecodeError, KeyError, ValueError, OSError):
        try:
            os.remove(path)
        except OSError:
            pass
        return None


def delete_lock(cwd, session_id):
    """Remove the session lock and any sidecar flag."""
    for path in (_lock_path(cwd, session_id), _compact_flag_path(cwd, session_id)):
        try:
            os.remove(path)
        except OSError:
            pass


def write_pending_lock(cwd, topic):
    """Write a pending lock when session_id is not yet available."""
    _ensure_dirs(cwd)
    data = {
        "session_id": "_pending",
        "topic": topic,
        "created_at": _now_utc().isoformat(),
        "ttl_hours": TTL_HOURS,
    }
    _atomic_write(_pending_path(cwd), data)


def claim_pending_lock(cwd, session_id):
    """Promote a pending lock to a real session lock.

    Returns the topic string if a pending lock was found, else None.
    """
    path = _pending_path(cwd)
    if not os.path.exists(path):
        return None
    try:
        with open(path) as f:
            data = json.load(f)
        topic = data.get("topic", "")
        write_lock(cwd, session_id, topic)
        os.remove(path)
        return topic
    except (json.JSONDecodeError, KeyError, OSError):
        try:
            os.remove(path)
        except OSError:
            pass
        return None


def cleanup_old_locks(cwd):
    """Delete lock and flag files older than CLEANUP_AGE_DAYS. Best-effort."""
    d = _locks_dir(cwd)
    if not os.path.isdir(d):
        return
    cutoff = _now_utc() - timedelta(days=CLEANUP_AGE_DAYS)
    for fname in os.listdir(d):
        fpath = os.path.join(d, fname)
        try:
            mtime = datetime.fromtimestamp(os.path.getmtime(fpath), tz=timezone.utc)
            if mtime < cutoff:
                os.remove(fpath)
        except OSError:
            pass


def set_compact_flag(cwd, session_id):
    """Mark that a compaction event occurred for this session."""
    _ensure_dirs(cwd)
    flag = _compact_flag_path(cwd, session_id)
    try:
        with open(flag, "w"):
            pass
    except OSError:
        pass


def is_post_compact(cwd, session_id):
    return os.path.exists(_compact_flag_path(cwd, session_id))


def append_drift_log(cwd, session_id, topic, tool_name, created_at_iso, post_compact):
    """Append one JSONL record to the drift log. Best-effort — never raises."""
    try:
        _ensure_dirs(cwd)
        now = _now_utc()
        created = _parse_iso(created_at_iso)
        minutes = (now - created).total_seconds() / 60.0
        record = {
            "ts": now.isoformat(),
            "session_id": session_id,
            "topic": topic,
            "tool_name": tool_name,
            "minutes_since_activation": round(minutes, 2),
            "post_compaction": post_compact,
        }
        with open(_drift_log_path(cwd), "a") as f:
            f.write(json.dumps(record) + "\n")
    except Exception:
        pass


def get_reminder(topic):
    return REMINDER_TEMPLATE.format(topic=topic)


def find_recent_lock(cwd):
    """Scan the locks dir for any unexpired lock (any session_id).

    Used by SessionStart/resume to inform the user of a recently active session.
    Returns the first unexpired lock dict found, or None.
    """
    d = _locks_dir(cwd)
    if not os.path.isdir(d):
        return None
    now = _now_utc()
    for fname in sorted(os.listdir(d)):
        if not fname.endswith(".json") or fname.startswith("_"):
            continue
        fpath = os.path.join(d, fname)
        try:
            with open(fpath) as f:
                data = json.load(f)
            created = _parse_iso(data["created_at"])
            ttl = timedelta(hours=data.get("ttl_hours", TTL_HOURS))
            if now < created + ttl:
                return data
        except Exception:
            continue
    return None
