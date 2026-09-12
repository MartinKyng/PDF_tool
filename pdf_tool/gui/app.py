"""Launch the pdf_tool GUI.

Run ``pdf-join-gui`` (console script) or ``python -m pdf_tool.gui``.
"""

from __future__ import annotations

import sys
from pathlib import Path

from ..version import APP_NAME, __version__


def main(argv: list[str] | None = None) -> int:
    """Create the application and run the main window. Returns an exit code."""
    try:
        from PySide6.QtWidgets import QApplication
    except ImportError:  # pragma: no cover - depends on installed extras
        print(
            "The desktop app needs its Qt runtime. For development, install:\n"
            "    python -m pip install -r requirements-dev.txt",
            file=sys.stderr,
        )
        return 1

    from .main_window import MainWindow
    from .style import apply_palette

    argv = list(argv) if argv is not None else sys.argv[1:]

    initial: list[Path] = []
    for arg in argv:
        path = Path(arg).expanduser()
        if path.is_file() and path.suffix.lower() == ".pdf":
            initial.append(path)

    # The frozen desktop app receives file paths from the OS when a user
    # double-clicks a PDF or drops one on its icon.  Keep those paths out of
    # Qt's own argument parser; they are loaded into the file list below.
    app = QApplication(sys.argv[:1])
    app.setApplicationName(APP_NAME)
    app.setApplicationVersion(__version__)
    app.setOrganizationName(APP_NAME)
    apply_palette(app)

    window = MainWindow(initial_files=initial or None)
    window.show()
    return app.exec()


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
