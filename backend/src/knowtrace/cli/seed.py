"""Load (or reload) the authored curriculum into the database: `python -m knowtrace.cli.seed`."""

from __future__ import annotations

import argparse
from pathlib import Path

from sqlmodel import Session

from knowtrace.core.db import get_engine, init_db
from knowtrace.core.settings import get_settings
from knowtrace.services.curriculum import seed_from_dir


def main(argv: list[str] | None = None) -> int:
    settings = get_settings()
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dir", type=Path, default=Path(settings.curriculum_dir))
    parser.add_argument(
        "--reseed",
        action="store_true",
        default=settings.auto_reseed,
        help="rebuild the database when the files changed (deletes runtime data)",
    )
    args = parser.parse_args(argv)
    init_db()
    with Session(get_engine()) as session:
        report, _ = seed_from_dir(session, args.dir, auto_reseed=args.reseed)
    print(f"{report.action}: hash={report.curriculum_hash[:12]} {report.counts}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
