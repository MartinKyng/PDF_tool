"""Allow ``python -m pdf_tool`` to behave like the ``pdf-join`` command."""

from __future__ import annotations

from .cli import main

if __name__ == "__main__":
    raise SystemExit(main())
