"""SQLite persistence for anonymous owners and task metadata."""
import json
import sqlite3
import threading
import time


class TaskStore:
    def __init__(self, db_path):
        self.db_path = db_path
        self._init_lock = threading.Lock()
        self._initialized = False
        self._init_db()

    def _connect(self):
        conn = sqlite3.connect(self.db_path, timeout=15)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA busy_timeout=15000")
        return conn

    def _init_db(self):
        with self._init_lock:
            if self._initialized:
                return
            with self._connect() as conn:
                conn.execute("PRAGMA journal_mode=WAL")
                conn.execute("""
                    CREATE TABLE IF NOT EXISTS owners (
                        owner_hash TEXT PRIMARY KEY,
                        settings_json TEXT NOT NULL DEFAULT '{}',
                        created_at REAL NOT NULL,
                        updated_at REAL NOT NULL
                    )
                """)
                conn.execute("""
                    CREATE TABLE IF NOT EXISTS tasks (
                        task_id TEXT PRIMARY KEY,
                        owner_hash TEXT NOT NULL,
                        state_json TEXT NOT NULL,
                        cancel_requested INTEGER NOT NULL DEFAULT 0,
                        delete_pending INTEGER NOT NULL DEFAULT 0,
                        created_at REAL NOT NULL,
                        updated_at REAL NOT NULL
                    )
                """)
                conn.execute(
                    "CREATE INDEX IF NOT EXISTS idx_tasks_owner_updated "
                    "ON tasks(owner_hash, updated_at DESC)")
            self._initialized = True

    @staticmethod
    def _encode(value):
        return json.dumps(value, ensure_ascii=False, separators=(",", ":"))

    @staticmethod
    def _decode(value, default):
        try:
            parsed = json.loads(value)
            return parsed if isinstance(parsed, type(default)) else default
        except (TypeError, ValueError, json.JSONDecodeError):
            return default

    def ensure_owner(self, owner_hash):
        now = time.time()
        with self._connect() as conn:
            conn.execute(
                "INSERT OR IGNORE INTO owners "
                "(owner_hash, settings_json, created_at, updated_at) "
                "VALUES (?, '{}', ?, ?)", (owner_hash, now, now))

    def get_owner_settings(self, owner_hash):
        self.ensure_owner(owner_hash)
        with self._connect() as conn:
            row = conn.execute(
                "SELECT settings_json FROM owners WHERE owner_hash=?",
                (owner_hash,)).fetchone()
        return self._decode(row["settings_json"] if row else "{}", {})

    def save_owner_settings(self, owner_hash, settings):
        self.ensure_owner(owner_hash)
        with self._connect() as conn:
            conn.execute(
                "UPDATE owners SET settings_json=?, updated_at=? "
                "WHERE owner_hash=?",
                (self._encode(settings), time.time(), owner_hash))

    def create_task(self, task_id, owner_hash, state):
        self.ensure_owner(owner_hash)
        now = time.time()
        with self._connect() as conn:
            conn.execute(
                "INSERT INTO tasks "
                "(task_id, owner_hash, state_json, created_at, updated_at) "
                "VALUES (?, ?, ?, ?, ?)",
                (task_id, owner_hash, self._encode(state), now, now))

    def update_task(self, task_id, state):
        with self._connect() as conn:
            conn.execute(
                "UPDATE tasks SET state_json=?, updated_at=? WHERE task_id=?",
                (self._encode(state), time.time(), task_id))

    def get_task(self, task_id, owner_hash=None):
        sql = ("SELECT task_id, owner_hash, state_json, cancel_requested, "
               "delete_pending, created_at, updated_at FROM tasks WHERE task_id=?")
        args = [task_id]
        if owner_hash is not None:
            sql += " AND owner_hash=?"
            args.append(owner_hash)
        with self._connect() as conn:
            row = conn.execute(sql, args).fetchone()
        if not row:
            return None
        return {
            "task_id": row["task_id"],
            "owner_hash": row["owner_hash"],
            "state": self._decode(row["state_json"], {}),
            "cancel_requested": bool(row["cancel_requested"]),
            "delete_pending": bool(row["delete_pending"]),
            "created_at": row["created_at"],
            "updated_at": row["updated_at"],
        }

    def list_tasks(self, owner_hash, limit=100):
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT task_id, state_json, cancel_requested, delete_pending, "
                "created_at, updated_at FROM tasks WHERE owner_hash=? "
                "ORDER BY updated_at DESC LIMIT ?", (owner_hash, limit)).fetchall()
        return [{
            "task_id": row["task_id"],
            "state": self._decode(row["state_json"], {}),
            "cancel_requested": bool(row["cancel_requested"]),
            "delete_pending": bool(row["delete_pending"]),
            "created_at": row["created_at"],
            "updated_at": row["updated_at"],
        } for row in rows]

    def set_flags(self, task_id, owner_hash, *, cancel=None, delete=None):
        fields = []
        args = []
        if cancel is not None:
            fields.append("cancel_requested=?")
            args.append(1 if cancel else 0)
        if delete is not None:
            fields.append("delete_pending=?")
            args.append(1 if delete else 0)
        if not fields:
            return False
        fields.append("updated_at=?")
        args.append(time.time())
        args.extend((task_id, owner_hash))
        with self._connect() as conn:
            cur = conn.execute(
                f"UPDATE tasks SET {', '.join(fields)} "
                "WHERE task_id=? AND owner_hash=?", args)
        return cur.rowcount > 0

    def delete_task(self, task_id, owner_hash=None):
        sql = "DELETE FROM tasks WHERE task_id=?"
        args = [task_id]
        if owner_hash is not None:
            sql += " AND owner_hash=?"
            args.append(owner_hash)
        with self._connect() as conn:
            cur = conn.execute(sql, args)
        return cur.rowcount > 0

    def mark_interrupted_tasks(self):
        terminal = {"ready", "done", "error", "cancelled"}
        changed = 0
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT task_id, state_json FROM tasks").fetchall()
            for row in rows:
                state = self._decode(row["state_json"], {})
                if state.get("stage") in terminal:
                    continue
                state["stage"] = "error"
                state["message"] = "服务器进程曾重启，原后台任务已中断；可删除任务后重新提交"
                conn.execute(
                    "UPDATE tasks SET state_json=?, cancel_requested=0, "
                    "delete_pending=0, updated_at=? WHERE task_id=?",
                    (self._encode(state), time.time(), row["task_id"]))
                changed += 1
        return changed
