"""Catch edits to the complete research freeze before an expensive replay."""
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "bank_monitoring"))
import replay_fdic_temporal as replay


class FrozenSourceContractTests(unittest.TestCase):
    def test_complete_frozen_source_manifest_still_matches(self):
        manifest = json.loads((replay.REF / "artifact_manifest.json").read_text())
        self.assertTrue(manifest["frozen_source"])
        replay.validate_files(manifest["frozen_source"])

    def test_changed_historical_dependency_pin_is_rejected(self):
        manifest = json.loads((replay.REF / "artifact_manifest.json").read_text())
        entry = next(item for item in manifest["frozen_source"]
                     if item["path"] == "requirements-fdic-temporal.txt")
        original = (replay.ROOT / entry["path"]).read_bytes()
        changed = original.replace(b"pytest==8.3.3", b"pytest==9.0.3")
        self.assertNotEqual(original, changed)
        with tempfile.TemporaryDirectory() as folder:
            temporary_root = Path(folder).resolve()
            (temporary_root / entry["path"]).write_bytes(changed)
            with patch.object(replay, "ROOT", temporary_root):
                with self.assertRaisesRegex(ValueError, "Release hash/byte mismatch"):
                    replay.validate_files([entry])


if __name__ == "__main__":
    unittest.main()
