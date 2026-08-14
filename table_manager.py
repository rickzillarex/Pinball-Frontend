#!/usr/bin/env python3
"""
Visual Pinball Cabinet - Table Manager
======================================

Companion admin tool for `pinball_frontend.py`.

The front-end is intentionally read-only; everything it consumes is created and
maintained here:

    config.json  -> vpx_exe_path, table_folder_path, media_folder_path,
                    rotation_angle, font_size, window_width, window_height
    tables.json  -> [ { filename, display_name, visible, media_file }, ... ]

Workflow
--------
1. Point the three paths at your VPX exe, your Tables folder and your Media
   folder (browse buttons provided).
2. Set rotation (90 / 270), the list font size and the framebuffer size.
3. Press "Rescan Folders" to scan the Tables folder for *.vpx files
   (alphabetically), scan the Media folder, and auto-match media to tables by
   comparing file names without their extension.
4. Edit display names, toggle visibility, override any media assignment.
5. Press "Save" to write config.json and tables.json.

Grid columns (left -> right):
    [x] Visible | Filename (read only) | Display Name (editable) |
    Assigned Media (read only) | Pick Image...

Requires: PyQt6   (pip install -r requirements.txt)
"""
from __future__ import annotations

import json
import os
from pathlib import Path

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QApplication,
    QComboBox,
    QFileDialog,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QSpinBox,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

BASE_DIR = Path(__file__).resolve().parent
CONFIG_PATH = BASE_DIR / "config.json"
TABLES_PATH = BASE_DIR / "tables.json"

IMAGE_EXTS = (".png", ".jpg", ".jpeg", ".webp", ".bmp", ".gif")

DEFAULT_CONFIG = {
    "vpx_exe_path": r"C:\vPinball\Visual Pinball\VPinballX.exe",
    "table_folder_path": r"C:\vPinball\Visual Pinball\Tables",
    "media_folder_path": r"C:\vPinball\Visual Pinball\Media",
    "rotation_angle": 270,
    "font_size": 42,
    "window_width": 3840,
    "window_height": 2160,
    "vpx_launch_arg": "-Play",
    "exit_grace_ms": 500,
    "fullscreen": True,
}

# Grid column indices
COL_VISIBLE = 0
COL_FILENAME = 1
COL_DISPLAY = 2
COL_MEDIA = 3
COL_PICK = 4


def load_json(path: Path, default):
    if not path.exists():
        return json.loads(json.dumps(default))
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return json.loads(json.dumps(default))


class TableManager(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("VPX Cabinet - Table Manager")
        self.resize(1180, 820)
        self.tables: list[dict] = []

        central = QWidget()
        self.setCentralWidget(central)
        root = QVBoxLayout(central)
        root.setContentsMargins(16, 16, 16, 16)
        root.setSpacing(14)

        root.addWidget(self._build_config_group())
        root.addWidget(self._build_actions_row())
        root.addWidget(self._build_table(), stretch=1)

        self.load_all()

    # ----------------------------------------------------- config section
    def _build_config_group(self) -> QGroupBox:
        box = QGroupBox("Configuration  (config.json)")
        form = QFormLayout(box)
        form.setLabelAlignment(Qt.AlignmentFlag.AlignRight)

        # --- path rows with browse buttons ---
        self.vpx_edit = QLineEdit()
        form.addRow("VPX executable:", self._path_row(self.vpx_edit, self._browse_vpx))

        self.table_edit = QLineEdit()
        form.addRow(
            "Tables folder:",
            self._path_row(self.table_edit, lambda: self._browse_dir(self.table_edit)),
        )

        self.media_edit = QLineEdit()
        form.addRow(
            "Media folder:",
            self._path_row(self.media_edit, lambda: self._browse_dir(self.media_edit)),
        )

        # --- numeric / choice rows ---
        self.rotation_combo = QComboBox()
        self.rotation_combo.addItems(["90", "270"])
        form.addRow("Rotation (degrees):", self.rotation_combo)

        self.font_spin = QSpinBox()
        self.font_spin.setRange(8, 400)
        self.font_spin.setSuffix(" px")
        form.addRow("List font size:", self.font_spin)

        self.width_spin = QSpinBox()
        self.width_spin.setRange(320, 15360)
        self.height_spin = QSpinBox()
        self.height_spin.setRange(240, 15360)
        size_row = QHBoxLayout()
        size_wrap = QWidget()
        size_wrap.setLayout(size_row)
        size_row.setContentsMargins(0, 0, 0, 0)
        size_row.addWidget(QLabel("W"))
        size_row.addWidget(self.width_spin)
        size_row.addSpacing(12)
        size_row.addWidget(QLabel("H"))
        size_row.addWidget(self.height_spin)
        size_row.addStretch(1)
        form.addRow("Window size:", size_wrap)

        return box

    def _path_row(self, edit: QLineEdit, on_browse) -> QWidget:
        wrap = QWidget()
        row = QHBoxLayout(wrap)
        row.setContentsMargins(0, 0, 0, 0)
        row.addWidget(edit, stretch=1)
        btn = QPushButton("Browse...")
        btn.clicked.connect(on_browse)
        row.addWidget(btn)
        return wrap

    # ---------------------------------------------------- actions section
    def _build_actions_row(self) -> QWidget:
        wrap = QWidget()
        row = QHBoxLayout(wrap)
        row.setContentsMargins(0, 0, 0, 0)

        rescan = QPushButton("Rescan Folders")
        rescan.clicked.connect(self.rescan)
        row.addWidget(rescan)

        reload_btn = QPushButton("Reload")
        reload_btn.clicked.connect(self.load_all)
        row.addWidget(reload_btn)

        row.addStretch(1)

        self.status = QLabel("")
        self.status.setStyleSheet("color:#888;")
        row.addWidget(self.status)
        row.addStretch(1)

        save = QPushButton("Save  (config.json + tables.json)")
        save.setStyleSheet("font-weight:600;")
        save.clicked.connect(self.save_all)
        row.addWidget(save)
        return wrap

    # ------------------------------------------------------ table section
    def _build_table(self) -> QTableWidget:
        self.grid = QTableWidget(0, 5)
        self.grid.setHorizontalHeaderLabels(
            ["Visible", "Filename", "Display Name", "Assigned Media", "Image"]
        )
        header = self.grid.horizontalHeader()
        header.setSectionResizeMode(COL_VISIBLE, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(COL_FILENAME, QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(COL_DISPLAY, QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(COL_MEDIA, QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(COL_PICK, QHeaderView.ResizeMode.ResizeToContents)
        self.grid.verticalHeader().setDefaultSectionSize(34)
        return self.grid

    # ----------------------------------------------------------- browsing
    def _browse_vpx(self) -> None:
        start = self.vpx_edit.text() or str(BASE_DIR)
        path, _ = QFileDialog.getOpenFileName(
            self, "Select VPinballX executable", start,
            "Executables (*.exe);;All files (*.*)",
        )
        if path:
            self.vpx_edit.setText(path)

    def _browse_dir(self, edit: QLineEdit) -> None:
        start = edit.text() or str(BASE_DIR)
        path = QFileDialog.getExistingDirectory(self, "Select folder", start)
        if path:
            edit.setText(path)

    # ------------------------------------------------------------- rescan
    def rescan(self) -> None:
        table_dir = self.table_edit.text().strip()
        media_dir = self.media_edit.text().strip()
        if not os.path.isdir(table_dir):
            QMessageBox.warning(self, "Rescan", "Tables folder is not a valid directory.")
            return

        # 1) scan tables (alphabetical)
        vpx_files = sorted(
            (f for f in os.listdir(table_dir) if f.lower().endswith(".vpx")),
            key=str.lower,
        )

        # 2) scan media
        media_files: list[str] = []
        if os.path.isdir(media_dir):
            media_files = [
                f for f in os.listdir(media_dir)
                if f.lower().endswith(IMAGE_EXTS)
            ]
        media_by_stem = {Path(f).stem.lower(): f for f in media_files}

        # Preserve any existing per-table edits (display name / visibility /
        # manual media choice) keyed by filename.
        existing = {t["filename"]: t for t in self.tables}

        rebuilt: list[dict] = []
        for fname in vpx_files:
            prev = existing.get(fname, {})
            stem = Path(fname).stem
            # 3) auto-match media by filename-without-extension
            auto_media = media_by_stem.get(stem.lower(), "")
            rebuilt.append({
                "filename": fname,
                "display_name": prev.get("display_name") or self._prettify(stem),
                "visible": prev.get("visible", True),
                # keep a manual override if one was set previously
                "media_file": prev.get("media_file") or auto_media,
            })

        self.tables = rebuilt
        self.populate_grid()
        self.status.setText(
            f"Found {len(vpx_files)} tables, {len(media_files)} media files."
        )

    @staticmethod
    def _prettify(stem: str) -> str:
        return stem.replace("_", " ").replace(".", " ").strip()

    # -------------------------------------------------------------- grid
    def populate_grid(self) -> None:
        self.grid.setRowCount(0)
        for row, table in enumerate(self.tables):
            self.grid.insertRow(row)

            # Visible checkbox
            chk = QTableWidgetItem()
            chk.setFlags(
                Qt.ItemFlag.ItemIsUserCheckable | Qt.ItemFlag.ItemIsEnabled
            )
            chk.setCheckState(
                Qt.CheckState.Checked if table.get("visible", True)
                else Qt.CheckState.Unchecked
            )
            chk.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            self.grid.setItem(row, COL_VISIBLE, chk)

            # Filename (read only)
            fn = QTableWidgetItem(table.get("filename", ""))
            fn.setFlags(Qt.ItemFlag.ItemIsEnabled)
            self.grid.setItem(row, COL_FILENAME, fn)

            # Display name (editable)
            dn = QTableWidgetItem(table.get("display_name", ""))
            self.grid.setItem(row, COL_DISPLAY, dn)

            # Assigned media (read only)
            md = QTableWidgetItem(table.get("media_file", ""))
            md.setFlags(Qt.ItemFlag.ItemIsEnabled)
            self.grid.setItem(row, COL_MEDIA, md)

            # Pick image button
            pick = QPushButton("Pick Image...")
            pick.clicked.connect(lambda _=False, r=row: self._pick_media(r))
            self.grid.setCellWidget(row, COL_PICK, pick)

    def _pick_media(self, row: int) -> None:
        start = self.media_edit.text() or str(BASE_DIR)
        path, _ = QFileDialog.getOpenFileName(
            self, "Select preview image", start,
            "Images (*.png *.jpg *.jpeg *.webp *.bmp *.gif);;All files (*.*)",
        )
        if not path:
            return
        media_dir = self.media_edit.text().strip()
        # Store just the file name when it lives in the media folder, otherwise
        # keep the absolute path so the front-end can still find it.
        if media_dir and os.path.dirname(path) == os.path.normpath(media_dir):
            value = os.path.basename(path)
        else:
            value = path
        item = self.grid.item(row, COL_MEDIA)
        if item:
            item.setText(value)

    # ------------------------------------------------------- load / save
    def load_all(self) -> None:
        cfg = load_json(CONFIG_PATH, DEFAULT_CONFIG)
        self.vpx_edit.setText(str(cfg.get("vpx_exe_path", "")))
        self.table_edit.setText(str(cfg.get("table_folder_path", "")))
        self.media_edit.setText(str(cfg.get("media_folder_path", "")))
        rot = str(cfg.get("rotation_angle", 270))
        self.rotation_combo.setCurrentText(rot if rot in ("90", "270") else "270")
        self.font_spin.setValue(int(cfg.get("font_size", 42)))
        self.width_spin.setValue(int(cfg.get("window_width", 3840)))
        self.height_spin.setValue(int(cfg.get("window_height", 2160)))

        self.tables = load_json(TABLES_PATH, [])
        # Always present alphabetically by filename.
        self.tables.sort(key=lambda t: t.get("filename", "").lower())
        self.populate_grid()
        self.status.setText("Loaded config.json and tables.json.")

    def _collect_from_grid(self) -> list[dict]:
        rows: list[dict] = []
        for row in range(self.grid.rowCount()):
            visible = (
                self.grid.item(row, COL_VISIBLE).checkState() == Qt.CheckState.Checked
            )
            rows.append({
                "filename": self.grid.item(row, COL_FILENAME).text(),
                "display_name": self.grid.item(row, COL_DISPLAY).text(),
                "visible": visible,
                "media_file": self.grid.item(row, COL_MEDIA).text(),
            })
        rows.sort(key=lambda t: t["filename"].lower())
        return rows

    def save_all(self) -> None:
        config = {
            "vpx_exe_path": self.vpx_edit.text().strip(),
            "table_folder_path": self.table_edit.text().strip(),
            "media_folder_path": self.media_edit.text().strip(),
            "rotation_angle": int(self.rotation_combo.currentText()),
            "font_size": int(self.font_spin.value()),
            "window_width": int(self.width_spin.value()),
            "window_height": int(self.height_spin.value()),
            "vpx_launch_arg": "-Play",
            "exit_grace_ms": 500,
            "fullscreen": True,
        }
        self.tables = self._collect_from_grid()
        try:
            CONFIG_PATH.write_text(json.dumps(config, indent=2), encoding="utf-8")
            TABLES_PATH.write_text(json.dumps(self.tables, indent=2), encoding="utf-8")
        except OSError as exc:
            QMessageBox.critical(self, "Save failed", str(exc))
            return
        self.status.setText(
            f"Saved. {len(self.tables)} tables written to tables.json."
        )


def main() -> int:
    app = QApplication([])
    win = TableManager()
    win.show()
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
