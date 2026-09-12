"""Allow ``python -m pdf_tool.gui`` to launch the GUI."""

from __future__ import annotations

from .app import main

if __name__ == "__main__":
    raise SystemExit(main())
