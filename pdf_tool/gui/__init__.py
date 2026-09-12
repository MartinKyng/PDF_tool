"""PySide6 front end for pdf_tool.

The GUI is the product surface and is bundled into the desktop executable.
It is kept in a subpackage so the PDF engine and headless tests stay easy to
maintain.  Source developers install its dependencies from
``requirements-dev.txt``; end users download the desktop build.
"""

from __future__ import annotations

import importlib.util


def is_pyside_available() -> bool:
    """True when the Qt bindings needed by the GUI are installed.

    Uses :func:`importlib.util.find_spec` so that merely asking does not pay
    the cost of importing Qt.
    """
    return importlib.util.find_spec("PySide6") is not None
