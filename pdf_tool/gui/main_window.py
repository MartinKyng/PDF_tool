"""The single window of the pdf_tool GUI."""

from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import QThread, Qt
from PySide6.QtGui import QDragEnterEvent, QDropEvent
from PySide6.QtWidgets import (
    QAbstractItemView,
    QCheckBox,
    QComboBox,
    QFileDialog,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QPushButton,
    QRadioButton,
    QSizePolicy,
    QStyle,
    QTabBar,
    QVBoxLayout,
    QWidget,
)

from ..images import IMAGE_EXTENSIONS, parse_name_list
from ..join import JoinResult
from ..units import ensure_pdf_suffix, human_size
from ..version import APP_NAME, __version__
from .file_list import FileItemDelegate, ROLE_PAGES, ROLE_PATH, ROLE_SIZE
from .worker import CompressWorker, ImagesWorker, JoinWorker, PageProbeWorker

DEFAULT_OUTPUT = "combined.pdf"


class MainWindow(QWidget):
    """Drag-and-drop a handful of PDFs, name the output, join them."""

    def __init__(self, initial_files: list[Path] | None = None) -> None:
        super().__init__()
        self.setWindowTitle(f"{APP_NAME}")
        self._mode = "join"
        self.setWindowIcon(self.style().standardIcon(QStyle.StandardPixmap.SP_FileIcon))
        self.resize(780, 660)
        self.setMinimumSize(560, 480)
        self.setAcceptDrops(True)

        self._output_dir = Path.home()
        self._threads: list[QThread] = []
        self._busy_flag = False

        self._build_ui()
        self._wire_ui()

        if initial_files:
            self.add_files(initial_files)

    # -- construction -----------------------------------------------------
    def _build_ui(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(24, 20, 24, 16)
        root.setSpacing(16)

        # header
        header = QVBoxLayout()
        header.setSpacing(2)
        self.title_label = QLabel(APP_NAME)
        self.title_label.setObjectName("appTitle")
        self.version_label = QLabel(f"v{__version__} · desktop")
        self.version_label.setObjectName("appVersion")
        title_row = QHBoxLayout()
        title_row.setSpacing(8)
        title_row.addWidget(self.title_label)
        title_row.addWidget(self.version_label)
        title_row.addStretch(1)
        header.addLayout(title_row)
        self.mode_bar = QTabBar()
        self.mode_bar.setObjectName("modeBar")
        self.mode_bar.addTab("Join PDFs")
        self.mode_bar.addTab("Images → PDF")
        self.mode_bar.addTab("Compress")
        self.mode_bar.setExpanding(False)
        header.addWidget(self.mode_bar)

        self.subtitle_label = QLabel(
            "A calm workspace for joining PDFs without changing their pages."
        )
        self.subtitle_label.setObjectName("appSubtitle")
        self.subtitle_label.setWordWrap(True)
        header.addWidget(self.subtitle_label)
        root.addLayout(header)

        # files card
        self.file_card = QFrame()
        self.file_card.setObjectName("fileCard")
        files_layout = QVBoxLayout(self.file_card)
        files_layout.setContentsMargins(16, 14, 16, 14)
        files_layout.setSpacing(10)

        files_head = QHBoxLayout()
        self.files_title = QLabel("Files to join")
        self.files_title.setObjectName("cardTitle")
        self.count_label = QLabel("0 files · 0 pages")
        self.count_label.setObjectName("cardHint")
        files_head.addWidget(self.files_title)
        files_head.addStretch(1)
        files_head.addWidget(self.count_label)
        files_layout.addLayout(files_head)

        toolbar = QHBoxLayout()
        toolbar.setSpacing(6)
        self.add_button = QPushButton("Add…")
        self.up_button = QPushButton("↑")
        self.down_button = QPushButton("↓")
        self.remove_button = QPushButton("Remove")
        self.clear_button = QPushButton("Clear")
        self.clear_button.setObjectName("danger")
        for btn in (self.up_button, self.down_button):
            btn.setFixedWidth(40)
        self.remove_button.setFixedWidth(84)
        self.clear_button.setFixedWidth(72)
        toolbar.addWidget(self.add_button)
        toolbar.addWidget(self.up_button)
        toolbar.addWidget(self.down_button)
        toolbar.addWidget(self.remove_button)
        toolbar.addStretch(1)
        toolbar.addWidget(self.clear_button)
        files_layout.addLayout(toolbar)

        self.list_widget = QListWidget()
        self.list_widget.setObjectName("fileList")
        self.list_widget.setItemDelegate(FileItemDelegate(self.list_widget))
        self.list_widget.setSelectionMode(QAbstractItemView.SelectionMode.ExtendedSelection)
        self.list_widget.setDragDropMode(QAbstractItemView.DragDropMode.InternalMove)
        self.list_widget.setDefaultDropAction(Qt.DropAction.MoveAction)
        self.list_widget.setSizePolicy(
            QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding
        )
        files_layout.addWidget(self.list_widget, 1)
        root.addWidget(self.file_card, 1)

        # output card
        self.output_card = QFrame()
        self.output_card.setObjectName("outputCard")
        out_layout = QVBoxLayout(self.output_card)
        out_layout.setContentsMargins(16, 14, 16, 14)
        out_layout.setSpacing(10)

        out_head = QLabel("Output")
        out_head.setObjectName("cardTitle")
        out_layout.addWidget(out_head)

        name_row = QHBoxLayout()
        name_row.setSpacing(8)
        self.output_edit = QLineEdit()
        self.output_edit.setPlaceholderText(f"e.g. {DEFAULT_OUTPUT}")
        self.output_edit.setText(DEFAULT_OUTPUT)
        self.browse_button = QPushButton("Choose folder…")
        name_row.addWidget(self.output_edit, 1)
        name_row.addWidget(self.browse_button)
        out_layout.addLayout(name_row)

        self.dir_label = QLabel(str(self._output_dir))
        self.dir_label.setObjectName("cardHint")
        self.dir_label.setWordWrap(True)
        out_layout.addWidget(self.dir_label)

        options_row = QHBoxLayout()
        options_row.setSpacing(16)
        layout_row = QHBoxLayout()
        layout_row.setSpacing(16)
        self.combined_radio = QRadioButton("One combined PDF")
        self.combined_radio.setChecked(True)
        self.separate_radio = QRadioButton("One PDF per picture")
        self.inherit_names_check = QCheckBox("Use original file names")
        self.combined_radio.setVisible(False)
        self.separate_radio.setVisible(False)
        self.inherit_names_check.setVisible(False)
        self.quality_label = QLabel("Size reduction")
        self.quality_combo = QComboBox()
        self.quality_combo.addItem("Light", "light")
        self.quality_combo.addItem("Balanced", "balanced")
        self.quality_combo.addItem("Strong", "strong")
        self.quality_combo.setCurrentIndex(1)
        self.quality_label.setVisible(False)
        self.quality_combo.setVisible(False)
        layout_row.addWidget(self.combined_radio)
        layout_row.addWidget(self.separate_radio)
        layout_row.addWidget(self.inherit_names_check)
        layout_row.addWidget(self.quality_label)
        layout_row.addWidget(self.quality_combo)
        layout_row.addStretch(1)
        out_layout.addLayout(layout_row)

        self.bookmarks_check = QCheckBox("Keep bookmarks")
        self.bookmarks_check.setChecked(True)
        self.overwrite_check = QCheckBox("Overwrite if it exists")
        options_row.addWidget(self.bookmarks_check)
        options_row.addWidget(self.overwrite_check)
        options_row.addStretch(1)
        out_layout.addLayout(options_row)
        root.addWidget(self.output_card)

        # action row
        action_row = QHBoxLayout()
        self.status_label = QLabel("Ready.")
        self.status_label.setObjectName("status")
        self.status_label.setWordWrap(True)
        self.join_button = QPushButton("Join PDFs")
        self.join_button.setObjectName("primaryAction")
        self.join_button.setFixedHeight(44)
        self.join_button.setMinimumWidth(160)
        action_row.addWidget(self.status_label, 1)
        action_row.addWidget(self.join_button)
        root.addLayout(action_row)

    def _wire_ui(self) -> None:
        self.add_button.clicked.connect(self._browse_add)
        self.up_button.clicked.connect(lambda: self._move(-1))
        self.down_button.clicked.connect(lambda: self._move(+1))
        self.remove_button.clicked.connect(self.remove_selected)
        self.clear_button.clicked.connect(self.clear_all)
        self.browse_button.clicked.connect(self._browse_output)
        self.join_button.clicked.connect(self.start_join)
        self.list_widget.model().rowsMoved.connect(self._refresh_counts)
        self.mode_bar.currentChanged.connect(self._on_mode_changed)
        self.combined_radio.toggled.connect(self._sync_image_output_widgets)
        self.inherit_names_check.toggled.connect(self._sync_image_output_widgets)

    # -- drag & drop ------------------------------------------------------
    def dragEnterEvent(self, event: QDragEnterEvent) -> None:  # noqa: N802
        if event.mimeData().hasUrls():
            event.acceptProposedAction()
        else:
            event.ignore()

    def dropEvent(self, event: QDropEvent) -> None:  # noqa: N802
        paths = [Path(url.toLocalFile()) for url in event.mimeData().urls()
                 if url.isLocalFile()]
        accepted = [p for p in paths if p.is_file() and self._accepts_path(p)]
        if accepted:
            self.add_files(accepted)
            event.acceptProposedAction()
        else:
            event.ignore()

    # -- public API (also used by tests) ---------------------------------
    def current_paths(self) -> list[Path]:
        """The files in the list, top to bottom."""
        return [Path(item.data(ROLE_PATH)) for item in self._items()]

    def add_files(self, paths) -> None:
        """Append ``paths`` to the list and kick off background page counts."""
        added: list[QListWidgetItem] = []
        for raw in paths:
            path = Path(raw).expanduser()
            item = QListWidgetItem(path.name)
            item.setData(ROLE_PATH, str(path))
            item.setData(ROLE_PAGES, None)
            try:
                item.setData(ROLE_SIZE, path.stat().st_size)
            except OSError:
                item.setData(ROLE_SIZE, None)
            self.list_widget.addItem(item)
            added.append(item)
        self._refresh_counts()
        if added:
            self._probe([i.data(ROLE_PATH) for i in added])

    def remove_selected(self) -> None:
        for item in reversed(self.list_widget.selectedItems()):
            self.list_widget.takeItem(self.list_widget.row(item))
        self._refresh_counts()

    def clear_all(self) -> None:
        self.list_widget.clear()
        self._refresh_counts()
        self.set_status("Ready.")

    def set_output_dir(self, directory: Path) -> None:
        self._output_dir = Path(directory)
        self.dir_label.setText(str(self._output_dir))

    def all_counted(self) -> bool:
        return all(i.data(ROLE_PAGES) is not None for i in self._items())

    # -- internals --------------------------------------------------------
    def _items(self) -> list[QListWidgetItem]:
        return [self.list_widget.item(i) for i in range(self.list_widget.count())]

    def _move(self, delta: int) -> None:
        row = self.list_widget.currentRow()
        if row < 0:
            return
        target = row + delta
        if not (0 <= target < self.list_widget.count()):
            return
        item = self.list_widget.takeItem(row)
        self.list_widget.insertItem(target, item)
        self.list_widget.setCurrentRow(target)
        self._refresh_counts()

    def _apply_page_count(self, path: str, pages: int) -> None:
        for item in self._items():
            if item.data(ROLE_PATH) == path:
                item.setData(ROLE_PAGES, pages)
        self._refresh_counts()

    def _probe_failed(self, path: str, message: str) -> None:
        for item in self._items():
            if item.data(ROLE_PATH) == path:
                item.setData(ROLE_PAGES, 0)
        self._refresh_counts()
        self.set_status(f"Could not read {Path(path).name}: {message}", "error")

    def _probe(self, paths: list[str]) -> None:
        thread = QThread(self)
        worker = PageProbeWorker(paths)
        worker.moveToThread(thread)
        thread._worker_anchor = worker  # keep the QObject alive for the run
        thread.started.connect(worker.run)
        worker.page_count.connect(self._apply_page_count)
        worker.probe_failed.connect(self._probe_failed)
        worker.finished.connect(thread.quit)
        worker.finished.connect(worker.deleteLater)
        thread.finished.connect(thread.deleteLater)
        thread.finished.connect(lambda: self._drop_thread(thread))
        self._threads.append(thread)
        thread.start()

    def _drop_thread(self, thread: QThread) -> None:
        if thread in self._threads:
            self._threads.remove(thread)

    def _on_mode_changed(self, index: int) -> None:
        self._mode = {1: "images", 2: "compress"}.get(index, "join")
        self.clear_all()
        images = self._mode == "images"
        compress = self._mode == "compress"
        if images:
            self.files_title.setText("Pictures to convert")
            self.subtitle_label.setText(
                "Drop JPEG, PNG and other pictures. Combine them, or write "
                "one PDF per picture using original names or names you type."
            )
            self.join_button.setText("Create PDF")
            self.bookmarks_check.setVisible(False)
            self.set_status("Add one or more pictures.")
        elif compress:
            self.files_title.setText("Files to compress")
            self.subtitle_label.setText(
                "Drop a PDF or picture. The tool writes a smaller copy and "
                "leaves the original untouched — for example 305 KB down to 250 KB."
            )
            self.join_button.setText("Compress")
            self.bookmarks_check.setVisible(False)
            self.output_edit.setText("compressed.pdf")
            self.set_status("Add a PDF or picture to shrink.")
        else:
            self.files_title.setText("Files to join")
            self.subtitle_label.setText(
                "A calm workspace for joining PDFs without changing their pages."
            )
            self.join_button.setText("Join PDFs")
            self.bookmarks_check.setVisible(True)
            self.output_edit.setText(DEFAULT_OUTPUT)
            self.set_status("Add at least two PDFs to join.")
        self.combined_radio.setVisible(images)
        self.separate_radio.setVisible(images)
        self.quality_label.setVisible(compress)
        self.quality_combo.setVisible(compress)
        self._sync_image_output_widgets()
        self._refresh_counts()

    def _sync_image_output_widgets(self, *_: object) -> None:
        images = self._mode == "images"
        separate = images and self.separate_radio.isChecked()
        self.inherit_names_check.setVisible(separate)
        inherit = separate and self.inherit_names_check.isChecked()
        self.output_edit.setEnabled(not inherit)
        if inherit:
            self.output_edit.setPlaceholderText("names come from the pictures")
        elif separate:
            self.output_edit.setPlaceholderText(
                "e.g. album.pdf  or  one.pdf, two.pdf"
            )
        else:
            self.output_edit.setPlaceholderText(f"e.g. {DEFAULT_OUTPUT}")

    def _accepts_path(self, path: Path) -> bool:
        suffix = path.suffix.lower()
        if self._mode == "images":
            return suffix in IMAGE_EXTENSIONS
        if self._mode == "compress":
            return suffix == ".pdf" or suffix in IMAGE_EXTENSIONS
        return suffix == ".pdf"

    def _min_files(self) -> int:
        return 1 if self._mode in {"images", "compress"} else 2

    def _refresh_counts(self, *_: object) -> None:
        files = self.list_widget.count()
        pages = sum((i.data(ROLE_PAGES) or 0) for i in self._items())
        self.count_label.setText(f"{files} file{'s' if files != 1 else ''} · {pages} pages")
        needed = self._min_files()
        enabled = files >= needed
        for btn in (self.join_button, self.up_button, self.down_button,
                    self.remove_button, self.clear_button):
            if btn is self.join_button:
                btn.setEnabled(enabled and not self._busy())
            else:
                btn.setEnabled(files > 0)
        if files < needed:
            if self._mode == "images":
                self.set_status("Add one or more pictures.")
            elif self._mode == "compress":
                self.set_status("Add a PDF or picture to shrink.")
            else:
                self.set_status("Add at least two PDFs to join.")

    def _busy(self) -> bool:
        return self._busy_flag

    # -- join -------------------------------------------------------------
    def start_join(self) -> None:
        paths = self.current_paths()
        needed = self._min_files()
        if len(paths) < needed:
            if self._mode == "images":
                self.set_status("Add at least one picture first.", "error")
            elif self._mode == "compress":
                self.set_status("Add a file to compress first.", "error")
            else:
                self.set_status("Add at least two PDF files first.", "error")
            return

        raw_name = self.output_edit.text().strip() or DEFAULT_OUTPUT
        name, _changed = ensure_pdf_suffix(Path(raw_name))
        output = self._output_dir / name

        self._set_busy(True)
        if self._mode == "images":
            self.set_status("Creating PDF…")
        elif self._mode == "compress":
            self.set_status("Compressing…")
        else:
            self.set_status("Joining…")

        thread = QThread(self)
        if self._mode == "compress":
            worker = CompressWorker(
                paths,
                output,
                overwrite=self.overwrite_check.isChecked(),
                preset=str(self.quality_combo.currentData() or "balanced"),
            )
        elif self._mode == "images":
            combined = self.combined_radio.isChecked()
            inherit = self.inherit_names_check.isChecked()
            names = None
            if not combined and not inherit:
                listed = parse_name_list(self.output_edit.text())
                if len(listed) == len(paths):
                    names = listed
                    output = self._output_dir / listed[0]
            elif not combined and inherit:
                output = self._output_dir
            worker = ImagesWorker(
                paths,
                output,
                overwrite=self.overwrite_check.isChecked(),
                combined=combined,
                inherit_names=inherit,
                names=names,
            )
        else:
            worker = JoinWorker(
                paths,
                output,
                overwrite=self.overwrite_check.isChecked(),
                keep_bookmarks=self.bookmarks_check.isChecked(),
            )
        worker.moveToThread(thread)
        thread._worker_anchor = worker  # keep the QObject alive for the run
        thread.started.connect(worker.run)
        worker.succeeded.connect(self._on_join_success)
        worker.failed.connect(self._on_join_failed)
        worker.finished.connect(thread.quit)
        worker.finished.connect(worker.deleteLater)
        thread.finished.connect(thread.deleteLater)
        thread.finished.connect(lambda: self._set_busy(False))
        thread.finished.connect(lambda: self._drop_thread(thread))
        self._threads.append(thread)
        thread.start()

    def _on_join_success(self, result: JoinResult) -> None:
        original = getattr(result, "original_bytes", None)
        outputs = getattr(result, "outputs", None)
        if original is not None:
            self.set_status(
                f"Wrote {result.output.name} — "
                f"{human_size(original)} → {human_size(result.size_bytes)}.",
                "ok",
            )
            return
        if outputs and len(outputs) > 1:
            self.set_status(
                f"Wrote {len(outputs)} files ({human_size(result.size_bytes)}).",
                "ok",
            )
            return
        pages = getattr(result, "total_pages", getattr(result, "pages", 0))
        self.set_status(
            f"Wrote {result.output.name} — {pages} pages "
            f"({human_size(result.size_bytes)}).",
            "ok",
        )

    def _on_join_failed(self, message: str) -> None:
        self.set_status(f"Could not finish: {message}", "error")

    def _set_busy(self, busy: bool) -> None:
        # keep a flag so _refresh_counts can disable the join button while busy
        self._busy_flag = busy
        self.join_button.setEnabled(
            not busy and self.list_widget.count() >= self._min_files()
        )
        for widget in (self.add_button, self.remove_button, self.clear_button,
                       self.up_button, self.down_button, self.output_edit,
                       self.browse_button, self.combined_radio,
                       self.separate_radio, self.inherit_names_check,
                       self.quality_combo):
            widget.setEnabled(not busy)
        if not busy:
            self._sync_image_output_widgets()

    def set_status(self, text: str, kind: str = "info") -> None:
        self.status_label.setText(text)
        self.status_label.setObjectName(
            {"error": "statusError", "ok": "statusOk"}.get(kind, "status")
        )
        # re-polish so the new object name takes effect immediately
        style = self.status_label.style()
        style.unpolish(self.status_label)
        style.polish(self.status_label)

    def _browse_add(self) -> None:
        if self._mode == "images":
            filt = (
                "Pictures (*.jpg *.jpeg *.png *.bmp *.gif *.tif *.tiff *.webp);;"
                "All files (*)"
            )
            title = "Choose pictures"
        else:
            filt = "PDF files (*.pdf);;All files (*)"
            title = "Choose PDFs to join"
        files, _ = QFileDialog.getOpenFileNames(
            self, title, str(self._output_dir), filt
        )
        if files:
            self.add_files([Path(f) for f in files])

    def _browse_output(self) -> None:
        directory = QFileDialog.getExistingDirectory(
            self, "Choose output folder", str(self._output_dir)
        )
        if directory:
            self.set_output_dir(Path(directory))
