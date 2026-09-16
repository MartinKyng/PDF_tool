"""Shrink PDFs and pictures without replacing the originals.

Lossless mode only Flate-compresses PDF streams and optimises PNG packing;
pixels, page objects and image dimensions are unchanged. Quality reduction
re-encodes rasters as JPEG at the same width and height — it never crops,
drops pages, or removes drawings.
"""

from __future__ import annotations

import os
import tempfile
from dataclasses import dataclass
from io import BytesIO
from pathlib import Path
from typing import Iterable, Sequence

from PIL import Image, ImageOps, UnidentifiedImageError
from pypdf import PdfReader, PdfWriter
from pypdf.errors import PdfReadError
from pypdf.generic import (
    DecodedStreamObject,
    NameObject,
    NumberObject,
)

from .errors import (
    EncryptedPdfError,
    InputNotFoundError,
    InvalidImageError,
    InvalidPdfError,
    OutputConflictError,
    OutputExistsError,
    UnsupportedCompressError,
)
from .images import is_image_path
from .join import (
    HEADER_SCAN_BYTES,
    PDF_HEADER,
    _default_file_mode,
    _expand,
    _is_same_file,
    _write_atomically,
)


PRESETS = {
    "lossless": {"lossy": False, "quality": None},
    "light": {"lossy": True, "quality": 90},
    "balanced": {"lossy": True, "quality": 75},
    "strong": {"lossy": True, "quality": 55},
}

DEFAULT_PRESET = "lossless"


@dataclass(frozen=True)
class CompressResult:
    """What :func:`compress_files` wrote."""

    output: Path
    outputs: tuple[Path, ...]
    original_bytes: int
    size_bytes: int
    pages: int

    @property
    def saved_bytes(self) -> int:
        return max(0, self.original_bytes - self.size_bytes)


def _write_bytes_atomically(data: bytes, dest: Path) -> Path:
    dest.parent.mkdir(parents=True, exist_ok=True)
    handle, tmp_name = tempfile.mkstemp(
        dir=str(dest.parent), prefix=f".{dest.name}.", suffix=".part"
    )
    tmp_path = Path(tmp_name)
    try:
        with os.fdopen(handle, "wb") as stream:
            stream.write(data)
        os.chmod(tmp_path, _default_file_mode())
        os.replace(tmp_path, dest)
    except BaseException:
        tmp_path.unlink(missing_ok=True)
        raise
    return dest


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


def _check_exists(path: Path) -> None:
    if not path.exists():
        raise InputNotFoundError(f"input file not found: {path}")
    if path.is_dir():
        raise InputNotFoundError(f"expected a file but found a directory: {path}")
    if not os.access(path, os.R_OK):
        raise InputNotFoundError(f"input file is not readable: {path}")


def _is_pdf(path: Path) -> bool:
    with path.open("rb") as handle:
        head = handle.read(HEADER_SCAN_BYTES)
    return PDF_HEADER in head


def _open_pdf(path: Path) -> PdfReader:
    try:
        reader = PdfReader(str(path))
    except PdfReadError as exc:
        raise InvalidPdfError(f"could not read '{path}' as a PDF: {exc}") from exc
    except OSError as exc:
        raise InputNotFoundError(f"could not open '{path}': {exc}") from exc
    if reader.is_encrypted:
        raise EncryptedPdfError(f"'{path}' is encrypted and cannot be compressed")
    return reader


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


def _compress_picture(path: Path, dest: Path, *, lossy: bool, quality: int | None) -> int:
    try:
        image = Image.open(path)
        image.load()
    except UnidentifiedImageError as exc:
        raise InvalidImageError(f"could not read '{path}' as an image: {exc}") from exc
    except OSError as exc:
        raise InvalidImageError(f"could not open '{path}': {exc}") from exc
    try:
        image = ImageOps.exif_transpose(image) or image
        buffer = BytesIO()
        original = path.stat().st_size
        if lossy:
            image = _to_rgb(image)
            image.save(buffer, format="JPEG", quality=int(quality or 75), optimize=True)
        else:
            if image.mode not in ("RGB", "RGBA", "L", "P"):
                image = image.convert("RGBA" if "A" in image.mode else "RGB")
            image.save(buffer, format="PNG", optimize=True, compress_level=9)
        data = buffer.getvalue()
        if len(data) >= original:
            data = path.read_bytes()
        _write_bytes_atomically(data, dest)
    finally:
        image.close()
    return dest.stat().st_size


def _xobject_to_image(obj) -> Image.Image | None:
    try:
        width = int(obj["/Width"])
        height = int(obj["/Height"])
        data = obj.get_data()
    except Exception:
        return None
    if width < 1 or height < 1 or not data:
        return None
    filt = obj.get("/Filter")
    filters = []
    if filt is not None:
        try:
            filters = [str(f) for f in filt]
        except TypeError:
            filters = [str(filt)]
    if "/DCTDecode" in filters:
        try:
            return Image.open(BytesIO(data))
        except Exception:
            return None
    color = obj.get("/ColorSpace")
    color_name = str(color) if color is not None else "/DeviceRGB"
    try:
        if color_name == "/DeviceGray":
            return Image.frombytes("L", (width, height), data)
        if color_name == "/DeviceRGB":
            return Image.frombytes("RGB", (width, height), data)
        if color_name == "/DeviceCMYK":
            return Image.frombytes("CMYK", (width, height), data)
    except Exception:
        return None
    return None


def _replace_with_jpeg(container, name, jpeg: bytes, size: tuple[int, int]) -> None:
    stream = DecodedStreamObject()
    stream.set_data(jpeg)
    stream[NameObject("/Type")] = NameObject("/XObject")
    stream[NameObject("/Subtype")] = NameObject("/Image")
    stream[NameObject("/Width")] = NumberObject(size[0])
    stream[NameObject("/Height")] = NumberObject(size[1])
    stream[NameObject("/ColorSpace")] = NameObject("/DeviceRGB")
    stream[NameObject("/BitsPerComponent")] = NumberObject(8)
    stream[NameObject("/Filter")] = NameObject("/DCTDecode")
    container[name] = stream


def _recompress_page_images(page, *, quality: int) -> None:
    """Re-encode raster images at the same pixel size. Never drop an image."""
    resources = page.get("/Resources")
    if resources is None:
        return
    resources = resources.get_object()
    xobject = resources.get("/XObject")
    if xobject is None:
        return
    xobject = xobject.get_object()
    for name in list(xobject.keys()):
        obj = xobject[name].get_object()
        if obj.get("/Subtype") != "/Image":
            continue
        image = _xobject_to_image(obj)
        if image is None:
            continue
        rgb = _to_rgb(image)
        buffer = BytesIO()
        rgb.save(buffer, format="JPEG", quality=quality, optimize=True)
        jpeg = buffer.getvalue()
        try:
            original = len(obj.get_data())
        except Exception:
            original = len(jpeg) + 1
        if len(jpeg) >= original:
            continue
        _replace_with_jpeg(xobject, name, jpeg, rgb.size)


def _compress_pdf(path: Path, dest: Path, *, lossy: bool, quality: int | None) -> tuple[int, int]:
    reader = _open_pdf(path)
    writer = PdfWriter()
    try:
        writer.append(reader)
        for page in writer.pages:
            if lossy:
                _recompress_page_images(page, quality=int(quality or 75))
            try:
                page.compress_content_streams()
            except Exception:
                pass
        try:
            try:
                writer.compress_identical_objects(
                    remove_duplicates=True, remove_unreferenced=True
                )
            except TypeError:
                writer.compress_identical_objects()
        except Exception:
            pass
        pages = len(writer.pages)
        _write_atomically(writer, dest)
    finally:
        reader.close()
    return dest.stat().st_size, pages


def _default_dest(
    source: Path,
    folder: Path,
    single_name: Path | None,
    count: int,
    *,
    lossy: bool,
) -> Path:
    if count == 1 and single_name is not None:
        if is_image_path(source) and single_name.suffix.lower() == ".pdf":
            ext = ".jpg" if lossy else source.suffix.lower() or ".png"
            return folder / f"{single_name.stem}{ext}"
        return folder / single_name.name
    if source.suffix.lower() == ".pdf":
        return folder / f"{source.stem}-compressed.pdf"
    ext = ".jpg" if lossy else source.suffix.lower() or ".png"
    return folder / f"{source.stem}-compressed{ext}"


def compress_files(
    inputs: Iterable[str | os.PathLike[str]],
    output: str | os.PathLike[str],
    *,
    overwrite: bool = False,
    preset: str = DEFAULT_PRESET,
) -> CompressResult:
    """Compress one or more PDFs or pictures into new files.

    ``output`` is the destination file when there is a single input, or the
    folder (or a name whose parent is the folder) when there are several.
    """
    if preset not in PRESETS:
        raise UnsupportedCompressError(
            f"unknown compression preset '{preset}'; use {', '.join(PRESETS)}"
        )
    settings = PRESETS[preset]
    paths = [_expand(p) for p in inputs]
    dest = _expand(output)

    if not paths:
        raise InputNotFoundError("compressing needs at least one file")

    for path in paths:
        _check_exists(path)
        if not (is_image_path(path) or path.suffix.lower() == ".pdf" or _is_pdf(path)):
            raise UnsupportedCompressError(
                f"can only compress PDFs and pictures, not '{path.suffix or path.name}'"
            )

    folder = dest if dest.is_dir() else dest.parent
    single_name = None if dest.is_dir() else dest
    lossy = bool(settings["lossy"])
    targets: list[Path] = []
    for path in paths:
        target = _default_dest(
            path, folder, single_name, len(paths), lossy=lossy
        )
        if is_image_path(path) and target.suffix.lower() == ".pdf":
            target = target.with_suffix(".jpg" if lossy else path.suffix)
        targets.append(target)
        _guard_output(target, paths, overwrite)

    original_total = sum(p.stat().st_size for p in paths)
    written = 0
    pages = 0
    for source, target in zip(paths, targets):
        if is_image_path(source):
            written += _compress_picture(
                source,
                target,
                lossy=lossy,
                quality=settings["quality"],
            )
            pages += 1
        else:
            size, n_pages = _compress_pdf(
                source,
                target,
                lossy=lossy,
                quality=settings["quality"],
            )
            written += size
            pages += n_pages

    return CompressResult(
        output=targets[0],
        outputs=tuple(targets),
        original_bytes=original_total,
        size_bytes=written,
        pages=pages,
    )
