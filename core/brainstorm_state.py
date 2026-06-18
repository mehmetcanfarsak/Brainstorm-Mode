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

# Shared conversational discipline, re-injected with every reminder. Targets two
# real failure modes: rapid-fire questioning, and boxing the user into narrow choices.
_PACING = (
    "Pace it — ask at most ONE question per reply and let the user breathe; never stack "
    "several questions or interrogate. Whenever you offer choices, always include an "
    "open-ended option (e.g. \"Open — let's explore\") so the user is never boxed into "
    "your framing. "
)

REMINDER_TEMPLATE = (
    'BRAINSTORM MODE ACTIVE — topic: "{topic}". Brainstorm as a conversation, not a report: '
    'offer a thought or two, then ask a question back — including open-ended ones. '
    + _PACING +
    'Do not dump a full structured list of framings/ideas at once. Diverge, don\'t converge; '
    'no code, no implementation detail. Use AskUserQuestion to let the user pick a direction. '
    'Editing tools (Edit, MultiEdit, NotebookEdit) are blocked; Bash and Write are allowed. '
    'Exit with /brainstorm-done.'
)

ACTIONABLE_REMINDER_TEMPLATE = (
    'BRAINSTORM MODE ACTIVE (actionable) — topic: "{topic}". Brainstorm as a conversation, '
    'not a report — a thought or two, then a question back — but aim every idea at action: '
    'each one should be concrete, scoped, and feasible, with a smallest-first-step and its '
    'main blocker named. Filter for feasibility; prefer ideas the user could start this week. '
    'Probe constraints (time, budget, skills, dependencies) before going wide. '
    + _PACING +
    'Use AskUserQuestion to let the user pick what to make actionable next. '
    'Still no code and no file edits: editing tools (Edit, MultiEdit, NotebookEdit) are '
    'blocked; Bash and Write are allowed. Exit with /brainstorm-done.'
)

ACADEMIC_REMINDER_TEMPLATE = (
    'BRAINSTORM MODE ACTIVE (academic) — topic: "{topic}". This is a literature-grounded '
    'research brainstorm. Ground every thread in the published literature: search for relevant '
    'work BEFORE weighing in — unprompted, every time, even just to answer a question — and '
    'shape the discussion around what is actually published. Anchor each idea to specific '
    'papers (authors, venue, year); separate established findings from open gaps and say which '
    'is which. SOURCE QUALITY POLICY (non-negotiable): cite only peer-reviewed work from '
    'reputable venues as primary references{venues_clause}. If the user names another venue as '
    'acceptable, honor it immediately and persist it (run activate.py --add-venues "<venue>") so '
    'this list keeps including it for the rest of the session. Preprints on arXiv are acceptable '
    'ONLY if they have been accepted to such a venue or are clearly from a credible group and '
    'directly relevant. Do NOT cite workshop papers, non-peer-reviewed preprints, or low-tier '
    'journals as primary references — vet every source against this policy before citing it. '
    'CITATION HONESTY: never call a paper influential, seminal, well-known, or state-of-the-art '
    'unless you verified that this session; say whether each claim comes from a search you just '
    'ran or from prior knowledge, and when a source\'s venue or impact is unverified, label it '
    '(e.g. "venue unverified") rather than presenting it as solid. '
    + _PACING +
    'Brainstorm as a conversation: a thought or two, then a question back. No code, no file '
    'edits: editing tools (Edit, MultiEdit, NotebookEdit) are blocked; Bash and Write are '
    'allowed (use Write to save reading lists). Exit with /brainstorm-done.'
)

# Brainstorm flavors. "divergent" is classic /brainstorm; "actionable" is
# /brainstorm-actionable (feasibility-filtered, next-step-oriented ideation);
# "academic" is /brainstorm-academic (literature-grounded, venue-vetted).
MODES = ("divergent", "actionable", "academic")
DEFAULT_MODE = "divergent"

# After this many blocked edit attempts in a session, the per-prompt reminder is
# prefixed with a sterner escalation line (the model keeps trying to edit anyway).
ESCALATION_THRESHOLD = 3

ESCALATION_TEMPLATE = (
    "ATTENTION: you have tried to use a blocked editing tool {n} times this session. "
    "Every attempt was denied and will keep being denied while brainstorm mode is active. "
    "Stop trying to edit — stay in ideation, or tell the user to run /brainstorm-done.\n\n"
)

EXPIRY_TEMPLATE = (
    'Brainstorm mode on "{topic}" has expired (reached its {hours}-hour limit). '
    "File-editing tools are unblocked again. "
    "Run /brainstorm {topic} to resume, or just continue normally."
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

def _expiry_path(cwd, session_id):
    return os.path.join(_locks_dir(cwd), f"{session_id}.expired")

def _sessions_dir(cwd):
    return os.path.join(cwd, ".claude", "brainstorm", "sessions")

def _ensure_dirs(cwd):
    os.makedirs(_locks_dir(cwd), exist_ok=True)

def _slug(topic):
    """Filesystem-safe slug for a topic; never empty."""
    cleaned = "".join(c if c.isalnum() else "-" for c in topic.lower())
    parts = [p for p in cleaned.split("-") if p]
    return ("-".join(parts))[:60] or "session"

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

def write_lock(cwd, session_id, topic, mode=DEFAULT_MODE, venues=None):
    """Write a session lock atomically. Returns the lock dict.

    `venues` (academic mode) is a free-text allowed-venue list that the
    per-prompt reminder re-injects every turn, so it cannot decay or be skipped.
    """
    _ensure_dirs(cwd)
    data = {
        "session_id": session_id,
        "topic": topic,
        "mode": mode if mode in MODES else DEFAULT_MODE,
        "created_at": _now_utc().isoformat(),
        "ttl_hours": TTL_HOURS,
    }
    if venues:
        data["venues"] = venues
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
            # TTL reached: leave a tombstone so the next prompt can announce the
            # expiry, then delete the lock (editing silently unblocks otherwise).
            _mark_expired(cwd, session_id, data.get("topic", ""))
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


def write_pending_lock(cwd, topic, mode=DEFAULT_MODE, venues=None):
    """Write a pending lock when session_id is not yet available."""
    _ensure_dirs(cwd)
    data = {
        "session_id": "_pending",
        "topic": topic,
        "mode": mode if mode in MODES else DEFAULT_MODE,
        "created_at": _now_utc().isoformat(),
        "ttl_hours": TTL_HOURS,
    }
    if venues:
        data["venues"] = venues
    _atomic_write(_pending_path(cwd), data)


def claim_pending_lock(cwd, session_id):
    """Promote a pending lock to a real session lock (mode and venues preserved).

    Returns the topic string if a pending lock was found, else None.
    """
    path = _pending_path(cwd)
    if not os.path.exists(path):
        return None
    try:
        with open(path) as f:
            data = json.load(f)
        topic = data.get("topic", "")
        write_lock(cwd, session_id, topic,
                   data.get("mode", DEFAULT_MODE), data.get("venues"))
        os.remove(path)
        return topic
    except (json.JSONDecodeError, KeyError, OSError):
        try:
            os.remove(path)
        except OSError:
            pass
        return None


def update_venues(cwd, session_id, add):
    """Merge `add` into the active session's allowed-venue list (academic mode).

    Lets the user broaden the venue policy mid-session; the merged list is what the
    per-prompt reminder re-injects from then on. Preserves created_at (does not
    reset the TTL). Returns the merged venue string, or None if no active lock.
    """
    lock = read_lock(cwd, session_id)
    if not lock:
        return None
    parts, seen = [], set()
    for chunk in (lock.get("venues", ""), add):
        for p in chunk.split(","):
            p = p.strip()
            if p and p.lower() not in seen:
                parts.append(p)
                seen.add(p.lower())
    merged = ", ".join(parts)
    data = dict(lock)
    data["venues"] = merged
    _atomic_write(_lock_path(cwd, session_id), data)
    return merged


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


def get_reminder(topic, drift_count=0, mode=DEFAULT_MODE, venues=None):
    """The per-prompt reminder for the given brainstorm mode. Escalates once a
    session has accumulated ESCALATION_THRESHOLD or more blocked edit attempts."""
    if mode == "academic":
        clause = f" (allowed venues: {venues})" if venues else ""
        reminder = ACADEMIC_REMINDER_TEMPLATE.format(topic=topic, venues_clause=clause)
    elif mode == "actionable":
        reminder = ACTIONABLE_REMINDER_TEMPLATE.format(topic=topic)
    else:
        reminder = REMINDER_TEMPLATE.format(topic=topic)
    if drift_count >= ESCALATION_THRESHOLD:
        return ESCALATION_TEMPLATE.format(n=drift_count) + reminder
    return reminder


def _mark_expired(cwd, session_id, topic):
    """Best-effort tombstone recording that a lock just hit its TTL."""
    try:
        with open(_expiry_path(cwd, session_id), "w") as f:
            f.write(topic)
    except OSError:
        pass


def pop_expiry_notice(cwd, session_id):
    """If a lock for this session just expired, return its topic and clear the
    tombstone (one-shot). Otherwise return None."""
    path = _expiry_path(cwd, session_id)
    if not os.path.exists(path):
        return None
    try:
        with open(path) as f:
            topic = f.read()
    except OSError:
        topic = ""
    try:
        os.remove(path)
    except OSError:
        pass
    return topic


def get_expiry_notice(topic):
    return EXPIRY_TEMPLATE.format(topic=topic, hours=TTL_HOURS)


def _session_drift_records(cwd, session_id):
    """All drift-log records for this session (list of dicts). Best-effort."""
    path = _drift_log_path(cwd)
    records = []
    if not os.path.exists(path):
        return records
    try:
        with open(path) as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    rec = json.loads(line)
                except (json.JSONDecodeError, ValueError):
                    continue
                if rec.get("session_id") == session_id:
                    records.append(rec)
    except OSError:
        pass
    return records


def count_session_drift(cwd, session_id):
    """Number of blocked-edit attempts recorded for this session."""
    return len(_session_drift_records(cwd, session_id))


def archive_session(cwd, session_id, handoff_text=""):
    """Write a durable markdown record of the session to sessions/<stamp>-<slug>.md.

    Captures topic, start/end/duration, the convergence handoff (if provided),
    and every blocked-edit (drift) event. Returns the path, or None if there is
    no active lock to archive. Best-effort — never raises.
    """
    try:
        lock = read_lock(cwd, session_id)
        if not lock:
            return None

        topic = lock.get("topic", "")
        created = lock["created_at"]
        now = _now_utc()
        duration_min = round((now - _parse_iso(created)).total_seconds() / 60.0, 1)
        records = _session_drift_records(cwd, session_id)

        sessions = _sessions_dir(cwd)
        os.makedirs(sessions, exist_ok=True)
        path = os.path.join(sessions, f"{now.strftime('%Y%m%d-%H%M%S')}-{_slug(topic)}.md")

        handoff = handoff_text.strip() if handoff_text else ""
        lines = [
            f"# Brainstorm session: {topic}",
            "",
            f"- **Mode:** {lock.get('mode', DEFAULT_MODE)}",
        ]
        if lock.get("venues"):
            lines.append(f"- **Allowed venues:** {lock['venues']}")
        lines += [
            f"- **Started:** {created}",
            f"- **Ended:** {now.isoformat()}",
            f"- **Duration:** {duration_min} min",
            f"- **Blocked edit attempts:** {len(records)}",
            "",
            "## Convergence handoff",
            "",
            handoff or "_(no handoff text was captured)_",
            "",
            "## Execution-drift events",
            "",
        ]
        if records:
            lines.append("| minutes in | tool | post-compaction |")
            lines.append("| --- | --- | --- |")
            for r in records:
                lines.append(
                    f"| {r.get('minutes_since_activation', '?')} "
                    f"| {r.get('tool_name', '?')} | {r.get('post_compaction', False)} |"
                )
        else:
            lines.append("_None — no blocked edit attempts this session._")
        lines.append("")

        with open(path, "w") as f:
            f.write("\n".join(lines))
        return path
    except Exception:
        return None


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
