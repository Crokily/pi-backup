#!/usr/bin/env python3
from __future__ import annotations

import asyncio
import hashlib
import json
import os
import random
import re
import shlex
import sqlite3
import string
import threading
import time
import traceback
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from functools import partial
from html import escape
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any, Iterable
from zoneinfo import ZoneInfo

import discord
import httpx
from dotenv import load_dotenv

HEARTBEAT_OK_TOKEN = "HEARTBEAT_OK"
HEARTBEAT_MODES = {"digest", "alert", "silent"}
REPORT_COMPLEX_MARKERS = ("```", "|---", "![](", "![", "<table", "<img", "# ", "## ")


def _csv_set(name: str) -> set[str]:
    raw = os.getenv(name, "").strip()
    if not raw:
        return set()
    return {x.strip() for x in raw.split(",") if x.strip()}


def _env_bool(name: str, default: bool) -> bool:
    raw = os.getenv(name)
    if raw is None:
        return default
    return raw.strip().lower() in {"1", "true", "yes", "on"}


def _parse_duration_seconds(raw: str, *, default_unit: str = "m") -> int:
    s = (raw or "").strip().lower()
    if not s:
        raise ValueError("empty duration")
    m = re.match(r"^(\d+)\s*([smhdw]?)$", s)
    if not m:
        raise ValueError(f"invalid duration: {raw}")
    n = int(m.group(1))
    unit = m.group(2) or default_unit
    mul = {
        "s": 1,
        "m": 60,
        "h": 3600,
        "d": 86400,
        "w": 7 * 86400,
    }.get(unit)
    if mul is None:
        raise ValueError(f"unsupported unit: {unit}")
    return n * mul


def _format_duration(seconds: int) -> str:
    if seconds % 86400 == 0:
        return f"{seconds // 86400}d"
    if seconds % 3600 == 0:
        return f"{seconds // 3600}h"
    if seconds % 60 == 0:
        return f"{seconds // 60}m"
    return f"{seconds}s"


def _parse_hhmm(value: str) -> int:
    m = re.match(r"^(\d{2}):(\d{2})$", (value or "").strip())
    if not m:
        raise ValueError("time must be HH:MM")
    hh = int(m.group(1))
    mm = int(m.group(2))
    if hh < 0 or hh > 23 or mm < 0 or mm > 59:
        raise ValueError("time out of range")
    return hh * 60 + mm


def _norm_text(text: str) -> str:
    return re.sub(r"\s+", " ", (text or "")).strip()


@dataclass
class Config:
    token: str
    dm_policy: str
    require_mention: bool
    admin_user_ids: set[str]
    allowed_guild_ids: set[str]
    allowed_channel_ids: set[str]
    history_max_turns: int
    sqlite_path: str
    system_prompt: str
    backend_mode: str

    pi_bin: str
    pi_model: str
    pi_thinking: str

    openai_base_url: str
    openai_api_key: str
    openai_model: str

    agent_command: str
    max_reply_chars: int

    research_enabled: bool
    web_search_bin: str
    research_max_results: int
    research_readable_sources: int
    research_page_char_limit: int

    heartbeat_default_enabled: bool
    heartbeat_poll_seconds: int
    heartbeat_task_timeout_sec: int
    heartbeat_max_tasks_per_tick: int
    heartbeat_default_max_alerts_per_day: int
    heartbeat_default_dedupe_window_sec: int
    startup_report_enabled: bool

    report_server_enabled: bool
    report_bind: str
    report_port: int
    report_base_url: str
    report_public_host: str
    report_dir: str
    report_auto_for_research: bool
    report_auto_min_chars: int

    async_tasks_enabled: bool
    async_task_workers: int
    async_task_poll_seconds: int
    async_task_timeout_sec: int
    async_task_max_attempts: int

    @staticmethod
    def from_env() -> "Config":
        token = os.getenv("DISCORD_BOT_TOKEN", "").strip()
        if not token:
            raise RuntimeError("DISCORD_BOT_TOKEN is required")

        dm_policy = os.getenv("DM_POLICY", "pairing").strip().lower()
        if dm_policy not in {"pairing", "allowlist", "open", "disabled"}:
            raise RuntimeError("DM_POLICY must be one of: pairing|allowlist|open|disabled")

        backend_mode = os.getenv("BACKEND_MODE", "pi").strip().lower()
        if backend_mode not in {"openai", "command", "pi"}:
            raise RuntimeError("BACKEND_MODE must be openai or command or pi")

        pi_thinking = os.getenv("PI_THINKING", os.getenv("PI_THINKING_DEFAULT", "")).strip().lower()
        valid_thinking = {"", "off", "minimal", "low", "medium", "high", "xhigh"}
        if pi_thinking not in valid_thinking:
            raise RuntimeError("PI_THINKING must be one of: off|minimal|low|medium|high|xhigh")

        try:
            dedupe_window = _parse_duration_seconds(
                os.getenv("HEARTBEAT_DEFAULT_DEDUPE_WINDOW", "6h"), default_unit="m"
            )
        except ValueError as e:
            raise RuntimeError(f"invalid HEARTBEAT_DEFAULT_DEDUPE_WINDOW: {e}") from e

        return Config(
            token=token,
            dm_policy=dm_policy,
            require_mention=_env_bool("REQUIRE_MENTION", True),
            admin_user_ids=_csv_set("ADMIN_USER_IDS"),
            allowed_guild_ids=_csv_set("ALLOWED_GUILD_IDS"),
            allowed_channel_ids=_csv_set("ALLOWED_CHANNEL_IDS"),
            history_max_turns=max(1, int(os.getenv("HISTORY_MAX_TURNS", "12"))),
            sqlite_path=os.getenv("SQLITE_PATH", "./discord_agent.db").strip(),
            system_prompt=os.getenv("SYSTEM_PROMPT", "You are a helpful assistant.").strip(),
            backend_mode=backend_mode,
            pi_bin=os.getenv("PI_BIN", "pi").strip() or "pi",
            pi_model=os.getenv("PI_MODEL", os.getenv("PI_MODEL_DEFAULT", "")).strip(),
            pi_thinking=pi_thinking,
            openai_base_url=os.getenv("OPENAI_BASE_URL", "https://api.openai.com/v1").strip(),
            openai_api_key=os.getenv("OPENAI_API_KEY", "").strip(),
            openai_model=os.getenv("OPENAI_MODEL", "gpt-4.1-mini").strip(),
            agent_command=os.getenv("AGENT_COMMAND", "").strip(),
            max_reply_chars=max(200, int(os.getenv("MAX_REPLY_CHARS", "1900"))),
            research_enabled=_env_bool("RESEARCH_ENABLED", True),
            web_search_bin=os.getenv("WEB_SEARCH_BIN", "/home/ubuntu/.pi/agent/bin/web-search").strip()
            or "/home/ubuntu/.pi/agent/bin/web-search",
            research_max_results=max(1, min(10, int(os.getenv("RESEARCH_MAX_RESULTS", "5")))),
            research_readable_sources=max(0, min(5, int(os.getenv("RESEARCH_READABLE_SOURCES", "2")))),
            research_page_char_limit=max(500, min(12000, int(os.getenv("RESEARCH_PAGE_CHAR_LIMIT", "3500")))),
            heartbeat_default_enabled=_env_bool("HEARTBEAT_DEFAULT_ENABLED", False),
            heartbeat_poll_seconds=max(10, min(600, int(os.getenv("HEARTBEAT_POLL_SECONDS", "45")))),
            heartbeat_task_timeout_sec=max(30, min(1800, int(os.getenv("HEARTBEAT_TASK_TIMEOUT_SEC", "240")))),
            heartbeat_max_tasks_per_tick=max(1, min(20, int(os.getenv("HEARTBEAT_MAX_TASKS_PER_TICK", "3")))),
            heartbeat_default_max_alerts_per_day=max(
                1, min(100, int(os.getenv("HEARTBEAT_DEFAULT_MAX_ALERTS_PER_DAY", "2")))
            ),
            heartbeat_default_dedupe_window_sec=max(60, min(30 * 86400, dedupe_window)),
            startup_report_enabled=_env_bool("STARTUP_REPORT_ENABLED", True),
            report_server_enabled=_env_bool("REPORT_SERVER_ENABLED", True),
            report_bind=os.getenv("REPORT_BIND", "0.0.0.0").strip() or "0.0.0.0",
            report_port=max(1024, min(65535, int(os.getenv("REPORT_PORT", "18080")))),
            report_base_url=os.getenv("REPORT_BASE_URL", "").strip(),
            report_public_host=os.getenv("REPORT_PUBLIC_HOST", "").strip(),
            report_dir=os.getenv("REPORT_DIR", "/home/ubuntu/discord-agent/web-reports").strip()
            or "/home/ubuntu/discord-agent/web-reports",
            report_auto_for_research=_env_bool("REPORT_AUTO_FOR_RESEARCH", True),
            report_auto_min_chars=max(600, min(20000, int(os.getenv("REPORT_AUTO_MIN_CHARS", "1800")))),
            async_tasks_enabled=_env_bool("ASYNC_TASKS_ENABLED", True),
            async_task_workers=max(1, min(8, int(os.getenv("ASYNC_TASK_WORKERS", "2")))),
            async_task_poll_seconds=max(1, min(30, int(os.getenv("ASYNC_TASK_POLL_SECONDS", "2")))),
            async_task_timeout_sec=max(30, min(7200, int(os.getenv("ASYNC_TASK_TIMEOUT_SEC", "1800")))),
            async_task_max_attempts=max(1, min(5, int(os.getenv("ASYNC_TASK_MAX_ATTEMPTS", "2")))),
        )


class Store:
    def __init__(self, path: str):
        self.db = sqlite3.connect(path)
        self.db.row_factory = sqlite3.Row
        self.db.execute(
            """
            create table if not exists messages (
              id integer primary key autoincrement,
              session_key text not null,
              role text not null,
              content text not null,
              ts integer not null
            )
            """
        )
        self.db.execute(
            """
            create table if not exists allowed_users (
              channel text not null,
              user_id text not null,
              primary key(channel, user_id)
            )
            """
        )
        self.db.execute(
            """
            create table if not exists pairing_requests (
              channel text not null,
              user_id text not null,
              code text not null,
              expires_at integer not null,
              primary key(channel, user_id)
            )
            """
        )
        self.db.execute(
            """
            create table if not exists runtime_settings (
              key text primary key,
              value text not null
            )
            """
        )
        self.db.execute(
            """
            create table if not exists heartbeat_tasks (
              id integer primary key autoincrement,
              name text not null,
              tag text not null,
              prompt text not null,
              every_sec integer not null,
              mode text not null,
              active_start text not null default '',
              active_end text not null default '',
              timezone text not null default 'UTC',
              max_alerts_per_day integer not null default 2,
              dedupe_window_sec integer not null default 21600,
              enabled integer not null default 1,
              target_kind text not null,
              target_id text not null,
              created_by text not null default '',
              created_at integer not null,
              updated_at integer not null,
              last_run_ts integer not null default 0,
              last_alert_ts integer not null default 0,
              last_result_hash text not null default '',
              last_result_excerpt text not null default '',
              last_status text not null default '',
              last_error text not null default '',
              fail_count integer not null default 0
            )
            """
        )
        self.db.execute(
            """
            create table if not exists heartbeat_daily_alerts (
              task_id integer not null,
              day_key text not null,
              count integer not null,
              primary key(task_id, day_key)
            )
            """
        )
        self.db.execute(
            """
            create table if not exists outbox_messages (
              id integer primary key autoincrement,
              target_kind text not null,
              target_id text not null,
              content text not null,
              context text not null default '',
              created_at integer not null,
              sent_at integer not null default 0,
              status text not null default 'pending',
              last_error text not null default ''
            )
            """
        )
        self.db.execute(
            """
            create table if not exists agent_tasks (
              id integer primary key autoincrement,
              kind text not null,
              session_key text not null,
              requester_id text not null,
              requester_name text not null default '',
              target_kind text not null,
              target_id text not null,
              user_text text not null,
              model_override text not null default '',
              thinking_override text not null default '',
              status text not null default 'pending',
              progress text not null default '',
              created_at integer not null,
              started_at integer not null default 0,
              finished_at integer not null default 0,
              attempts integer not null default 0,
              max_attempts integer not null default 1,
              result_text text not null default '',
              error_text text not null default ''
            )
            """
        )
        self._ensure_table_column("agent_tasks", "model_override", "text not null default ''")
        self._ensure_table_column("agent_tasks", "thinking_override", "text not null default ''")
        self.db.commit()

    def _ensure_table_column(self, table: str, column: str, ddl: str) -> None:
        cur = self.db.execute(f"pragma table_info({table})")
        cols = {str(r[1]) for r in cur.fetchall()}
        if column in cols:
            return
        self.db.execute(f"alter table {table} add column {column} {ddl}")

    @staticmethod
    def _row_to_dict(row: sqlite3.Row | None) -> dict[str, Any] | None:
        if row is None:
            return None
        return {k: row[k] for k in row.keys()}

    def add_message(self, session_key: str, role: str, content: str) -> None:
        self.db.execute(
            "insert into messages(session_key, role, content, ts) values(?,?,?,?)",
            (session_key, role, content, int(time.time())),
        )
        self.db.commit()

    def get_history(self, session_key: str, max_turns: int) -> list[tuple[str, str]]:
        cur = self.db.execute(
            """
            select role, content from messages
            where session_key = ?
            order by id desc
            limit ?
            """,
            (session_key, max_turns * 2),
        )
        rows = list(cur.fetchall())
        rows.reverse()
        return [(str(r[0]), str(r[1])) for r in rows]

    def allow_user(self, channel: str, user_id: str) -> None:
        self.db.execute(
            "insert or ignore into allowed_users(channel, user_id) values(?,?)",
            (channel, user_id),
        )
        self.db.commit()

    def is_user_allowed(self, channel: str, user_id: str) -> bool:
        cur = self.db.execute(
            "select 1 from allowed_users where channel = ? and user_id = ?",
            (channel, user_id),
        )
        return cur.fetchone() is not None

    def upsert_pairing(self, channel: str, user_id: str, ttl_sec: int = 3600) -> str:
        cur = self.db.execute(
            "select code, expires_at from pairing_requests where channel = ? and user_id = ?",
            (channel, user_id),
        )
        row = cur.fetchone()
        now = int(time.time())
        if row and int(row[1]) > now:
            return str(row[0])
        code = "".join(random.choice(string.digits) for _ in range(6))
        self.db.execute(
            "insert or replace into pairing_requests(channel, user_id, code, expires_at) values(?,?,?,?)",
            (channel, user_id, code, now + ttl_sec),
        )
        self.db.commit()
        return code

    def approve_pairing_code(self, channel: str, code: str) -> str | None:
        now = int(time.time())
        cur = self.db.execute(
            "select user_id, expires_at from pairing_requests where channel = ? and code = ?",
            (channel, code),
        )
        row = cur.fetchone()
        if not row:
            return None
        if int(row[1]) <= now:
            return None
        user_id = str(row[0])
        self.allow_user(channel, user_id)
        self.db.execute(
            "delete from pairing_requests where channel = ? and user_id = ?",
            (channel, user_id),
        )
        self.db.commit()
        return user_id

    def set_runtime(self, key: str, value: str) -> None:
        self.db.execute(
            "insert or replace into runtime_settings(key, value) values(?,?)",
            (key, value),
        )
        self.db.commit()

    def get_runtime(self, key: str, default: str = "") -> str:
        cur = self.db.execute("select value from runtime_settings where key = ?", (key,))
        row = cur.fetchone()
        if not row:
            return default
        return str(row[0])

    def add_heartbeat_task(
        self,
        *,
        name: str,
        tag: str,
        prompt: str,
        every_sec: int,
        mode: str,
        active_start: str,
        active_end: str,
        timezone_name: str,
        max_alerts_per_day: int,
        dedupe_window_sec: int,
        target_kind: str,
        target_id: str,
        created_by: str,
    ) -> int:
        now = int(time.time())
        cur = self.db.execute(
            """
            insert into heartbeat_tasks(
              name, tag, prompt, every_sec, mode,
              active_start, active_end, timezone,
              max_alerts_per_day, dedupe_window_sec,
              enabled, target_kind, target_id,
              created_by, created_at, updated_at
            ) values(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
            """,
            (
                name,
                tag,
                prompt,
                int(every_sec),
                mode,
                active_start,
                active_end,
                timezone_name,
                int(max_alerts_per_day),
                int(dedupe_window_sec),
                1,
                target_kind,
                target_id,
                created_by,
                now,
                now,
            ),
        )
        self.db.commit()
        return int(cur.lastrowid)

    def get_heartbeat_task(self, task_id: int) -> dict[str, Any] | None:
        cur = self.db.execute("select * from heartbeat_tasks where id = ?", (task_id,))
        return self._row_to_dict(cur.fetchone())

    def list_heartbeat_tasks(self, include_disabled: bool = True) -> list[dict[str, Any]]:
        if include_disabled:
            cur = self.db.execute("select * from heartbeat_tasks order by id asc")
        else:
            cur = self.db.execute("select * from heartbeat_tasks where enabled = 1 order by id asc")
        return [self._row_to_dict(row) or {} for row in cur.fetchall()]

    def set_heartbeat_task_enabled(self, task_id: int, enabled: bool) -> bool:
        now = int(time.time())
        cur = self.db.execute(
            "update heartbeat_tasks set enabled = ?, updated_at = ? where id = ?",
            (1 if enabled else 0, now, task_id),
        )
        self.db.commit()
        return cur.rowcount > 0

    def delete_heartbeat_task(self, task_id: int) -> bool:
        cur = self.db.execute("delete from heartbeat_tasks where id = ?", (task_id,))
        self.db.commit()
        return cur.rowcount > 0

    def update_heartbeat_task_fields(self, task_id: int, fields: dict[str, Any]) -> None:
        if not fields:
            return
        cols = [
            "name",
            "tag",
            "prompt",
            "every_sec",
            "mode",
            "active_start",
            "active_end",
            "timezone",
            "max_alerts_per_day",
            "dedupe_window_sec",
            "enabled",
            "target_kind",
            "target_id",
            "updated_at",
            "last_run_ts",
            "last_alert_ts",
            "last_result_hash",
            "last_result_excerpt",
            "last_status",
            "last_error",
            "fail_count",
        ]
        pairs: list[tuple[str, Any]] = []
        for k, v in fields.items():
            if k in cols:
                pairs.append((k, v))
        if not pairs:
            return
        sql = "update heartbeat_tasks set " + ", ".join(f"{k} = ?" for k, _ in pairs) + " where id = ?"
        vals = [v for _, v in pairs] + [task_id]
        self.db.execute(sql, vals)
        self.db.commit()

    def get_daily_alert_count(self, task_id: int, day_key: str) -> int:
        cur = self.db.execute(
            "select count from heartbeat_daily_alerts where task_id = ? and day_key = ?",
            (task_id, day_key),
        )
        row = cur.fetchone()
        if not row:
            return 0
        return int(row[0])

    def increment_daily_alert_count(self, task_id: int, day_key: str) -> int:
        current = self.get_daily_alert_count(task_id, day_key)
        next_count = current + 1
        self.db.execute(
            "insert or replace into heartbeat_daily_alerts(task_id, day_key, count) values(?,?,?)",
            (task_id, day_key, next_count),
        )
        self.db.commit()
        return next_count

    def queue_outbox(self, target_kind: str, target_id: str, content: str, context: str = "") -> int:
        now = int(time.time())
        cur = self.db.execute(
            """
            insert into outbox_messages(target_kind, target_id, content, context, created_at, sent_at, status, last_error)
            values(?,?,?,?,?,0,'pending','')
            """,
            (target_kind, target_id, content, context, now),
        )
        self.db.commit()
        return int(cur.lastrowid)

    def get_outbox_message(self, msg_id: int) -> dict[str, Any] | None:
        cur = self.db.execute("select * from outbox_messages where id = ?", (msg_id,))
        return self._row_to_dict(cur.fetchone())

    def list_pending_outbox(self, limit: int = 50) -> list[dict[str, Any]]:
        cur = self.db.execute(
            "select * from outbox_messages where status = 'pending' order by id asc limit ?",
            (max(1, int(limit)),),
        )
        return [self._row_to_dict(row) or {} for row in cur.fetchall()]

    def count_pending_outbox(self) -> int:
        cur = self.db.execute("select count(*) from outbox_messages where status = 'pending'")
        return int(cur.fetchone()[0])

    def mark_outbox_sent(self, msg_id: int) -> None:
        now = int(time.time())
        self.db.execute(
            "update outbox_messages set status = 'sent', sent_at = ?, last_error = '' where id = ?",
            (now, msg_id),
        )
        self.db.commit()

    def mark_outbox_failed(self, msg_id: int, error: str) -> None:
        self.db.execute(
            "update outbox_messages set status = 'pending', last_error = ? where id = ?",
            (error[:500], msg_id),
        )
        self.db.commit()

    # ---------------- Async agent tasks ----------------

    def enqueue_agent_task(
        self,
        *,
        kind: str,
        session_key: str,
        requester_id: str,
        requester_name: str,
        target_kind: str,
        target_id: str,
        user_text: str,
        model_override: str = "",
        thinking_override: str = "",
        max_attempts: int,
    ) -> int:
        now = int(time.time())
        cur = self.db.execute(
            """
            insert into agent_tasks(
              kind, session_key, requester_id, requester_name,
              target_kind, target_id, user_text,
              model_override, thinking_override,
              status, progress, created_at, started_at, finished_at,
              attempts, max_attempts, result_text, error_text
            ) values(?,?,?,?,?,?,?,?,?,'pending','queued',?,0,0,0,?, '', '')
            """,
            (
                kind,
                session_key,
                requester_id,
                requester_name,
                target_kind,
                target_id,
                user_text,
                (model_override or "").strip(),
                (thinking_override or "").strip().lower(),
                now,
                max(1, int(max_attempts)),
            ),
        )
        self.db.commit()
        return int(cur.lastrowid)

    def get_agent_task(self, task_id: int) -> dict[str, Any] | None:
        cur = self.db.execute("select * from agent_tasks where id = ?", (task_id,))
        return self._row_to_dict(cur.fetchone())

    def list_agent_tasks(
        self,
        *,
        limit: int = 20,
        requester_id: str | None = None,
        status: str | None = None,
    ) -> list[dict[str, Any]]:
        cap = max(1, min(200, int(limit)))
        if requester_id and status:
            cur = self.db.execute(
                "select * from agent_tasks where requester_id = ? and status = ? order by id desc limit ?",
                (requester_id, status, cap),
            )
        elif requester_id:
            cur = self.db.execute(
                "select * from agent_tasks where requester_id = ? order by id desc limit ?",
                (requester_id, cap),
            )
        elif status:
            cur = self.db.execute(
                "select * from agent_tasks where status = ? order by id desc limit ?",
                (status, cap),
            )
        else:
            cur = self.db.execute("select * from agent_tasks order by id desc limit ?", (cap,))
        return [self._row_to_dict(row) or {} for row in cur.fetchall()]

    def count_pending_agent_tasks(self) -> int:
        cur = self.db.execute("select count(*) from agent_tasks where status = 'pending'")
        return int(cur.fetchone()[0])

    def claim_next_agent_task(self) -> dict[str, Any] | None:
        cur = self.db.execute("select id from agent_tasks where status = 'pending' order by id asc limit 1")
        row = cur.fetchone()
        if not row:
            return None

        task_id = int(row[0])
        now = int(time.time())
        upd = self.db.execute(
            """
            update agent_tasks
            set status = 'running', progress = 'running', started_at = ?, attempts = attempts + 1
            where id = ? and status = 'pending'
            """,
            (now, task_id),
        )
        self.db.commit()
        if upd.rowcount <= 0:
            return None
        return self.get_agent_task(task_id)

    def set_agent_task_progress(self, task_id: int, progress: str) -> None:
        self.db.execute(
            "update agent_tasks set progress = ? where id = ?",
            ((progress or "")[:300], int(task_id)),
        )
        self.db.commit()

    def mark_agent_task_done(self, task_id: int, result_text: str) -> None:
        now = int(time.time())
        self.db.execute(
            """
            update agent_tasks
            set status = 'done', progress = 'done', finished_at = ?,
                result_text = ?, error_text = ''
            where id = ?
            """,
            (now, (result_text or "")[:120000], int(task_id)),
        )
        self.db.commit()

    def mark_agent_task_failed(self, task_id: int, error_text: str) -> None:
        now = int(time.time())
        self.db.execute(
            """
            update agent_tasks
            set status = 'failed', progress = 'failed', finished_at = ?,
                error_text = ?, result_text = ''
            where id = ?
            """,
            (now, (error_text or "")[:2000], int(task_id)),
        )
        self.db.commit()

    def reset_agent_task_to_pending(self, task_id: int, progress: str = "queued") -> bool:
        upd = self.db.execute(
            """
            update agent_tasks
            set status = 'pending', progress = ?, error_text = '', result_text = '', started_at = 0, finished_at = 0
            where id = ? and status in ('running','failed')
            """,
            ((progress or "queued")[:300], int(task_id)),
        )
        self.db.commit()
        return upd.rowcount > 0

    def recover_running_agent_tasks(self) -> list[dict[str, Any]]:
        rows = self.list_agent_tasks(limit=500, status="running")
        recovered: list[dict[str, Any]] = []
        for row in rows:
            task_id = int(row.get("id") or 0)
            attempts = int(row.get("attempts") or 0)
            max_attempts = max(1, int(row.get("max_attempts") or 1))
            if attempts < max_attempts:
                self.reset_agent_task_to_pending(task_id, progress="requeued-after-restart")
                latest = self.get_agent_task(task_id) or row
                latest["recovery_action"] = "requeued"
                recovered.append(latest)
            else:
                self.mark_agent_task_failed(task_id, "Interrupted by restart and max attempts reached")
                latest = self.get_agent_task(task_id) or row
                latest["recovery_action"] = "failed"
                recovered.append(latest)
        return recovered


class AgentBackend:
    def __init__(self, cfg: Config):
        self.cfg = cfg

    async def ask(
        self,
        session_key: str,
        history: list[tuple[str, str]],
        user_text: str,
        *,
        pi_model: str | None = None,
        pi_thinking: str | None = None,
    ) -> str:
        if self.cfg.backend_mode == "openai":
            return await self._ask_openai(history, user_text)
        if self.cfg.backend_mode == "pi":
            return await self._ask_pi(session_key, user_text, pi_model=pi_model, pi_thinking=pi_thinking)
        return await self._ask_command(session_key, user_text)

    async def _ask_openai(self, history: list[tuple[str, str]], user_text: str) -> str:
        if not self.cfg.openai_api_key:
            return "OPENAI_API_KEY is not configured."
        messages = [{"role": "system", "content": self.cfg.system_prompt}]
        messages.extend({"role": role, "content": content} for role, content in history)
        messages.append({"role": "user", "content": user_text})
        url = self.cfg.openai_base_url.rstrip("/") + "/chat/completions"
        headers = {
            "Authorization": f"Bearer {self.cfg.openai_api_key}",
            "Content-Type": "application/json",
        }
        payload = {
            "model": self.cfg.openai_model,
            "messages": messages,
            "temperature": 0.2,
        }
        async with httpx.AsyncClient(timeout=90) as client:
            resp = await client.post(url, headers=headers, json=payload)
            resp.raise_for_status()
            data = resp.json()
        return (
            data.get("choices", [{}])[0]
            .get("message", {})
            .get("content", "(empty response)")
            .strip()
            or "(empty response)"
        )

    async def _ask_pi(
        self,
        session_key: str,
        user_text: str,
        *,
        pi_model: str | None = None,
        pi_thinking: str | None = None,
    ) -> str:
        sessions_dir = "/home/ubuntu/discord-agent/pi-sessions"
        os.makedirs(sessions_dir, exist_ok=True)
        safe = "".join(ch if ch.isalnum() or ch in {"-", "_", "."} else "_" for ch in session_key)
        session_path = os.path.join(sessions_dir, f"{safe}.jsonl")

        model_to_use = (pi_model or self.cfg.pi_model).strip()
        thinking_to_use = (pi_thinking or self.cfg.pi_thinking).strip().lower()

        cmd = [self.cfg.pi_bin, "--session", session_path]
        if model_to_use:
            cmd.extend(["--model", model_to_use])
        if thinking_to_use:
            cmd.extend(["--thinking", thinking_to_use])
        cmd.extend(["-p", user_text])

        proc = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            cwd="/home/ubuntu",
            env=os.environ.copy(),
        )
        try:
            out, err = await proc.communicate()
        except asyncio.CancelledError:
            try:
                proc.kill()
            except ProcessLookupError:
                pass
            await proc.communicate()
            raise

        if proc.returncode != 0:
            e = err.decode("utf-8", "ignore").strip()
            return f"pi backend failed: {e[:600]}"
        text = out.decode("utf-8", "ignore").strip()
        return text or "(empty response)"

    async def _ask_command(self, session_key: str, user_text: str) -> str:
        if not self.cfg.agent_command:
            return "AGENT_COMMAND is not configured."
        cmd = shlex.split(self.cfg.agent_command)
        env = os.environ.copy()
        env["SESSION_KEY"] = session_key
        env["SYSTEM_PROMPT"] = self.cfg.system_prompt
        proc = await asyncio.create_subprocess_exec(
            *cmd,
            stdin=asyncio.subprocess.PIPE,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            env=env,
        )
        try:
            out, err = await proc.communicate(user_text.encode("utf-8"))
        except asyncio.CancelledError:
            try:
                proc.kill()
            except ProcessLookupError:
                pass
            await proc.communicate()
            raise

        if proc.returncode != 0:
            return f"Command backend failed: {err.decode('utf-8', 'ignore')[:500]}"
        text = out.decode("utf-8", "ignore").strip()
        return text or "(empty response)"


class DiscordAgent(discord.Client):
    THINKING_LEVELS = {"off", "minimal", "low", "medium", "high", "xhigh"}

    def __init__(self, cfg: Config, store: Store, backend: AgentBackend):
        intents = discord.Intents.default()
        intents.message_content = True
        intents.guild_messages = True
        intents.dm_messages = True
        super().__init__(intents=intents)
        self.cfg = cfg
        self.store = store
        self.backend = backend

        self.pi_model_override = self.store.get_runtime("pi_model_override", "").strip()
        self.pi_thinking_override = self.store.get_runtime("pi_thinking_override", "").strip().lower()

        self._hb_loop_task: asyncio.Task | None = None
        self._hb_lock = asyncio.Lock()
        self._startup_report_sent = False

        self._task_loop_tasks: list[asyncio.Task] = []
        self._async_recovery_done = False

        self._report_server: ThreadingHTTPServer | None = None
        self._report_server_thread: threading.Thread | None = None

    async def on_ready(self):
        print(f"Discord agent online: {self.user}")
        self._start_report_server_if_needed()
        if self._hb_loop_task is None or self._hb_loop_task.done():
            self._hb_loop_task = asyncio.create_task(self._heartbeat_loop())

        if self.cfg.async_tasks_enabled:
            if not self._async_recovery_done:
                recovered = self.store.recover_running_agent_tasks()
                for task in recovered:
                    kind = str(task.get("kind") or "chat")
                    tid = int(task.get("id") or 0)
                    action = str(task.get("recovery_action") or "requeued")
                    target_kind = str(task.get("target_kind") or "channel")
                    target_id = str(task.get("target_id") or "")
                    if not target_id:
                        continue
                    if action == "requeued":
                        note = f"🔁 Task #{tid} ({kind}) was interrupted by restart and has been re-queued."
                    else:
                        note = f"❌ Task #{tid} ({kind}) failed after restart recovery (max attempts reached)."
                    await self._send_with_outbox(target_kind, target_id, note, context=f"task-recover:{tid}")
                self._async_recovery_done = True

            alive = [t for t in self._task_loop_tasks if not t.done()]
            if len(alive) < self.cfg.async_task_workers:
                next_index = len(alive) + 1
                for i in range(self.cfg.async_task_workers - len(alive)):
                    wid = next_index + i
                    alive.append(asyncio.create_task(self._async_task_loop(worker_id=wid)))
            self._task_loop_tasks = alive

        # First flush pending messages (recover from restarts), then send startup status report once.
        await self._flush_outbox(limit=80)
        await self._send_startup_report_once()

    async def close(self):
        if self._hb_loop_task and not self._hb_loop_task.done():
            self._hb_loop_task.cancel()
            try:
                await self._hb_loop_task
            except Exception:
                pass
        running_workers = [t for t in self._task_loop_tasks if not t.done()]
        for t in running_workers:
            t.cancel()
        for t in running_workers:
            try:
                await t
            except Exception:
                pass
        self._task_loop_tasks = []
        self._stop_report_server()
        await super().close()

    async def on_error(self, event_method: str, *args, **kwargs):
        tb = traceback.format_exc()
        print(f"discord event error in {event_method}:\n{tb}")

        if not self.cfg.admin_user_ids:
            return

        now = int(time.time())
        try:
            last = int(self.store.get_runtime("last_runtime_error_ts", "0") or "0")
        except Exception:
            last = 0
        if now - last < 120:
            return

        self.store.set_runtime("last_runtime_error_ts", str(now))
        preview = tb.strip().splitlines()[-1] if tb.strip() else "unknown error"
        text = (
            f"⚠️ Runtime error in `{event_method}`\n"
            f"time: {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%SZ')}\n"
            f"error: {preview[:500]}"
        )
        admin_id = sorted(self.cfg.admin_user_ids)[0]
        await self._send_with_outbox("dm", admin_id, text, context="runtime-error")

    @staticmethod
    def _chunks(text: str, n: int) -> Iterable[str]:
        for i in range(0, len(text), n):
            yield text[i : i + n]

    def _session_key(self, msg: discord.Message) -> str:
        if isinstance(msg.channel, discord.DMChannel):
            return "agent:main:main"
        if isinstance(msg.channel, discord.Thread):
            return f"agent:main:discord:channel:{msg.channel.parent_id}:thread:{msg.channel.id}"
        return f"agent:main:discord:channel:{msg.channel.id}"

    def _is_admin(self, user_id: int) -> bool:
        return str(user_id) in self.cfg.admin_user_ids

    def _current_pi_model(self) -> str | None:
        value = (self.pi_model_override or self.cfg.pi_model).strip()
        return value or None

    def _current_pi_thinking(self) -> str | None:
        value = (self.pi_thinking_override or self.cfg.pi_thinking).strip().lower()
        return value or None

    def _runtime_summary(self) -> str:
        model = self._current_pi_model() or "<default from pi>"
        thinking = self._current_pi_thinking() or "<pi default>"
        source = "override" if (self.pi_model_override or self.pi_thinking_override) else "env/default"
        hb = "on" if self._is_heartbeat_enabled() else "off"
        report_state = "on" if self.cfg.report_server_enabled else "off"
        report_base = self._report_base_url()
        async_state = "on" if self.cfg.async_tasks_enabled else "off"
        pending_tasks = self.store.count_pending_agent_tasks() if self.cfg.async_tasks_enabled else 0
        return (
            f"Backend mode: {self.cfg.backend_mode}\n"
            f"PI model: {model}\n"
            f"PI thinking: {thinking}\n"
            f"Source: {source}\n"
            f"Heartbeat: {hb}\n"
            f"Report server: {report_state} ({report_base})\n"
            f"Async tasks: {async_state} (workers={self.cfg.async_task_workers}, pending={pending_tasks}, timeout={self.cfg.async_task_timeout_sec}s)"
        )

    # ---------------- Report Web Layer (HTML publish) ----------------

    def _report_base_url(self) -> str:
        explicit = (self.cfg.report_base_url or "").strip()
        if explicit:
            return explicit.rstrip("/")

        host = (self.cfg.report_public_host or "").strip()
        if host:
            if host.startswith("http://") or host.startswith("https://"):
                return host.rstrip("/")
            return f"http://{host}:{self.cfg.report_port}"

        return f"http://127.0.0.1:{self.cfg.report_port}"

    def _start_report_server_if_needed(self) -> None:
        if not self.cfg.report_server_enabled:
            return
        if self._report_server is not None:
            return

        reports_dir = Path(self.cfg.report_dir)
        reports_dir.mkdir(parents=True, exist_ok=True)

        handler = partial(SimpleHTTPRequestHandler, directory=str(reports_dir))
        try:
            server = ThreadingHTTPServer((self.cfg.report_bind, self.cfg.report_port), handler)
        except OSError as e:
            print(f"report server start failed: {e}")
            return

        server.daemon_threads = True
        thread = threading.Thread(target=server.serve_forever, name="report-server", daemon=True)
        thread.start()

        self._report_server = server
        self._report_server_thread = thread
        print(
            f"report server started on {self.cfg.report_bind}:{self.cfg.report_port}, base={self._report_base_url()}"
        )

    def _stop_report_server(self) -> None:
        server = self._report_server
        thread = self._report_server_thread
        self._report_server = None
        self._report_server_thread = None
        if server is None:
            return
        try:
            server.shutdown()
            server.server_close()
        except Exception:
            pass
        if thread and thread.is_alive():
            thread.join(timeout=2)

    @staticmethod
    def _looks_complex_markdown(text: str) -> bool:
        t = text or ""
        if any(marker in t for marker in REPORT_COMPLEX_MARKERS):
            return True
        # table-ish signals
        if "\n|" in t and "|" in t and ("---" in t or "\n|:" in t):
            return True
        return False

    def _build_report_html(self, *, title: str, markdown: str, meta_lines: list[str]) -> str:
        title_safe = escape(title)
        meta_html = "".join(f"<li>{escape(line)}</li>" for line in meta_lines if line.strip())
        md_json = json.dumps(markdown, ensure_ascii=False)
        return f"""<!doctype html>
<html lang=\"zh-CN\">
<head>
  <meta charset=\"utf-8\" />
  <meta name=\"viewport\" content=\"width=device-width, initial-scale=1\" />
  <title>{title_safe}</title>
  <link rel=\"stylesheet\" href=\"https://cdn.jsdelivr.net/npm/github-markdown-css@5.8.1/github-markdown-dark.min.css\" />
  <style>
    body {{ background: #0d1117; color: #c9d1d9; margin: 0; font-family: ui-sans-serif, -apple-system, Segoe UI, Roboto, Helvetica, Arial; }}
    .wrap {{ max-width: 1080px; margin: 20px auto; padding: 0 16px 32px; }}
    .card {{ background: #161b22; border: 1px solid #30363d; border-radius: 10px; padding: 16px; }}
    .meta {{ margin: 10px 0 16px; color: #8b949e; font-size: 14px; }}
    .meta ul {{ margin: 0; padding-left: 18px; }}
    .markdown-body {{ background: transparent !important; }}
    details {{ margin-top: 18px; }}
    pre#raw {{ white-space: pre-wrap; word-break: break-word; }}
    a {{ color: #58a6ff; }}
  </style>
</head>
<body>
  <div class=\"wrap\">
    <div class=\"card\">
      <h1>{title_safe}</h1>
      <div class=\"meta\"><ul>{meta_html}</ul></div>
      <article id=\"content\" class=\"markdown-body\"></article>
      <details>
        <summary>查看原始 Markdown</summary>
        <pre id=\"raw\"></pre>
      </details>
    </div>
  </div>

  <script src=\"https://cdn.jsdelivr.net/npm/marked/marked.min.js\"></script>
  <script src=\"https://cdn.jsdelivr.net/npm/dompurify@3.1.6/dist/purify.min.js\"></script>
  <script>
    const markdown = {md_json};
    document.getElementById('raw').textContent = markdown;
    const html = marked.parse(markdown, {{ gfm: true, breaks: true }});
    document.getElementById('content').innerHTML = DOMPurify.sanitize(html);
  </script>
</body>
</html>
"""

    def _publish_markdown_report(self, *, title: str, markdown: str, meta: list[str]) -> str | None:
        if not self.cfg.report_server_enabled:
            return None

        try:
            self._start_report_server_if_needed()
            reports_dir = Path(self.cfg.report_dir)
            reports_dir.mkdir(parents=True, exist_ok=True)

            slug = re.sub(r"[^a-zA-Z0-9_-]+", "-", title).strip("-").lower() or "report"
            name = f"{int(time.time())}-{slug[:40]}-{uuid.uuid4().hex[:8]}.html"
            path = reports_dir / name

            html = self._build_report_html(title=title, markdown=markdown, meta_lines=meta)
            path.write_text(html, encoding="utf-8")
            return f"{self._report_base_url()}/{name}"
        except Exception as e:
            print(f"publish report failed: {e}")
            return None

    async def _send_text_to_msg_target_with_outbox(self, msg: discord.Message, text: str, *, context: str) -> None:
        target_kind, target_id = self._target_from_message(msg)
        for chunk in self._chunks(text, self.cfg.max_reply_chars):
            ok = await self._send_with_outbox(target_kind, target_id, chunk, context=context)
            if ok:
                continue
            # fallback immediate send (best effort) to avoid user seeing no response
            try:
                await msg.channel.send(chunk)
            except Exception as e:
                print(f"fallback direct send failed: {e}")

    # ---------------- Outbox (restart-safe proactive reporting) ----------------

    async def _deliver_direct(self, target_kind: str, target_id: str, content: str) -> None:
        if target_kind == "channel":
            cid = int(target_id)
            channel = self.get_channel(cid)
            if channel is None:
                channel = await self.fetch_channel(cid)
            for chunk in self._chunks(content, self.cfg.max_reply_chars):
                await channel.send(chunk)
            return

        if target_kind == "dm":
            uid = int(target_id)
            user = await self.fetch_user(uid)
            for chunk in self._chunks(content, self.cfg.max_reply_chars):
                await user.send(chunk)
            return

        raise RuntimeError(f"unsupported target_kind: {target_kind}")

    async def _deliver_outbox_row(self, row: dict[str, Any]) -> bool:
        msg_id = int(row["id"])
        target_kind = str(row.get("target_kind", "")).strip()
        target_id = str(row.get("target_id", "")).strip()
        content = str(row.get("content", "")).strip()
        if not target_kind or not target_id or not content:
            self.store.mark_outbox_failed(msg_id, "invalid outbox row")
            return False

        try:
            await self._deliver_direct(target_kind, target_id, content)
            self.store.mark_outbox_sent(msg_id)
            return True
        except Exception as e:
            self.store.mark_outbox_failed(msg_id, str(e))
            return False

    async def _send_with_outbox(self, target_kind: str, target_id: str, content: str, *, context: str = "") -> bool:
        msg_id = self.store.queue_outbox(target_kind, target_id, content, context=context)
        row = self.store.get_outbox_message(msg_id)
        if not row:
            return False
        return await self._deliver_outbox_row(row)

    async def _flush_outbox(self, limit: int = 50) -> int:
        rows = self.store.list_pending_outbox(limit=limit)
        delivered = 0
        for row in rows:
            ok = await self._deliver_outbox_row(row)
            if ok:
                delivered += 1
        return delivered

    async def _send_startup_report_once(self) -> None:
        if self._startup_report_sent or not self.cfg.startup_report_enabled:
            return
        if not self.cfg.admin_user_ids:
            self._startup_report_sent = True
            return

        pending = self.store.count_pending_outbox()
        pending_tasks = self.store.count_pending_agent_tasks() if self.cfg.async_tasks_enabled else 0
        hb_state = "on" if self._is_heartbeat_enabled() else "off"
        ts = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%SZ")
        report_info = self._report_base_url() if self.cfg.report_server_enabled else "disabled"
        text = (
            "🔄 Agent restart detected\n"
            f"- time: {ts}\n"
            f"- heartbeat: {hb_state}\n"
            f"- async tasks: {'on' if self.cfg.async_tasks_enabled else 'off'} (workers={self.cfg.async_task_workers}, pending={pending_tasks})\n"
            f"- pending outbox messages: {pending}\n"
            f"- report web: {report_info}\n"
            "I will proactively flush pending reports."
        )
        for admin_id in sorted(self.cfg.admin_user_ids):
            await self._send_with_outbox("dm", admin_id, text, context="startup-report")

        self._startup_report_sent = True

    # ---------------- Async task runtime ----------------

    @staticmethod
    def _fmt_ts(ts: int) -> str:
        if ts <= 0:
            return "-"
        return datetime.fromtimestamp(ts, timezone.utc).strftime("%Y-%m-%d %H:%M:%SZ")

    def _can_view_task(self, msg: discord.Message, task: dict[str, Any]) -> bool:
        if self._is_admin(msg.author.id):
            return True
        return str(task.get("requester_id") or "") == str(msg.author.id)

    def _task_pi_model(self, task: dict[str, Any]) -> str | None:
        override = str(task.get("model_override") or "").strip()
        if override:
            return override
        return self._current_pi_model()

    def _task_pi_thinking(self, task: dict[str, Any]) -> str | None:
        override = str(task.get("thinking_override") or "").strip().lower()
        if override:
            return override
        return self._current_pi_thinking()

    @staticmethod
    def _parse_task_overrides(raw: str) -> tuple[str, str, str]:
        tokens = shlex.split((raw or "").strip())
        model = ""
        thinking = ""
        body_tokens: list[str] = []
        in_body = False

        for token in tokens:
            if in_body:
                body_tokens.append(token)
                continue

            if "=" not in token:
                in_body = True
                body_tokens.append(token)
                continue

            k, v = token.split("=", 1)
            key = k.strip().lower()
            val = v.strip()
            if key == "model":
                model = val
                continue
            if key in {"thinking", "think"}:
                thinking = val.lower()
                continue

            # Unknown key is treated as part of prompt to keep parser forgiving.
            in_body = True
            body_tokens.append(token)

        return model, thinking, " ".join(body_tokens).strip()

    def _validate_task_overrides(self, model: str, thinking: str) -> tuple[bool, str, str, str]:
        model_clean = (model or "").strip()
        thinking_clean = (thinking or "").strip().lower()

        if model_clean.lower() in {"default", "reset", "none", "auto"}:
            model_clean = ""

        if thinking_clean in {"default", "reset", "none", "auto"}:
            thinking_clean = ""
        elif thinking_clean and thinking_clean not in self.THINKING_LEVELS:
            return False, model_clean, "", "thinking must be off|minimal|low|medium|high|xhigh|default"

        return True, model_clean, thinking_clean, ""

    async def _queue_agent_task_from_message(
        self,
        msg: discord.Message,
        *,
        kind: str,
        user_text: str,
        model_override: str = "",
        thinking_override: str = "",
    ) -> int:
        target_kind, target_id = self._target_from_message(msg)
        session_key = self._session_key(msg)
        requester_id = str(msg.author.id)
        requester_name = str(msg.author)
        task_id = self.store.enqueue_agent_task(
            kind=kind,
            session_key=session_key,
            requester_id=requester_id,
            requester_name=requester_name,
            target_kind=target_kind,
            target_id=target_id,
            user_text=user_text,
            model_override=model_override,
            thinking_override=thinking_override,
            max_attempts=self.cfg.async_task_max_attempts,
        )
        return task_id

    def _format_agent_task_line(self, task: dict[str, Any]) -> str:
        tid = int(task.get("id") or 0)
        kind = str(task.get("kind") or "chat")
        status = str(task.get("status") or "pending")
        progress = str(task.get("progress") or "")
        created_at = self._fmt_ts(int(task.get("created_at") or 0))
        attempts = int(task.get("attempts") or 0)
        max_attempts = int(task.get("max_attempts") or 1)
        model = str(task.get("model_override") or "").strip() or "<default>"
        thinking = str(task.get("thinking_override") or "").strip() or "<default>"
        prompt_preview = _norm_text(str(task.get("user_text") or ""))[:80]
        return (
            f"#{tid} [{status}] kind={kind} attempts={attempts}/{max_attempts} "
            f"model={model} think={thinking} created={created_at} progress={progress or '-'} q={prompt_preview}"
        )

    async def _run_chat_task_body(self, task: dict[str, Any]) -> str:
        task_id = int(task.get("id") or 0)
        session_key = str(task.get("session_key") or "")
        user_text = str(task.get("user_text") or "")

        model = self._task_pi_model(task)
        thinking = self._task_pi_thinking(task)

        self.store.set_agent_task_progress(task_id, "running:chat")
        history = self.store.get_history(session_key, self.cfg.history_max_turns)
        answer = await self.backend.ask(
            session_key,
            history,
            user_text,
            pi_model=model,
            pi_thinking=thinking,
        )

        self.store.add_message(session_key, "user", user_text)
        self.store.add_message(session_key, "assistant", answer)

        return f"✅ Task #{task_id} finished.\n\n{answer}"

    async def _run_research_task_body(self, task: dict[str, Any]) -> str:
        task_id = int(task.get("id") or 0)
        session_key = str(task.get("session_key") or "")
        query = str(task.get("user_text") or "").strip()

        model = self._task_pi_model(task)
        thinking = self._task_pi_thinking(task)

        self.store.set_agent_task_progress(task_id, "running:researching")
        history = self.store.get_history(session_key, self.cfg.history_max_turns)
        context, results = await self._build_research_context(query)
        research_prompt = (
            "你现在处于'深度调研模式'。\n"
            "请基于给定的检索证据回答用户问题，要求：\n"
            "1) 先给结论摘要，再给关键事实，再给风险/不确定性。\n"
            "2) 尽量引用来源编号 [1][2]。\n"
            "3) 对证据不足的地方明确说'证据不足'，不要编造。\n"
            "4) 最后给出下一步建议（可执行）。\n\n"
            f"用户问题：{query}\n\n"
            f"可用证据：\n{context}\n"
        )

        self.store.set_agent_task_progress(task_id, "running:analyzing")
        answer = await self.backend.ask(
            session_key,
            history,
            research_prompt,
            pi_model=model,
            pi_thinking=thinking,
        )

        full_answer = answer
        if results:
            source_lines = ["", "Sources:"]
            for i, r in enumerate(results, start=1):
                url = r.get("url", "").strip()
                if not url:
                    continue
                source_lines.append(f"[{i}] {url}")
            full_answer = full_answer + "\n" + "\n".join(source_lines)

        self.store.add_message(session_key, "user", f"!research {query}")
        self.store.add_message(session_key, "assistant", full_answer)

        publish_url: str | None = None
        self.store.set_agent_task_progress(task_id, "running:formatting")
        if self.cfg.report_server_enabled and self.cfg.report_auto_for_research:
            if len(full_answer) >= self.cfg.report_auto_min_chars or self._looks_complex_markdown(full_answer):
                meta = [
                    f"Query: {query}",
                    f"Generated: {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%SZ')}",
                    f"Backend: {self.cfg.backend_mode}",
                    f"PI model: {model or '<default>'}",
                    f"PI thinking: {thinking or '<default>'}",
                ]
                publish_url = self._publish_markdown_report(
                    title=f"Research - {query}",
                    markdown=full_answer,
                    meta=meta,
                )

        if publish_url:
            summary = _norm_text(answer)
            if len(summary) > 1200:
                summary = summary[:1200] + " ..."
            return (
                f"✅ Task #{task_id} research finished. Long output published:\n"
                f"{publish_url}\n\n"
                "摘要：\n"
                f"{summary}"
            )

        return f"✅ Task #{task_id} research finished.\n\n{full_answer}"

    async def _process_one_async_task(self, *, worker_id: int) -> bool:
        task = self.store.claim_next_agent_task()
        if not task:
            return False

        task_id = int(task.get("id") or 0)
        kind = str(task.get("kind") or "chat").strip().lower()
        target_kind = str(task.get("target_kind") or "channel")
        target_id = str(task.get("target_id") or "")
        attempts = int(task.get("attempts") or 1)
        max_attempts = max(1, int(task.get("max_attempts") or self.cfg.async_task_max_attempts))
        model_label = str(task.get("model_override") or "").strip() or "<default>"
        thinking_label = str(task.get("thinking_override") or "").strip() or "<default>"

        queue_wait = max(0, int(time.time()) - int(task.get("created_at") or 0))
        if target_id:
            await self._send_with_outbox(
                target_kind,
                target_id,
                (
                    f"▶️ Task #{task_id} started on worker-{worker_id} "
                    f"(kind={kind}, model={model_label}, thinking={thinking_label}, waited={queue_wait}s)."
                ),
                context=f"task-start:{task_id}",
            )

        self.store.set_agent_task_progress(task_id, f"running@worker-{worker_id}")

        try:
            if kind == "research":
                output_text = await asyncio.wait_for(
                    self._run_research_task_body(task),
                    timeout=self.cfg.async_task_timeout_sec,
                )
            else:
                output_text = await asyncio.wait_for(
                    self._run_chat_task_body(task),
                    timeout=self.cfg.async_task_timeout_sec,
                )

            self.store.mark_agent_task_done(task_id, output_text)
            if target_id:
                await self._send_with_outbox(
                    target_kind,
                    target_id,
                    output_text,
                    context=f"task-done:{task_id}",
                )
            return True

        except asyncio.CancelledError:
            raise
        except Exception as e:
            if isinstance(e, asyncio.TimeoutError):
                err = f"timeout after {self.cfg.async_task_timeout_sec}s"
            else:
                err = str(e)[:500] or e.__class__.__name__

            if attempts < max_attempts:
                self.store.reset_agent_task_to_pending(
                    task_id,
                    progress=f"retry-pending ({attempts + 1}/{max_attempts})",
                )
                if target_id:
                    await self._send_with_outbox(
                        target_kind,
                        target_id,
                        (
                            f"⚠️ Task #{task_id} failed on worker-{worker_id} attempt {attempts}/{max_attempts}, retrying.\n"
                            f"error: {err}"
                        ),
                        context=f"task-retry:{task_id}",
                    )
            else:
                self.store.mark_agent_task_failed(task_id, err)
                if target_id:
                    await self._send_with_outbox(
                        target_kind,
                        target_id,
                        (
                            f"❌ Task #{task_id} failed after {attempts}/{max_attempts} attempts (last worker-{worker_id}).\n"
                            f"error: {err}"
                        ),
                        context=f"task-failed:{task_id}",
                    )
            return True

    async def _async_task_loop(self, *, worker_id: int) -> None:
        while not self.is_closed():
            did_work = False
            try:
                if worker_id == 1:
                    await self._flush_outbox(limit=20)
                did_work = await self._process_one_async_task(worker_id=worker_id)
            except asyncio.CancelledError:
                raise
            except Exception as e:
                print(f"async task loop error (worker-{worker_id}): {e}")
            await asyncio.sleep(0.2 if did_work else self.cfg.async_task_poll_seconds)

    # ---------------- Heartbeat runtime ----------------

    def _is_heartbeat_enabled(self) -> bool:
        raw = self.store.get_runtime("hb_enabled", "").strip().lower()
        if not raw:
            return self.cfg.heartbeat_default_enabled
        return raw in {"1", "true", "yes", "on"}

    def _set_heartbeat_enabled(self, enabled: bool) -> None:
        self.store.set_runtime("hb_enabled", "true" if enabled else "false")

    @staticmethod
    def _resolve_tz(name: str) -> ZoneInfo:
        try:
            return ZoneInfo((name or "UTC").strip() or "UTC")
        except Exception:
            return ZoneInfo("UTC")

    def _task_day_key(self, task: dict[str, Any], now_ts: int) -> str:
        tz = self._resolve_tz(str(task.get("timezone") or "UTC"))
        return datetime.fromtimestamp(now_ts, tz).strftime("%Y-%m-%d")

    def _task_in_active_hours(self, task: dict[str, Any], now_ts: int) -> bool:
        start = str(task.get("active_start") or "").strip()
        end = str(task.get("active_end") or "").strip()
        if not start or not end:
            return True

        try:
            start_m = _parse_hhmm(start)
            end_m = _parse_hhmm(end)
        except ValueError:
            return True

        tz = self._resolve_tz(str(task.get("timezone") or "UTC"))
        dt = datetime.fromtimestamp(now_ts, tz)
        cur = dt.hour * 60 + dt.minute
        if start_m == end_m:
            return True
        if start_m < end_m:
            return start_m <= cur < end_m
        return cur >= start_m or cur < end_m

    def _task_due(self, task: dict[str, Any], now_ts: int) -> bool:
        if int(task.get("enabled") or 0) != 1:
            return False
        every = max(30, int(task.get("every_sec") or 0))
        last_run = int(task.get("last_run_ts") or 0)
        if now_ts - last_run < every:
            return False
        return self._task_in_active_hours(task, now_ts)

    @staticmethod
    def _normalize_heartbeat_reply(reply: str) -> tuple[bool, str]:
        text = (reply or "").strip()
        if not text:
            return True, ""

        token = HEARTBEAT_OK_TOKEN
        stripped = text
        did_strip = False
        for _ in range(6):
            up = stripped.upper()
            if up.startswith(token):
                stripped = stripped[len(token) :].lstrip(" \n\t:,-")
                did_strip = True
                continue
            if up.endswith(token):
                stripped = stripped[: -len(token)].rstrip(" \n\t:,-")
                did_strip = True
                continue
            break

        stripped = stripped.strip()
        if not stripped:
            return True, ""
        if stripped.upper() == token:
            return True, ""
        if did_strip and len(stripped) <= 220:
            return True, ""

        return False, stripped

    @staticmethod
    def _heartbeat_result_hash(text: str) -> str:
        norm = _norm_text(text)
        if not norm:
            return ""
        return hashlib.sha1(norm.encode("utf-8")).hexdigest()

    @staticmethod
    def _target_from_message(msg: discord.Message) -> tuple[str, str]:
        if isinstance(msg.channel, discord.DMChannel):
            return "dm", str(msg.author.id)
        return "channel", str(msg.channel.id)

    def _build_heartbeat_prompt(self, task: dict[str, Any], trigger: str) -> str:
        return (
            "你正在执行一个周期性心跳任务（Heartbeat Task）。\n"
            "请先判断是否有值得打扰用户的新信息。\n"
            f"如果没有，请只回复：{HEARTBEAT_OK_TOKEN}\n"
            "如果有，请按以下结构输出：\n"
            "1) 一句话结论\n"
            "2) 关键变化（最多5条）\n"
            "3) 建议动作（可执行）\n"
            "要求：不编造；不确定就明确写“证据不足”。\n\n"
            f"任务ID: {task.get('id')}\n"
            f"任务名称: {task.get('name')}\n"
            f"任务标签: {task.get('tag')}\n"
            f"触发方式: {trigger}\n"
            f"任务说明:\n{task.get('prompt')}\n"
        )

    def _build_heartbeat_report(self, task: dict[str, Any], content: str, *, trigger: str, now_ts: int) -> str:
        ts = datetime.fromtimestamp(now_ts, timezone.utc).strftime("%Y-%m-%d %H:%M:%SZ")
        return (
            f"🫀 Heartbeat #{task.get('id')} · {task.get('name')}\n"
            f"tag={task.get('tag')} · mode={task.get('mode')} · trigger={trigger} · {ts}\n\n"
            f"{content}"
        )

    async def _run_heartbeat_task(
        self,
        task: dict[str, Any],
        *,
        trigger: str,
        deliver: bool,
    ) -> dict[str, str]:
        now_ts = int(time.time())
        task_id = int(task.get("id") or 0)
        name = str(task.get("name") or f"task-{task_id}")
        mode = str(task.get("mode") or "digest").strip().lower()
        if mode not in HEARTBEAT_MODES:
            mode = "digest"

        session_key = f"agent:heartbeat:task:{task_id}"
        history_turns = max(2, min(8, self.cfg.history_max_turns // 2))
        history = self.store.get_history(session_key, history_turns)
        prompt = self._build_heartbeat_prompt(task, trigger)

        try:
            answer = await asyncio.wait_for(
                self.backend.ask(
                    session_key,
                    history,
                    prompt,
                    pi_model=self._current_pi_model(),
                    pi_thinking=self._current_pi_thinking(),
                ),
                timeout=self.cfg.heartbeat_task_timeout_sec,
            )
        except Exception as e:
            fail_count = int(task.get("fail_count") or 0) + 1
            self.store.update_heartbeat_task_fields(
                task_id,
                {
                    "updated_at": now_ts,
                    "last_run_ts": now_ts,
                    "last_status": "error",
                    "last_error": str(e)[:500],
                    "fail_count": fail_count,
                },
            )
            if deliver and fail_count in {1, 3, 5}:
                target_kind = str(task.get("target_kind") or "channel")
                target_id = str(task.get("target_id") or "")
                if target_id:
                    err_msg = (
                        f"⚠️ Heartbeat #{task_id} `{name}` failed\n"
                        f"error: {str(e)[:300]}\n"
                        f"fail_count: {fail_count}"
                    )
                    await self._send_with_outbox(
                        target_kind,
                        target_id,
                        err_msg,
                        context=f"heartbeat-error:{task_id}",
                    )
            return {"status": "error", "note": str(e)[:200]}

        self.store.add_message(session_key, "user", f"[heartbeat:{trigger}] {prompt}")
        self.store.add_message(session_key, "assistant", answer)

        is_ok, clean = self._normalize_heartbeat_reply(answer)
        clean = clean.strip()
        result_hash = self._heartbeat_result_hash(clean)

        dedupe_window = max(
            60,
            int(task.get("dedupe_window_sec") or self.cfg.heartbeat_default_dedupe_window_sec),
        )
        last_hash = str(task.get("last_result_hash") or "")
        last_alert_ts = int(task.get("last_alert_ts") or 0)
        duplicate = bool(clean and result_hash and result_hash == last_hash and now_ts - last_alert_ts < dedupe_window)

        should_attempt_alert = False
        skip_reason = ""
        if is_ok:
            skip_reason = "ok"
        elif mode == "silent":
            skip_reason = "silent"
        elif duplicate:
            skip_reason = "duplicate"
        elif not deliver:
            skip_reason = "manual-no-delivery"
        else:
            should_attempt_alert = True

        alert_queued = False
        if should_attempt_alert:
            day_key = self._task_day_key(task, now_ts)
            used = self.store.get_daily_alert_count(task_id, day_key)
            max_alerts = max(
                1,
                int(task.get("max_alerts_per_day") or self.cfg.heartbeat_default_max_alerts_per_day),
            )
            if used >= max_alerts:
                skip_reason = "rate-limit"
            else:
                report = self._build_heartbeat_report(task, clean, trigger=trigger, now_ts=now_ts)
                target_kind = str(task.get("target_kind") or "channel")
                target_id = str(task.get("target_id") or "")
                if target_id:
                    await self._send_with_outbox(
                        target_kind,
                        target_id,
                        report,
                        context=f"heartbeat-alert:{task_id}",
                    )
                    self.store.increment_daily_alert_count(task_id, day_key)
                    alert_queued = True
                else:
                    skip_reason = "no-target"

        status = "ok" if is_ok else ("alert" if alert_queued else f"skip:{skip_reason or 'n/a'}")
        update_fields: dict[str, Any] = {
            "updated_at": now_ts,
            "last_run_ts": now_ts,
            "last_status": status,
            "last_error": "",
            "fail_count": 0,
            "last_result_hash": result_hash,
            "last_result_excerpt": clean[:500],
        }
        if alert_queued:
            update_fields["last_alert_ts"] = now_ts
        self.store.update_heartbeat_task_fields(task_id, update_fields)

        note = clean[:180] if clean else (HEARTBEAT_OK_TOKEN if is_ok else skip_reason)
        return {"status": status, "note": note}

    async def _run_due_heartbeat_tasks(self) -> None:
        now_ts = int(time.time())
        tasks = self.store.list_heartbeat_tasks(include_disabled=False)
        due = [t for t in tasks if self._task_due(t, now_ts)]
        due.sort(key=lambda x: int(x.get("last_run_ts") or 0))
        due = due[: self.cfg.heartbeat_max_tasks_per_tick]
        if not due:
            return

        async with self._hb_lock:
            for task in due:
                await self._run_heartbeat_task(task, trigger="schedule", deliver=True)

    async def _heartbeat_loop(self) -> None:
        while not self.is_closed():
            try:
                await self._flush_outbox(limit=30)
                if self._is_heartbeat_enabled():
                    await self._run_due_heartbeat_tasks()
            except Exception as e:
                print(f"heartbeat loop error: {e}")
            await asyncio.sleep(self.cfg.heartbeat_poll_seconds)

    # ---------------- Admin commands ----------------

    def _hb_help_text(self) -> str:
        return (
            "Heartbeat commands (admin):\n"
            "- `!hb on` / `!hb off`\n"
            "- `!hb status`\n"
            "- `!hb list`\n"
            "- `!hb add name=... tag=... every=... mode=... prompt=... [hours=09:00-23:00] [tz=Asia/Shanghai] [max=2] [dedupe=6h] [target=here|dm:<uid>|channel:<cid>]`\n"
            "- `!hb run <id|all>`\n"
            "- `!hb pause <id>` / `!hb resume <id>`\n"
            "- `!hb remove <id>`"
        )

    @staticmethod
    def _parse_kv(raw: str) -> dict[str, str]:
        args: dict[str, str] = {}
        for token in shlex.split(raw):
            if "=" not in token:
                continue
            k, v = token.split("=", 1)
            k = k.strip().lower()
            v = v.strip()
            if k:
                args[k] = v
        return args

    def _parse_target_spec(self, msg: discord.Message, spec: str) -> tuple[str, str] | tuple[None, str]:
        s = (spec or "here").strip().lower()
        if s in {"", "here"}:
            return self._target_from_message(msg)
        if s == "admin":
            if not self.cfg.admin_user_ids:
                return None, "No ADMIN_USER_IDS configured."
            admin_id = sorted(self.cfg.admin_user_ids)[0]
            return "dm", admin_id
        if s.startswith("dm:"):
            uid = s[3:].strip()
            if uid.isdigit():
                return "dm", uid
            return None, "target dm:<uid> expects numeric uid"
        if s.startswith("channel:"):
            cid = s[8:].strip()
            if cid.isdigit():
                return "channel", cid
            return None, "target channel:<cid> expects numeric cid"
        return None, "target must be here|admin|dm:<uid>|channel:<cid>"

    def _format_hb_task(self, task: dict[str, Any]) -> str:
        tid = int(task.get("id") or 0)
        enabled = int(task.get("enabled") or 0) == 1
        every = _format_duration(max(1, int(task.get("every_sec") or 1)))
        mode = str(task.get("mode") or "digest")
        tag = str(task.get("tag") or "general")
        name = str(task.get("name") or f"task-{tid}")
        target = f"{task.get('target_kind')}:{task.get('target_id')}"
        status = str(task.get("last_status") or "-")
        return f"#{tid} [{'on' if enabled else 'off'}] {name} tag={tag} every={every} mode={mode} target={target} last={status}"

    async def _handle_hb_command(self, msg: discord.Message) -> bool:
        content = msg.content.strip()
        if not content.startswith("!hb"):
            return False
        if not self._is_admin(msg.author.id):
            await msg.channel.send("You are not an admin for heartbeat commands.")
            return True

        parts = content.split(maxsplit=2)
        if len(parts) == 1:
            await msg.channel.send(self._hb_help_text())
            return True

        cmd = parts[1].strip().lower()

        if cmd == "help":
            await msg.channel.send(self._hb_help_text())
            return True

        if cmd == "on":
            self._set_heartbeat_enabled(True)
            await msg.channel.send("✅ Heartbeat enabled.")
            return True

        if cmd == "off":
            self._set_heartbeat_enabled(False)
            await msg.channel.send("⏸️ Heartbeat disabled.")
            return True

        if cmd == "status":
            tasks = self.store.list_heartbeat_tasks(include_disabled=True)
            enabled_tasks = [t for t in tasks if int(t.get("enabled") or 0) == 1]
            pending = self.store.count_pending_outbox()
            text = (
                f"Heartbeat: {'on' if self._is_heartbeat_enabled() else 'off'}\n"
                f"poll={self.cfg.heartbeat_poll_seconds}s\n"
                f"tasks={len(tasks)} (enabled={len(enabled_tasks)})\n"
                f"pending_outbox={pending}"
            )
            await msg.channel.send(text)
            return True

        if cmd == "list":
            tasks = self.store.list_heartbeat_tasks(include_disabled=True)
            if not tasks:
                await msg.channel.send("No heartbeat tasks.")
                return True
            lines = ["Heartbeat tasks:"]
            for t in tasks:
                lines.append(self._format_hb_task(t))
            text = "\n".join(lines)
            for chunk in self._chunks(text, self.cfg.max_reply_chars):
                await msg.channel.send(chunk)
            return True

        if cmd == "add":
            if len(parts) < 3 or not parts[2].strip():
                await msg.channel.send(
                    "Usage: `!hb add name=... tag=... every=... mode=... prompt=... [hours=09:00-23:00] [tz=Asia/Shanghai] [max=2] [dedupe=6h] [target=here|dm:<uid>|channel:<cid>]`"
                )
                return True

            kv = self._parse_kv(parts[2])
            name = kv.get("name", "").strip()
            tag = kv.get("tag", "general").strip() or "general"
            prompt = kv.get("prompt", "").strip()
            every_raw = kv.get("every", "").strip()
            mode = kv.get("mode", "digest").strip().lower()
            hours_raw = kv.get("hours", "").strip()
            tz_name = kv.get("tz", "UTC").strip() or "UTC"
            max_raw = kv.get("max", str(self.cfg.heartbeat_default_max_alerts_per_day)).strip()
            dedupe_raw = kv.get("dedupe", _format_duration(self.cfg.heartbeat_default_dedupe_window_sec)).strip()
            target_raw = kv.get("target", "here").strip()

            if not name:
                await msg.channel.send("`name` is required.")
                return True
            if not prompt:
                await msg.channel.send("`prompt` is required.")
                return True
            if mode not in HEARTBEAT_MODES:
                await msg.channel.send("`mode` must be one of: digest|alert|silent")
                return True

            try:
                every_sec = _parse_duration_seconds(every_raw, default_unit="m")
            except ValueError as e:
                await msg.channel.send(f"Invalid `every`: {e}")
                return True
            if every_sec < 60:
                await msg.channel.send("`every` must be >= 60s")
                return True

            try:
                dedupe_sec = _parse_duration_seconds(dedupe_raw, default_unit="m")
            except ValueError as e:
                await msg.channel.send(f"Invalid `dedupe`: {e}")
                return True

            try:
                max_alerts = int(max_raw)
            except ValueError:
                await msg.channel.send("`max` must be integer")
                return True
            max_alerts = max(1, min(100, max_alerts))

            active_start = ""
            active_end = ""
            if hours_raw:
                hm = re.match(r"^(\d{2}:\d{2})-(\d{2}:\d{2})$", hours_raw)
                if not hm:
                    await msg.channel.send("`hours` must be HH:MM-HH:MM")
                    return True
                try:
                    _parse_hhmm(hm.group(1))
                    _parse_hhmm(hm.group(2))
                except ValueError as e:
                    await msg.channel.send(f"Invalid hours: {e}")
                    return True
                active_start = hm.group(1)
                active_end = hm.group(2)

            # timezone validation
            try:
                ZoneInfo(tz_name)
            except Exception:
                await msg.channel.send("Invalid `tz` (use IANA timezone, e.g. Asia/Shanghai)")
                return True

            parsed_target = self._parse_target_spec(msg, target_raw)
            if parsed_target[0] is None:
                await msg.channel.send(f"Invalid target: {parsed_target[1]}")
                return True
            target_kind, target_id = parsed_target  # type: ignore[misc]

            task_id = self.store.add_heartbeat_task(
                name=name,
                tag=tag,
                prompt=prompt,
                every_sec=every_sec,
                mode=mode,
                active_start=active_start,
                active_end=active_end,
                timezone_name=tz_name,
                max_alerts_per_day=max_alerts,
                dedupe_window_sec=dedupe_sec,
                target_kind=str(target_kind),
                target_id=str(target_id),
                created_by=str(msg.author.id),
            )
            await msg.channel.send(f"✅ Heartbeat task created: #{task_id} `{name}`")
            return True

        if cmd in {"pause", "resume", "remove", "run"}:
            if len(parts) < 3 or not parts[2].strip():
                await msg.channel.send(f"Usage: `!hb {cmd} <id>`" + (" or `!hb run all`" if cmd == "run" else ""))
                return True
            arg = parts[2].strip().lower()

            if cmd == "run" and arg == "all":
                tasks = self.store.list_heartbeat_tasks(include_disabled=False)
                if not tasks:
                    await msg.channel.send("No enabled heartbeat tasks.")
                    return True
                await msg.channel.send(f"Running {len(tasks)} heartbeat task(s)...")
                results: list[str] = []
                async with self._hb_lock:
                    for t in tasks:
                        r = await self._run_heartbeat_task(t, trigger="manual", deliver=False)
                        results.append(f"#{t.get('id')} {t.get('name')}: {r.get('status')} · {r.get('note')}")
                text = "Manual run finished:\n" + "\n".join(results)
                for chunk in self._chunks(text, self.cfg.max_reply_chars):
                    await msg.channel.send(chunk)
                return True

            if not arg.isdigit():
                await msg.channel.send("Task id must be an integer.")
                return True
            task_id = int(arg)
            task = self.store.get_heartbeat_task(task_id)
            if not task:
                await msg.channel.send(f"Task #{task_id} not found.")
                return True

            if cmd == "pause":
                self.store.set_heartbeat_task_enabled(task_id, False)
                await msg.channel.send(f"⏸️ Task #{task_id} paused.")
                return True

            if cmd == "resume":
                self.store.set_heartbeat_task_enabled(task_id, True)
                await msg.channel.send(f"▶️ Task #{task_id} resumed.")
                return True

            if cmd == "remove":
                self.store.delete_heartbeat_task(task_id)
                await msg.channel.send(f"🗑️ Task #{task_id} removed.")
                return True

            if cmd == "run":
                await msg.channel.send(f"Running heartbeat task #{task_id}...")
                async with self._hb_lock:
                    result = await self._run_heartbeat_task(task, trigger="manual", deliver=False)
                await msg.channel.send(
                    f"✅ Task #{task_id} finished: {result.get('status')} · {result.get('note')}"
                )
                return True

        await msg.channel.send(self._hb_help_text())
        return True

    async def _handle_admin(self, msg: discord.Message) -> bool:
        content = msg.content.strip()

        if content.startswith("!hb"):
            return await self._handle_hb_command(msg)

        if content.startswith("!approve "):
            if not self._is_admin(msg.author.id):
                await msg.channel.send("You are not an admin for approval commands.")
                return True
            code = content.split(maxsplit=1)[1].strip()
            user_id = self.store.approve_pairing_code("discord", code)
            if user_id:
                await msg.channel.send(f"Approved pairing code {code} for user {user_id}.")
                try:
                    user = await self.fetch_user(int(user_id))
                    await user.send("✅ You are approved. You can message me now.")
                except Exception:
                    pass
            else:
                await msg.channel.send("Invalid or expired code.")
            return True

        if content == "!runtime":
            await msg.channel.send(self._runtime_summary())
            return True

        if content.startswith("!model"):
            if not self._is_admin(msg.author.id):
                await msg.channel.send("You are not an admin for model commands.")
                return True
            if self.cfg.backend_mode != "pi":
                await msg.channel.send("Current backend is not pi; !model has no effect.")
                return True
            parts = content.split(maxsplit=1)
            if len(parts) == 1:
                current = self._current_pi_model() or "<default from pi>"
                await msg.channel.send(
                    "Usage: `!model <model-id>` or `!model default`\n"
                    f"Current PI model: {current}"
                )
                return True
            value = parts[1].strip()
            if value.lower() in {"default", "reset", "none"}:
                self.pi_model_override = ""
                self.store.set_runtime("pi_model_override", "")
                await msg.channel.send("PI model override cleared (using env/default).")
                return True
            self.pi_model_override = value
            self.store.set_runtime("pi_model_override", value)
            await msg.channel.send(f"PI model override set to: `{value}`")
            return True

        if content.startswith("!thinking") or content.startswith("!think"):
            if not self._is_admin(msg.author.id):
                await msg.channel.send("You are not an admin for thinking commands.")
                return True
            if self.cfg.backend_mode != "pi":
                await msg.channel.send("Current backend is not pi; !thinking/!think has no effect.")
                return True
            parts = content.split(maxsplit=1)
            if len(parts) == 1:
                current = self._current_pi_thinking() or "<pi default>"
                await msg.channel.send(
                    "Usage: `!thinking off|minimal|low|medium|high|xhigh` or `!thinking default`\n"
                    "Alias: `!think off|minimal|low|medium|high|xhigh` or `!think default`\n"
                    f"Current PI thinking: {current}"
                )
                return True
            value = parts[1].strip().lower()
            if value in {"default", "reset", "none"}:
                self.pi_thinking_override = ""
                self.store.set_runtime("pi_thinking_override", "")
                await msg.channel.send("PI thinking override cleared (using env/default).")
                return True
            if value not in self.THINKING_LEVELS:
                await msg.channel.send("Invalid thinking level. Use: off|minimal|low|medium|high|xhigh")
                return True
            self.pi_thinking_override = value
            self.store.set_runtime("pi_thinking_override", value)
            await msg.channel.send(f"PI thinking override set to: `{value}`")
            return True

        return False

    # ---------------- local commands (search / research / capability) ----------------

    async def _exec_cmd(self, *args: str, timeout_sec: int = 90) -> tuple[int, str, str]:
        proc = await asyncio.create_subprocess_exec(
            *args,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            cwd="/home/ubuntu",
            env=os.environ.copy(),
        )
        try:
            out, err = await asyncio.wait_for(proc.communicate(), timeout=timeout_sec)
        except asyncio.TimeoutError:
            proc.kill()
            await proc.communicate()
            return 124, "", "command timeout"
        return proc.returncode, out.decode("utf-8", "ignore"), err.decode("utf-8", "ignore")

    async def _search_web(self, query: str) -> list[dict[str, str]]:
        rc, out, err = await self._exec_cmd(
            self.cfg.web_search_bin,
            query,
            "-n",
            str(self.cfg.research_max_results),
            "--json",
            timeout_sec=60,
        )
        if rc != 0:
            raise RuntimeError((err or out or "web search failed").strip()[:600])
        try:
            data = json.loads(out)
        except json.JSONDecodeError as e:
            raise RuntimeError(f"invalid web search JSON: {e}") from e
        results: list[dict[str, str]] = []
        for item in data:
            if not isinstance(item, dict):
                continue
            results.append(
                {
                    "title": str(item.get("title", "")).strip(),
                    "url": str(item.get("url", "")).strip(),
                    "snippet": str(item.get("snippet", "")).strip(),
                    "published": str(item.get("published", "")).strip(),
                }
            )
        return results

    @staticmethod
    def _clean_web_text(text: str) -> str:
        txt = text.replace("\r", "\n")
        txt = re.sub(r"<script.*?</script>", " ", txt, flags=re.S | re.I)
        txt = re.sub(r"<style.*?</style>", " ", txt, flags=re.S | re.I)
        txt = re.sub(r"<[^>]+>", " ", txt)
        txt = re.sub(r"\n{3,}", "\n\n", txt)
        txt = re.sub(r"[ \t]{2,}", " ", txt)
        return txt.strip()

    async def _fetch_readable_text(self, url: str) -> str:
        clean_url = url.strip()
        if not clean_url:
            return ""
        mirror = "https://r.jina.ai/http://" + clean_url.replace("https://", "").replace("http://", "")

        headers = {"User-Agent": "Mozilla/5.0 (compatible; DiscordAgentResearch/1.0)"}
        async with httpx.AsyncClient(timeout=45, follow_redirects=True, headers=headers) as client:
            for candidate in (mirror, clean_url):
                try:
                    resp = await client.get(candidate)
                    if resp.status_code >= 400:
                        continue
                    text = resp.text.strip()
                    if text:
                        return text
                except Exception:
                    continue
        return ""

    async def _build_research_context(self, query: str) -> tuple[str, list[dict[str, str]]]:
        results = await self._search_web(query)
        if not results:
            return "No web results found.", []

        lines: list[str] = []
        lines.append(f"Research query: {query}")
        lines.append("\nWeb results:")
        for i, r in enumerate(results, start=1):
            lines.append(f"[{i}] {r.get('title') or '(untitled)'}")
            lines.append(f"URL: {r.get('url') or '(missing)'}")
            if r.get("published"):
                lines.append(f"Published: {r['published']}")
            if r.get("snippet"):
                lines.append(f"Snippet: {r['snippet']}")
            lines.append("")

        readable_n = min(self.cfg.research_readable_sources, len(results))
        for i in range(readable_n):
            r = results[i]
            url = r.get("url", "").strip()
            if not url:
                continue
            page_text = await self._fetch_readable_text(url)
            if not page_text:
                continue
            cleaned = self._clean_web_text(page_text)
            excerpt = cleaned[: self.cfg.research_page_char_limit]
            lines.append(f"[Source {i + 1} excerpt begin]")
            lines.append(excerpt)
            lines.append(f"[Source {i + 1} excerpt end]\n")

        return "\n".join(lines), results

    async def _handle_local_commands(self, msg: discord.Message) -> bool:
        content = msg.content.strip()

        if content == "!help":
            text = (
                "Commands:\n"
                "- `!capabilities` 查看当前能力清单\n"
                "- `!search <query>` 仅返回检索结果\n"
                "- `!ask [model=...] [thinking=...] <prompt>` 发起异步对话任务\n"
                "- `!research [model=...] [thinking=...] <query>` 调研模式（默认异步排队）\n"
                "- `!tasks` 查看我的异步任务\n"
                "- `!task <id>` 查看单个异步任务状态\n"
                "- `!runtime` 查看当前后端/模型/thinking\n"
                "Admin:\n"
                "- `!approve <code>` 批准 DM pairing\n"
                "- `!model <model-id|default>` 设置/清除 PI 模型\n"
                "- `!thinking <off|minimal|low|medium|high|xhigh|default>` 设置/清除 PI thinking（可用别名 `!think`）\n"
                "- `!hb ...` 统一心跳框架管理（`!hb help` 查看）\n"
                "- `!tasks all` 查看全局异步任务（admin）"
            )
            await msg.channel.send(text)
            return True

        if content == "!capabilities":
            search_status = "enabled" if self.cfg.research_enabled else "disabled"
            web_tool = "ok" if os.path.exists(self.cfg.web_search_bin) else "missing"
            hb_state = "enabled" if self._is_heartbeat_enabled() else "disabled"
            report_state = "enabled" if self.cfg.report_server_enabled else "disabled"
            async_state = "enabled" if self.cfg.async_tasks_enabled else "disabled"
            pending_async = self.store.count_pending_agent_tasks() if self.cfg.async_tasks_enabled else 0
            text = (
                "Agent capabilities:\n"
                f"- backend: {self.cfg.backend_mode}\n"
                "- conversation memory: sqlite + per-channel session\n"
                f"- dm policy: {self.cfg.dm_policy}\n"
                f"- research mode: {search_status}\n"
                f"- async task queue: {async_state} (workers={self.cfg.async_task_workers}, pending={pending_async})\n"
                f"- web-search tool: {web_tool} ({self.cfg.web_search_bin})\n"
                f"- report web layer: {report_state} ({self._report_base_url()})\n"
                f"- heartbeat framework: {hb_state}\n"
                f"- current PI model: {self._current_pi_model() or '<default>'}\n"
                f"- current PI thinking: {self._current_pi_thinking() or '<default>'}\n"
                "- commands: !help !capabilities !search !ask !research !tasks !task !runtime !thinking !think !hb"
            )
            await msg.channel.send(text)
            return True

        if content.startswith("!tasks"):
            parts = content.split()
            show_all = len(parts) >= 2 and parts[1].strip().lower() == "all"
            if show_all and not self._is_admin(msg.author.id):
                await msg.channel.send("Only admins can run `!tasks all`.")
                return True

            requester_id = None if show_all else str(msg.author.id)
            rows = self.store.list_agent_tasks(limit=12, requester_id=requester_id)
            if not rows:
                await msg.channel.send("No async tasks.")
                return True

            header = "Async tasks (global):" if show_all else "Your async tasks:"
            lines = [header]
            for row in rows:
                lines.append(self._format_agent_task_line(row))
            text = "\n".join(lines)
            for chunk in self._chunks(text, self.cfg.max_reply_chars):
                await msg.channel.send(chunk)
            return True

        if content.startswith("!task"):
            parts = content.split(maxsplit=1)
            if len(parts) < 2 or not parts[1].strip().isdigit():
                await msg.channel.send("Usage: `!task <id>`")
                return True

            task_id = int(parts[1].strip())
            task = self.store.get_agent_task(task_id)
            if not task:
                await msg.channel.send(f"Task #{task_id} not found.")
                return True
            if not self._can_view_task(msg, task):
                await msg.channel.send("You are not allowed to view this task.")
                return True

            lines = [
                f"Task #{task_id}",
                f"- kind: {task.get('kind')}",
                f"- status: {task.get('status')}",
                f"- progress: {task.get('progress') or '-'}",
                f"- requester: {task.get('requester_name') or task.get('requester_id')}",
                f"- attempts: {task.get('attempts')}/{task.get('max_attempts')}",
                f"- model override: {task.get('model_override') or '<default>'}",
                f"- thinking override: {task.get('thinking_override') or '<default>'}",
                f"- created: {self._fmt_ts(int(task.get('created_at') or 0))}",
                f"- started: {self._fmt_ts(int(task.get('started_at') or 0))}",
                f"- finished: {self._fmt_ts(int(task.get('finished_at') or 0))}",
            ]
            if str(task.get("status") or "") == "failed":
                err = str(task.get("error_text") or "").strip()
                if err:
                    lines.append(f"- error: {err[:500]}")
            if str(task.get("status") or "") == "done":
                preview = _norm_text(str(task.get("result_text") or ""))
                if preview:
                    lines.append(f"- result preview: {preview[:300]}")

            await msg.channel.send("\n".join(lines))
            return True

        if content.startswith("!ask"):
            parts = content.split(maxsplit=1)
            if len(parts) < 2 or not parts[1].strip():
                await msg.channel.send("Usage: `!ask [model=...] [thinking=...] <prompt>`")
                return True

            model_raw, thinking_raw, prompt = self._parse_task_overrides(parts[1].strip())
            ok, model_override, thinking_override, err = self._validate_task_overrides(model_raw, thinking_raw)
            if not ok:
                await msg.channel.send(f"Invalid overrides: {err}")
                return True
            if not prompt:
                await msg.channel.send("Usage: `!ask [model=...] [thinking=...] <prompt>`")
                return True

            if self.cfg.async_tasks_enabled:
                task_id = await self._queue_agent_task_from_message(
                    msg,
                    kind="chat",
                    user_text=prompt,
                    model_override=model_override,
                    thinking_override=thinking_override,
                )
                pending = max(0, self.store.count_pending_agent_tasks() - 1)
                model_show = model_override or "<default>"
                think_show = thinking_override or "<default>"
                await msg.channel.send(
                    f"🧾 Task #{task_id} queued (chat). model={model_show} thinking={think_show}. "
                    f"Pending ahead: {pending}. Use `!task {task_id}` to track."
                )
                return True

            session_key = self._session_key(msg)
            history = self.store.get_history(session_key, self.cfg.history_max_turns)
            async with msg.channel.typing():
                try:
                    answer = await asyncio.wait_for(
                        self.backend.ask(
                            session_key,
                            history,
                            prompt,
                            pi_model=model_override or self._current_pi_model(),
                            pi_thinking=thinking_override or self._current_pi_thinking(),
                        ),
                        timeout=self.cfg.async_task_timeout_sec,
                    )
                except asyncio.TimeoutError:
                    await msg.channel.send(f"Request timeout after {self.cfg.async_task_timeout_sec}s.")
                    return True

            self.store.add_message(session_key, "user", prompt)
            self.store.add_message(session_key, "assistant", answer)
            for chunk in self._chunks(answer, self.cfg.max_reply_chars):
                await msg.channel.send(chunk)
            return True

        if content.startswith("!search"):
            if not self.cfg.research_enabled:
                await msg.channel.send("Research feature is disabled by config.")
                return True
            parts = content.split(maxsplit=1)
            if len(parts) < 2 or not parts[1].strip():
                await msg.channel.send("Usage: `!search <query>`")
                return True
            query = parts[1].strip()
            async with msg.channel.typing():
                try:
                    results = await self._search_web(query)
                except Exception as e:
                    await msg.channel.send(f"Search failed: {str(e)[:500]}")
                    return True

            if not results:
                await msg.channel.send("No results found.")
                return True

            lines = [f"🔎 Search results for: {query}"]
            for i, r in enumerate(results, start=1):
                title = r.get("title") or "(untitled)"
                url = r.get("url") or "(missing-url)"
                snippet = (r.get("snippet") or "").strip()
                lines.append(f"[{i}] {title}\n{url}")
                if snippet:
                    lines.append(f"    {snippet[:220]}")
            text = "\n".join(lines)
            for chunk in self._chunks(text, self.cfg.max_reply_chars):
                await msg.channel.send(chunk)
            return True

        if content.startswith("!research"):
            if not self.cfg.research_enabled:
                await msg.channel.send("Research feature is disabled by config.")
                return True
            parts = content.split(maxsplit=1)
            if len(parts) < 2 or not parts[1].strip():
                await msg.channel.send("Usage: `!research [model=...] [thinking=...] <query>`")
                return True

            model_raw, thinking_raw, query = self._parse_task_overrides(parts[1].strip())
            ok, model_override, thinking_override, err = self._validate_task_overrides(model_raw, thinking_raw)
            if not ok:
                await msg.channel.send(f"Invalid overrides: {err}")
                return True
            if not query:
                await msg.channel.send("Usage: `!research [model=...] [thinking=...] <query>`")
                return True

            if self.cfg.async_tasks_enabled:
                task_id = await self._queue_agent_task_from_message(
                    msg,
                    kind="research",
                    user_text=query,
                    model_override=model_override,
                    thinking_override=thinking_override,
                )
                pending = max(0, self.store.count_pending_agent_tasks() - 1)
                model_show = model_override or "<default>"
                think_show = thinking_override or "<default>"
                await msg.channel.send(
                    f"🧾 Task #{task_id} queued (research). model={model_show} thinking={think_show}. "
                    f"Pending ahead: {pending}. Use `!task {task_id}` to track."
                )
                return True

            # fallback sync mode
            status_msg = await msg.channel.send(f"🔎 正在调研：`{query}`")
            session_key = self._session_key(msg)
            history = self.store.get_history(session_key, self.cfg.history_max_turns)

            try:
                async with msg.channel.typing():
                    context, results = await self._build_research_context(query)
                    research_prompt = (
                        "你现在处于'深度调研模式'。\n"
                        "请基于给定的检索证据回答用户问题，要求：\n"
                        "1) 先给结论摘要，再给关键事实，再给风险/不确定性。\n"
                        "2) 尽量引用来源编号 [1][2]。\n"
                        "3) 对证据不足的地方明确说'证据不足'，不要编造。\n"
                        "4) 最后给出下一步建议（可执行）。\n\n"
                        f"用户问题：{query}\n\n"
                        f"可用证据：\n{context}\n"
                    )
                    answer = await asyncio.wait_for(
                        self.backend.ask(
                            session_key,
                            history,
                            research_prompt,
                            pi_model=model_override or self._current_pi_model(),
                            pi_thinking=thinking_override or self._current_pi_thinking(),
                        ),
                        timeout=self.cfg.async_task_timeout_sec,
                    )
            except Exception as e:
                await status_msg.edit(content=f"Research failed: {str(e)[:500]}")
                return True

            full_answer = answer
            if results:
                source_lines = ["", "Sources:"]
                for i, r in enumerate(results, start=1):
                    url = r.get("url", "").strip()
                    if not url:
                        continue
                    source_lines.append(f"[{i}] {url}")
                full_answer = full_answer + "\n" + "\n".join(source_lines)

            self.store.add_message(session_key, "user", f"!research {query}")
            self.store.add_message(session_key, "assistant", full_answer)

            publish_url: str | None = None
            if self.cfg.report_server_enabled and self.cfg.report_auto_for_research:
                if len(full_answer) >= self.cfg.report_auto_min_chars or self._looks_complex_markdown(full_answer):
                    meta = [
                        f"Query: {query}",
                        f"Generated: {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%SZ')}",
                        f"Backend: {self.cfg.backend_mode}",
                        f"PI model: {model_override or self._current_pi_model() or '<default>'}",
                        f"PI thinking: {thinking_override or self._current_pi_thinking() or '<default>'}",
                    ]
                    publish_url = self._publish_markdown_report(
                        title=f"Research - {query}",
                        markdown=full_answer,
                        meta=meta,
                    )

            if publish_url:
                summary = _norm_text(answer)
                if len(summary) > 1200:
                    summary = summary[:1200] + " ..."
                response_text = (
                    "✅ 调研完成。内容较长，已生成网页报告：\n"
                    f"{publish_url}\n\n"
                    "摘要：\n"
                    f"{summary}"
                )
                await status_msg.edit(content="✅ 调研完成（已生成网页报告）")
                await self._send_text_to_msg_target_with_outbox(
                    msg,
                    response_text,
                    context="research-report-link",
                )
                return True

            await status_msg.edit(content="✅ 调研完成")
            await self._send_text_to_msg_target_with_outbox(
                msg,
                full_answer,
                context="research-reply",
            )
            return True

        return False

    async def on_message(self, msg: discord.Message):
        if msg.author.bot:
            return

        is_dm = isinstance(msg.channel, discord.DMChannel)

        if not is_dm:
            guild_id = str(msg.guild.id) if msg.guild else ""
            channel_id = str(msg.channel.id)
            if self.cfg.allowed_guild_ids and guild_id not in self.cfg.allowed_guild_ids:
                return
            if self.cfg.allowed_channel_ids and channel_id not in self.cfg.allowed_channel_ids:
                return

        # admin commands are evaluated early (still gated by guild/channel allowlists above)
        if await self._handle_admin(msg):
            return

        if is_dm:
            if self.cfg.dm_policy == "disabled":
                return
            if self.cfg.dm_policy in {"allowlist", "pairing"}:
                if not self.store.is_user_allowed("discord", str(msg.author.id)):
                    if self.cfg.dm_policy == "allowlist":
                        await msg.channel.send("You are not allowlisted.")
                        return
                    code = self.store.upsert_pairing("discord", str(msg.author.id))
                    await msg.channel.send(
                        "🔐 Pairing required. Ask an admin to approve this code with `!approve <code>`:\n"
                        f"`{code}`"
                    )
                    return

        if await self._handle_local_commands(msg):
            return

        user_text = msg.content.strip()
        if not user_text:
            return

        if not is_dm:
            if self.cfg.require_mention and self.user and self.user not in msg.mentions:
                return

        if self.user:
            user_text = user_text.replace(f"<@{self.user.id}>", "").replace(
                f"<@!{self.user.id}>", ""
            ).strip()

        if not user_text:
            return

        if self.cfg.async_tasks_enabled:
            task_id = await self._queue_agent_task_from_message(msg, kind="chat", user_text=user_text)
            pending = max(0, self.store.count_pending_agent_tasks() - 1)
            await msg.channel.send(
                f"🧾 Task #{task_id} queued. Pending ahead: {pending}. Use `!task {task_id}` to track."
            )
            return

        session_key = self._session_key(msg)
        history = self.store.get_history(session_key, self.cfg.history_max_turns)

        async with msg.channel.typing():
            try:
                answer = await asyncio.wait_for(
                    self.backend.ask(
                        session_key,
                        history,
                        user_text,
                        pi_model=self._current_pi_model(),
                        pi_thinking=self._current_pi_thinking(),
                    ),
                    timeout=self.cfg.async_task_timeout_sec,
                )
            except asyncio.TimeoutError:
                await msg.channel.send(f"Request timeout after {self.cfg.async_task_timeout_sec}s.")
                return

        self.store.add_message(session_key, "user", user_text)
        self.store.add_message(session_key, "assistant", answer)

        for chunk in self._chunks(answer, self.cfg.max_reply_chars):
            await msg.channel.send(chunk)


def main() -> None:
    load_dotenv()
    cfg = Config.from_env()
    store = Store(cfg.sqlite_path)
    backend = AgentBackend(cfg)
    client = DiscordAgent(cfg, store, backend)
    client.run(cfg.token)


if __name__ == "__main__":
    main()
