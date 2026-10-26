"""Regression checks for accidental edits to otherwise valid SQLite caches."""
import importlib.util
from contextlib import closing
from pathlib import Path
import json
import shutil
from unittest.mock import patch
import sqlite3
import tempfile
import unittest

spec = importlib.util.spec_from_file_location("verified_cache", Path(__file__).resolve().parents[1] / "scripts/prepare_verified_stores.py")
cache = importlib.util.module_from_spec(spec)
spec.loader.exec_module(cache)


class VerifiedCacheTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.database = Path(self.temp.name) / "sample.sqlite"
        with closing(sqlite3.connect(self.database)) as conn, conn:
            conn.execute("CREATE TABLE origination (loan_id TEXT PRIMARY KEY, fico INTEGER)")
            conn.execute("INSERT INTO origination VALUES ('synthetic', 700)")
            conn.execute("CREATE TABLE performance (loan_id TEXT, period INTEGER, PRIMARY KEY (loan_id,period))")
            conn.execute("INSERT INTO performance VALUES ('synthetic', 202001)")
        self.source = "synthetic-source-digest"
        self.methods = {"synthetic-method": "digest"}
        self.audit = {"origination": {"rows": 1}, "performance": {"rows": 1}}
        self.record = cache.attest(self.database, self.source, self.methods, self.audit)

    def tearDown(self):
        self.temp.cleanup()

    def test_untouched_cache_reuses_the_recorded_bytes(self):
        cache.verify_attestation(self.database, self.record, self.source, self.methods)

    def test_valid_sql_edit_fails_even_when_integrity_and_counts_still_pass(self):
        with closing(sqlite3.connect(self.database)) as conn, conn:
            conn.execute("UPDATE origination SET fico=799")
            self.assertEqual(conn.execute("PRAGMA integrity_check").fetchone()[0], "ok")
            self.assertEqual(conn.execute("SELECT COUNT(*) FROM origination").fetchone()[0], 1)
        with self.assertRaisesRegex(ValueError, "cache bytes changed"):
            cache.verify_attestation(self.database, self.record, self.source, self.methods)

    def test_missing_cache_and_wrong_source_or_method_fail(self):
        with self.assertRaises(ValueError):
            cache.verify_attestation(self.database, self.record, "changed-source", self.methods)
        with self.assertRaises(ValueError):
            cache.verify_attestation(self.database, self.record, self.source, {"method": "changed"})
        self.database.unlink()
        with self.assertRaises(ValueError):
            cache.verify_attestation(self.database, self.record, self.source, self.methods)

    def test_entrypoint_rejects_changed_cache_before_any_ingestion_or_reuse(self):
        root = Path(self.temp.name)
        processed = root / "data/processed"
        processed.mkdir(parents=True)
        raw = root / "data/raw"
        raw.mkdir()
        intake = root / "source_intake/reports"
        intake.mkdir(parents=True)
        source_path = raw / "sample_2012.zip"
        source_path.write_bytes(b"synthetic pinned input")
        source_hash = cache.sha256(source_path)
        database = processed / "sample_2012.sqlite"
        shutil.copyfile(self.database, database)
        record = cache.attest(database, source_hash, self.methods, self.audit)
        (intake / "source_2012.json").write_text(json.dumps({"zip_sha256": source_hash}))
        (processed / "cache_attestation.json").write_text(json.dumps({"caches": {"2012": record}}))
        with patch.object(cache, "YEARS", (2012,)), patch.object(cache, "method_hashes", return_value=self.methods), patch.object(cache.subprocess, "run") as ingest:
            self.assertTrue(cache.prepare(root, verify_only=True)["passed"])
            with closing(sqlite3.connect(database)) as conn, conn:
                conn.execute("UPDATE origination SET fico=799")
            with self.assertRaisesRegex(ValueError, "cache bytes changed"):
                cache.prepare(root, verify_only=True)
            ingest.assert_not_called()

    def test_inconsistent_fresh_counts_cannot_be_attested(self):
        with self.assertRaisesRegex(ValueError, "row counts disagree"):
            cache.attest(self.database, self.source, self.methods,
                         {"origination": {"rows": 2}, "performance": {"rows": 1}})


if __name__ == "__main__":
    unittest.main()
