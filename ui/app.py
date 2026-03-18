# ui/app.py — PySide6, Dark Theme (Catppuccin Mocha)

import os
import sys
import platform
import random
import numpy as np

from PySide6.QtWidgets import (
    QApplication, QWidget, QMainWindow, QVBoxLayout, QHBoxLayout,
    QPushButton, QLabel, QProgressBar, QTextEdit, QGroupBox,
    QComboBox, QStatusBar, QFileDialog, QFrame, QDialog, QMessageBox,
    QSizePolicy
)
from PySide6.QtCore import Qt, QThreadPool
from PySide6.QtGui import QFont, QTextCursor, QPixmap, QImage
import pip

from stains import available_stains, get_stain
from ui.analysis_worker import Sox9Worker
from ui.batch_worker import BatchWorker
from ui.threshold_dialog import ThresholdDialog
from ui.roi_dialog import ROIDialog
from analysis.core_pipeline import find_images_in_folder
from analysis.batch_runner import find_sox9_folders

STYLESHEET = """
QWidget {
    font-family: 'Segoe UI', system-ui, sans-serif;
    font-size: 13px;
}
QMainWindow, QWidget {
    background-color: #1e1e2e;
    color: #cdd6f4;
}
QGroupBox {
    border: 1px solid #313244;
    border-radius: 8px;
    margin-top: 14px;
    padding: 10px 8px 8px 8px;
    font-weight: 600;
    color: #89b4fa;
    font-size: 12px;
}
QGroupBox::title {
    subcontrol-origin: margin;
    left: 10px;
    padding: 0 6px;
}
QPushButton {
    background-color: #313244;
    color: #cdd6f4;
    border: 1px solid #45475a;
    border-radius: 6px;
    padding: 7px 14px;
    text-align: left;
}
QPushButton:hover {
    background-color: #45475a;
    border-color: #89b4fa;
    color: #ffffff;
}
QPushButton:pressed { background-color: #585b70; }
QPushButton:disabled {
    background-color: #1e1e2e;
    color: #45475a;
    border-color: #313244;
}
QPushButton#primary {
    background-color: #89b4fa;
    color: #1e1e2e;
    font-weight: 700;
    font-size: 14px;
    border: none;
    text-align: center;
    border-radius: 8px;
}
QPushButton#primary:hover { background-color: #b4befe; }
QPushButton#primary:disabled {
    background-color: #313244;
    color: #585b70;
}
QPushButton#success {
    background-color: #a6e3a1;
    color: #1e1e2e;
    font-weight: 600;
    border: none;
    text-align: left;
}
QPushButton#success:hover { background-color: #94e2d5; }
QPushButton#warning {
    background-color: #fab387;
    color: #1e1e2e;
    font-weight: 600;
    border: none;
    text-align: left;
}
QPushButton#settings_btn {
    background-color: #181825;
    color: #6c7086;
    border: 1px solid #313244;
    border-radius: 6px;
    padding: 4px 8px;
    text-align: center;
    font-size: 15px;
}
QPushButton#settings_btn:hover {
    background-color: #313244;
    color: #cdd6f4;
    border-color: #89b4fa;
}
QComboBox {
    background-color: #313244;
    color: #cdd6f4;
    border: 1px solid #45475a;
    border-radius: 6px;
    padding: 6px 10px;
    min-height: 28px;
}
QComboBox:hover { border-color: #89b4fa; }
QComboBox::drop-down { border: none; width: 20px; }
QComboBox QAbstractItemView {
    background-color: #313244;
    color: #cdd6f4;
    border: 1px solid #45475a;
    selection-background-color: #45475a;
    outline: none;
}
QProgressBar {
    background-color: #313244;
    border: none;
    border-radius: 4px;
    max-height: 6px;
    text-align: center;
    color: transparent;
}
QProgressBar::chunk {
    background-color: #89b4fa;
    border-radius: 4px;
}
QProgressBar#tile_bar::chunk {
    background-color: #a6e3a1;
}
QTextEdit {
    background-color: #11111b;
    color: #cdd6f4;
    border: 1px solid #313244;
    border-radius: 6px;
    font-family: 'Cascadia Code', 'Consolas', 'Courier New', monospace;
    font-size: 12px;
    padding: 6px;
    selection-background-color: #45475a;
}
QStatusBar {
    background-color: #181825;
    color: #6c7086;
    font-size: 11px;
    border-top: 1px solid #313244;
    padding: 2px 8px;
}
QLabel#header {
    font-size: 20px;
    font-weight: 700;
    color: #cdd6f4;
    letter-spacing: 1px;
}
QLabel#subheader {
    font-size: 11px;
    color: #6c7086;
    letter-spacing: 2px;
}
QLabel#section {
    font-size: 11px;
    font-weight: 600;
    color: #6c7086;
    letter-spacing: 1px;
    text-transform: uppercase;
}
QLabel#info {
    color: #a6adc8;
    font-size: 12px;
}
QFrame#separator {
    background-color: #313244;
    max-height: 1px;
    border: none;
}
QFrame#sidebar {
    background-color: #181825;
    border-right: 1px solid #313244;
}
"""


def _style_titlebar(window: QMainWindow):
        """
        Färbt die native Titelleiste dunkel und setzt das App-Icon.
        Windows: Win32 DWMAPI (funktioniert ab Windows 11 22H2, teilweise Win10)
        macOS:   AppKit NSWindow
        """
        import platform

        # ── Icon (beide OS) ───────────────────────────────────────────────
        # Mikroskop-Emoji als SVG-Icon rendern – kein externes File nötig
        from PySide6.QtGui import QIcon, QPainter, QColor
        from PySide6.QtCore import QSize
        from PySide6.QtWidgets import QApplication
        from PySide6.QtSvg import QSvgRenderer
        import io

        # Einfaches SVG-Mikroskop-Icon in den App-Farben
        svg = b"""<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 64 64">
        <rect width="64" height="64" rx="12" fill="#1e1e2e"/>
        <circle cx="32" cy="20" r="10" fill="none" stroke="#89b4fa" stroke-width="3.5"/>
        <line x1="32" y1="30" x2="32" y2="44" stroke="#89b4fa" stroke-width="3.5" stroke-linecap="round"/>
        <line x1="20" y1="44" x2="44" y2="44" stroke="#89b4fa" stroke-width="3.5" stroke-linecap="round"/>
        <line x1="32" y1="10" x2="38" y2="4" stroke="#a6e3a1" stroke-width="2.5" stroke-linecap="round"/>
        <circle cx="32" cy="20" r="4" fill="#89b4fa" opacity="0.5"/>
        </svg>"""

        renderer = QSvgRenderer(svg)
        from PySide6.QtGui import QPixmap
        pixmap = QPixmap(64, 64)
        pixmap.fill(QColor(0, 0, 0, 0))
        painter = QPainter(pixmap)
        renderer.render(painter)
        painter.end()
        icon = QIcon(pixmap)
        window.setWindowIcon(icon)
        QApplication.instance().setWindowIcon(icon)

        # ── Titelleiste einfärben ─────────────────────────────────────────
        os_name = platform.system()

        if os_name == "Windows":
            try:
                import ctypes
                from ctypes import wintypes
                hwnd = int(window.winId())
                # DWMWA_CAPTION_COLOR = 35  (Windows 11 22H2+)
                # Farbe als 0x00BBGGRR
                color = ctypes.c_uint(0x00_2E_1E_1E)  # #1e1e2e in BGR
                ctypes.windll.dwmapi.DwmSetWindowAttribute(
                    hwnd, 35, ctypes.byref(color), ctypes.sizeof(color))
                # DWMWA_TEXT_COLOR = 36
                text_color = ctypes.c_uint(0x00_F4_D6_CD)  # #cdd6f4 in BGR
                ctypes.windll.dwmapi.DwmSetWindowAttribute(
                    hwnd, 36, ctypes.byref(text_color), ctypes.sizeof(text_color))
            except Exception as e:
                print(f"[Titlebar] Windows DWM fehlgeschlagen: {e}")

        elif os_name == "Darwin":
            try:
                from PySide6.QtCore import QTimer
                def _apply_macos():
                    try:
                        import objc
                        from AppKit import NSApplication, NSColor
                        ns_app  = NSApplication.sharedApplication()
                        ns_win  = ns_app.windows()[0]
                        # Titelleiste verstecken + unified look
                        ns_win.setTitlebarAppearsTransparent_(True)
                        ns_win.setBackgroundColor_(
                            NSColor.colorWithRed_green_blue_alpha_(
                                0x1e/255, 0x1e/255, 0x2e/255, 1.0))
                        # Dark appearance erzwingen
                        from AppKit import NSAppearance
                        dark = NSAppearance.appearanceNamed_("NSAppearanceNameDarkAqua")
                        ns_win.setAppearance_(dark)
                    except Exception as e:
                        print(f"[Titlebar] macOS AppKit fehlgeschlagen: {e}")
                # Kurz warten bis das Fenster wirklich da ist
                QTimer.singleShot(100, _apply_macos)
            except Exception as e:
                print(f"[Titlebar] macOS Setup fehlgeschlagen: {e}")

class _TerminalRedirector:
    """Leitet stdout/stderr in das Terminal-QTextEdit um."""
    def __init__(self, widget):
        self._widget = widget
        self._buffer = ""

    def write(self, text: str):
        if not text:
            return
        # Zeilenweise in Widget schreiben
        self._buffer += text
        while "\n" in self._buffer:
            line, self._buffer = self._buffer.split("\n", 1)
            if line:
                self._widget.append(
                    f'<span style="color:#a6e3a1;">{line}</span>')
        self._widget.ensureCursorVisible()

    def flush(self):
        if self._buffer:
            self._widget.append(
                f'<span style="color:#a6e3a1;">{self._buffer}</span>')
            self._buffer = ""

    def fileno(self):
        raise OSError("no fileno")

class HistologyUI(QMainWindow):
    def __init__(self):
        super().__init__()
        self.threadpool          = QThreadPool()
        self.confirmed_threshold = 60
        self.folder              = None
        self._use_roi            = False
        self._roi_points         = None
        self._batch_worker       = None
        self._last_marker_arr    = None   # Cache für resizeEvent
        self._last_dapi_arr      = None

        # Feature 1 – Pipeline-Parameter
        self._pipeline_params = {
            "positive_fraction": 0.10,
            "min_nucleus_area":  40,
            "max_nucleus_area":  3000,
        }

        self.setWindowTitle("Histo Analyzer")
        self.setMinimumSize(960, 820)

        self.status_bar = QStatusBar()
        self.setStatusBar(self.status_bar)
        self._set_status("Bereit", "idle")

        central = QWidget()
        self.setCentralWidget(central)
        root = QHBoxLayout(central)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        # ── Sidebar ───────────────────────────────────────────────────
        sidebar = QFrame()
        sidebar.setObjectName("sidebar")
        sidebar.setFixedWidth(270)
        sl = QVBoxLayout(sidebar)
        sl.setContentsMargins(16, 20, 16, 16)
        sl.setSpacing(4)

        lbl_logo = QLabel("🔬 HISTO"); lbl_logo.setObjectName("header")
        lbl_sub  = QLabel("ANALYZER  ·  v2.0"); lbl_sub.setObjectName("subheader")
        sl.addWidget(lbl_logo); sl.addWidget(lbl_sub)
        sl.addSpacing(16); sl.addWidget(self._separator())

        sl.addSpacing(12); sl.addWidget(self._section_label("Färbung"))
        self.stain_box = QComboBox()
        self.stain_box.addItems(available_stains())
        self.stain_box.currentTextChanged.connect(self._on_stain_changed)
        sl.addWidget(self.stain_box)

        sl.addSpacing(12); sl.addWidget(self._section_label("Ordner"))
        self.folder_label = QLabel("Kein Ordner gewählt")
        self.folder_label.setObjectName("info"); self.folder_label.setWordWrap(True)
        btn_folder = QPushButton("📁   Ordner wählen")
        btn_folder.clicked.connect(self._select_folder)
        sl.addWidget(btn_folder); sl.addWidget(self.folder_label)

        sl.addSpacing(12); sl.addWidget(self._section_label("Einstellungen"))

        self.btn_threshold = QPushButton("🔬   Threshold einstellen...")
        self.btn_threshold.clicked.connect(self._open_threshold_dialog)
        self.threshold_info = QLabel(f"Threshold: {self.confirmed_threshold}")
        self.threshold_info.setObjectName("info")

        self.btn_roi = QPushButton("📐   ROI einzeichnen...")
        self.btn_roi.clicked.connect(self._open_roi_dialog)

        self.btn_roi_mode = QPushButton("🔍   Modus: Ganzes Bild")
        self.btn_roi_mode.clicked.connect(self._toggle_roi_mode)

        self.btn_auto_roi = QPushButton("🤖   Auto-ROI vorschlagen")
        self.btn_auto_roi.clicked.connect(self._open_auto_roi)
        self.btn_auto_roi.setToolTip(
            "MobileSAM schlägt automatisch eine ROI vor\n"
            "basierend auf gespeicherten Referenzen")
        self._auto_roi_info = QLabel("0 Referenzen gespeichert")
        self._auto_roi_info.setObjectName("info")
        self._update_auto_roi_info()

        for w in [self.btn_threshold, self.threshold_info,
                  self.btn_roi, self.btn_roi_mode,
                  self.btn_auto_roi, self._auto_roi_info]:
            sl.addWidget(w)

        # ── Settings-Zahnrad (Feature 1) ──────────────────────────────
        sl.addSpacing(4)
        gear_row = QHBoxLayout()
        gear_row.setSpacing(6)
        self.btn_settings = QPushButton("⚙")
        self.btn_settings.setObjectName("settings_btn")
        self.btn_settings.setFixedSize(30, 26)
        self.btn_settings.setToolTip(
            "Erweiterte Pipeline-Parameter\n"
            "(positive_fraction, min/max Kerngröße …)")
        self.btn_settings.clicked.connect(self._open_settings_dialog)

        self._settings_info = QLabel("pos_frac=0.10  min=40px²")
        self._settings_info.setObjectName("info")
        self._settings_info.setStyleSheet("color:#585b70; font-size:11px;")
        self._settings_info.setWordWrap(True)
        gear_row.addWidget(self.btn_settings)
        gear_row.addWidget(self._settings_info)
        sl.addLayout(gear_row)
        # ──────Reset Knopf──────────────────────────────────────────────
        sl.addSpacing(8)
        sl.addWidget(self._separator())
        sl.addSpacing(4)
        sl.addWidget(self._section_label("Reset"))
        btn_reset = QPushButton("🗑   ROI & Referenzen löschen")
        btn_reset.setStyleSheet(
            "QPushButton { color: #f38ba8; border-color: #f38ba8; }")
        btn_reset.clicked.connect(self._reset_roi_and_references)
        sl.addWidget(btn_reset)

        # ──────────────────────────────────────────────────────────────

        sl.addStretch()
        sl.addWidget(self._separator()); sl.addSpacing(8)
        self.btn_analyze = QPushButton("▶   Analyse starten")
        self.btn_analyze.setObjectName("primary")
        self.btn_analyze.setMinimumHeight(44)
        self.btn_analyze.clicked.connect(self._start_analysis)
        sl.addWidget(self.btn_analyze)

        # ── Hauptbereich ──────────────────────────────────────────────
        main_area  = QWidget()
        main_layout = QVBoxLayout(main_area)
        main_layout.setContentsMargins(20, 20, 20, 16)
        main_layout.setSpacing(12)

       # ── Tab: Analyse-Log | Terminal ───────────────────────────────
        from PySide6.QtWidgets import QTabWidget
        self.log_tabs = QTabWidget()
        self.log_tabs.setStyleSheet("""
            QTabWidget::pane {
                border: 1px solid #313244;
                border-radius: 6px;
                background: #11111b;
            }
            QTabBar::tab {
                background: #1e1e2e;
                color: #6c7086;
                border: 1px solid #313244;
                border-bottom: none;
                padding: 5px 14px;
                border-radius: 4px 4px 0 0;
                font-size: 12px;
            }
            QTabBar::tab:selected {
                background: #313244;
                color: #cdd6f4;
                font-weight: 600;
            }
            QTabBar::tab:hover { color: #cdd6f4; }
        """)

        # Tab 1: Analyse-Log
        self.log_view = QTextEdit()
        self.log_view.setReadOnly(True)
        self.log_view.setPlaceholderText(
            "Der Analyse-Log erscheint hier...\n\n"
            "1. Ordner wählen\n2. Färbung auswählen\n"
            "3. Optional: Threshold und ROI einstellen\n4. Analyse starten")
        self.log_tabs.addTab(self.log_view, "📋  Analyse-Log")

        # Tab 2: Terminal (stdout/stderr)
        self.terminal_view = QTextEdit()
        self.terminal_view.setReadOnly(True)
        self.terminal_view.setPlaceholderText("Terminal-Output erscheint hier...")
        self.terminal_view.setStyleSheet(
            "QTextEdit { font-family: 'Cascadia Code', 'Consolas', monospace; "
            "font-size: 11px; color: #a6e3a1; background: #11111b; }")
        self.log_tabs.addTab(self.terminal_view, "🖥  Terminal")

        main_layout.addWidget(self.log_tabs, stretch=3)

       # ── Feature 3: Live-Vorschau (Marker | DAPI) ──────────────────
        preview_grp = QGroupBox("Aktuelles Bild")
        pv_layout   = QVBoxLayout(preview_grp)
        pv_layout.setContentsMargins(6, 6, 6, 6)
        pv_layout.setSpacing(4)

        img_row = QHBoxLayout()
        img_row.setSpacing(6)

        left_col = QVBoxLayout()
        self.preview_marker = QLabel("Marker")
        self.preview_marker.setAlignment(Qt.AlignCenter)
        self.preview_marker.setMinimumHeight(160)
        self.preview_marker.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.preview_marker.setStyleSheet(
            "background:#11111b; border:1px solid #313244; "
            "border-radius:6px; color:#45475a; font-size:11px;")
        self.preview_marker_name = QLabel("—")
        self.preview_marker_name.setAlignment(Qt.AlignCenter)
        self.preview_marker_name.setStyleSheet("color:#585b70; font-size:10px;")
        left_col.addWidget(self.preview_marker)
        left_col.addWidget(self.preview_marker_name)

        right_col = QVBoxLayout()
        self.preview_dapi = QLabel("DAPI")
        self.preview_dapi.setAlignment(Qt.AlignCenter)
        self.preview_dapi.setMinimumHeight(160)
        self.preview_dapi.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.preview_dapi.setStyleSheet(
            "background:#11111b; border:1px solid #313244; "
            "border-radius:6px; color:#45475a; font-size:11px;")
        self.preview_dapi_name = QLabel("—")
        self.preview_dapi_name.setAlignment(Qt.AlignCenter)
        self.preview_dapi_name.setStyleSheet("color:#585b70; font-size:10px;")
        right_col.addWidget(self.preview_dapi)
        right_col.addWidget(self.preview_dapi_name)

        img_row.addLayout(left_col)
        img_row.addLayout(right_col)
        pv_layout.addLayout(img_row)
        main_layout.addWidget(preview_grp, stretch=2)
        # ──────────────────────────────────────────────────────────────

        progress_grp = QGroupBox("Fortschritt")
        pg = QVBoxLayout(progress_grp); pg.setSpacing(6)
        self.label_global   = QLabel("Gesamt  0%"); self.label_global.setObjectName("info")
        self.progress_global = QProgressBar(); self.progress_global.setValue(0)
        self.label_current  = QLabel("Aktueller Schritt  0%"); self.label_current.setObjectName("info")
        self.progress_current = QProgressBar(); self.progress_current.setObjectName("tile_bar")
        self.progress_current.setValue(0)
        for w in [self.label_global, self.progress_global,
                  self.label_current, self.progress_current]:
            pg.addWidget(w)
        main_layout.addWidget(progress_grp)

        root.addWidget(sidebar)
        root.addWidget(main_area, stretch=1)
        self._on_stain_changed(self.stain_box.currentText())
        import sys
        self._stdout_redirector = _TerminalRedirector(self.terminal_view)
        sys.stdout = self._stdout_redirector
        sys.stderr = self._stdout_redirector

    # ── Helpers ───────────────────────────────────────────────────────
    def _separator(self):
        f = QFrame(); f.setObjectName("separator"); f.setFrameShape(QFrame.HLine)
        return f

    def _section_label(self, text):
        lbl = QLabel(text.upper()); lbl.setObjectName("section"); return lbl

    def _set_status(self, msg, state="idle"):
        c = {"idle":"#6c7086","running":"#89b4fa","ok":"#a6e3a1","error":"#f38ba8"}.get(state,"#6c7086")
        self.status_bar.setStyleSheet(
            "QStatusBar {"
            f"background:#181825;color:{c};"
            "font-size:11px;border-top:1px solid #313244;padding:2px 8px;}")
        self.status_bar.showMessage(msg)

    def _log(self, msg, color=None):
        if "✔" in msg or "Fertig" in msg: color = "#a6e3a1"
        elif "✗" in msg or "Fehler" in msg or "Error" in msg: color = "#f38ba8"
        elif "⚠" in msg or "Warnung" in msg: color = "#fab387"
        elif msg.startswith("──"): color = "#89b4fa"
        if color:
            self.log_view.append(f'<span style="color:{color};">{msg}</span>')
        else:
            self.log_view.append(msg)
        self.log_view.ensureCursorVisible()

    def _reset_roi_and_references(self):
        reply = QMessageBox.question(
            self, "Reset bestätigen",
            "Folgendes wird gelöscht:\n"
            "• Alle gespeicherten ROI-JSON Dateien im aktuellen Ordner\n"
            "• Alle gespeicherten Lern-Referenzen (AppData)\n\n"
            "Fortfahren?",
            QMessageBox.Yes | QMessageBox.No
        )
        if reply != QMessageBox.Yes:
            return

        deleted = 0

        # ROI-JSONs im aktuellen Ordner löschen
        if self.folder:
            import glob
            for json_file in glob.glob(
                    os.path.join(self.folder, "**", "*_roi.json"),
                    recursive=True):
                try:
                    os.remove(json_file)
                    deleted += 1
                except Exception:
                    pass

        # Alle Lern-Referenzen löschen
        from analysis.roi_learner import clear_all_references
        clear_all_references()

        # UI zurücksetzen
        self._roi_points = None
        self._use_roi    = False
        self.btn_roi.setText("📐   ROI einzeichnen...")
        self.btn_roi.setObjectName("")
        self.btn_roi.style().unpolish(self.btn_roi)
        self.btn_roi.style().polish(self.btn_roi)
        self.btn_roi_mode.setText("🔍   Modus: Ganzes Bild")
        self.btn_roi_mode.setObjectName("")
        self.btn_roi_mode.style().unpolish(self.btn_roi_mode)
        self.btn_roi_mode.style().polish(self.btn_roi_mode)
        self._update_auto_roi_info()

        self._log(f"✔ Reset: {deleted} ROI-JSON(s) gelöscht + alle Referenzen zurückgesetzt")

    # ── Feature 3: Bildvorschau ───────────────────────────────────────
    def resizeEvent(self, event):
        super().resizeEvent(event)
        if self._last_marker_arr is not None:
            self._render_label(self.preview_marker, self._last_marker_arr)
        if self._last_dapi_arr is not None:
            self._render_label(self.preview_dapi, self._last_dapi_arr)

    def _arr_to_pixmap(self, arr_uint8_rgb, label) -> QPixmap:
        h, w, _ = arr_uint8_rgb.shape
        qimg = QImage(arr_uint8_rgb.tobytes(), w, h, w * 3, QImage.Format_RGB888)
        return QPixmap.fromImage(qimg)
    
    def _show_preview(self, marker_path: str, dapi_path: str = None):
        if not marker_path or not os.path.exists(marker_path):
            return
        try:
            from PIL import Image as PilImage
            threshold = self.confirmed_threshold
            raw = np.array(PilImage.open(marker_path)).astype(np.float32)
            ch  = raw[..., 0] if raw.ndim == 3 else raw
            vmin, vmax = ch.min(), ch.max()
            norm = np.clip((ch - vmin) / max(vmax - vmin, 1) * 255, 0, 255).astype(np.uint8)
            rgb = np.stack([norm, norm, norm], axis=-1)
            above = norm >= threshold
            rgb[above]  = [255, 60, 60]
            rgb[~above] = np.stack([norm[~above]//2,
                                     norm[~above]//2,
                                     norm[~above]//2], axis=-1)
            self._last_marker_arr = rgb
            self._render_label(self.preview_marker, rgb)
            self.preview_marker_name.setText(os.path.basename(marker_path))
        except Exception as e:
            self.preview_marker.setText(f"n.v.\n{e}")

        if dapi_path and os.path.exists(dapi_path):
            self._show_dapi_preview(dapi_path)

    def _show_dapi_preview(self, dapi_path: str):
        if not dapi_path or not os.path.exists(dapi_path):
            return
        try:
            from PIL import Image as PilImage
            raw  = np.array(PilImage.open(dapi_path)).astype(np.float32)
            ch   = raw[..., 2] if raw.ndim == 3 else raw
            vmin, vmax = ch.min(), ch.max()
            norm = np.clip((ch - vmin) / max(vmax - vmin, 1) * 255, 0, 255).astype(np.uint8)
            rgb  = np.zeros((*norm.shape, 3), dtype=np.uint8)
            rgb[..., 0] = norm // 4
            rgb[..., 1] = norm // 3
            rgb[..., 2] = norm
            self._last_dapi_arr = rgb
            self._render_label(self.preview_dapi, rgb)
            self.preview_dapi_name.setText(os.path.basename(dapi_path))
        except Exception as e:
            self.preview_dapi.setText(f"n.v.\n{e}")

    def _show_overlay_preview(self, overlay_path: str):
        if not overlay_path or not os.path.exists(overlay_path):
            return
        try:
            from PIL import Image as PilImage
            img = np.array(PilImage.open(overlay_path))
            d   = img[..., :3].astype(np.uint8) if img.ndim == 3 else \
                  np.stack([img.astype(np.uint8)]*3, axis=-1)
            self._last_marker_arr = d
            self._render_label(self.preview_marker, d)
            self.preview_marker_name.setText(
                f"Overlay: {os.path.basename(overlay_path)}")
        except Exception as e:
            self.preview_marker.setText(f"n.v.\n{e}")

    def _render_label(self, label, arr: np.ndarray):
        """Skaliert arr auf die aktuelle Label-Größe und setzt Pixmap."""
        h, w, _ = arr.shape
        qimg = QImage(arr.tobytes(), w, h, w * 3, QImage.Format_RGB888)
        px   = QPixmap.fromImage(qimg)
        lw   = label.width()  if label.width()  > 10 else label.minimumWidth()
        lh   = label.height() if label.height() > 10 else label.minimumHeight()
        label.setPixmap(px.scaled(lw, lh, Qt.KeepAspectRatioByExpanding,
                                  Qt.SmoothTransformation))

    def _show_overlay_preview(self, overlay_path: str):
        if not overlay_path or not os.path.exists(overlay_path):
            return
        try:
            from PIL import Image as PilImage
            img = np.array(PilImage.open(overlay_path))
            d   = img[..., :3].astype(np.uint8) if img.ndim == 3 else \
                  np.stack([img.astype(np.uint8)]*3, axis=-1)
            self.preview_marker.setPixmap(
                self._arr_to_pixmap(d, self.preview_marker))
            self.preview_marker_name.setText(
                f"Overlay: {os.path.basename(overlay_path)}")
        except Exception as e:
            self.preview_marker.setText(f"n.v.\n{e}")

    # ── Ordner ────────────────────────────────────────────────────────
    def _select_folder(self):
        path = QFileDialog.getExistingDirectory(self, "Ordner wählen")
        if path:
            self.folder = path
            short = os.path.basename(path)
            self.folder_label.setText(f"📂 {short}")
            self.folder_label.setToolTip(path)
            self._set_status(f"Ordner: {short}", "idle")

    # ── Stain-UI ──────────────────────────────────────────────────────
    def _on_stain_changed(self, name: str):
        stain   = get_stain(name)
        visible = bool(stain.implemented)
        for w in [self.btn_threshold, self.threshold_info,
                  self.btn_roi, self.btn_roi_mode,
                  self.btn_settings, self._settings_info]:
            w.setVisible(visible)
        if visible:
            self.btn_threshold.setText(f"🔬   Threshold ({name.split('/')[0]})...")

    # ── Feature 1: Settings ───────────────────────────────────────────
    def _open_settings_dialog(self):
        from ui.settings_dialog import SettingsDialog
        dlg = SettingsDialog(self._pipeline_params, parent=self)
        if dlg.exec() == QDialog.Accepted:
            self._pipeline_params = dlg.get_params()
            pf  = self._pipeline_params["positive_fraction"]
            mna = self._pipeline_params["min_nucleus_area"]
            self._settings_info.setText(f"pos_frac={pf}  min={mna}px²")
            self._log(
                f"Einstellungen: positive_fraction={pf}, "
                f"min_nucleus_area={mna}, "
                f"max_nucleus_area={self._pipeline_params['max_nucleus_area']}")

    # ── Feature 2: erster passender Stain-Ordner ─────────────────────
    def _get_first_stain_folder(self) -> str:
        if not self.folder:
            return ""
        keyword = self.stain_box.currentText().split("/")[0]
        try:
            from analysis.core_pipeline import find_stain_folders
            probe_folders, _ = find_stain_folders(self.folder, keyword)
            if probe_folders:
                return probe_folders[0]
        except Exception:
            pass
        return self.folder

    # ── Threshold ─────────────────────────────────────────────────────
    def _open_threshold_dialog(self):
        if not self.folder:
            QMessageBox.warning(self, "Fehler", "Bitte zuerst Ordner wählen.")
            return
        stain_name = self.stain_box.currentText()
        stain      = get_stain(stain_name)
        folder_for_dialog = self._get_first_stain_folder()   # Feature 2
        dlg = stain.get_threshold_dialog(folder_for_dialog, parent=self)
        if dlg is None:
            QMessageBox.information(self, "Info",
                f"{stain_name} benötigt keinen manuellen Threshold.")
            return
        if dlg.exec() == QDialog.Accepted:
            self.confirmed_threshold = dlg.confirmed_threshold
            self.threshold_info.setText(f"Threshold: {self.confirmed_threshold}")
            self._log(f"Threshold gesetzt: {self.confirmed_threshold}")

    # ── ROI ───────────────────────────────────────────────────────────
    def _open_roi_dialog(self):
        if not self.folder:
            QMessageBox.warning(self, "Fehler", "Bitte zuerst Ordner wählen.")
            return

        stain_name     = self.stain_box.currentText()
        stain          = get_stain(stain_name)
        is_brightfield = (stain_name == "Von Kossa")

        # Alle passenden Ordner sammeln
        from analysis.core_pipeline import find_stain_folders
        keyword = stain_name.split("/")[0]
        probe_folders, _ = find_stain_folders(self.folder, keyword)

        if not probe_folders:
            # Kein Unterordner — aktuellen Ordner direkt verwenden
            probe_folders = [self.folder]

       # Bild-Pfade für alle Ordner ermitteln
        img_paths = []
        for f in probe_folders:
            try:
                if is_brightfield:
                    from analysis.brightfield_pipeline import find_brightfield_image
                    p = find_brightfield_image(f)
                else:
                    try:
                        _, p = find_images_in_folder(f)
                    except ValueError:
                        # Kein separater DAPI — erstes Bild nehmen
                        from analysis.brightfield_pipeline import find_brightfield_image
                        p = find_brightfield_image(f)
                img_paths.append(p)
            except Exception:
                pass

        if not img_paths:
            QMessageBox.warning(self, "Fehler", "Keine Bilder gefunden.")
            return

        dlg = stain.get_roi_dialog(img_paths[0], parent=self)
        if dlg is None:
            QMessageBox.information(self, "Info",
                f"{stain_name} benötigt keine ROI.")
            return

        # Alle Pfade übergeben damit der Dialog durchblättern kann
        dlg.set_image_list(img_paths)
        dlg.roi_confirmed.connect(self._on_roi_confirmed)
        self._show_preview(img_paths[0], img_paths[0])
        dlg.exec()

    def _update_auto_roi_info(self):
        from analysis.roi_learner import get_reference_count
        from analysis.roi_predictor import is_model_available
        n = get_reference_count()
        if is_model_available():
            self._auto_roi_info.setText(f"{n} Referenzen  ✔ Modell trainiert")
            self._auto_roi_info.setStyleSheet("color:#a6e3a1; font-size:11px;")
        else:
            hint = " — zu wenig" if n < 20 else " — bereit zum Training"
            self._auto_roi_info.setText(f"{n} Referenzen{hint}")
            self._auto_roi_info.setStyleSheet("color:#585b70; font-size:11px;")

    def _open_auto_roi(self):
        from analysis.roi_predictor import is_model_available, ROIPredictor
        from analysis.roi_learner import get_reference_count

        if not self.folder:
            QMessageBox.warning(self, "Fehler", "Bitte zuerst Ordner wählen.")
            return

        # Modell trainiert?
        if not is_model_available():
            n = get_reference_count()
            QMessageBox.information(
                self, "Modell nicht trainiert",
                f"Das ROI-Modell wurde noch nicht trainiert.\n\n"
                f"Gespeicherte Referenzen: {n}\n\n"
                f"Bitte ausführen:\n"
                f"  python train_roi_model.py\n\n"
                f"Empfehlung: mindestens 20 Referenzen vor dem Training."
            )
            return

        # Bild laden
        stain_name     = self.stain_box.currentText()
        is_brightfield = (stain_name == "Von Kossa")

        from analysis.core_pipeline import find_stain_folders
        keyword = stain_name.split("/")[0]
        probe_folders, _ = find_stain_folders(self.folder, keyword)
        search_folder = probe_folders[0] if probe_folders else self.folder

        try:
            if is_brightfield:
                from analysis.brightfield_pipeline import (
                    find_brightfield_image, load_as_uint8_rgb)
                img_path = find_brightfield_image(search_folder)
                rgb = load_as_uint8_rgb(img_path)
            else:
                from analysis.core_pipeline import find_images_in_folder
                from PIL import Image as PilImage
                try:
                    marker_path, _ = find_images_in_folder(search_folder)
                    img_path = marker_path
                except ValueError:
                    from analysis.brightfield_pipeline import find_brightfield_image
                    img_path = find_brightfield_image(search_folder)
                raw = np.array(PilImage.open(img_path))
                if raw.ndim == 2:
                    rgb = np.stack([raw, raw, raw], axis=-1)
                else:
                    rgb = raw[..., :3]
                rgb = (rgb / max(rgb.max(), 1) * 255).astype(np.uint8)
        except Exception as e:
            QMessageBox.warning(self, "Fehler", f"Bild nicht gefunden:\n{e}")
            return

        if not hasattr(self, "_roi_predictor"):
            self._roi_predictor = ROIPredictor()
        if not self._roi_predictor.load():
            QMessageBox.warning(
                    self, "Fehler",
                    "Modell konnte nicht geladen werden.\n"
                    "Bitte 'pip install ultralytics' ausführen."
            )
            return

        # Vorhersage
        self._log("  Auto-ROI: Knorpel wird erkannt...")
        result = self._roi_predictor.predict(rgb)

        if result is None:
            QMessageBox.warning(
                self, "Keine ROI erkannt",
                "Das Modell konnte keinen Knorpel erkennen.\n\n"
                "Mögliche Ursachen:\n"
                "• Zu wenig Trainingsdaten\n"
                "• Bild sehr unterschiedlich von Trainingsdaten\n\n"
                "Bitte ROI manuell einzeichnen."
            )
            return

        # Vorschlag anzeigen
        from ui.roi_suggestion_dialog import ROISuggestionDialog
        # estimate-Dict für den Dialog simulieren
        estimate = {
            "confidence": result["confidence"],
            "n_refs":     get_reference_count(),
            "prompt_points": [],
        }
        # ROISuggestionDialog direkt mit Ergebnis befüllen
        dlg = ROISuggestionDialog(
            image_path=img_path,
            rgb=rgb,
            estimate=estimate,
            segmenter=None,
            stain_name=stain_name,
            parent=self,
        )
        # Ergebnis direkt setzen ohne SAM laufen zu lassen
        dlg._result  = result
        dlg._polygon = result["polygon_normalized"]
        dlg._on_sam_done(result)

        dlg.roi_confirmed.connect(self._on_auto_roi_confirmed)
        dlg.roi_skipped.connect(lambda: self._log("  Auto-ROI übersprungen"))
        dlg.exec()
        self._update_auto_roi_info()

    def _on_auto_roi_confirmed(self, points: list):
        self._roi_points = points
        self._use_roi    = True
        self.btn_roi.setText(f"📐   ROI ✓  ({len(points)} Punkte, Auto)")
        self.btn_roi.setObjectName("success")
        self.btn_roi.style().unpolish(self.btn_roi)
        self.btn_roi.style().polish(self.btn_roi)
        self.btn_roi_mode.setText("✂️   Modus: Mit ROI")
        self.btn_roi_mode.setObjectName("success")
        self.btn_roi_mode.style().unpolish(self.btn_roi_mode)
        self.btn_roi_mode.style().polish(self.btn_roi_mode)
        self._log(f"✔ Auto-ROI übernommen  ({len(points)} Punkte)")
        self._update_auto_roi_info()


    def _on_roi_confirmed(self, points):
        self._roi_points = points
        self.btn_roi.setText(f"📐   ROI ✓  ({len(points)} Punkte)")
        self.btn_roi.setObjectName("success")
        self.btn_roi.style().unpolish(self.btn_roi)
        self.btn_roi.style().polish(self.btn_roi)
        self._log(f"ROI gesetzt: {len(points)} Punkte")

    def _toggle_roi_mode(self):
        self._use_roi = not self._use_roi
        if self._use_roi:
            self.btn_roi_mode.setText("✂️   Modus: Mit ROI")
            self.btn_roi_mode.setObjectName("success")
        else:
            self.btn_roi_mode.setText("🔍   Modus: Ganzes Bild")
            self.btn_roi_mode.setObjectName("")
        self.btn_roi_mode.style().unpolish(self.btn_roi_mode)
        self.btn_roi_mode.style().polish(self.btn_roi_mode)

    def _find_dapi_path_in(self, folder: str):
        try:
            _, dapi_path = find_images_in_folder(folder)
            return dapi_path
        except Exception:
            pass
        QMessageBox.warning(self, "Fehler", "Kein DAPI-Bild gefunden.")
        return None

    def _find_dapi_path(self):
        if not self.folder:
            QMessageBox.warning(self, "Fehler", "Bitte zuerst Ordner wählen.")
            return None
        try:
            _, dapi_path = find_images_in_folder(self.folder)
            return dapi_path
        except Exception:
            folders = find_sox9_folders(self.folder)
            if folders:
                try:
                    _, dapi_path = find_images_in_folder(folders[0])
                    return dapi_path
                except Exception:
                    pass
        QMessageBox.warning(self, "Fehler", "Kein DAPI-Bild gefunden.")
        return None
    # ─ Update-Check ─────────────────────────────────────────────────
    def _start_update_check(self):
        try:
            from ui.updater import UpdateChecker
            from version import VERSION, UPDATE_REPO, UPDATE_BRANCH
            self._updater = UpdateChecker(VERSION, UPDATE_REPO, UPDATE_BRANCH)
            self._updater.update_available.connect(self._on_update_found)
            self._updater.error.connect(lambda e: print(f"[Update] {e}"))
            self._updater.check_async()
        except Exception:
            pass

    def _on_update_found(self, new_version: str, changelog: str, files: list):
        self._update_data = (new_version, changelog, files)
        self.btn_update.setText(f"⬆  v{new_version} verfügbar!")
        self.btn_update.setVisible(True)

    def _on_update_clicked(self):
        from ui.update_dialog import UpdateDialog
        from version import UPDATE_REPO, UPDATE_BRANCH
        import os, sys

        executable = os.path.abspath(sys.argv[0])
        if '.app/Contents' in executable:
            app_root = os.path.dirname(
                os.path.dirname(
                    os.path.dirname(
                        os.path.dirname(executable))))
        else:
            app_root = os.path.dirname(os.path.abspath(executable))

        new_version, changelog, files = self._update_data
        dlg = UpdateDialog(
            new_version=new_version,
            changelog=changelog,
            files=files,
            update_repo=UPDATE_REPO,
            app_root=app_root,
            parent=self,
        )
        dlg.exec()
    # ── Analyse ───────────────────────────────────────────────────────
    def _start_analysis(self):
        if not self.folder:
            QMessageBox.warning(self, "Fehler", "Bitte Ordner wählen.")
            return
        stain_name = self.stain_box.currentText()
        stain      = get_stain(stain_name)
        if not stain.implemented:
            QMessageBox.information(self, "In Entwicklung",
                f"'{stain_name}' ist noch nicht implementiert.")
            return
        self.run_stain_analysis(stain_name)

    def run_stain_analysis(self, stain_name: str):
        from analysis.core_pipeline import find_stain_folders
        keyword = stain_name.split("/")[0]
        probe_folders, _ = find_stain_folders(self.folder, keyword)
        if not probe_folders:
            self._run_single(stain_name)
            return
        reply = QMessageBox.question(
            self, "Batch-Analyse",
            f"{len(probe_folders)} {keyword}-Unterordner gefunden.\nAlle analysieren?",
            QMessageBox.Yes | QMessageBox.No)
        if reply == QMessageBox.Yes:
            self._start_batch(stain_name)

    def _run_single(self, stain_name: str):
        from analysis.core_pipeline import find_images_in_folder
        from stains import get_stain
        self.log_view.clear()
        self._set_status("Analyse läuft...", "running")
        self.btn_analyze.setEnabled(False)

        stain = get_stain(stain_name)
        is_brightfield = (stain_name == "Von Kossa")

        try:
            if is_brightfield:
                from analysis.brightfield_pipeline import find_brightfield_image
                marker_path = find_brightfield_image(self.folder)
                dapi_path   = marker_path   # Dummy – wird in VonKossaStain ignoriert
            else:
                marker_path, dapi_path = find_images_in_folder(self.folder)
        except ValueError as e:
            QMessageBox.warning(self, "Fehler", str(e))
            self.btn_analyze.setEnabled(True)
            return

        self._show_preview(marker_path, dapi_path)                       # Feature 3
        roi_mask = None
        roi_ref  = marker_path if is_brightfield else dapi_path
        if self._use_roi:
            from ui.roi_dialog import ROIDialog
            from PIL import Image
            arr      = np.array(Image.open(roi_ref))
            roi_mask = ROIDialog.load_roi_mask(roi_ref, arr.shape[0], arr.shape[1])
        from ui.single_worker import SingleWorker
        worker = SingleWorker(
            stain=stain, marker_path=marker_path, dapi_path=dapi_path,
            output_folder=self.folder, roi_mask=roi_mask,
            threshold=self.confirmed_threshold,
            pipeline_params=self._pipeline_params,            # Feature 1
        )
        worker.signals.finished.connect(self._on_single_finished)
        worker.signals.log.connect(self._log)
        worker.signals.overlay.connect(self._show_overlay_preview)   # Feature 3
        worker.signals.error.connect(lambda e: self._set_status(f"✗ {e}", "error"))
        self.threadpool.start(worker)

    def _start_batch(self, stain_name: str):
        keyword = stain_name.split("/")[0]
        self.log_view.clear()
        self.progress_global.setValue(0)
        self.progress_current.setValue(0)
        self.btn_analyze.setEnabled(False)
        self._set_status(f"Batch: {keyword}...", "running")
        self._batch_worker = BatchWorker(
            root_folder=self.folder, stain_name=keyword,
            threshold=self.confirmed_threshold, use_roi=self._use_roi,
            pipeline_params=self._pipeline_params,            # Feature 1
        )
        self._batch_worker.signals.progress.connect(self._on_global_progress)
        self._batch_worker.signals.progress_tile.connect(self._on_tile_progress)
        self._batch_worker.signals.log.connect(self._log)
        self._batch_worker.signals.folder_done.connect(self._on_folder_done)
        self._batch_worker.signals.folder_error.connect(self._on_folder_error)
        self._batch_worker.signals.finished.connect(self._on_batch_finished)
        self._batch_worker.signals.preview.connect(self._show_preview)          # Feature 3
        self._batch_worker.signals.overlay.connect(self._show_overlay_preview)  # Feature 3
        self.threadpool.start(self._batch_worker)

    # ── Callbacks ─────────────────────────────────────────────────────
    def _on_global_progress(self, val):
        self.progress_global.setValue(val)
        self.label_global.setText(f"Gesamt  {val}%")

    def _on_tile_progress(self, val):
        self.progress_current.setValue(val)
        self.label_current.setText(f"Aktueller Schritt  {val}%")

    def _on_single_finished(self, text):
        self.btn_analyze.setEnabled(True)
        self.progress_global.setValue(100)
        self._set_status("✔ Analyse abgeschlossen", "ok")
        self._log(f"✔ {text}")

    def _on_folder_done(self, name, result):
        self.progress_current.setValue(100)
        self._set_status(f"✔ {name}", "running")
        if result.get("overlay"):                             # Feature 3
            self._show_overlay_preview(result["overlay"])

    def _on_folder_error(self, name, error):
        self._log(f"✗ {name}: {error}")
        self._set_status(f"✗ Fehler: {name}", "error")

    def _on_batch_finished(self, csv_path, plot_path):
        self.btn_analyze.setEnabled(True)
        self.progress_global.setValue(100)
        self._set_status("✔ Batch abgeschlossen", "ok")
        self._log("── Batch-Analyse abgeschlossen ──")
        if csv_path:  self._log(f"✔ CSV:  {csv_path}")
        if plot_path: self._log(f"✔ Plot: {plot_path}")
        QMessageBox.information(self, "Fertig",
            f"Batch-Analyse abgeschlossen!\n\nErgebnisse in:\n{self.folder}/Results/")
        



def run_ui():
    app = QApplication(sys.argv)
    app.setStyleSheet(STYLESHEET)
    ui = HistologyUI()
    _style_titlebar(ui)
    ui.show()
    sys.exit(app.exec())
