"""Join (concatenate) PDF files without editing their content.

The join is a *page-level copy*: every page of every input is cloned into a
new document in the order given.  Page content streams are copied as-is --
nothing is re-rendered, re-encoded, rasterised, resized or reordered, so the
output pages are bit-identical in content to the input pages.
"""

from __future__ import annotations

import os
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, Sequence

from pypdf import PdfReader, PdfWriter
from pypdf.errors import PdfReadError

from .errors import (
    EncryptedPdfError,
    InputNotFoundError,
    InvalidPdfError,
    NotEnoughInputsError,
    OutputConflictError,
    OutputExistsError,
)

#: The magic bytes that start every PDF file.
PDF_HEADER = b"%PDF-"

#: Per the PDF specification the header must appear in the first 1024 bytes.
HEADER_SCAN_BYTES = 1024

MINIMUM_INPUTS = 2


@dataclass(frozen=True)
class JoinedFile:
    """One input file that took part in the join."""

    path: Path
    pages: int


@dataclass(frozen=True)
class JoinResult:
    """What :func:`join_pdfs` did, for reporting back to the caller."""

    output: Path
    files: tuple[JoinedFile, ...]
    total_pages: int
    size_bytes: int


def _expand(path: str | os.PathLike[str]) -> Path:
    """Normalise a user-supplied path (``~`` expanded, relative kept)."""
    return Path(path).expanduser()


def _is_same_file(a: Path, b: Path) -> bool:
    """True when two paths point at the same file on disk."""
    try:
        return os.path.samefile(a, b)
    except OSError:
        # One of them does not exist yet: fall back to comparing paths.
        return os.path.normcase(os.path.abspath(a)) == os.path.normcase(
            os.path.abspath(b)
        )


def _check_input(path: Path) -> None:
    """Raise a helpful error if ``path`` is not a usable PDF file."""
    if not path.exists():
        raise InputNotFoundError(f"input file not found: {path}")
    if path.is_dir():
        raise InputNotFoundError(f"expected a PDF file but found a directory: {path}")
    if not os.access(path, os.R_OK):
        raise InputNotFoundError(f"input file is not readable: {path}")

    with path.open("rb") as handle:
        head = handle.read(HEADER_SCAN_BYTES)
    if PDF_HEADER not in head:
        raise InvalidPdfError(
            f"not a PDF file (no '{PDF_HEADER.decode()}' header): {path}"
        )


def _open_reader(path: Path) -> PdfReader:
    """Open ``path`` as a PdfReader, converting library errors to ours."""
    try:
        reader = PdfReader(str(path))
    except PdfReadError as exc:
        raise InvalidPdfError(f"could not read '{path}' as a PDF: {exc}") from exc
    except OSError as exc:
        raise InputNotFoundError(f"could not open '{path}': {exc}") from exc

    if reader.is_encrypted:
        raise EncryptedPdfError(
            f"'{path}' is encrypted; pdf_tool joins PDFs as-is and will not "
            "decrypt them"
        )
    return reader


def join_pdfs(
    inputs: Iterable[str | os.PathLike[str]],
    output: str | os.PathLike[str],
    *,
    overwrite: bool = False,
    keep_bookmarks: bool = True,
) -> JoinResult:
    """Concatenate ``inputs`` into a single PDF written to ``output``.

    Args:
        inputs: Two or more PDF files, joined in the order given.
        output: Where to write the combined PDF.  Parent directories are
            created if needed.
        overwrite: When ``False`` (the default), an existing ``output`` file
            raises :class:`~pdf_tool.errors.OutputExistsError` instead of
            being replaced.
        keep_bookmarks: When ``True`` (the default), each input's outline
            (bookmarks) is copied into the output.

    Returns:
        A :class:`JoinResult` describing the output file and the pages taken
        from each input.

    Raises:
        NotEnoughInputsError: Fewer than two inputs were given.
        InputNotFoundError: An input does not exist or cannot be read.
        InvalidPdfError: An input is not a valid PDF.
        EncryptedPdfError: An input is password protected.
        OutputExistsError: ``output`` exists and ``overwrite`` is ``False``.
        OutputConflictError: ``output`` is the same file as an input.
    """
    paths = [_expand(p) for p in inputs]
    dest = _expand(output)

    if len(paths) < MINIMUM_INPUTS:
        raise NotEnoughInputsError(
            f"joining needs at least {MINIMUM_INPUTS} PDF files, got {len(paths)}"
        )

    for path in paths:
        _check_input(path)

    for path in paths:
        if _is_same_file(dest, path):
            raise OutputConflictError(
                f"output '{dest}' is the same file as input '{path}'; "
                "choose a different output name"
            )

    if dest.exists() and not overwrite:
        raise OutputExistsError(
            f"output file already exists: {dest} (use --overwrite to replace it)"
        )

    writer = PdfWriter()
    readers: list[PdfReader] = []
    joined: list[JoinedFile] = []
    try:
        for path in paths:
            reader = _open_reader(path)
            readers.append(reader)
            page_count = len(reader.pages)
            # ``append`` clones the pages of ``reader`` into ``writer``
            # verbatim; page content streams are never rewritten.
            writer.append(reader, import_outline=keep_bookmarks)
            joined.append(JoinedFile(path=path, pages=page_count))

        tmp_path = _write_atomically(writer, dest)
    finally:
        for reader in readers:
            reader.close()

    return JoinResult(
        output=dest,
        files=tuple(joined),
        total_pages=sum(item.pages for item in joined),
        size_bytes=os.path.getsize(tmp_path),
    )


def _default_file_mode() -> int:
    """The permissions a normally created file would get under this umask."""
    current = os.umask(0)
    os.umask(current)  # restore immediately; there is no atomic way to read it
    return 0o666 & ~current


def _write_atomically(writer: PdfWriter, dest: Path) -> Path:
    """Write ``writer`` to ``dest`` via a temporary file.

    A half-written output file is worse than no output file: if writing fails
    part way through, nothing is left behind at ``dest``.
    """
    dest.parent.mkdir(parents=True, exist_ok=True)

    handle, tmp_name = tempfile.mkstemp(
        dir=str(dest.parent), prefix=f".{dest.name}.", suffix=".part"
    )
    tmp_path = Path(tmp_name)
    try:
        with os.fdopen(handle, "wb") as stream:
            writer.write(stream)
        # mkstemp creates the file 0600; give the result the permissions the
        # user would expect from a file they created themselves.
        os.chmod(tmp_path, _default_file_mode())
        os.replace(tmp_path, dest)
    except BaseException:
        tmp_path.unlink(missing_ok=True)
        raise
    return dest


def summarise(paths: Sequence[str | os.PathLike[str]]) -> str:
    """Human-readable one-line description of the inputs (for --dry-run)."""
    return ", ".join(str(_expand(p)) for p in paths)
