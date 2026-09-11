"""Background workers so the GUI never blocks on disk I/O.

Two workers live here:

* :class:`PageProbeWorker` counts the pages of every file the user adds, so a
  folder of large PDFs cannot freeze the window.
* :class:`JoinWorker` performs the actual merge off the UI thread and reports
  progress, success and failure through signals.
"""

from __future__ import annotations

from pathlib import Path
from typing import Sequence

from PySide6.QtCore import QObject, Signal

from pypdf import PdfReader

from ..errors import PdfToolError
from ..join import JoinResult, join_pdfs


class PageProbeWorker(QObject):
    """Count pages for a batch of files.

    Signals carry the results back so the list widget can update item
    subtitles as they arrive.
    """

    page_count = Signal(str, int)      # (path, pages)
    probe_failed = Signal(str, str)    # (path, message)
    finished = Signal()

    def __init__(self, paths: Sequence[str], parent: QObject | None = None) -> None:
        super().__init__(parent)
        self._paths = list(paths)

    def run(self) -> None:  # pragma: no cover - thin; run on a QThread
        for raw in self._paths:
            try:
                with PdfReader(str(raw)) as reader:
                    self.page_count.emit(raw, len(reader.pages))
            except Exception as exc:  # a bad file must not kill the probe
                self.probe_failed.emit(raw, str(exc))
        self.finished.emit()


class JoinWorker(QObject):
    """Run :func:`pdf_tool.join_pdfs` and forward the outcome via signals."""

    started = Signal()
    succeeded = Signal(object)   # JoinResult
    failed = Signal(str)         # one-line user message
    finished = Signal()          # always emitted after succeeded/failed

    def __init__(
        self,
        inputs: Sequence[str | Path],
        output: str | Path,
        *,
        overwrite: bool,
        keep_bookmarks: bool,
        parent: QObject | None = None,
    ) -> None:
        super().__init__(parent)
        self._inputs = [str(p) for p in inputs]
        self._output = str(output)
        self._overwrite = overwrite
        self._keep_bookmarks = keep_bookmarks

    def run(self) -> None:
        self.started.emit()
        try:
            result: JoinResult = join_pdfs(
                self._inputs,
                self._output,
                overwrite=self._overwrite,
                keep_bookmarks=self._keep_bookmarks,
            )
        except PdfToolError as exc:
            self.failed.emit(str(exc))
        except Exception as exc:  # defensive: never leave the UI wedged
            self.failed.emit(f"unexpected error: {exc}")
        else:
            self.succeeded.emit(result)
        self.finished.emit()
