import json
import sqlite3
import uuid
from datetime import datetime, timezone
from . import config

SCHEMA = '''
CREATE TABLE IF NOT EXISTS tasks (
 id TEXT PRIMARY KEY, repo TEXT NOT NULL, kind TEXT NOT NULL, args TEXT NOT NULL,
 status TEXT NOT NULL, result TEXT NOT NULL DEFAULT '', created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS devices(token TEXT PRIMARY KEY, created_at TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS subscriptions(token TEXT NOT NULL, repo TEXT NOT NULL,
 PRIMARY KEY(token, repo));
CREATE TABLE IF NOT EXISTS deliveries(delivery_id TEXT PRIMARY KEY, received_at TEXT NOT NULL);
CREATE VIRTUAL TABLE IF NOT EXISTS repo_index USING fts5(repo UNINDEXED, path UNINDEXED, content, tokenize='unicode61');
'''

def db():
    config.DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(config.DB_PATH), timeout=15)
    conn.row_factory = sqlite3.Row
    return conn

def initialize():
    with db() as conn:
        conn.executescript(SCHEMA)
        # A process can die while a task is running. Don't claim it succeeded.
        conn.execute("UPDATE tasks SET status='failed', result='Worker interrupted; retry manually' WHERE status='running'")

def create_task(repo, kind, arguments):
    task_id = str(uuid.uuid4())
    timestamp = datetime.now(timezone.utc).isoformat()
    with db() as conn:
        conn.execute('INSERT INTO tasks (id, repo, kind, args, status, created_at) VALUES (?,?,?,?,?,?)',
                     (task_id, repo, kind, json.dumps(arguments, ensure_ascii=False), 'pending_confirmation', timestamp))
    return get_task(task_id)

def get_task(task_id):
    with db() as conn:
        row = conn.execute('SELECT * FROM tasks WHERE id=?', (task_id,)).fetchone()
    return dict(row) if row else None

def list_tasks():
    with db() as conn:
        return [dict(row) for row in conn.execute('SELECT * FROM tasks ORDER BY created_at DESC LIMIT 100')]

def update_status(task_id, status, result=''):
    with db() as conn:
        conn.execute('UPDATE tasks SET status=?, result=? WHERE id=?', (status, result, task_id))

def queue_task(task_id):
    with db() as conn:
        cursor = conn.execute("UPDATE tasks SET status='queued' WHERE id=? AND status='pending_confirmation'", (task_id,))
        return cursor.rowcount == 1

def record_delivery(delivery_id):
    with db() as conn:
        cursor = conn.execute('INSERT OR IGNORE INTO deliveries VALUES (?,?)',
                              (delivery_id, datetime.now(timezone.utc).isoformat()))
        return cursor.rowcount == 1

def register_device(token, repos):
    with db() as conn:
        conn.execute('INSERT OR REPLACE INTO devices VALUES (?,?)', (token, datetime.now(timezone.utc).isoformat()))
        conn.execute('DELETE FROM subscriptions WHERE token=?', (token,))
        conn.executemany('INSERT INTO subscriptions VALUES (?,?)', [(token, r) for r in repos])

def tokens_for_repo(repo):
    with db() as conn:
        return [r['token'] for r in conn.execute('SELECT token FROM subscriptions WHERE repo=?', (repo,))]

def store_index(repo, chunks):
    with db() as conn:
        conn.execute('DELETE FROM repo_index WHERE repo=?', (repo,))
        conn.executemany('INSERT INTO repo_index (repo,path,content) VALUES (?,?,?)',
                         [(repo, path, content) for path, content in chunks])

def search_index(repo, terms, limit=8):
    with db() as conn:
        rows = conn.execute('SELECT path,content FROM repo_index WHERE repo=? AND repo_index MATCH ? ORDER BY bm25(repo_index) LIMIT ?',
                            (repo, terms, limit)).fetchall()
        return [dict(r) for r in rows]
