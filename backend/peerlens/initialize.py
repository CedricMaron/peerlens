"""Create the data directory and database.

Invoked by the setup scripts as ``python -m peerlens.initialize``. Kept as a
module rather than an inline ``python -c`` snippet so that neither bash nor
PowerShell has to quote a multi-line program correctly.

Safe to run repeatedly.
"""

from __future__ import annotations

from . import config
from .db import init_db


def main() -> int:
    config.ensure_directories()
    init_db()
    print(f"  database: {config.DB_PATH}")
    print(f"  uploads:  {config.UPLOAD_DIR}")
    print(f"  prompts:  {config.PROMPTS_DIR}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
