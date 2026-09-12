"""Shared fixtures for the pdf_tool test suite."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

# Make ``factories`` importable regardless of how pytest is invoked.
sys.path.insert(0, str(Path(__file__).parent))

from factories import write_pdf  # noqa: E402


@pytest.fixture
def make_pdf(tmp_path: Path):
    """Return a callable that writes a generated PDF into ``tmp_path``."""

    def _make_pdf(name: str, page_labels: list[str]) -> Path:
        return write_pdf(tmp_path / name, page_labels)

    return _make_pdf


@pytest.fixture
def two_pdfs(make_pdf) -> tuple[Path, Path]:
    """A 2-page PDF and a 3-page PDF, with known per-page content."""
    first = make_pdf("first.pdf", ["first-1", "first-2"])
    second = make_pdf("second.pdf", ["second-1", "second-2", "second-3"])
    return first, second

# ---------------------------------------------------------------- GUI helpers
import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")


@pytest.fixture(scope="session")
def qapp():
    """A session-wide QApplication, skipped if Qt cannot run on this host."""
    pytest.importorskip("PySide6")
    from PySide6.QtWidgets import QApplication

    app = QApplication.instance() or QApplication([])
    yield app


@pytest.fixture
def qwait(qapp):
    """Return a helper that pumps the event loop until a condition holds."""

    def _wait(condition, timeout_ms=5000, interval_ms=25):
        import time

        deadline = time.monotonic() + timeout_ms / 1000.0
        while time.monotonic() < deadline:
            qapp.processEvents()
            if condition():
                qapp.processEvents()
                return True
            time.sleep(interval_ms / 1000.0)
        qapp.processEvents()
        return condition()

    return _wait
