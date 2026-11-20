"""Write the API contract to docs/openapi.json (input for the Step 6A TypeScript client)."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from knowtrace.core.db import make_engine
from knowtrace.core.settings import Settings
from knowtrace.main import create_app

DEFAULT_OUT = Path(__file__).resolve().parents[4] / "docs" / "openapi.json"


def render() -> str:
    """Deterministic JSON for the contract; no database or network needed."""
    app = create_app(Settings(_env_file=None), engine=make_engine("sqlite://"), seed_on_startup=False)
    return json.dumps(app.openapi(), indent=2, sort_keys=True) + "\n"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT)
    args = parser.parse_args(argv)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(render(), encoding="utf-8")
    print(f"wrote {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
