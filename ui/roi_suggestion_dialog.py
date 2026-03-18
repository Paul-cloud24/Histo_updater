# ui/roi_suggestion_dialog.py
"""
Dialog der einen automatischen ROI-Vorschlag (via MobileSAM) anzeigt.

Workflow:
  1. System schaetzt Knorpelposition aus gespeicherten Referenzen
  2. MobileSAM segmentiert den Knorpel
  3. Nutzer sieht gruenes Polygon als Vorschlag
  4. Optionen: Bestaetigen / Neu zeichnen / Ueberspringen
"""

import os
import numpy as np
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QPushButton,
    QLabel, QProgressBar, QGroupBox, QSizePolicy, QMessageBox
)
from PySide6.QtCore import Qt, Signal, QThread, QObject
from PySide6.QtGui import QImage, QPixmap, QPainter, QPen, QColor, QPolygonF, QFont
from PySide6.QtCore import QPointF


# ══════════════════════════════════════════════════════════════════════
# Hintergrund-Worker fuer SAM (damit UI nicht einfriert)
# ══════════════════════════════════════════════════════════════════════

class SamWorkerSignals(QObject):
    finished = Signal(dict)   # Ergebnis-Dict oder {}
    progress = Signal(str)    # Status-Text
    error    = Signal(str)


class SamWorker(QThread):
    """Fuehrt SAM-Segmentierung im Hintergrund aus."""

    def __init__(self, rgb: np.ndarray, estimate: dict, segmenter):
        super().__init__()
        self.rgb       = rgb
        self.estimate  = estimate
        self.segmenter = segmenter
        self.signals   = SamWorkerSignals()

    def run(self):
        try:
            self.signals.progress.emit("Bild vorbereiten...")
            from analysis.sam_segmenter import run_sam_suggestion
            result = run_sam_suggestion(self.rgb, self.estimate, self.segmenter)
            self.signals.finished.emit(result or {})
        except Exception as e:
            self.signals.error.emit(str(e))
            self.signals.finished.emit({})


# ══════════════════════════════════════════════════════════════════════
# Haupt-Dialog
# ══════════════════════════════════════════════════════════════════════

class ROISuggestionDialog(QDialog):
    """
    Zeigt einen automatischen ROI-Vorschlag und laesst den Nutzer
    bestaetigen, neu zeichnen oder ueberspringen.

    Signals:
        roi_confirmed(list):  normalisierte Polygon-Punkte bestaetigt
        roi_skipped():        Nutzer hat uebersprungen
    """

    roi_confirmed = Signal(list)
    roi_skipped   = Signal()

    def __init__(self, image_path: str, rgb: np.ndarray,
                 estimate: dict, segmenter,
                 stain_name: str = "unbekannt",
                 parent=None):
        super().__init__(parent)
        self.image_path  = image_path
        self.rgb         = rgb
        self.estimate    = estimate
        self.segmenter   = segmenter
        self.stain_name  = stain_name
        self._result     = None   # SAM-Ergebnis
        self._polygon    = []     # aktuelles Polygon (normalisiert)

        self.setWindowTitle("ROI-Vorschlag — Knorpel-Erkennung")
        self.setMinimumSize(900, 680)
        self.setModal(True)

        self._build_ui()
         # SAM nur starten wenn ein Segmenter übergeben wurde
        if segmenter is not None:
            self._start_sam()
        else:
            # YOLO-Modus: Status direkt setzen
            self.status_label.setText("Warte auf YOLO-Vorhersage...")
            self.progress_bar.setRange(0, 0)

    # ── UI ────────────────────────────────────────────────────────────

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(8)

        # Header
        n_refs = self.estimate.get("n_refs", 0)
        conf   = self.estimate.get("confidence", 0.0)
        hdr = QLabel(
            f"Automatischer ROI-Vorschlag  —  "
            f"{n_refs} Referenzen  |  Konfidenz: {conf*100:.0f}%  |  "
            f"Färbung: {self.stain_name}"
        )
        hdr.setStyleSheet("color:#89b4fa; font-weight:600; font-size:12px;")
        layout.addWidget(hdr)

        # Vorschau
        preview_grp = QGroupBox("Vorschlag  (🟢 = erkannter Knorpel)")
        pv_layout   = QVBoxLayout(preview_grp)
        self.preview_label = QLabel("SAM segmentiert...")
        self.preview_label.setAlignment(Qt.AlignCenter)
        self.preview_label.setMinimumHeight(420)
        self.preview_label.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.preview_label.setStyleSheet(
            "background:#11111b; border:1px solid #313244; "
            "border-radius:6px; color:#585b70; font-size:13px;")
        pv_layout.addWidget(self.preview_label)
        layout.addWidget(preview_grp, stretch=1)
        
        # ── Helligkeit / Kontrast ──────────────────────────────────────
        from PySide6.QtWidgets import QSlider
        ctrl_row = QHBoxLayout()
        ctrl_row.setSpacing(8)

        ctrl_row.addWidget(QLabel("☀ Helligkeit:"))
        self.slider_brightness = QSlider(Qt.Horizontal)
        self.slider_brightness.setRange(-100, 100)
        self.slider_brightness.setValue(0)
        self.slider_brightness.setFixedWidth(120)
        self.slider_brightness.valueChanged.connect(self._on_display_changed)
        ctrl_row.addWidget(self.slider_brightness)

        ctrl_row.addSpacing(16)
        ctrl_row.addWidget(QLabel("◑ Kontrast:"))
        self.slider_contrast = QSlider(Qt.Horizontal)
        self.slider_contrast.setRange(50, 200)
        self.slider_contrast.setValue(100)
        self.slider_contrast.setFixedWidth(120)
        self.slider_contrast.valueChanged.connect(self._on_display_changed)
        ctrl_row.addWidget(self.slider_contrast)

        btn_reset = QPushButton("↺")
        btn_reset.setFixedWidth(28)
        btn_reset.setToolTip("Helligkeit/Kontrast zurücksetzen")
        btn_reset.clicked.connect(lambda: (
            self.slider_brightness.setValue(0),
            self.slider_contrast.setValue(100)
        ))
        ctrl_row.addWidget(btn_reset)
        ctrl_row.addStretch()
        layout.addLayout(ctrl_row)
        # ──────────────────────────────────────────────────────────────

        # Fortschrittsbalken (waehrend SAM laeuft)
        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, 0)   # indeterminiert
        self.progress_bar.setMaximumHeight(5)
        layout.addWidget(self.progress_bar)

        # Status-Label
        self.status_label = QLabel("MobileSAM segmentiert Knorpel...")
        self.status_label.setStyleSheet("color:#a6adc8; font-size:11px;")
        self.status_label.setAlignment(Qt.AlignCenter)
        layout.addWidget(self.status_label)

        # Buttons
        btn_row = QHBoxLayout()
        btn_row.setSpacing(8)

        self.btn_confirm = QPushButton("✔  Vorschlag übernehmen")
        self.btn_confirm.setObjectName("primary")
        self.btn_confirm.setMinimumHeight(40)
        self.btn_confirm.setEnabled(False)
        self.btn_confirm.clicked.connect(self._on_confirm)

        self.btn_redraw = QPushButton("✏  Manuell neu zeichnen")
        self.btn_redraw.setEnabled(False)
        self.btn_redraw.clicked.connect(self._on_redraw)

        self.btn_save_ref = QPushButton("💾  Als Referenz speichern")
        self.btn_save_ref.setEnabled(False)
        self.btn_save_ref.setToolTip(
            "Speichert diese ROI als Lernbeispiel für zukünftige Bilder")
        self.btn_save_ref.clicked.connect(self._on_save_reference)

        btn_skip = QPushButton("⏭  Überspringen")
        btn_skip.clicked.connect(self._on_skip)

        for b in [self.btn_confirm, self.btn_redraw,
                  self.btn_save_ref, btn_skip]:
            btn_row.addWidget(b)

        layout.addLayout(btn_row)

    # ── SAM starten ───────────────────────────────────────────────────

    def _start_sam(self):
        self._worker = SamWorker(self.rgb, self.estimate, self.segmenter)
        self._worker.signals.progress.connect(self.status_label.setText)
        self._worker.signals.finished.connect(self._on_sam_done)
        self._worker.signals.error.connect(self._on_sam_error)
        self._worker.start()

    def _on_sam_done(self, result: dict):
        self.progress_bar.setRange(0, 1)
        self.progress_bar.setValue(1)

        if not result or "polygon_normalized" not in result:
            self.status_label.setText(
                "⚠ Segmentierung fehlgeschlagen — bitte manuell zeichnen")
            self.btn_redraw.setEnabled(True)
            return

        self._result  = result
        self._polygon = result["polygon_normalized"]
        area_pct      = result["mask"].mean() * 100
        conf          = result.get("confidence", 0.0)
        source        = "YOLO" if self.segmenter is None else "SAM"

        self.status_label.setText(
            f"✔ {source}-Segmentierung  |  "
            f"Fläche: {area_pct:.1f}%  |  "
            f"Konfidenz: {conf*100:.0f}%  |  "
            f"{len(self._polygon)} Punkte"
        )
        self.btn_confirm.setEnabled(True)
        self.btn_redraw.setEnabled(True)
        self.btn_save_ref.setEnabled(True)
        self._render_preview()

    def _on_sam_error(self, error: str):
        self.progress_bar.setRange(0, 1)
        self.status_label.setText(f"✗ Fehler: {error}")
        self.btn_redraw.setEnabled(True)

    # ── Vorschau rendern ──────────────────────────────────────────────

    def _render_preview(self):
        if not self._polygon or self.rgb is None:
            return

        rgb = self._get_adjusted_rgb()
        h, w = rgb.shape[:2]

        # Maske als gruene Flaeche einblenden
        if self._result and "mask" in self._result:
            mask = self._result["mask"]
            overlay = rgb.copy()
            overlay[mask] = (
                overlay[mask].astype(np.int32) * 0.5 +
                np.array([0, 200, 80]) * 0.5
            ).clip(0, 255).astype(np.uint8)
            rgb = overlay

        # Polygon-Kontur zeichnen (via Qt)
        qimg = QImage(rgb.tobytes(), w, h, w * 3, QImage.Format_RGB888)
        pm   = QPixmap.fromImage(qimg)

        lw = self.preview_label.width()  if self.preview_label.width()  > 10 else 860
        lh = self.preview_label.height() if self.preview_label.height() > 10 else 420

        pm_scaled = pm.scaled(lw, lh, Qt.KeepAspectRatio, Qt.SmoothTransformation)
        scale_x   = pm_scaled.width()  / w
        scale_y   = pm_scaled.height() / h
        ox        = (lw - pm_scaled.width())  // 2
        oy        = (lh - pm_scaled.height()) // 2

        result_pm = QPixmap(lw, lh)
        result_pm.fill(QColor("#11111b"))
        painter = QPainter(result_pm)
        painter.drawPixmap(ox, oy, pm_scaled)

        # Polygon
        pts = QPolygonF([
            QPointF(ox + x * w * scale_x, oy + y * h * scale_y)
            for x, y in self._polygon
        ])
        painter.setPen(QPen(QColor(0, 255, 100), 2))
        painter.setBrush(QColor(0, 255, 100, 40))
        painter.drawPolygon(pts)

        # Prompt-Punkte anzeigen
        painter.setPen(QPen(QColor(255, 220, 0), 1))
        painter.setBrush(QColor(255, 220, 0))
        for px, py in self.estimate.get("prompt_points", []):
            painter.drawEllipse(
                QPointF(ox + px * w * scale_x, oy + py * h * scale_y),
                4, 4
            )

        painter.end()
        self.preview_label.setPixmap(result_pm)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        if self._polygon:
            self._render_preview()

    # ── Aktionen ──────────────────────────────────────────────────────
    
    def _on_display_changed(self):
        self._render_preview()

    def _get_adjusted_rgb(self) -> np.ndarray:
        """Gibt Helligkeit/Kontrast-angepasstes RGB zurück."""
        brightness = self.slider_brightness.value()
        contrast   = self.slider_contrast.value() / 100.0
        img = self.rgb.astype(np.float32)
        img = img * contrast + brightness * 2.55
        return np.clip(img, 0, 255).astype(np.uint8)

    def _on_confirm(self):
        """Vorschlag bestaetigen — ROI wird direkt uebernommen."""
        if not self._polygon:
            return
        self.roi_confirmed.emit(self._polygon)
        self.accept()

    def _on_redraw(self):
        """Oeffnet manuellen ROI-Dialog zum Neu-Zeichnen."""
        from ui.roi_dialog import ROIDialog
        dlg = ROIDialog(self.image_path, parent=self)
        # Vorschlag als Startpunkt laden (falls vorhanden)
        if self._polygon:
            dlg.canvas.load_polygon(self._polygon)
        dlg.roi_confirmed.connect(self._on_manual_confirmed)
        dlg.exec()

    def _on_manual_confirmed(self, points: list):
        """Callback wenn manuell neu gezeichnet wurde."""
        self._polygon = points
        self.roi_confirmed.emit(points)
        self.accept()

    def _on_save_reference(self):
        """Speichert die aktuelle ROI als Lernreferenz."""
        if not self._polygon:
            return
        from analysis.roi_learner import save_reference
        h, w = self.rgb.shape[:2]
        save_reference(
            image_path=self.image_path,
            polygon_normalized=self._polygon,
            image_shape=(h, w),
            stain=self.stain_name,
        )
        self.btn_save_ref.setText("✔ Gespeichert")
        self.btn_save_ref.setEnabled(False)

    def _on_skip(self):
        """Ueberspringen — keine ROI fuer dieses Bild."""
        self.roi_skipped.emit()
        self.reject()


# ══════════════════════════════════════════════════════════════════════
# Download-Dialog
# ══════════════════════════════════════════════════════════════════════

class ModelDownloadDialog(QDialog):
    """
    Dialog der den MobileSAM-Download anzeigt und startet.
    Wird einmalig beim ersten Verwenden von Auto-ROI gezeigt.
    """

    download_finished = Signal(bool)  # True = Erfolg

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("MobileSAM herunterladen")
        self.setFixedSize(460, 200)
        self.setModal(True)
        self._build_ui()

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setSpacing(12)
        layout.setContentsMargins(20, 20, 20, 20)

        info = QLabel(
            "MobileSAM wird einmalig heruntergeladen (~40 MB).\n"
            "Dieses Modell ermöglicht die automatische Knorpel-Erkennung."
        )
        info.setWordWrap(True)
        info.setStyleSheet("color:#cdd6f4;")
        layout.addWidget(info)

        self.progress = QProgressBar()
        self.progress.setRange(0, 100)
        self.progress.setValue(0)
        layout.addWidget(self.progress)

        self.status = QLabel("Warte auf Start...")
        self.status.setStyleSheet("color:#a6adc8; font-size:11px;")
        self.status.setAlignment(Qt.AlignCenter)
        layout.addWidget(self.status)

        btn_row = QHBoxLayout()
        self.btn_start  = QPushButton("⬇  Download starten")
        self.btn_start.setObjectName("primary")
        self.btn_start.clicked.connect(self._start_download)
        btn_cancel = QPushButton("Abbrechen")
        btn_cancel.clicked.connect(self.reject)
        btn_row.addWidget(btn_cancel)
        btn_row.addWidget(self.btn_start)
        layout.addLayout(btn_row)

    def _start_download(self):
        self.btn_start.setEnabled(False)
        self.status.setText("Lade herunter...")

        self._dl_thread = QThread()
        self._dl_worker = _DownloadWorker()
        self._dl_worker.moveToThread(self._dl_thread)
        self._dl_thread.started.connect(self._dl_worker.run)
        self._dl_worker.progress.connect(self.progress.setValue)
        self._dl_worker.progress.connect(
            lambda p: self.status.setText(f"  {p}%"))
        self._dl_worker.finished.connect(self._on_done)
        self._dl_thread.start()

    def _on_done(self, success: bool):
        self._dl_thread.quit()
        if success:
            self.status.setText("✔ Download abgeschlossen!")
            self.progress.setValue(100)
            self.download_finished.emit(True)
            self.accept()
        else:
            self.status.setText("✗ Download fehlgeschlagen — Internetverbindung prüfen")
            self.btn_start.setEnabled(True)
            self.download_finished.emit(False)


class _DownloadWorker(QObject):
    progress = Signal(int)
    finished = Signal(bool)

    def run(self):
        from analysis.sam_segmenter import download_model
        ok = download_model(progress_callback=self.progress.emit)
        self.finished.emit(ok)