"""pdf_tool - small, predictable utilities for working with PDF files.

The first tool is :func:`pdf_tool.join_pdfs`, which concatenates two or more
PDF files in the order given, without touching page content.
"""

from __future__ import annotations

from .compress import CompressResult, compress_files
from .errors import (
    CompressError,
    EncryptedPdfError,
    ImagesError,
    InputNotFoundError,
    InvalidImageError,
    InvalidPdfError,
    JoinError,
    NameCountError,
    NotEnoughImagesError,
    NotEnoughInputsError,
    OutputConflictError,
    OutputExistsError,
    PdfToolError,
    UnsupportedCompressError,
)
from .images import ConvertedImage, ImagesToPdfResult, images_to_pdf
from .join import JoinedFile, JoinResult, join_pdfs
from .version import APP_NAME, __version__

__all__ = [
    "APP_NAME",
    "__version__",
    "join_pdfs",
    "JoinResult",
    "JoinedFile",
    "images_to_pdf",
    "ImagesToPdfResult",
    "ConvertedImage",
    "PdfToolError",
    "JoinError",
    "ImagesError",
    "NotEnoughInputsError",
    "NameCountError",
    "NotEnoughImagesError",
    "InputNotFoundError",
    "InvalidPdfError",
    "InvalidImageError",
    "EncryptedPdfError",
    "OutputExistsError",
    "OutputConflictError",
]
