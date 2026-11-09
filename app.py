"""
app.py — DEPRECATED. Moorchid no longer ships a Streamlit UI.

The product now lives in two places:

    UI/    — Vite + React frontend (the user-facing client)
    main.py — FastAPI backend (the only HTTP API surface)

Running this file directly is **no longer supported** and will print a
migration message. To start the application:

    # Backend
    uvicorn main:app --host 0.0.0.0 --port 8000

    # Frontend (in another terminal)
    cd UI && npm install && npm run dev

The Streamlit-specific helpers in `soulcontext_ui/` and this file are kept
only as historical reference; they do **not** write to the database on
import. Do not point any launcher at `app.py` going forward.

This shim intentionally:
  • does NOT call init_db()
  • does NOT import streamlit at module level
  • exits before any DB work, eliminating the SQLite lock contention that
    occurred when both the FastAPI server and the Streamlit process opened
    the same file.
"""

from __future__ import annotations

import sys
from pathlib import Path

# Ensure project root is on sys.path so error messages can locate files.
PROJECT_ROOT = Path(__file__).resolve().parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))


def main() -> int:
    print(
        "\n"
        "============================================================\n"
        " Moorchid: Streamlit UI has been retired (v2.0)\n"
        "============================================================\n"
        "\n"
        " The product is now a FastAPI backend + Vite/React frontend:\n"
        "\n"
        "   Backend  →  uvicorn main:app --host 0.0.0.0 --port 8000\n"
        "   Frontend →  cd UI && npm install && npm run dev\n"
        "\n"
        " `app.py` is preserved only as historical reference.\n"
        " Running both the FastAPI server and this Streamlit file used to\n"
        " lock the SQLite database; this shim refuses to start so that\n"
        " only one writer is ever active.\n"
        "\n"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())