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
