"""Mechanical purity guard: the domain layer may import only the standard library and itself,
and must not touch the clock, the environment, or global randomness."""

from __future__ import annotations

import ast
import subprocess
import sys
from pathlib import Path

import pytest

DOMAIN = Path(__file__).resolve().parents[2] / "src" / "knowtrace" / "domain"
SCRIPT = Path(__file__).resolve().parents[3] / "scripts" / "check_purity.sh"
FILES = sorted(DOMAIN.glob("*.py"))
STDLIB = set(sys.stdlib_module_names)
# these stdlib modules would smuggle in I/O, time or global state
BANNED_STDLIB = {
    "os",
    "sys",
    "time",
    "socket",
    "subprocess",
    "sqlite3",
    "urllib",
    "http",
    "pathlib",
    "shutil",
    "logging",
}


def _imports(path: Path) -> set[str]:
    tree = ast.parse(path.read_text())
    mods: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            mods |= {a.name for a in node.names}
        elif isinstance(node, ast.ImportFrom) and node.module and node.level == 0:
            mods.add(node.module)
    return mods


@pytest.mark.parametrize("path", FILES, ids=lambda p: p.name)
def test_domain_imports_only_stdlib_and_itself(path: Path) -> None:
    for mod in _imports(path):
        root = mod.split(".")[0]
        if root == "knowtrace":
            assert mod.startswith("knowtrace.domain"), f"{path.name} imports {mod}"
        else:
            assert root in STDLIB, f"{path.name} imports third-party {mod}"
            assert root not in BANNED_STDLIB, f"{path.name} imports impure stdlib module {mod}"


@pytest.mark.parametrize("path", FILES, ids=lambda p: p.name)
def test_no_global_randomness_or_clock_calls(path: Path) -> None:
    src = path.read_text()
    for needle in (
        "random.random(",
        "random.seed(",
        "random.choice(",
        "random.shuffle(",
        "datetime.now(",
        "time.time(",
    ):
        assert needle not in src, f"{path.name} uses {needle}"


def test_purity_script_passes() -> None:
    out = subprocess.run(["bash", str(SCRIPT), str(DOMAIN)], capture_output=True, text=True, check=False)
    assert out.returncode == 0, out.stdout + out.stderr
    assert "purity check passed" in out.stdout


def test_purity_script_catches_a_violation(tmp_path: Path) -> None:
    (tmp_path / "bad.py").write_text("import os\nfrom fastapi import FastAPI\nx = os.environ['A']\n")
    out = subprocess.run(["bash", str(SCRIPT), str(tmp_path)], capture_output=True, text=True, check=False)
    assert out.returncode == 1 and "PURITY VIOLATIONS" in out.stdout
