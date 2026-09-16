"""Exception types raised by :mod:`pdf_tool`.

Every error a user can trigger through the CLI derives from
:class:`PdfToolError`, so the command line interface can turn any of them
into a clean one-line message instead of a traceback.
"""

from __future__ import annotations


class PdfToolError(Exception):
    """Base class for every error raised by pdf_tool."""


class JoinError(PdfToolError):
    """Base class for errors raised while joining PDFs."""


class NotEnoughInputsError(JoinError):
    """Fewer than two input files were supplied."""


class InputNotFoundError(JoinError):
    """An input path does not exist, or is not a regular file."""


class InvalidPdfError(JoinError):
    """An input file exists but is not a readable PDF."""


class EncryptedPdfError(JoinError):
    """An input PDF is encrypted and cannot be read without a password."""


class OutputExistsError(JoinError):
    """The output file already exists and overwriting was not allowed."""


class OutputConflictError(JoinError):
    """The output file is the same file as one of the inputs."""


class ImagesError(PdfToolError):
    """Base class for errors raised while converting images to PDF."""


class InvalidImageError(ImagesError):
    """An input file exists but is not a readable picture."""


class NotEnoughImagesError(ImagesError):
    """No image files were supplied."""


class NameCountError(ImagesError):
    """Individual output names do not match the number of images."""


class CompressError(PdfToolError):
    """Base class for errors raised while compressing files."""


class UnsupportedCompressError(CompressError):
    """The file type cannot be compressed by this tool."""