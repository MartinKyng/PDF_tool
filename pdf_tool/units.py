"""Tiny presentation helpers shared by the CLI and the GUI."""

from __future__ import annotations

from pathlib import Path


def ensure_pdf_suffix(path: Path) -> tuple[Path, bool]:
    """Append ``.pdf`` to ``path`` when it has no PDF extension.

    Returns the path to use and whether it was changed, so the caller can tell
    the user about it.
    """
    if path.suffix.lower() == ".pdf":
        return path, False
    return path.with_suffix(path.suffix + ".pdf"), True


def human_size(size_bytes: int | float) -> str:
    """Format a byte count the way a person would read it."""
    size = float(size_bytes)
    for unit in ("B", "KB", "MB", "GB"):
        if size < 1024 or unit == "GB":
            if unit == "B":
                return f"{int(size)} B"
            return f"{size:.1f} {unit}"
        size /= 1024
    return f"{size:.1f} GB"  # pragma: no cover - unreachable
