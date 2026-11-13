"""Single-writer, transactional checkpoints. No state is created on import."""
from __future__ import annotations

from contextlib import contextmanager
from pathlib import Path
import json
import os
import sqlite3

from common import GenerationError, atomic_write, canonical, file_hash, pretty, utc_now

DATABASE = "checkpoint.sqlite3"
LOCKFILE = ".writer.lock"


@contextmanager
def writer_lock(directory: Path):
    """OS releases lock on crash; no stale-PID lock-file deletion is needed."""
    directory.mkdir(parents=True, exist_ok=True)
    stream = (directory / LOCKFILE).open("a+b")
    locked = False
    try:
        if stream.seek(0, os.SEEK_END) == 0:
            stream.write(b"\0")
            stream.flush()
        stream.seek(0)
        try:
            if os.name == "nt":
                import msvcrt
                msvcrt.locking(stream.fileno(), msvcrt.LK_NBLCK, 1)
            else:
                import fcntl
                fcntl.flock(stream.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
            locked = True
        except OSError as exc:
            raise GenerationError(f"Another process is writing this run: {directory}") from exc
        yield
    finally:
        if locked:
            stream.seek(0)
            if os.name == "nt":
                import msvcrt
                msvcrt.locking(stream.fileno(), msvcrt.LK_UNLCK, 1)
            else:
                import fcntl
                fcntl.flock(stream.fileno(), fcntl.LOCK_UN)
        stream.close()


def check_output_directory(directory: Path):
    if directory.exists() and not (directory / DATABASE).exists():
        unexpected = [entry.name for entry in directory.iterdir() if entry.name != LOCKFILE]
        if unexpected:
            raise GenerationError(f"Output directory is not an owned generation run: {directory}; use a new empty directory")


class Store:
    def __init__(self, directory: Path, run_identity: dict, stage_sizes: dict, make_plan):
        self.directory = directory
        self.connection = sqlite3.connect(directory / DATABASE, isolation_level=None, timeout=10)
        self.connection.row_factory = sqlite3.Row
        try:
            self.connection.execute("PRAGMA journal_mode=WAL")
            self.connection.execute("PRAGMA synchronous=FULL")
            self.connection.execute("PRAGMA foreign_keys=ON")
            existing = {row[0] for row in self.connection.execute("SELECT name FROM sqlite_master WHERE type='table'")}
            if existing - {"metadata", "stages", "records", "exports"}:
                raise GenerationError("Checkpoint contains unknown tables; refusing to modify it")
            with self.transaction():
                self.connection.execute("CREATE TABLE IF NOT EXISTS metadata (key TEXT PRIMARY KEY, value TEXT NOT NULL)")
                self.connection.execute("CREATE TABLE IF NOT EXISTS stages (name TEXT PRIMARY KEY, total_units INTEGER NOT NULL, expected_rows INTEGER NOT NULL, completed_units INTEGER NOT NULL DEFAULT 0, written_rows INTEGER NOT NULL DEFAULT 0)")
                self.connection.execute("CREATE TABLE IF NOT EXISTS records (stage TEXT NOT NULL REFERENCES stages(name), position INTEGER NOT NULL, record_id TEXT NOT NULL, payload TEXT NOT NULL, PRIMARY KEY(stage, position), UNIQUE(stage, record_id))")
                self.connection.execute("CREATE TABLE IF NOT EXISTS exports (name TEXT PRIMARY KEY, sha256 TEXT NOT NULL, bytes INTEGER NOT NULL)")
                saved = self.get("identity")
                if saved is None:
                    if self.connection.execute("SELECT count(*) FROM records").fetchone()[0]:
                        raise GenerationError("Checkpoint has records without run identity")
                    self.set("identity", run_identity)
                    self.set("startedAt", utc_now())
                    self.set("plan", make_plan())
                    self.set("complete", False)
                    for name, size in stage_sizes.items():
                        self.connection.execute("INSERT INTO stages(name,total_units,expected_rows) VALUES(?,?,?)", (name, size[0], size[1]))
                elif saved != run_identity:
                    raise GenerationError("Run identity differs: restore original code/config/catalogues/Python or choose a new --output directory")
            if self.connection.execute("PRAGMA quick_check").fetchone()[0] != "ok":
                raise GenerationError("SQLite checkpoint integrity check failed")
            for stage, (units, rows) in stage_sizes.items():
                progress = self.progress(stage)
                actual = self.connection.execute("SELECT count(*) FROM records WHERE stage=?", (stage,)).fetchone()[0]
                if progress["total_units"] != units or progress["expected_rows"] != rows or actual != progress["written_rows"]:
                    raise GenerationError(f"Checkpoint counts disagree for stage {stage}")
                if not 0 <= progress["completed_units"] <= units or not 0 <= actual <= rows:
                    raise GenerationError(f"Invalid checkpoint progress for stage {stage}")
        except BaseException:
            self.connection.close()
            raise

    @contextmanager
    def transaction(self):
        self.connection.execute("BEGIN IMMEDIATE")
        try:
            yield
            self.connection.execute("COMMIT")
        except BaseException:
            if self.connection.in_transaction:
                self.connection.execute("ROLLBACK")
            raise

    def get(self, key):
        row = self.connection.execute("SELECT value FROM metadata WHERE key=?", (key,)).fetchone()
        return json.loads(row[0]) if row else None

    def set(self, key, value):
        self.connection.execute("INSERT INTO metadata(key,value) VALUES(?,?) ON CONFLICT(key) DO UPDATE SET value=excluded.value", (key, canonical(value).decode("utf-8")))

    @property
    def plan(self):
        return self.get("plan")

    def progress(self, stage: str) -> dict:
        row = self.connection.execute("SELECT * FROM stages WHERE name=?", (stage,)).fetchone()
        if row is None:
            raise GenerationError(f"Missing checkpoint stage: {stage}")
        return dict(row)

    def rows(self, stage: str) -> list[dict]:
        return [json.loads(row[0]) for row in self.connection.execute("SELECT payload FROM records WHERE stage=? ORDER BY position", (stage,))]

    def commit_units(self, stage: str, start: int, units: list[list[dict]]):
        """All rows, including transfer pairs, and their cursor commit together."""
        with self.transaction():
            progress = self.progress(stage)
            if progress["completed_units"] != start:
                raise GenerationError(f"Concurrent or inconsistent cursor for {stage}")
            position = progress["written_rows"]
            for group in units:
                if not group:
                    raise GenerationError("A generation unit must produce at least one row")
                for row in group:
                    record_id = row.get("_id", row.get("transactionId"))
                    self.connection.execute("INSERT INTO records(stage,position,record_id,payload) VALUES(?,?,?,?)", (stage, position, record_id, canonical(row).decode("utf-8")))
                    position += 1
            new_cursor = start + len(units)
            if new_cursor > progress["total_units"] or position > progress["expected_rows"]:
                raise GenerationError(f"Stage {stage} exceeded planned counts")
            if new_cursor == progress["total_units"] and position != progress["expected_rows"]:
                raise GenerationError(f"Stage {stage} ended with wrong record count")
            self.connection.execute("UPDATE stages SET completed_units=?,written_rows=? WHERE name=?", (new_cursor, position, stage))
            self.set("updatedAt", utc_now())

    def export(self, filename: str, writer):
        if Path(filename).name != filename or filename == DATABASE:
            raise GenerationError("Invalid export filename")
        path = self.directory / filename
        saved = self.connection.execute("SELECT sha256 FROM exports WHERE name=?", (filename,)).fetchone()
        if saved and path.exists():
            if file_hash(path) != saved[0]:
                raise GenerationError(f"Committed export was modified: {path}; restore original or use new run")
            return saved[0]
        digest = atomic_write(path, writer)
        with self.transaction():
            self.connection.execute("INSERT INTO exports(name,sha256,bytes) VALUES(?,?,?) ON CONFLICT(name) DO UPDATE SET sha256=excluded.sha256,bytes=excluded.bytes", (filename, digest, path.stat().st_size))
        return digest

    def export_json(self, name: str, value):
        return self.export(name, lambda stream: stream.write(pretty(value)))

    def exported_files(self) -> dict:
        return {row["name"]: {"sha256": row["sha256"], "bytes": row["bytes"]} for row in self.connection.execute("SELECT * FROM exports WHERE name != 'manifest.json' ORDER BY name")}

    def mark_complete(self):
        with self.transaction():
            self.set("complete", True)
            self.set("completedAt", utc_now())

    def close(self):
        self.connection.close()


def read_status(directory: Path) -> dict:
    database = directory / DATABASE
    if not database.is_file():
        return {"directory": str(directory), "started": False}
    connection = sqlite3.connect(database.as_uri() + "?mode=ro", uri=True, timeout=5)
    connection.row_factory = sqlite3.Row
    try:
        names = {row[0] for row in connection.execute("SELECT name FROM sqlite_master WHERE type='table'")}
        if not {"metadata", "stages", "exports"}.issubset(names):
            return {"directory": str(directory), "started": True, "initialisationInterrupted": True}
        metadata = {row["key"]: json.loads(row["value"]) for row in connection.execute("SELECT * FROM metadata")}
        exports = []
        for row in connection.execute("SELECT * FROM exports ORDER BY name"):
            path = directory / row["name"]
            exports.append({"name": row["name"], "exists": path.is_file(), "hashMatches": path.is_file() and file_hash(path) == row["sha256"]})
        return {"directory": str(directory), "started": True, "complete": metadata.get("complete", False),
                "fingerprint": metadata.get("identity", {}).get("fingerprint"),
                "stages": [dict(row) for row in connection.execute("SELECT * FROM stages ORDER BY rowid")], "exports": exports}
    finally:
        connection.close()
