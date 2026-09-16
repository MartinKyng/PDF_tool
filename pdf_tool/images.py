"""Convert picture files (JPEG, PNG and friends) into PDF pages.

Each image becomes one page sized to the picture. Source files are never
modified. You can write a single combined PDF, or one PDF per picture
(named by the user, or from the original file names).
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from io import BytesIO
from pathlib import Path
from typing import Iterable, Sequence

from PIL import Image, ImageOps, UnidentifiedImageError
from pypdf import PdfReader, PdfWriter

from .errors import (
    InputNotFoundError,
    InvalidImageError,
    NameCountError,
    NotEnoughImagesError,
    OutputConflictError,
    OutputExistsError,
)
from .join import _expand, _is_same_file, _write_atomically
from .units import ensure_pdf_suffix

IMAGE_EXTENSIONS = frozenset(
    {".jpg", ".jpeg", ".png", ".bmp", ".gif", ".tif", ".tiff", ".webp"}
)

MINIMUM_INPUTS = 1


@dataclass(frozen=True)
class ConvertedImage:
    """One picture that became a page in an output PDF."""

    path: Path
    width: int
    height: int
    output: Path


@dataclass(frozen=True)
class ImagesToPdfResult:
    """What :func:`images_to_pdf` did, for reporting back to the caller."""

    output: Path
    outputs: tuple[Path, ...]
    files: tuple[ConvertedImage, ...]
    total_pages: int
    size_bytes: int
    combined: bool


def is_image_path(path: str | os.PathLike[str]) -> bool:
    """True when ``path`` has a recognised picture extension."""
    return Path(path).suffix.lower() in IMAGE_EXTENSIONS


def parse_name_list(text: str) -> list[str]:
    """Split a comma-separated list of output names the user typed."""
    return [part.strip() for part in text.split(",") if part.strip()]


def individual_destinations(
    sources: Sequence[Path],
    *,
    folder: Path,
    inherit_names: bool,
    name_text: str,
) -> list[Path]:
    """Resolve one output path per source image.

    * ``inherit_names``: ``photo.jpg`` → ``folder/photo.pdf``.
    * Comma-separated ``name_text``: one explicit name per image.
    * Otherwise ``name_text`` is a stem: ``album.pdf`` → ``album-1.pdf``, …
    """
    if inherit_names:
        return [_as_pdf_name(folder / source.stem) for source in sources]

    names = parse_name_list(name_text)
    if len(names) == 1 and len(sources) != 1:
        stem, _ = ensure_pdf_suffix(Path(names[0]))
        return [_as_pdf_name(folder / f"{stem.stem}-{index}") for index in range(1, len(sources) + 1)]
    if len(names) == len(sources):
        return [_as_pdf_name(folder / name) for name in names]
    if not names:
        return [_as_pdf_name(folder / source.stem) for source in sources]
    raise NameCountError(
        f"got {len(names)} output name(s) for {len(sources)} image(s); "
        "give one name per image, a single stem (writes stem-1.pdf, …), "
        "or use original file names"
    )


def _as_pdf_name(path: Path) -> Path:
    dest, _ = ensure_pdf_suffix(path)
    return dest


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


def _guard_output(dest: Path, sources: Sequence[Path], overwrite: bool) -> None:
    for path in sources:
        if _is_same_file(dest, path):
            raise OutputConflictError(
                f"output '{dest}' is the same file as input '{path}'; "
                "choose a different output name"
            )
    if dest.exists() and not overwrite:
        raise OutputExistsError(
            f"output file already exists: {dest} (use --overwrite to replace it)"
        )


def _write_one(image: Image.Image, dest: Path) -> None:
    writer = PdfWriter()
    reader = _image_as_pdf_reader(image)
    try:
        writer.append(reader)
        _write_atomically(writer, dest)
    finally:
        reader.close()


def images_to_pdf(
    inputs: Iterable[str | os.PathLike[str]],
    output: str | os.PathLike[str],
    *,
    overwrite: bool = False,
    combined: bool = True,
    inherit_names: bool = False,
    names: Sequence[str] | None = None,
) -> ImagesToPdfResult:
    """Convert pictures to PDF.

    Args:
        inputs: One or more image files, in the order they should appear.
        output: Combined PDF path, or (when not ``combined``) the folder /
            stem used to build per-image names.
        overwrite: When ``False``, existing outputs raise
            :class:`~pdf_tool.errors.OutputExistsError`.
        combined: When ``True``, all images go into one PDF. When ``False``,
            each image is written as its own one-page PDF.
        inherit_names: For individual PDFs, use each image's stem
            (``holiday.jpg`` → ``holiday.pdf``). Ignored when ``combined``.
        names: Optional explicit per-image file names (same count as inputs).
            When omitted and not inheriting, ``output``'s stem is numbered
            (``album.pdf`` → ``album-1.pdf``, ``album-2.pdf``, …).
    """
    paths = [_expand(p) for p in inputs]
    dest = _expand(output)

    if len(paths) < MINIMUM_INPUTS:
        raise NotEnoughImagesError(
            f"converting needs at least {MINIMUM_INPUTS} image file, got {len(paths)}"
        )

    for path in paths:
        _check_input(path)

    if combined:
        _guard_output(dest, paths, overwrite)
        return _write_combined(paths, dest)

    folder = dest if dest.is_dir() else dest.parent
    if inherit_names:
        targets = individual_destinations(
            paths, folder=folder, inherit_names=True, name_text=""
        )
    elif names:
        if len(names) != len(paths):
            raise NameCountError(
                f"got {len(names)} output name(s) for {len(paths)} image(s)"
            )
        targets = [_as_pdf_name(folder / name) for name in names]
    else:
        targets = individual_destinations(
            paths, folder=folder, inherit_names=False, name_text=dest.name
        )

    for target in targets:
        _guard_output(target, paths, overwrite)

    converted: list[ConvertedImage] = []
    total_size = 0
    for source, target in zip(paths, targets):
        image = _open_image(source)
        width, height = image.size
        _write_one(image, target)
        image.close()
        converted.append(
            ConvertedImage(path=source, width=width, height=height, output=target)
        )
        total_size += os.path.getsize(target)

    return ImagesToPdfResult(
        output=targets[0],
        outputs=tuple(targets),
        files=tuple(converted),
        total_pages=len(converted),
        size_bytes=total_size,
        combined=False,
    )


def _write_combined(paths: Sequence[Path], dest: Path) -> ImagesToPdfResult:
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
            converted.append(
                ConvertedImage(path=path, width=width, height=height, output=dest)
            )

        tmp_path = _write_atomically(writer, dest)
    finally:
        for reader in readers:
            reader.close()

    return ImagesToPdfResult(
        output=dest,
        outputs=(dest,),
        files=tuple(converted),
        total_pages=len(converted),
        size_bytes=os.path.getsize(tmp_path),
        combined=True,
    )
