"""Launch the pdf_tool GUI.

Run ``pdf-join-gui`` (console script) or ``python -m pdf_tool.gui``.
"""

from __future__ import annotations

import sys
from pathlib import Path


def main(argv: list[str] | None = None) -> int:
    """Create the application and run the main window. Returns an exit code."""
    try:
        from PySide6.QtWidgets import QApplication
    except ImportError:  # pragma: no cover - depends on installed extras
        print(
            "The GUI needs the Qt bindings. Install them with:\n"
            "    pip install \"pdf-tool[gui]\"\n"
            "or  pip install PySide6",
            file=sys.stderr,
        )
        return 1

    from .main_window import MainWindow
    from .style import apply_palette

    argv = list(argv) if argv is not None else sys.argv[1:]

    initial: list[Path] = []
    for arg in argv:
        path = Path(arg)
        if path.is_file():
            initial.append(path)

    app = QApplication(sys.argv[:1])
    app.setApplicationName("PDF Tool")
    apply_palette(app)

    window = MainWindow(initial_files=initial or None)
    window.show()
    return app.exec()


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
