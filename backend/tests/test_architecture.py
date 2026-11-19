"""The layering rules from Step 4 are enforced by import-linter; this keeps them in the test run."""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

BACKEND = Path(__file__).resolve().parents[1]


def test_import_contracts_are_kept() -> None:
    exe = Path(sys.executable).with_name("lint-imports")
    env = {**os.environ, "PYTHONPATH": str(BACKEND / "src")}
    out = subprocess.run([str(exe)], cwd=BACKEND, capture_output=True, text=True, env=env, check=False)
    assert out.returncode == 0, out.stdout + out.stderr
    assert "0 broken" in out.stdout
