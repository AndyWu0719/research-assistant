from __future__ import annotations

import json
import subprocess
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "release_metadata.py"


class ReleaseMetadataScript(unittest.TestCase):
    def run_script(self, *args: str) -> dict[str, object]:
        process = subprocess.run(
            [str(ROOT / ".venv" / "bin" / "python"), str(SCRIPT), *args],
            cwd=ROOT,
            capture_output=True,
            text=True,
            check=True,
        )
        return json.loads(process.stdout)

    def test_workflow_dispatch_uses_version_file_when_version_missing(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            version_file = Path(temp_dir) / "VERSION"
            version_file.write_text("1.1.1\n", encoding="utf-8")
            payload = self.run_script(
                "--event-name",
                "workflow_dispatch",
                "--ref-type",
                "branch",
                "--ref-name",
                "main",
                "--version-file",
                str(version_file),
            )
        self.assertEqual(payload["version"], "1.1.1")
        self.assertEqual(payload["release_tag"], "")
        self.assertFalse(payload["should_upload"])

    def test_manual_release_upload_derives_v_prefixed_tag(self) -> None:
        payload = self.run_script(
            "--event-name",
            "workflow_dispatch",
            "--ref-type",
            "branch",
            "--ref-name",
            "main",
            "--version",
            "1.1.2",
            "--upload-to-release",
            "true",
        )
        self.assertEqual(payload["version"], "1.1.2")
        self.assertEqual(payload["release_tag"], "v1.1.2")
        self.assertTrue(payload["should_upload"])

    def test_tag_push_forces_release_upload(self) -> None:
        payload = self.run_script(
            "--event-name",
            "push",
            "--ref-type",
            "tag",
            "--ref-name",
            "v1.1.3",
        )
        self.assertEqual(payload["version"], "1.1.3")
        self.assertEqual(payload["release_tag"], "v1.1.3")
        self.assertTrue(payload["should_upload"])


if __name__ == "__main__":
    unittest.main()
