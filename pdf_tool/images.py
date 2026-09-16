"""Convert picture files (JPEG, PNG and friends) into a single PDF.

Each image becomes one page sized to the picture. Source files are never
modified; the PDF is written atomically, matching the join engine's safety
rules.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from io import BytesIO
from pathlib import Path
from typing import Iterable

from PIL import Image, ImageOps, UnidentifiedImageError
from pypdf import PdfReader, PdfWriter

from .errors import (
    InputNotFoundError,
    InvalidImageError,
    NotEnoughImagesError,
    OutputConflictError,
    OutputExistsError,
)
from .join import _expand, _is_same_file, _write_atomically

IMAGE_EXTENSIONS = frozenset(
    {".jpg", ".jpeg", ".png", ".bmp", ".gif", ".tif", ".tiff", ".webp"}
)

MINIMUM_INPUTS = 1


@dataclass(frozen=True)
class ConvertedImage:
    """One picture that became a page in the output PDF."""

    path: Path
    width: int
    height: int


@dataclass(frozen=True)
class ImagesToPdfResult:
    """What :func:`images_to_pdf` did, for reporting back to the caller."""

    output: Path
    files: tuple[ConvertedImage, ...]
    total_pages: int
    size_bytes: int


def is_image_path(path: str | os.PathLike[str]) -> bool:
    """True when ``path`` has a recognised picture extension."""
    return Path(path).suffix.lower() in IMAGE_EXTENSIONS


def _check_input(path: Path) -> None:
    if not path.exists():
        raise InputNotFoundError(f"input file not found: {path}")
    if path.is_dir():
        raise InputNotFoundError(
            f"expected an image file but found a directory: {path}"
        )
    if not os.access(path, os.R_OK):
        raise InputNotFoundError(f"input file is not readable: {path}")
    if not is_image_path(path):
        raise InvalidImageError(
            f"not a supported image type ({path.suffix or 'no extension'}): {path}"
        )


def _open_image(path: Path) -> Image.Image:
    try:
        image = Image.open(path)
        image.load()
    except UnidentifiedImageError as exc:
        raise InvalidImageError(f"could not read '{path}' as an image: {exc}") from exc
    except OSError as exc:
        raise InvalidImageError(f"could not open '{path}': {exc}") from exc
    try:
        image = ImageOps.exif_transpose(image)
    except Exception:
        pass
    return image


def _to_rgb(image: Image.Image) -> Image.Image:
    if image.mode == "RGB":
        return image
    if image.mode in ("RGBA", "LA") or (
        image.mode == "P" and "transparency" in image.info
    ):
        rgba = image.convert("RGBA")
        background = Image.new("RGB", rgba.size, (255, 255, 255))
        background.paste(rgba, mask=rgba.split()[-1])
        return background
    return image.convert("RGB")


def _image_as_pdf_reader(image: Image.Image) -> PdfReader:
    rgb = _to_rgb(image)
    buffer = BytesIO()
    rgb.save(buffer, format="PDF", resolution=72.0)
    buffer.seek(0)
    return PdfReader(buffer)


def images_to_pdf(
    inputs: Iterable[str | os.PathLike[str]],
    output: str | os.PathLike[str],
    *,
    overwrite: bool = False,
) -> ImagesToPdfResult:
    """Place each picture in ``inputs`` on its own page of a new PDF.

    Args:
        inputs: One or more image files, in the order they should appear.
        output: Where to write the PDF. Parent directories are created.
        overwrite: When ``False``, an existing ``output`` raises
            :class:`~pdf_tool.errors.OutputExistsError`.

    Returns:
        An :class:`ImagesToPdfResult` describing the output.
    """
    paths = [_expand(p) for p in inputs]
    dest = _expand(output)

    if len(paths) < MINIMUM_INPUTS:
        raise NotEnoughImagesError(
            f"converting needs at least {MINIMUM_INPUTS} image file, got {len(paths)}"
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
    converted: list[ConvertedImage] = []
    readers: list[PdfReader] = []
    try:
        for path in paths:
            image = _open_image(path)
            width, height = image.size
            reader = _image_as_pdf_reader(image)
            readers.append(reader)
            image.close()
            writer.append(reader)
            converted.append(ConvertedImage(path=path, width=width, height=height))

        tmp_path = _write_atomically(writer, dest)
    finally:
        for reader in readers:
            reader.close()

    return ImagesToPdfResult(
        output=dest,
        files=tuple(converted),
        total_pages=len(converted),
        size_bytes=os.path.getsize(tmp_path),
    )
