"""A small, modern dark theme for the pdf_tool GUI.

The theme is expressed as a :class:`~PySide6.QtGui.QPalette` plus a QSS
stylesheet.  Keeping it in one module makes it easy to retheme the whole app
without touching the widgets.
"""

from __future__ import annotations

# --- palette ------------------------------------------------------------
BACKGROUND = "#14161b"     # window background
SURFACE = "#1d2027"        # cards / inputs
SURFACE_RAISED = "#252932" # raised elements (rows, buttons)
BORDER = "#333845"         # hairlines
TEXT = "#e8eaf0"           # primary text
TEXT_MUTED = "#9aa1b0"     # secondary text
ACCENT = "#6c8cff"         # primary action
ACCENT_PRESSED = "#5474e8"
DANGER = "#ff6b6b"         # destructive actions

FONT_FAMILY = "'Inter', 'Segoe UI', 'Helvetica Neue', Arial, sans-serif"

QSS = f"""
/* base */
QWidget {{
    background-color: {BACKGROUND};
    color: {TEXT};
    font-family: {FONT_FAMILY};
    font-size: 13px;
}}
QLabel {{ background: transparent; }}
QLabel#appTitle {{
    font-size: 20px;
    font-weight: 700;
    letter-spacing: 0.2px;
}}
QLabel#appSubtitle {{ color: {TEXT_MUTED}; font-size: 12px; }}

/* card that wraps the file list */
QFrame#fileCard, QFrame#outputCard {{
    background-color: {SURFACE};
    border: 1px solid {BORDER};
    border-radius: 12px;
}}
QFrame#cardTitleBar {{ background: transparent; border: none; }}
QLabel#cardTitle {{ font-weight: 600; font-size: 13px; }}
QLabel#cardHint {{ color: {TEXT_MUTED}; font-size: 12px; }}

/* file list */
QListWidget {{
    background-color: {SURFACE};
    border: none;
    outline: none;
    padding: 8px;
}}
QListWidget::item {{
    background: transparent;
    border-radius: 8px;
    padding: 8px 10px;
}}
QListWidget::item:selected {{ background-color: {SURFACE_RAISED}; color: {ACCENT}; }}
QListWidget::item:hover:!selected {{ background-color: rgba(255,255,255,8%); }}

/* buttons */
QPushButton {{
    background-color: {SURFACE_RAISED};
    color: {TEXT};
    border: 1px solid {BORDER};
    border-radius: 8px;
    padding: 7px 14px;
    font-weight: 500;
}}
QPushButton:hover {{ border-color: {ACCENT}; }}
QPushButton:pressed {{ background-color: {BORDER}; }}
QPushButton:disabled {{ color: {TEXT_MUTED}; border-color: {BORDER}; }}
QPushButton#primaryAction {{
    background-color: {ACCENT};
    border: none;
    color: #ffffff;
    font-size: 14px;
    font-weight: 600;
    padding: 11px 18px;
    border-radius: 10px;
}}
QPushButton#primaryAction:hover {{ background-color: {ACCENT_PRESSED}; }}
QPushButton#primaryAction:disabled {{ background-color: {BORDER}; color: {TEXT_MUTED}; }}
QPushButton#danger {{ background-color: transparent; color: {DANGER}; border-color: {BORDER}; }}

/* inputs */
QLineEdit {{
    background-color: {SURFACE_RAISED};
    border: 1px solid {BORDER};
    border-radius: 8px;
    padding: 8px 10px;
    selection-background-color: {ACCENT};
}}
QLineEdit:focus {{ border-color: {ACCENT}; }}

/* checkboxes */
QCheckBox {{ spacing: 8px; }}
QCheckBox::indicator {{
    width: 16px; height: 16px;
    border-radius: 5px;
    border: 1px solid {BORDER};
    background-color: {SURFACE_RAISED};
}}
QCheckBox::indicator:checked {{ background-color: {ACCENT}; border-color: {ACCENT}; }}

/* status bar */
QLabel#status {{
    color: {TEXT_MUTED};
    font-size: 12px;
    padding: 4px 2px;
}}
QLabel#statusError {{ color: {DANGER}; }}
QLabel#statusOk {{ color: #7ddc9a; }}
"""


def apply_palette(qapp) -> None:
    """Set the QPalette and stylesheet on ``qapp`` (the QApplication)."""
    from PySide6.QtGui import QColor, QPalette

    palette = QPalette()
    for role in (
        QPalette.ColorRole.Window,
        QPalette.ColorRole.Base,
        QPalette.ColorRole.Button,
    ):
        palette.setColor(role, QColor(SURFACE))
    palette.setColor(QPalette.ColorRole.WindowText, QColor(TEXT))
    palette.setColor(QPalette.ColorRole.Text, QColor(TEXT))
    palette.setColor(QPalette.ColorRole.ButtonText, QColor(TEXT))
    palette.setColor(QPalette.ColorRole.Highlight, QColor(ACCENT))
    palette.setColor(QPalette.ColorRole.HighlightedText, QColor("#ffffff"))
    palette.setColor(QPalette.ColorRole.PlaceholderText, QColor(TEXT_MUTED))
    qapp.setPalette(palette)
    qapp.setStyleSheet(QSS)
