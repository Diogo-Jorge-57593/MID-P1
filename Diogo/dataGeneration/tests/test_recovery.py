"""Future runtime checks. NOT executed during implementation.

Running this suite creates isolated temporary datasets, never writes MongoDB,
and compares uninterrupted/resumed runs. Invoke only when generation is allowed.
"""
from __future__ import annotations

import json
import os
from pathlib import Path
import sqlite3
import subprocess
import sys
import tempfile
import unittest

HERE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(HERE))
from checkpoint import Store, writer_lock
from common import GenerationError, file_hash


def invoke(directory: Path, *options, success=True):
    result = subprocess.run([sys.executable, "-B", str(HERE / "generate.py"), "run",
                             "--output", str(directory), *options],
                            capture_output=True, text=True, encoding="utf-8",
                            env={**os.environ, "PYTHONUTF8": "1"})
    if success and result.returncode:
        raise AssertionError(result.stdout + result.stderr)
    return result


class CheckpointTests(unittest.TestCase):
    def test_hard_abort_leaves_last_committed_batch_intact(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            with writer_lock(root):
                store = Store(root, {"fingerprint": "manual-crash"}, {"transactions": (2, 3)}, lambda: {})
                store.commit_units("transactions", 0, [[{"transactionId": "manual-1"}]])
                store.close()
            script = """
import os, sqlite3, sys
connection = sqlite3.connect(sys.argv[1], isolation_level=None)
connection.execute('BEGIN IMMEDIATE')
connection.execute('INSERT INTO records(stage,position,record_id,payload) VALUES(?,?,?,?)',
                   ('transactions', 1, 'manual-2', '{"transactionId":"manual-2"}'))
connection.execute("UPDATE stages SET completed_units=2,written_rows=3 WHERE name='transactions'")
os._exit(17)
"""
            failed = subprocess.run([sys.executable, "-B", "-c", script, str(root / "checkpoint.sqlite3")])
            self.assertEqual(failed.returncode, 17)
            with writer_lock(root):
                resumed = Store(root, {"fingerprint": "manual-crash"}, {"transactions": (2, 3)}, lambda: {})
                try:
                    self.assertEqual(resumed.progress("transactions")["completed_units"], 1)
                    self.assertEqual(len(resumed.rows("transactions")), 1)
                    resumed.commit_units("transactions", 1, [[{"transactionId": "manual-2"}, {"transactionId": "manual-3"}]])
                    self.assertEqual(len(resumed.rows("transactions")), 3)
                finally:
                    resumed.close()

    def test_failed_pair_rolls_back_both_records_and_cursor(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            with writer_lock(root):
                store = Store(root, {"fingerprint": "manual-test"}, {"transactions": (2, 3)}, lambda: {})
                try:
                    store.commit_units("transactions", 0, [[{"transactionId": "manual-1"}]])
                    with self.assertRaises(sqlite3.IntegrityError):
                        store.commit_units("transactions", 1, [[{"transactionId": "manual-2"}, {"transactionId": "manual-1"}]])
                    self.assertEqual(store.progress("transactions")["completed_units"], 1)
                    self.assertEqual(len(store.rows("transactions")), 1)
                    store.commit_units("transactions", 1, [[{"transactionId": "manual-2"}, {"transactionId": "manual-3"}]])
                    self.assertEqual(store.progress("transactions")["completed_units"], 2)
                    self.assertEqual(len(store.rows("transactions")), 3)
                finally:
                    store.close()

    def test_partial_export_recovery_and_modified_export_rejection(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            with writer_lock(root):
                store = Store(root, {"fingerprint": "manual-test"}, {"clients": (0, 0)}, lambda: {})
                try:
                    def interrupted(stream):
                        stream.write(b"partial")
                        raise OSError("simulated interruption")
                    with self.assertRaises(OSError):
                        store.export("manual.txt", interrupted)
                    self.assertFalse((root / "manual.txt").exists())
                    store.export("manual.txt", lambda stream: stream.write(b"complete"))
                    self.assertEqual((root / "manual.txt").read_bytes(), b"complete")
                    (root / "manual.txt").write_bytes(b"modified")
                    with self.assertRaises(GenerationError):
                        store.export("manual.txt", lambda stream: stream.write(b"complete"))
                    self.assertEqual((root / "manual.txt").read_bytes(), b"modified")
                finally:
                    store.close()

    def test_different_identity_cannot_resume(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            with writer_lock(root):
                store = Store(root, {"fingerprint": "original"}, {"clients": (0, 0)}, lambda: {})
                store.close()
                with self.assertRaises(GenerationError):
                    Store(root, {"fingerprint": "changed"}, {"clients": (0, 0)}, lambda: {})


class GeneratorTests(unittest.TestCase):
    def test_reference_resume_at_transfer_boundary_matches_clean_run(self):
        with tempfile.TemporaryDirectory() as temp:
            clean, resumed = Path(temp) / "clean", Path(temp) / "resumed"
            invoke(clean, "--profile", "reference")
            # 19 entity units, then one ordinary unit and one two-row pair.
            invoke(resumed, "--profile", "reference", "--batch-size", "1", "--stop-after-units", "21")
            connection = sqlite3.connect(resumed / "checkpoint.sqlite3")
            try:
                progress = connection.execute("SELECT completed_units,written_rows FROM stages WHERE name='transactions'").fetchone()
                self.assertEqual(progress, (2, 3))
            finally:
                connection.close()
            invoke(resumed, "--profile", "reference", "--batch-size", "7")
            manifest = json.loads((clean / "manifest.json").read_text(encoding="utf-8"))
            for filename in manifest["files"]:
                self.assertEqual(file_hash(clean / filename), file_hash(resumed / filename), filename)
            again = invoke(resumed, "--profile", "reference")
            self.assertIn("Complete and validated", again.stdout)

    def test_missing_export_is_rebuilt_and_changed_input_is_rejected(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp) / "run"
            invoke(root, "--profile", "reference")
            digest = file_hash(root / "transactions.csv")
            (root / "transactions.csv").unlink()
            invoke(root, "--profile", "reference")
            self.assertEqual(file_hash(root / "transactions.csv"), digest)
            config = json.loads((HERE / "config.json").read_text(encoding="utf-8"))
            config["seed"] += 1
            changed = Path(temp) / "changed.json"
            changed.write_text(json.dumps(config), encoding="utf-8")
            rejected = invoke(root, "--profile", "reference", "--config", str(changed), success=False)
            self.assertNotEqual(rejected.returncode, 0)
            self.assertIn("Run identity differs", rejected.stderr)

    def test_scale_resume_matches_default_quotas_and_clean_outputs(self):
        with tempfile.TemporaryDirectory() as temp:
            clean, resumed = Path(temp) / "clean", Path(temp) / "resumed"
            invoke(clean, "--profile", "scale", "--batch-size", "113")
            # 3,025 entity units + 6,000 ordinary rows + one complete pair.
            invoke(resumed, "--profile", "scale", "--batch-size", "37", "--stop-after-units", "9026")
            invoke(resumed, "--profile", "scale", "--batch-size", "89")
            manifest = json.loads((clean / "manifest.json").read_text(encoding="utf-8"))
            self.assertEqual(manifest["counts"], {"clients": 500, "employees": 25, "accounts": 1000, "applications": 1500, "transactions": 8000})
            for filename in manifest["files"]:
                self.assertEqual(file_hash(clean / filename), file_hash(resumed / filename), filename)

    def test_broken_csv_fails_independent_validation(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp) / "run"
            invoke(root, "--profile", "reference")
            path = root / "transactions.csv"
            content = path.read_bytes().replace(b";A001;", b";A999;", 1)
            path.write_bytes(content)
            result = subprocess.run([sys.executable, "-B", str(HERE / "validate.py"), str(root)], capture_output=True, text=True, encoding="utf-8", env={**os.environ, "PYTHONUTF8": "1"})
            self.assertNotEqual(result.returncode, 0)
            self.assertIn('"valid": false', result.stdout)


if __name__ == "__main__":
    unittest.main()
