"""Tests for :func:`pdf_tool.compress_files`."""

from __future__ import annotations

from pathlib import Path

import pytest
from PIL import Image

from factories import build_image_pdf_bytes
from helpers import read

from pdf_tool import UnsupportedCompressError, compress_files
from pdf_tool.cli import main


def _noisy_png(path: Path, size: tuple[int, int] = (80, 80)) -> Path:
    pixels = bytes((x * y + x) % 256 for y in range(size[1]) for x in range(size[0]) for _ in range(3))
    Image.frombytes("RGB", size, pixels).save(path, format="PNG", compress_level=0)
    return path


def _image_pdf(path: Path) -> Path:
    width = height = 64
    rgb = bytes((i * 13) % 256 for i in range(width * height * 3))
    path.write_bytes(build_image_pdf_bytes("photo", rgb, width, height))
    return path


class TestCompressPictures:
    def test_png_becomes_a_smaller_jpeg(self, tmp_path):
        source = _noisy_png(tmp_path / "big.png")
        out = tmp_path / "small.jpg"

        result = compress_files([source], out, preset="strong")

        assert out.exists()
        assert result.size_bytes < result.original_bytes
        assert result.size_bytes == out.stat().st_size
        Image.open(out).verify()

    def test_original_is_untouched(self, tmp_path):
        source = _noisy_png(tmp_path / "keep.png")
        before = source.read_bytes()

        compress_files([source], tmp_path / "out.jpg")

        assert source.read_bytes() == before


class TestCompressPdf:
    def test_image_pdf_shrinks(self, tmp_path):
        source = _image_pdf(tmp_path / "photo.pdf")
        out = tmp_path / "photo-small.pdf"

        result = compress_files([source], out, preset="strong")

        assert out.exists()
        assert out.read_bytes().startswith(b"%PDF-")
        assert len(read(out).pages) == 1
        assert result.size_bytes < result.original_bytes

    def test_unsupported_type_is_rejected(self, tmp_path):
        notes = tmp_path / "notes.txt"
        notes.write_text("hello", encoding="utf-8")
        with pytest.raises(UnsupportedCompressError):
            compress_files([notes], tmp_path / "out.bin")


class TestCliCompress:
    def test_compress_flag(self, tmp_path, capsys):
        source = _noisy_png(tmp_path / "shot.png")
        out = tmp_path / "shot.jpg"

        code = main(["--compress", str(source), "-o", str(out), "--quality", "strong"])
        printed = capsys.readouterr().out

        assert code == 0
        assert out.exists()
        assert "Compressed 1 file(s)" in printed
        assert "→" in printed
