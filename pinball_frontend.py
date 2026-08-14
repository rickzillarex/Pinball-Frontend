#!/usr/bin/env python3
"""
Visual Pinball Cabinet Front-End
================================

A lightweight, keyboard-driven launcher for a Visual Pinball X (VPX) cabinet.

The app is designed for a cabinet whose playfield monitor is a 4K panel
(3840x2160) that is physically mounted in PORTRAIT but reported to Windows as
LANDSCAPE.  The entire UI is therefore drawn into a landscape framebuffer and
rotated 90 or 270 degrees so that it reads upright to the player.

This app is READ ONLY.  All configuration and the curated table list are
managed by the companion `table_manager.py`.

    config.json  -> paths, rotation, font size, window size  (managed elsewhere)
    tables.json  -> curated list of tables                    (managed elsewhere)

Controls
--------
    UP / DOWN     move the selection
    RIGHT         launch the selected table in VPX
    LEFT          quit the front-end

Launch behaviour
----------------
On RIGHT the front-end minimizes itself, starts VPX with the selected table,
and waits (via QProcess.finished) for VPX to close.  A 500 ms grace period lets
Windows settle focus before the front-end restores and re-enables its keyboard
handling.  Because VPX takes exclusive fullscreen input while it runs, the
arrow keys used both in-game and in this front-end never collide.

See `VPX_LAUNCH_NOTES.txt` for the command-line research behind the launch
arguments.

Requires: PyQt6   (pip install -r requirements.txt)
"""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path

from PyQt6.QtCore import Qt, QProcess, QTimer
from PyQt6.QtGui import QPixmap
from PyQt6.QtWidgets import (
    QApplication,
    QFrame,
    QGraphicsScene,
    QGraphicsView,
    QHBoxLayout,
    QLabel,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

BASE_DIR = Path(__file__).resolve().parent
CONFIG_PATH = BASE_DIR / "config.json"
TABLES_PATH = BASE_DIR / "tables.json"

# Written on first run if the files are missing.  In normal use these files are
# created and maintained by table_manager.py.
DEFAULT_CONFIG = {
    "vpx_exe_path": r"C:\vPinball\Visual Pinball\VPinballX.exe",
    "table_folder_path": r"C:\vPinball\Visual Pinball\Tables",
    "media_folder_path": r"C:\vPinball\Visual Pinball\Media",
    "rotation_angle": 270,          # 90 or 270
    "font_size": 42,                # pixels, table-list text
    "window_width": 3840,           # physical framebuffer width
    "window_height": 2160,          # physical framebuffer height
    "vpx_launch_arg": "-Play",      # see VPX_LAUNCH_NOTES.txt ("/play" on old builds)
    "exit_grace_ms": 500,           # focus-settle delay after VPX closes
    "fullscreen": True,
}

DEFAULT_TABLES: list[dict] = []

ACCENT = "#22e0d6"   # selected-row accent


def load_json(path: Path, default):
    """Load JSON, writing `default` if the file does not exist / is invalid."""
    if not path.exists():
        path.write_text(json.dumps(default, indent=2), encoding="utf-8")
        return json.loads(json.dumps(default))
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        path.write_text(json.dumps(default, indent=2), encoding="utf-8")
        return json.loads(json.dumps(default))


class FrontEnd(QWidget):
    """The actual UI: a table list on the left, a preview image on the right.

    Drawn at the *logical* (portrait) size.  A RotatedView rotates this widget
    into the landscape framebuffer.
    """

    def __init__(self, config: dict, tables: list[dict]):
        super().__init__()
        self.config = config
        # Only visible tables reach the front-end.
        self.tables = [t for t in tables if t.get("visible", True)]
        self.index = 0
        self.process: QProcess | None = None
        self.row_labels: list[QLabel] = []

        self._build_ui()
        self.update_selection()

    # ------------------------------------------------------------------ UI
    def _build_ui(self) -> None:
        # Logical size is the physical size with width/height swapped, because
        # the view will rotate us by 90/270.
        logical_w = self.config["window_height"]
        logical_h = self.config["window_width"]
        self.setFixedSize(logical_w, logical_h)
        self.setStyleSheet("background-color:#000000;")

        font_size = int(self.config.get("font_size", 42))
        preview_w = logical_w // 3  # preview takes at most 1/3 of the width

        root = QHBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        # ---- Left: scrollable table list --------------------------------
        self.scroll = QScrollArea()
        self.scroll.setWidgetResizable(True)
        self.scroll.setFrameShape(QFrame.Shape.NoFrame)
        self.scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.scroll.setStyleSheet("background:#000; border:0;")

        list_host = QWidget()
        list_host.setStyleSheet("background:#000;")
        self.list_layout = QVBoxLayout(list_host)
        self.list_layout.setContentsMargins(80, 80, 40, 80)
        self.list_layout.setSpacing(int(font_size * 0.45))
        self.list_layout.setAlignment(Qt.AlignmentFlag.AlignTop)

        if not self.tables:
            empty = QLabel("No visible tables.\nUse the Table Manager to add some.")
            empty.setStyleSheet(f"color:#ffffff; font-size:{font_size}px;")
            self.list_layout.addWidget(empty)
        else:
            for i, table in enumerate(self.tables):
                lbl = QLabel(table.get("display_name") or table.get("filename", "?"))
                lbl.setFont(lbl.font())
                lbl.setStyleSheet(f"color:#ffffff; font-size:{font_size}px;")
                self.row_labels.append(lbl)
                self.list_layout.addWidget(lbl)

        self.scroll.setWidget(list_host)
        root.addWidget(self.scroll, stretch=2)

        # ---- Right: preview image ---------------------------------------
        right = QWidget()
        right.setFixedWidth(preview_w)
        right.setStyleSheet("background:#050505;")
        right_layout = QVBoxLayout(right)
        right_layout.setContentsMargins(30, 80, 60, 80)
        right_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)

        self.preview = QLabel("NO PREVIEW")
        self.preview.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.preview.setStyleSheet(
            "color:#444; font-size:28px; letter-spacing:3px;"
            "background:#0a0a0a; border:1px solid #1a1a1a;"
        )
        # Preview drawing area: portrait, scaled from the 3840x2160 view ratio.
        self.preview.setFixedSize(preview_w - 90, int((preview_w - 90) * 1.55))
        right_layout.addWidget(self.preview)

        root.addWidget(right, stretch=0)

    # ------------------------------------------------------------- helpers
    def update_selection(self) -> None:
        font_size = int(self.config.get("font_size", 42))
        for i, lbl in enumerate(self.row_labels):
            if i == self.index:
                lbl.setStyleSheet(
                    f"color:#000000; font-size:{font_size}px; font-weight:700;"
                    f"background:{ACCENT}; padding:6px 24px; border-radius:8px;"
                )
            else:
                lbl.setStyleSheet(
                    f"color:#ffffff; font-size:{font_size}px; padding:6px 24px;"
                )
        if self.row_labels:
            self.scroll.ensureWidgetVisible(self.row_labels[self.index], 0, 120)
            self.load_preview(self.tables[self.index])

    def load_preview(self, table: dict) -> None:
        media = table.get("media_file") or ""
        path = os.path.join(self.config.get("media_folder_path", ""), media)
        pix = QPixmap(path) if media and os.path.isfile(path) else QPixmap()
        if pix.isNull():
            self.preview.setPixmap(QPixmap())
            self.preview.setText("NO PREVIEW")
            return
        self.preview.setText("")
        self.preview.setPixmap(
            pix.scaled(
                self.preview.width(),
                self.preview.height(),
                Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.SmoothTransformation,
            )
        )

    # ----------------------------------------------------------- key input
    def handle_key(self, key: int) -> None:
        if not self.tables:
            if key == Qt.Key.Key_Left:
                QApplication.quit()
            return
        if key in (Qt.Key.Key_Up, Qt.Key.Key_W):
            self.index = (self.index - 1) % len(self.tables)
            self.update_selection()
        elif key in (Qt.Key.Key_Down, Qt.Key.Key_S):
            self.index = (self.index + 1) % len(self.tables)
            self.update_selection()
        elif key in (Qt.Key.Key_Right, Qt.Key.Key_Return, Qt.Key.Key_Enter):
            self.launch_selected()
        elif key in (Qt.Key.Key_Left, Qt.Key.Key_Escape):
            QApplication.quit()

    # -------------------------------------------------------------- launch
    def launch_selected(self) -> None:
        if self.process is not None:  # already running
            return
        table = self.tables[self.index]
        exe = self.config.get("vpx_exe_path", "")
        table_path = os.path.join(
            self.config.get("table_folder_path", ""), table.get("filename", "")
        )

        if not os.path.isfile(exe):
            self.preview.setText("VPX NOT FOUND\nCheck config.json")
            return
        if not os.path.isfile(table_path):
            self.preview.setText("TABLE FILE\nNOT FOUND")
            return

        arg = self.config.get("vpx_launch_arg", "-Play")
        self.process = QProcess(self)
        self.process.finished.connect(self._on_vpx_finished)
        # VpinballX.exe -Play "C:\...\Table.vpx"
        self.process.start(exe, [arg, table_path])

        # Step aside so VPX owns the screen and the keyboard.
        top = self.window()
        top.showMinimized()

    def _on_vpx_finished(self, *_args) -> None:
        self.process = None
        grace = int(self.config.get("exit_grace_ms", 500))
        QTimer.singleShot(grace, self._restore)

    def _restore(self) -> None:
        top = self.window()
        if self.config.get("fullscreen", True):
            top.showFullScreen()
        else:
            top.showNormal()
        top.raise_()
        top.activateWindow()
        top.setFocus()


class RotatedView(QGraphicsView):
    """Hosts the FrontEnd widget inside a scene and rotates it 90/270 degrees.

    Rotating a QGraphicsView is the most reliable way to rotate an entire live,
    interactive Qt widget tree (as opposed to painting to a rotated pixmap,
    which loses interactivity).
    """

    def __init__(self, frontend: FrontEnd, angle: int):
        super().__init__()
        self.frontend = frontend
        scene = QGraphicsScene(self)
        self.proxy = scene.addWidget(frontend)
        self.setScene(scene)
        self.setSceneRect(self.proxy.boundingRect())

        # 90  -> content turned clockwise (monitor rotated CCW to view upright)
        # 270 -> content turned counter-clockwise
        self.rotate(90 if angle == 90 else 270)

        self.setStyleSheet("background:#000; border:0;")
        self.setFrameShape(QFrame.Shape.NoFrame)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)

    def resizeEvent(self, event):
        # Keep the rotated content perfectly fitted to the framebuffer.
        self.fitInView(self.proxy, Qt.AspectRatioMode.KeepAspectRatio)
        super().resizeEvent(event)

    def keyPressEvent(self, event):
        self.frontend.handle_key(event.key())


def main() -> int:
    app = QApplication(sys.argv)
    app.setApplicationName("VPX Cabinet Front-End")

    config = load_json(CONFIG_PATH, DEFAULT_CONFIG)
    tables = load_json(TABLES_PATH, DEFAULT_TABLES)

    frontend = FrontEnd(config, tables)
    view = RotatedView(frontend, int(config.get("rotation_angle", 270)))
    view.setWindowTitle("VPX Cabinet Front-End")

    if config.get("fullscreen", True):
        view.showFullScreen()
    else:
        view.resize(int(config["window_width"]), int(config["window_height"]))
        view.show()

    view.setFocus()
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
