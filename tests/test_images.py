"""Tests for :func:`pdf_tool.images_to_pdf`."""

from __future__ import annotations

from pathlib import Path

import pytest
from PIL import Image

from helpers import read

from pdf_tool import (
    InputNotFoundError,
    InvalidImageError,
    NotEnoughImagesError,
    OutputExistsError,
    images_to_pdf,
)
from pdf_tool.cli import main


def _write_rgb(path: Path, colour: tuple[int, int, int], size=(8, 12)) -> Path:
    Image.new("RGB", size, colour).save(path)
    return path


@pytest.fixture
def two_jpegs(tmp_path: Path) -> tuple[Path, Path]:
    first = _write_rgb(tmp_path / "red.jpg", (255, 0, 0), (16, 10))
    second = _write_rgb(tmp_path / "blue.png", (0, 0, 255), (20, 30))
    return first, second


class TestImagesToPdf:
    def test_two_pictures_become_two_pages(self, two_jpegs, tmp_path):
        first, second = two_jpegs
        out = tmp_path / "album.pdf"

        result = images_to_pdf([first, second], out)

        assert result.total_pages == 2
        assert out.exists()
        assert out.read_bytes().startswith(b"%PDF-")
        assert len(read(out).pages) == 2
        assert [item.path for item in result.files] == [first, second]

    def test_single_image_is_allowed(self, two_jpegs, tmp_path):
        first, _ = two_jpegs
        out = tmp_path / "one.pdf"

        result = images_to_pdf([first], out)

        assert result.total_pages == 1
        assert len(read(out).pages) == 1

    def test_page_size_matches_image_pixels(self, two_jpegs, tmp_path):
        first, _ = two_jpegs
        out = tmp_path / "sized.pdf"

        images_to_pdf([first], out)

        box = read(out).pages[0].mediabox
        assert float(box.width) == 16
        assert float(box.height) == 10

    def test_inputs_are_not_modified(self, two_jpegs, tmp_path):
        first, second = two_jpegs
        before = {path: path.read_bytes() for path in (first, second)}

        images_to_pdf([first, second], tmp_path / "album.pdf")

        assert {path: path.read_bytes() for path in (first, second)} == before

    def test_no_inputs_is_rejected(self, tmp_path):
        with pytest.raises(NotEnoughImagesError):
            images_to_pdf([], tmp_path / "album.pdf")

    def test_missing_input_is_reported(self, two_jpegs, tmp_path):
        first, _ = two_jpegs
        with pytest.raises(InputNotFoundError, match="ghost"):
            images_to_pdf([first, tmp_path / "ghost.jpg"], tmp_path / "album.pdf")

    def test_non_image_is_reported(self, two_jpegs, tmp_path):
        first, _ = two_jpegs
        notes = tmp_path / "notes.txt"
        notes.write_text("nope", encoding="utf-8")
        with pytest.raises(InvalidImageError):
            images_to_pdf([first, notes], tmp_path / "album.pdf")

    def test_existing_output_is_not_replaced(self, two_jpegs, tmp_path):
        first, second = two_jpegs
        out = tmp_path / "album.pdf"
        out.write_bytes(b"precious")

        with pytest.raises(OutputExistsError):
            images_to_pdf([first, second], out)

        assert out.read_bytes() == b"precious"

    def test_overwrite_replaces(self, two_jpegs, tmp_path):
        first, second = two_jpegs
        out = tmp_path / "album.pdf"
        out.write_bytes(b"precious")

        images_to_pdf([first, second], out, overwrite=True)

        assert out.read_bytes().startswith(b"%PDF-")


class TestCliImages:
    def test_images_flag_writes_a_pdf(self, two_jpegs, tmp_path, capsys):
        first, second = two_jpegs
        out = tmp_path / "from-cli.pdf"

        code = main(["--images", str(first), str(second), "-o", str(out)])
        printed = capsys.readouterr().out

        assert code == 0
        assert out.exists()
        assert "Converting 2 image file(s)" in printed
        assert "Wrote" in printed
        assert len(read(out).pages) == 2
