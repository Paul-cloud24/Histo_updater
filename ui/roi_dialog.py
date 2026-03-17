# ui/roi_dialog.py

import os
import json
import numpy as np
from PIL import Image

from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QPushButton,
    QLabel, QSizePolicy, QMessageBox
)
from PySide6.QtGui import (
    QPixmap, QImage, QPainter, QPen, QPolygonF, QColor, QFont
)
from PySide6.QtCore import Qt, QPointF, Signal



class ROICanvas(QLabel):
    """Canvas auf dem das DAPI-Bild angezeigt und Polygon gezeichnet wird."""

    polygon_changed = Signal()  # Signal dass sich das Polygon geändert hat (Punkte hinzugefügt, gelöscht, geschlossen)
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setAlignment(Qt.AlignTop | Qt.AlignLeft)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.setMinimumSize(600, 500)
        self.setCursor(Qt.CrossCursor)

        self._base_pixmap = None   # originales Bild
        self._points      = []     # Liste von QPointF (in Pixmap-Koordinaten)
        self._closed      = False  # Polygon geschlossen?
        self._scale       = 1.0    # Pixmap-Skalierung gegenüber Originalbild
        self._img_w       = 1
        self._img_h       = 1

    def load_image(self, img_array: np.ndarray):
        """Lädt ein numpy uint8 Graustufenbild."""
        h, w = img_array.shape
        self._img_w = w
        self._img_h = h

        # Normieren für Anzeige
        vmax = img_array.max() if img_array.max() > 0 else 1
        display = (img_array.astype(np.float32) / vmax * 255).astype(np.uint8)

        qimg = QImage(display.tobytes(), w, h, w, QImage.Format_Grayscale8)
        self._base_pixmap = QPixmap.fromImage(qimg)
        self._points = []
        self._closed = False
        self._update_display()

    def load_polygon(self, points_norm):
        """
        Lädt gespeichertes Polygon.
        points_norm: Liste von (x_rel, y_rel) in 0..1 Koordinaten
        """
        if self._base_pixmap is None:
            return
        pm_w = self._base_pixmap.width()
        pm_h = self._base_pixmap.height()
        self._points = [
            QPointF(x * pm_w, y * pm_h) for x, y in points_norm
        ]
        self._closed = len(self._points) >= 3
        self._update_display()

    def get_polygon_normalized(self):
        """Gibt Polygon als Liste von (x_rel, y_rel) in 0..1 zurück."""
        if not self._points or self._base_pixmap is None:
            return []
        pm_w = self._base_pixmap.width()
        pm_h = self._base_pixmap.height()
        return [(p.x() / pm_w, p.y() / pm_h) for p in self._points]

    def get_mask(self, h, w):
        """Erzeugt bool-Maske (h x w) aus dem Polygon."""
        from PIL import ImageDraw as PilDraw
        pts_norm = self.get_polygon_normalized()
        if len(pts_norm) < 3:
            return np.ones((h, w), dtype=bool)  # keine ROI = alles

        pts_px = [(int(x * w), int(y * h)) for x, y in pts_norm]
        mask_img = Image.new("L", (w, h), 0)
        PilDraw.Draw(mask_img).polygon(pts_px, fill=255)
        return np.array(mask_img) > 0

    def undo_last(self):
        if self._points:
            self._points.pop()
            self._closed = False
            self._update_display()
            self.polygon_changed.emit()

    def clear(self):
        self._points = []
        self._closed = False
        self._update_display()
        self.polygon_changed.emit()

    def close_polygon(self):
        if len(self._points) >= 3:
            self._closed = True
            self._update_display()
            self.polygon_changed.emit()

    # ── Events ────────────────────────────────────────────────────────────

    def mousePressEvent(self, event):
        if self._base_pixmap is None:
            return
        if self._closed:
            return  # Polygon fertig — kein weiteres Klicken

        # Klick-Position relativ zum angezeigten Bild
        pt = self._label_to_pixmap(event.pos())
        if pt is None:
            return

        # Prüfen ob Klick nahe am ersten Punkt → schließen
        if len(self._points) >= 3:
            first = self._points[0]
            dist = ((pt.x() - first.x())**2 + (pt.y() - first.y())**2) ** 0.5
            if dist < 12:
                self.close_polygon()
                return

        self._points.append(pt)
        self._update_display()
        self.polygon_changed.emit()

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self._update_display()

    # ── Internes ──────────────────────────────────────────────────────────

    def _label_to_pixmap(self, pos):
        """Konvertiert Label-Koordinaten zu Pixmap-Koordinaten."""
        if self._base_pixmap is None:
            return None
        lw, lh = self.width(), self.height()
        pm = self._base_pixmap.scaled(
            lw, lh, Qt.KeepAspectRatio, Qt.SmoothTransformation
        )
        # Offset (Bild ist zentriert im Label)
        ox = (lw - pm.width())  // 2
        oy = (lh - pm.height()) // 2
        x = (pos.x() - ox) * self._base_pixmap.width()  / pm.width()
        y = (pos.y() - oy) * self._base_pixmap.height() / pm.height()
        if 0 <= x <= self._base_pixmap.width() and \
           0 <= y <= self._base_pixmap.height():
            return QPointF(x, y)
        return None

    def _update_display(self):
        if self._base_pixmap is None:
            return

        lw, lh = max(self.width(), 1), max(self.height(), 1)
        pm = self._base_pixmap.scaled(
            lw, lh, Qt.KeepAspectRatio, Qt.SmoothTransformation
        )
        scale_x = pm.width()  / self._base_pixmap.width()
        scale_y = pm.height() / self._base_pixmap.height()

        ox = (lw - pm.width())  // 2
        oy = (lh - pm.height()) // 2

        canvas = pm.copy()
        painter = QPainter(canvas)
        painter.setRenderHint(QPainter.Antialiasing)

        # Polygon-Füllung (halbtransparent grün)
        if len(self._points) >= 3 and self._closed:
            poly = QPolygonF([
                QPointF(p.x() * scale_x, p.y() * scale_y)
                for p in self._points
            ])
            painter.setBrush(QColor(0, 255, 0, 60))
            painter.setPen(QPen(QColor(0, 255, 0), 2))
            painter.drawPolygon(poly)

        # Linien zwischen Punkten
        pen_line = QPen(QColor(255, 220, 0), 2, Qt.SolidLine)
        painter.setPen(pen_line)
        for i in range(1, len(self._points)):
            p1 = QPointF(self._points[i-1].x() * scale_x,
                         self._points[i-1].y() * scale_y)
            p2 = QPointF(self._points[i].x()   * scale_x,
                         self._points[i].y()   * scale_y)
            painter.drawLine(p1, p2)

        # Schlusslinie zum ersten Punkt (gestrichelt wenn offen)
        if len(self._points) >= 2:
            p_first = QPointF(self._points[0].x() * scale_x,
                              self._points[0].y() * scale_y)
            p_last  = QPointF(self._points[-1].x() * scale_x,
                              self._points[-1].y() * scale_y)
            if self._closed:
                painter.setPen(QPen(QColor(0, 255, 0), 2))
            else:
                painter.setPen(QPen(QColor(255, 220, 0), 2, Qt.DashLine))
            painter.drawLine(p_last, p_first)

        # Punkte einzeichnen
        for i, p in enumerate(self._points):
            px = p.x() * scale_x
            py = p.y() * scale_y
            if i == 0:
                # Erster Punkt = grün (Schliessen-Hinweis)
                painter.setBrush(QColor(0, 255, 100))
                painter.setPen(QPen(Qt.white, 1))
                painter.drawEllipse(QPointF(px, py), 7, 7)
            else:
                painter.setBrush(QColor(255, 220, 0))
                painter.setPen(QPen(Qt.white, 1))
                painter.drawEllipse(QPointF(px, py), 5, 5)

        # Hinweis-Text
        painter.setPen(QPen(Qt.white))
        font = QFont(); font.setPointSize(9)
        painter.setFont(font)
        if not self._points:
            painter.drawText(8, 18, "Klicken um Punkte zu setzen")
        elif not self._closed:
            painter.drawText(8, 18,
                f"{len(self._points)} Punkte — "
                "Ersten Punkt erneut klicken zum Schließen")
        else:
            painter.drawText(8, 18,
                f"ROI: {len(self._points)} Punkte ✓  "
                "(\"Übernehmen\" zum Bestätigen)")

        painter.end()

        # Pixmap mit Offset ins Label setzen
        result = QPixmap(lw, lh)
        result.fill(Qt.black)
        p2 = QPainter(result)
        p2.drawPixmap(ox, oy, canvas)
        p2.end()

        self.setPixmap(result)


class ROIDialog(QDialog):
    """
    Dialog zum Einzeichnen der ROI als Polygon auf dem DAPI-Bild.
    Das Polygon wird als JSON neben dem Bild gespeichert.
    """

    roi_confirmed = Signal(list)   # gibt normalisierte Punkte zurück

    def __init__(self, dapi_path: str, parent=None):
        super().__init__(parent)
        self.dapi_path   = dapi_path
        self.json_path   = self._get_json_path(dapi_path)
        self._dapi_array = None

        self.setWindowTitle("ROI einzeichnen — DAPI-Kanal")
        self.setMinimumSize(800, 650)
        self._build_ui()
        self._load_dapi()
        self._try_load_existing_roi()

    # ── UI ────────────────────────────────────────────────────────────────

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(6)

        # Info-Label
        self.info_label = QLabel(
            "Klicke Punkte um das ROI-Polygon einzuzeichnen. "
            "Ersten Punkt erneut anklicken zum Schließen."
        )
        self.info_label.setWordWrap(True)
        layout.addWidget(self.info_label)

        # Canvas
        self.canvas = ROICanvas()
        self.canvas.polygon_changed.connect(self._on_polygon_changed)
        layout.addWidget(self.canvas, stretch=1)

        # Buttons
        btn_row = QHBoxLayout()

        self.btn_undo = QPushButton("↩ Rückgängig")
        self.btn_undo.clicked.connect(self.canvas.undo_last)

        self.btn_clear = QPushButton("✕ Löschen")
        self.btn_clear.clicked.connect(self._on_clear)

        self.btn_close_poly = QPushButton("⬡ Polygon schließen")
        self.btn_close_poly.clicked.connect(self.canvas.close_polygon)

        self.btn_ok = QPushButton("✔ Übernehmen")
        self.btn_ok.setEnabled(False)
        self.btn_ok.setStyleSheet(
            "QPushButton { background: #2d7a2d; color: white; "
            "font-weight: bold; padding: 6px 16px; }"
        )
        self.btn_ok.clicked.connect(self._on_confirm)

        btn_cancel = QPushButton("Abbrechen")
        btn_cancel.clicked.connect(self.reject)

        for b in [self.btn_undo, self.btn_clear,
                  self.btn_close_poly, self.btn_ok, btn_cancel]:
            btn_row.addWidget(b)

        layout.addLayout(btn_row)

    # ── Laden ─────────────────────────────────────────────────────────────

    def _load_dapi(self):

        img = np.array(Image.open(self.dapi_path))
        # DAPI = B-Kanal (Index 2) bei RGB
        if img.ndim == 3:
            self._dapi_array = img[..., 2]
        else:
            self._dapi_array = img

        self.canvas.load_image(self._dapi_array)

    def _try_load_existing_roi(self):
        if not os.path.exists(self.json_path):
            return
        try:
            with open(self.json_path) as f:
                data = json.load(f)
            pts = data.get("polygon_normalized", [])
            if len(pts) < 3:
                return

            msg = QMessageBox(
                QMessageBox.Question,
                "Vorhandene ROI gefunden",
                f"Es wurde eine gespeicherte ROI mit {len(pts)} Punkten gefunden.\n\n"
                "Möchtest du diese laden oder neu zeichnen?",
                parent=self
            )
            btn_load = msg.addButton("Laden",       QMessageBox.AcceptRole)
            btn_new  = msg.addButton("Neu zeichnen", QMessageBox.RejectRole)
            msg.setDefaultButton(btn_load)
            msg.exec_()

            if msg.clickedButton() == btn_load:
                self.canvas.load_polygon(pts)
                self.info_label.setText(
                    f"Vorhandene ROI geladen ({len(pts)} Punkte). "
                    "Direkt übernehmen oder Punkte anpassen."
                )
            # bei "Neu zeichnen" passiert nichts → leeres Canvas

        except Exception:
            pass

    # ── Events ────────────────────────────────────────────────────────────

    def _on_polygon_changed(self):
        pts = self.canvas.get_polygon_normalized()
        closed = self.canvas._closed
        self.btn_ok.setEnabled(closed and len(pts) >= 3)
        self.btn_close_poly.setEnabled(
            len(pts) >= 3 and not closed
        )

    def _on_clear(self):
        reply = QMessageBox.question(
            self, "ROI löschen",
            "Aktuelles Polygon löschen und neu beginnen?",
            QMessageBox.Yes | QMessageBox.No
        )
        if reply == QMessageBox.Yes:
            self.canvas.clear()

    def _on_confirm(self):
        pts = self.canvas.get_polygon_normalized()
        if len(pts) < 3:
            return

        # Als JSON speichern
        os.makedirs(os.path.dirname(self.json_path), exist_ok=True)
        with open(self.json_path, "w") as f:
            json.dump({
                "polygon_normalized": pts,
                "dapi_path": self.dapi_path,
                "n_points":  len(pts),
            }, f, indent=2)

        self.roi_confirmed.emit(pts)
        self.accept()

    # ── Helpers ───────────────────────────────────────────────────────────

    @staticmethod
    def _get_json_path(dapi_path: str) -> str:
        folder = os.path.join(os.path.dirname(dapi_path), "results")
        base   = os.path.splitext(os.path.basename(dapi_path))[0]
        return os.path.join(folder, f"{base}_roi.json")

    @staticmethod
    def load_roi_mask(dapi_path: str, h: int, w: int) -> np.ndarray:
        """
        Lädt gespeicherte ROI-Maske für ein Bild.
        Gibt None zurück wenn keine ROI gespeichert ist.
        """
        json_path = ROIDialog._get_json_path(dapi_path)
        if not os.path.exists(json_path):
            return None
        try:
            with open(json_path) as f:
                data = json.load(f)
            pts_norm = data.get("polygon_normalized", [])
            if len(pts_norm) < 3:
                return None

            from PIL import ImageDraw as PilDraw
            pts_px  = [(int(x * w), int(y * h)) for x, y in pts_norm]
            mask_img = Image.new("L", (w, h), 0)
            PilDraw.Draw(mask_img).polygon(pts_px, fill=255)
            return np.array(mask_img) > 0
        except Exception:
            return None