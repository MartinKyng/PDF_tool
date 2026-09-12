"""Helpers for inspecting PDFs inside tests."""

from __future__ import annotations

import io
from pathlib import Path
from typing import Union

from pypdf import PdfReader, PdfWriter

from factories import build_pdf_bytes


def page_content(page) -> bytes:
    """Return the decoded content stream bytes of a page.

    ``/Contents`` is either a single stream or an array of streams; both are
    supported so the helper stays useful for real-world PDFs.
    """
    contents = page["/Contents"]
    if isinstance(contents, list):
        return b"\n".join(item.get_object().get_data() for item in contents)
    return contents.get_object().get_data()


def page_labels(reader: PdfReader) -> list[str]:
    """Extract the ``(label)`` text drawn by each page of ``reader``.

    The fixtures draw exactly one ``Tj`` per page, so pulling the text out of
    the content stream gives an unambiguous fingerprint of page identity and
    page order.
    """
    labels: list[str] = []
    for page in reader.pages:
        raw = page_content(page).decode("latin-1")
        start = raw.index("(") + 1
        end = raw.rindex(")")
        labels.append(raw[start:end])
    return labels


def read(path: Union[str, Path]) -> PdfReader:
    """Open a PDF for inspection."""
    return PdfReader(str(path))


def outline_titles(reader: PdfReader) -> list[str]:
    """Flatten a reader's bookmark outline into a list of titles."""
    titles: list[str] = []

    def walk(items) -> None:
        for item in items:
            if isinstance(item, list):
                walk(item)
            else:
                titles.append(item.title)

    walk(reader.outline)
    return titles


def write_bookmarked_pdf(path: Path, page_labels: list[str], title: str) -> Path:
    """Write a PDF carrying one bookmark pointing at its first page."""
    writer = PdfWriter()
    writer.append(io.BytesIO(build_pdf_bytes(page_labels)))
    writer.add_outline_item(title, 0)
    with path.open("wb") as handle:
        writer.write(handle)
    return path


def write_encrypted_pdf(path: Path, password: str = "hunter2") -> Path:
    """Write a password-protected single page PDF."""
    writer = PdfWriter()
    writer.append(io.BytesIO(build_pdf_bytes(["locked page"])))
    writer.encrypt(password)
    with path.open("wb") as handle:
        writer.write(handle)
    return path
