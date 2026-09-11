"""Tests for :func:`pdf_tool.join_pdfs`."""

from __future__ import annotations

import os
import stat

import pytest
from pypdf import PdfWriter

from factories import build_image_pdf_bytes, write_pdf
from helpers import (
    outline_titles,
    page_content,
    page_labels,
    read,
    write_bookmarked_pdf,
    write_encrypted_pdf,
)

from pdf_tool import (
    EncryptedPdfError,
    InputNotFoundError,
    InvalidPdfError,
    NotEnoughInputsError,
    OutputConflictError,
    OutputExistsError,
    join_pdfs,
)


class TestJoining:
    def test_two_files_are_combined_in_order(self, two_pdfs, tmp_path):
        first, second = two_pdfs
        out = tmp_path / "combined.pdf"

        result = join_pdfs([first, second], out)

        assert result.total_pages == 5
        assert page_labels(read(out)) == [
            "first-1",
            "first-2",
            "second-1",
            "second-2",
            "second-3",
        ]

    def test_output_is_a_readable_pdf_named_by_the_user(self, two_pdfs, tmp_path):
        first, second = two_pdfs
        out = tmp_path / "whatever-the-user-called-it.pdf"

        result = join_pdfs([first, second], out)

        assert out.exists()
        assert result.output == out
        assert out.read_bytes().startswith(b"%PDF-")
        assert len(read(out).pages) == 5

    def test_three_or_more_files_are_joined(self, make_pdf, tmp_path):
        inputs = [
            make_pdf("a.pdf", ["a-1"]),
            make_pdf("b.pdf", ["b-1", "b-2"]),
            make_pdf("c.pdf", ["c-1"]),
            make_pdf("d.pdf", ["d-1", "d-2", "d-3"]),
        ]

        result = join_pdfs(inputs, tmp_path / "many.pdf")

        assert result.total_pages == 7
        assert page_labels(read(tmp_path / "many.pdf")) == [
            "a-1",
            "b-1",
            "b-2",
            "c-1",
            "d-1",
            "d-2",
            "d-3",
        ]
        assert [item.pages for item in result.files] == [1, 2, 1, 3]

    def test_the_same_file_can_appear_twice(self, two_pdfs, tmp_path):
        first, _ = two_pdfs

        join_pdfs([first, first], tmp_path / "doubled.pdf")

        assert page_labels(read(tmp_path / "doubled.pdf")) == [
            "first-1",
            "first-2",
            "first-1",
            "first-2",
        ]

    def test_inputs_are_not_modified(self, two_pdfs, tmp_path):
        first, second = two_pdfs
        before = {path: path.read_bytes() for path in (first, second)}

        join_pdfs([first, second], tmp_path / "combined.pdf")

        assert {path: path.read_bytes() for path in (first, second)} == before

    def test_output_parent_directory_is_created(self, two_pdfs, tmp_path):
        first, second = two_pdfs
        out = tmp_path / "nested" / "deeper" / "combined.pdf"

        join_pdfs([first, second], out)

        assert out.exists()


class TestNothingIsEdited:
    def test_page_content_streams_are_byte_identical(self, two_pdfs, tmp_path):
        first, second = two_pdfs
        sources = [read(first), read(second)]
        original_streams = [page_content(p) for r in sources for p in r.pages]

        join_pdfs([first, second], tmp_path / "combined.pdf")

        joined = [page_content(p) for p in read(tmp_path / "combined.pdf").pages]
        assert joined == original_streams

    def test_page_geometry_is_preserved(self, two_pdfs, tmp_path):
        first, second = two_pdfs
        original_boxes = [
            tuple(float(v) for v in p.mediabox)
            for r in (read(first), read(second))
            for p in r.pages
        ]

        join_pdfs([first, second], tmp_path / "combined.pdf")

        joined_boxes = [
            tuple(float(v) for v in p.mediabox)
            for p in read(tmp_path / "combined.pdf").pages
        ]
        assert joined_boxes == original_boxes

    def test_page_resources_are_preserved(self, two_pdfs, tmp_path):
        first, second = two_pdfs

        join_pdfs([first, second], tmp_path / "combined.pdf")

        for page in read(tmp_path / "combined.pdf").pages:
            font = page["/Resources"]["/Font"]["/F1"].get_object()
            assert font["/BaseFont"] == "/Helvetica"
            assert font["/Subtype"] == "/Type1"

    def test_embedded_image_bytes_are_copied_without_re_encoding(
        self, make_pdf, tmp_path
    ):
        width = height = 4
        rgb = bytes(range(width * height * 3))  # 48 distinct byte values
        with_image = tmp_path / "with-image.pdf"
        with_image.write_bytes(
            build_image_pdf_bytes("with-image", rgb, width, height)
        )
        text_only = write_pdf(tmp_path / "text-only.pdf", ["text-only"])

        join_pdfs([with_image, text_only], tmp_path / "combined.pdf")

        pages = list(read(tmp_path / "combined.pdf").pages)
        assert len(pages) == 2

        image = pages[0]["/Resources"]["/XObject"]["/Im1"].get_object()
        assert image.get_data() == rgb
        assert int(image["/Width"]) == width
        assert int(image["/Height"]) == height
        assert image["/ColorSpace"] == "/DeviceRGB"
        assert page_content(pages[1]) == page_content(
            read(text_only).pages[0]
        )

    def test_compressed_input_is_joined_and_stays_readable(self, make_pdf, tmp_path):
        """Real-world PDFs store their content Flate-compressed; that must work."""
        writer = PdfWriter()
        writer.append(make_pdf("uncompressed.pdf", ["compressed-page"]))
        for page in writer.pages:
            page.compress_content_streams()
        compressed = tmp_path / "compressed.pdf"
        with compressed.open("wb") as handle:
            writer.write(handle)
        assert b"FlateDecode" in compressed.read_bytes()  # fixture really is compressed

        other = make_pdf("other.pdf", ["other-page"])
        join_pdfs([compressed, other], tmp_path / "combined.pdf")

        assert page_labels(read(tmp_path / "combined.pdf")) == [
            "compressed-page",
            "other-page",
        ]

    def test_document_metadata_is_not_combined(self, make_pdf, tmp_path):
        """Characterisation test: inputs' /Info entries are not merged.

        pypdf gives the joined document its own document information
        dictionary, so the per-file Title/Author of the inputs do not
        survive.  Recorded here so the behaviour is deliberate rather than a
        surprise -- see the limitations section of the README.
        """
        writer = PdfWriter()
        writer.append(make_pdf("seed.pdf", ["seed-page"]))
        writer.add_metadata({"/Title": "First Doc", "/Author": "Ada"})
        first = tmp_path / "first.pdf"
        with first.open("wb") as handle:
            writer.write(handle)
        second = make_pdf("second.pdf", ["plain"])

        assert read(first).metadata["/Title"] == "First Doc"

        join_pdfs([first, second], tmp_path / "combined.pdf")

        merged = read(tmp_path / "combined.pdf").metadata
        assert merged is None or "/Title" not in merged

    def test_bookmarks_from_the_inputs_are_carried_over(self, make_pdf, tmp_path):
        first = write_bookmarked_pdf(tmp_path / "first.pdf", ["f-1"], "Chapter One")
        second = write_bookmarked_pdf(
            tmp_path / "second.pdf", ["s-1", "s-2"], "Chapter Two"
        )

        join_pdfs([first, second], tmp_path / "combined.pdf")

        assert outline_titles(read(tmp_path / "combined.pdf")) == [
            "Chapter One",
            "Chapter Two",
        ]

    def test_bookmarks_can_be_dropped_on_request(self, make_pdf, tmp_path):
        first = write_bookmarked_pdf(tmp_path / "first.pdf", ["f-1"], "Chapter One")
        second = write_bookmarked_pdf(tmp_path / "second.pdf", ["s-1"], "Chapter Two")

        join_pdfs([first, second], tmp_path / "combined.pdf", keep_bookmarks=False)

        assert outline_titles(read(tmp_path / "combined.pdf")) == []


class TestValidation:
    def test_one_input_is_rejected(self, make_pdf, tmp_path):
        only = make_pdf("only.pdf", ["lonely"])

        with pytest.raises(NotEnoughInputsError, match="at least 2"):
            join_pdfs([only], tmp_path / "combined.pdf")

    def test_no_inputs_is_rejected(self, tmp_path):
        with pytest.raises(NotEnoughInputsError):
            join_pdfs([], tmp_path / "combined.pdf")

    def test_missing_input_is_reported(self, make_pdf, tmp_path):
        present = make_pdf("present.pdf", ["here"])
        missing = tmp_path / "missing.pdf"

        with pytest.raises(InputNotFoundError, match="missing.pdf"):
            join_pdfs([present, missing], tmp_path / "combined.pdf")

    def test_directory_as_input_is_reported(self, make_pdf, tmp_path):
        present = make_pdf("present.pdf", ["here"])

        with pytest.raises(InputNotFoundError, match="directory"):
            join_pdfs([present, tmp_path], tmp_path / "combined.pdf")

    def test_non_pdf_file_is_reported(self, make_pdf, tmp_path):
        present = make_pdf("present.pdf", ["here"])
        impostor = tmp_path / "notes.txt"
        impostor.write_text("this is not a PDF", encoding="utf-8")

        with pytest.raises(InvalidPdfError, match="not a PDF file"):
            join_pdfs([present, impostor], tmp_path / "combined.pdf")

    def test_truncated_pdf_is_reported(self, make_pdf, tmp_path):
        present = make_pdf("present.pdf", ["here"])
        broken = tmp_path / "broken.pdf"
        broken.write_bytes(b"%PDF-1.4\nthis stops mid file\n")

        with pytest.raises(InvalidPdfError, match="broken.pdf"):
            join_pdfs([present, broken], tmp_path / "combined.pdf")

    def test_encrypted_input_is_reported(self, make_pdf, tmp_path):
        present = make_pdf("present.pdf", ["here"])
        locked = write_encrypted_pdf(tmp_path / "locked.pdf")

        with pytest.raises(EncryptedPdfError, match="encrypted"):
            join_pdfs([present, locked], tmp_path / "combined.pdf")


class TestOutputGuards:
    def test_existing_output_is_not_silently_replaced(self, two_pdfs, tmp_path):
        first, second = two_pdfs
        out = tmp_path / "combined.pdf"
        out.write_bytes(b"precious")

        with pytest.raises(OutputExistsError, match="--overwrite"):
            join_pdfs([first, second], out)

        assert out.read_bytes() == b"precious"

    def test_overwrite_replaces_an_existing_output(self, two_pdfs, tmp_path):
        first, second = two_pdfs
        out = tmp_path / "combined.pdf"
        out.write_bytes(b"precious")

        result = join_pdfs([first, second], out, overwrite=True)

        assert result.total_pages == 5
        assert len(read(out).pages) == 5

    def test_output_may_not_be_one_of_the_inputs(self, two_pdfs, tmp_path):
        first, second = two_pdfs

        with pytest.raises(OutputConflictError, match="same file"):
            join_pdfs([first, second], first)

    def test_output_equal_to_input_via_a_different_path(self, two_pdfs, tmp_path):
        first, second = two_pdfs

        with pytest.raises(OutputConflictError):
            join_pdfs([first, second], tmp_path / "subdir" / ".." / "first.pdf")

    def test_output_permissions_match_a_normally_created_file(self, two_pdfs, tmp_path):
        """mkstemp creates 0600 files; the result must not inherit that."""
        first, second = two_pdfs
        out = tmp_path / "combined.pdf"

        join_pdfs([first, second], out)

        umask = os.umask(0)
        os.umask(umask)
        assert stat.S_IMODE(out.stat().st_mode) == 0o666 & ~umask

    def test_a_failed_write_leaves_no_output_behind(
        self, two_pdfs, tmp_path, monkeypatch
    ):
        first, second = two_pdfs
        out = tmp_path / "combined.pdf"

        def explode(self, stream):
            raise RuntimeError("disk on fire")

        monkeypatch.setattr(PdfWriter, "write", explode)

        with pytest.raises(RuntimeError, match="disk on fire"):
            join_pdfs([first, second], out)

        assert not out.exists()
        assert {p.name for p in tmp_path.iterdir()} == {"first.pdf", "second.pdf"}
