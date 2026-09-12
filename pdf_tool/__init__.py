"""pdf_tool - small, predictable utilities for working with PDF files.

The first tool is :func:`pdf_tool.join_pdfs`, which concatenates two or more
PDF files in the order given, without touching page content.
"""

from __future__ import annotations

from .errors import (
    EncryptedPdfError,
    InputNotFoundError,
    InvalidPdfError,
    JoinError,
    NotEnoughInputsError,
    OutputConflictError,
    OutputExistsError,
    PdfToolError,
)
from .join import JoinedFile, JoinResult, join_pdfs
from .version import APP_NAME, __version__

__all__ = [
    "APP_NAME",
    "__version__",
    "join_pdfs",
    "JoinResult",
    "JoinedFile",
    "PdfToolError",
    "JoinError",
    "NotEnoughInputsError",
    "InputNotFoundError",
    "InvalidPdfError",
    "EncryptedPdfError",
    "OutputExistsError",
    "OutputConflictError",
]
