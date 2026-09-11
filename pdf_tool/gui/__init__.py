"""PySide6 front end for pdf_tool.

The GUI is intentionally an optional extra: it is never imported by the
command line tool, so ``pdf-join`` keeps working without Qt.  Install it with
``pip install pdf-tool[gui]`` (or ``pip install PySide6``).
"""

from __future__ import annotations

import importlib.util


def is_pyside_available() -> bool:
    """True when the Qt bindings needed by the GUI are installed.

    Uses :func:`importlib.util.find_spec` so that merely asking does not pay
    the cost of importing Qt.
    """
    return importlib.util.find_spec("PySide6") is not None
