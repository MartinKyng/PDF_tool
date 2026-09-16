"""Headless tests for the PySide6 GUI.

These run with ``QT_QPA_PLATFORM=offscreen`` so they need no display.  On a
host where Qt cannot even be loaded (missing system libraries) the module is
skipped entirely, so the core CLI tests still run.
"""

from __future__ import annotations


import pytest

pytest.importorskip("PySide6")

from helpers import page_labels, read  # noqa: E402

from pdf_tool.gui.main_window import MainWindow  # noqa: E402


def _two_file_window(qapp, tmp_path, two_pdfs):
    first, second = two_pdfs
    win = MainWindow()
    win.set_output_dir(tmp_path)
    win.add_files([first, second])
    return win, first, second


class TestListManagement:
    def test_files_are_listed_and_counted(self, qapp, qwait, tmp_path, two_pdfs):
        win, first, second = _two_file_window(qapp, tmp_path, two_pdfs)

        assert qwait(lambda: win.all_counted()), "page counts never arrived"
        assert win.current_paths() == [first, second]
        assert "2 files" in win.count_label.text()
        assert "5 pages" in win.count_label.text()

    def test_move_up_and_down_reorder(self, qapp, qwait, tmp_path, two_pdfs):
        win, first, second = _two_file_window(qapp, tmp_path, two_pdfs)
        qwait(lambda: win.all_counted())

        win.list_widget.setCurrentRow(1)
        win._move(-1)
        assert win.current_paths() == [second, first]

        win.list_widget.setCurrentRow(0)
        win._move(+1)
        assert win.current_paths() == [first, second]

    def test_remove_selected(self, qapp, qwait, tmp_path, two_pdfs):
        win, first, second = _two_file_window(qapp, tmp_path, two_pdfs)
        qwait(lambda: win.all_counted())

        win.list_widget.setCurrentRow(0)
        win.remove_selected()
        assert win.current_paths() == [second]

    def test_clear_all(self, qapp, tmp_path, two_pdfs):
        win, _, _ = _two_file_window(qapp, tmp_path, two_pdfs)
        win.clear_all()
        assert win.current_paths() == []
        assert "0 files" in win.count_label.text()


class TestJoiningFromGui:
    def test_join_creates_the_named_output(self, qapp, qwait, tmp_path, two_pdfs):
        win, first, second = _two_file_window(qapp, tmp_path, two_pdfs)
        qwait(lambda: win.all_counted())
        win.output_edit.setText("joined-from-gui.pdf")

        win.start_join()
        assert qwait(lambda: (tmp_path / "joined-from-gui.pdf").exists())

        out = read(tmp_path / "joined-from-gui.pdf")
        assert len(out.pages) == 5

    def test_join_applies_the_order_in_the_list(self, qapp, qwait, tmp_path, two_pdfs):
        win, first, second = _two_file_window(qapp, tmp_path, two_pdfs)
        qwait(lambda: win.all_counted())
        win.list_widget.setCurrentRow(1)
        win._move(-1)  # second before first

        win.start_join()
        assert qwait(lambda: (tmp_path / "combined.pdf").exists())

        labels = page_labels(read(tmp_path / "combined.pdf"))
        assert labels[:1] == ["second-1"]

    def test_join_requires_two_files(self, qapp, tmp_path, make_pdf):
        only = make_pdf("only.pdf", ["one"])
        win = MainWindow()
        win.set_output_dir(tmp_path)
        win.add_files([only])

        win.start_join()
        assert "at least two" in win.status_label.text()
        assert not (tmp_path / "combined.pdf").exists()

    def test_appends_pdf_extension_to_the_output(self, qapp, qwait, tmp_path, two_pdfs):
        win, _, _ = _two_file_window(qapp, tmp_path, two_pdfs)
        qwait(lambda: win.all_counted())
        win.output_edit.setText("no-extension")

        win.start_join()
        assert qwait(lambda: (tmp_path / "no-extension.pdf").exists())

    def test_overwrite_respects_the_checkbox(self, qapp, qwait, tmp_path, two_pdfs):
        win, _, _ = _two_file_window(qapp, tmp_path, two_pdfs)
        qwait(lambda: win.all_counted())
        existing = tmp_path / "combined.pdf"
        existing.write_bytes(b"precious")

        win.start_join()  # overwrite unchecked -> refuse
        assert qwait(lambda: "exists" in win.status_label.text())
        assert existing.read_bytes() == b"precious"

        win.overwrite_check.setChecked(True)
        win.start_join()

        def replaced():
            blob = existing.read_bytes()
            return blob.startswith(b"%PDF-") and len(read(existing).pages) == 5

        assert qwait(replaced)

    def test_success_status_is_positive(self, qapp, qwait, tmp_path, two_pdfs):
        win, _, _ = _two_file_window(qapp, tmp_path, two_pdfs)
        qwait(lambda: win.all_counted())

        win.start_join()
        assert qwait(lambda: "Wrote" in win.status_label.text())


class TestImagesMode:
    def test_one_picture_creates_a_pdf(self, qapp, qwait, tmp_path):
        from PIL import Image

        pic = tmp_path / "shot.png"
        Image.new("RGB", (12, 8), (10, 20, 30)).save(pic)

        win = MainWindow()
        win.set_output_dir(tmp_path)
        win.mode_bar.setCurrentIndex(1)
        win.add_files([pic])
        qwait(lambda: win.all_counted())
        win.output_edit.setText("from-pictures.pdf")

        win.start_join()
        assert qwait(lambda: (tmp_path / "from-pictures.pdf").exists())
        assert len(read(tmp_path / "from-pictures.pdf").pages) == 1


class TestRendering:
    def test_window_renders_to_an_image(self, qapp, qwait, tmp_path, two_pdfs):
        """The offscreen platform still rasterises; prove the window paints."""
        win, _, _ = _two_file_window(qapp, tmp_path, two_pdfs)
        qwait(lambda: win.all_counted())
        win.resize(760, 640)
        qapp.processEvents()

        image = win.grab()
        target = tmp_path / "gui.png"
        assert image.save(str(target))
        assert target.stat().st_size > 0
