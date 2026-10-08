# agent/checkpointing.py

"""
Phase 18b, durability: a SQLite checkpointer, so a paused review (and the
human's recorded decision) survives a process restart.

Three facts shape this small file, each learned the hard way earlier in
this project:

  - check_same_thread=False is REQUIRED. FastAPI runs sync routes in a
    thread pool, so the run will be started on one worker thread and
    decided on another, while the connection was created at startup on
    a third. A default sqlite3 connection refuses to be used from any
    thread but its creator ("SQLite objects created in a thread can
    only be used in that same thread" -- the same sentence the earlier
    StaticPool bug ended on). SqliteSaver makes the shared connection
    safe with its own internal lock.
  - The saver is built from an explicit connection, NOT
    SqliteSaver.from_conn_string(): that is a context manager that
    closes the connection when its `with` block ends, which suits a
    short script and not a server that must keep one open.
  - ONE process, ONE file. The lock lives inside the process; SQLite
    on a shared volume does not make two replicas safe. Run a single
    replica, and in Kubernetes put the file on storage that outlives
    the pod: a file on a pod's own disk disappears when the pod is
    replaced.

No default location and no environment-variable magic: the caller
decides where the file lives and passes the result to
start_supplier_review / resume_supplier_review. A hidden global would be
exactly the kind of shared state the tests are written to avoid.
"""

import sqlite3
from pathlib import Path

from langgraph.checkpoint.sqlite import SqliteSaver


def make_sqlite_checkpointer(path: str) -> SqliteSaver:
    if path != ":memory:":
        Path(path).parent.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(path, check_same_thread=False)
    saver = SqliteSaver(connection)
    saver.setup()
    return saver
