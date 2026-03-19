# ui/model_manager_dialog.py
"""
Modell-Manager Dialog.

Zeigt alle gespeicherten ROI-Modelle und erlaubt:
  - Modell auswählen (aktiv setzen)
  - Referenz-ROIs ansehen, einzeln löschen, neu einzeichnen
  - Modell löschen
  - Neues Modell trainieren (Name + Färbung eingeben)
"""

import os
import json
import numpy as np
from pathlib import Path
from datetime import datetime

from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QPushButton, QLabel,
    QListWidget, QListWidgetItem, QSplitter, QGroupBox,
    QTabWidget, QWidget, QScrollArea, QFrame, QLineEdit,
    QComboBox, QMessageBox, QSizePolicy, QGridLayout,
    QProgressBar
)
from PySide6.QtCore import Qt, Signal, QThread, QObject
from PySide6.QtGui import QPixmap, QImage, QColor, QFont


# ══════════════════════════════════════════════════════════════════════
# Haupt-Dialog
# ══════════════════════════════════════════════════════════════════════

class ModelManagerDialog(QDialog):

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("🤖  Modell-Manager")
        self.setMinimumSize(1000, 680)
        self.setModal(True)
        self._selected_model = None
        self._build_ui()
        self._load_models()

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(8)

        # Tabs
        self.tabs = QTabWidget()
        self.tabs.setStyleSheet("""
            QTabBar::tab { padding: 6px 16px; }
            QTabBar::tab:selected { font-weight: 600; }
        """)

        self.tab_models = QWidget()
        self.tab_train  = QWidget()
        self.tabs.addTab(self.tab_models, "📋  Modelle")
        self.tabs.addTab(self.tab_train,  "🏋  Neues Modell trainieren")

        layout.addWidget(self.tabs)

        self._build_models_tab()
        self._build_train_tab()

        # Schließen
        btn_row = QHBoxLayout()
        btn_close = QPushButton("Schließen")
        btn_close.clicked.connect(self.accept)
        btn_row.addStretch()
        btn_row.addWidget(btn_close)
        layout.addLayout(btn_row)

    # ── Tab 1: Modelle ────────────────────────────────────────────────

    def _build_models_tab(self):
        layout = QHBoxLayout(self.tab_models)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(8)

        # Linke Spalte: Modell-Liste
        left = QVBoxLayout()
        lbl = QLabel("GESPEICHERTE MODELLE")
        lbl.setStyleSheet("color:#6c7086; font-size:11px; font-weight:600;")
        left.addWidget(lbl)

        self.model_list = QListWidget()
        self.model_list.setFixedWidth(280)
        self.model_list.currentItemChanged.connect(self._on_model_selected)
        left.addWidget(self.model_list, stretch=1)

        # Modell-Buttons
        mb_row = QHBoxLayout()
        self.btn_activate = QPushButton("✔ Aktivieren")
        self.btn_activate.setEnabled(False)
        self.btn_activate.clicked.connect(self._activate_model)
        self.btn_delete_model = QPushButton("🗑 Löschen")
        self.btn_delete_model.setEnabled(False)
        self.btn_delete_model.setStyleSheet("color:#f38ba8;")
        self.btn_delete_model.clicked.connect(self._delete_model)
        mb_row.addWidget(self.btn_activate)
        mb_row.addWidget(self.btn_delete_model)
        left.addLayout(mb_row)

        layout.addLayout(left)

        # Rechte Spalte: Modell-Details + Referenzen
        right = QVBoxLayout()

        # Modell-Info
        self.model_info_grp = QGroupBox("Modell-Details")
        info_layout = QGridLayout(self.model_info_grp)
        self.lbl_name       = QLabel("—")
        self.lbl_stain      = QLabel("—")
        self.lbl_slice      = QLabel("—")
        self.lbl_created    = QLabel("—")
        self.lbl_refs       = QLabel("—")
        self.lbl_map        = QLabel("—")

        for row, (key, val) in enumerate([
            ("Name:", self.lbl_name),
            ("Färbung:", self.lbl_stain),
            ("Schnitt:", self.lbl_slice),
            ("Erstellt:", self.lbl_created),
            ("Referenzen:", self.lbl_refs),
            ("mAP50:", self.lbl_map),
        ]):
            lbl = QLabel(key)
            lbl.setStyleSheet("color:#6c7086; font-size:11px;")
            info_layout.addWidget(lbl, row, 0)
            info_layout.addWidget(val, row, 1)

        right.addWidget(self.model_info_grp)

        # Referenzen
        ref_grp = QGroupBox("Referenz-ROIs dieses Modells")
        ref_layout = QVBoxLayout(ref_grp)

        self.ref_list = QListWidget()
        self.ref_list.currentItemChanged.connect(self._on_ref_selected)
        ref_layout.addWidget(self.ref_list, stretch=1)

        # Referenz-Vorschau
        self.ref_preview = QLabel("Referenz auswählen")
        self.ref_preview.setAlignment(Qt.AlignCenter)
        self.ref_preview.setFixedHeight(140)
        self.ref_preview.setStyleSheet(
            "background:#11111b; border:1px solid #313244; "
            "border-radius:6px; color:#45475a;")
        ref_layout.addWidget(self.ref_preview)

        # Referenz-Buttons
        rb_row = QHBoxLayout()
        self.btn_redraw_ref = QPushButton("✏ Neu einzeichnen")
        self.btn_redraw_ref.setEnabled(False)
        self.btn_redraw_ref.clicked.connect(self._redraw_reference)
        self.btn_delete_ref = QPushButton("🗑 Referenz entfernen")
        self.btn_delete_ref.setEnabled(False)
        self.btn_delete_ref.setStyleSheet("color:#f38ba8;")
        self.btn_delete_ref.clicked.connect(self._delete_reference)
        rb_row.addWidget(self.btn_redraw_ref)
        rb_row.addWidget(self.btn_delete_ref)
        ref_layout.addLayout(rb_row)

        right.addWidget(ref_grp, stretch=1)
        layout.addLayout(right, stretch=1)

    # ── Tab 2: Neues Modell trainieren ────────────────────────────────

    def _build_train_tab(self):
        layout = QVBoxLayout(self.tab_train)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(12)

        # Modell-Info eingeben
        info_grp = QGroupBox("Modell-Informationen")
        grid = QGridLayout(info_grp)
        grid.setSpacing(8)

        grid.addWidget(QLabel("Modell-Name:"), 0, 0)
        self.edit_name = QLineEdit()
        self.edit_name.setPlaceholderText("z.B. Sox9 Tibia medial")
        grid.addWidget(self.edit_name, 0, 1)

        grid.addWidget(QLabel("Färbung:"), 1, 0)
        self.combo_stain = QComboBox()
        from stains import available_stains
        self.combo_stain.addItems(available_stains())
        grid.addWidget(self.combo_stain, 1, 1)

        grid.addWidget(QLabel("Schnitt / Gewebetyp:"), 2, 0)
        self.edit_slice = QLineEdit()
        self.edit_slice.setPlaceholderText("z.B. Tibia, Femur, Allgemein")
        grid.addWidget(self.edit_slice, 2, 1)

        layout.addWidget(info_grp)

        # Referenzen-Info
        ref_info_grp = QGroupBox("Vorhandene Referenzen")
        ref_info_layout = QVBoxLayout(ref_info_grp)
        from analysis.roi_learner import get_reference_count
        n = get_reference_count()
        self.lbl_ref_count = QLabel(
            f"Aktuell gespeicherte Referenzen: {n}\n"
            f"{'✔ Genug für Training' if n >= 10 else '⚠ Empfehlung: mindestens 20 Referenzen'}"
        )
        self.lbl_ref_count.setStyleSheet(
            "color:#a6e3a1;" if n >= 10 else "color:#fab387;")
        ref_info_layout.addWidget(self.lbl_ref_count)
        layout.addWidget(ref_info_grp)

        # Training-Fortschritt
        self.train_progress = QProgressBar()
        self.train_progress.setRange(0, 0)
        self.train_progress.setVisible(False)
        layout.addWidget(self.train_progress)

        self.train_status = QLabel("")
        self.train_status.setStyleSheet("color:#a6adc8; font-size:11px;")
        self.train_status.setAlignment(Qt.AlignCenter)
        layout.addWidget(self.train_status)

        layout.addStretch()

        # Train-Button
        self.btn_train = QPushButton("🏋  Training starten")
        self.btn_train.setObjectName("primary")
        self.btn_train.setMinimumHeight(44)
        self.btn_train.clicked.connect(self._start_training)
        layout.addWidget(self.btn_train)

    # ── Modelle laden ─────────────────────────────────────────────────

    def _load_models(self):
        from analysis.roi_model_registry import load_registry
        self.model_list.clear()
        models = load_registry()

        for m in models:
            exists = Path(m["model_path"]).exists()
            active = m.get("active", False)
            name   = m["name"]
            stain  = m.get("stain", "?")
            label  = f"{'✔ ' if active else '  '}{name}  [{stain}]"
            if not exists:
                label += "  ⚠"

            item = QListWidgetItem(label)
            item.setData(Qt.UserRole, m)
            if active:
                item.setForeground(QColor("#a6e3a1"))
                font = item.font()
                font.setBold(True)
                item.setFont(font)
            elif not exists:
                item.setForeground(QColor("#f38ba8"))
            self.model_list.addItem(item)

        if self.model_list.count() == 0:
            item = QListWidgetItem("Keine Modelle vorhanden")
            item.setForeground(QColor("#585b70"))
            self.model_list.addItem(item)

    def _on_model_selected(self, current, previous):
        if current is None:
            return
        m = current.data(Qt.UserRole)
        if m is None:
            return

        self._selected_model = m
        self.btn_activate.setEnabled(not m.get("active", False))
        self.btn_delete_model.setEnabled(True)

        # Details anzeigen
        created = m.get("created", "")[:10]
        self.lbl_name.setText(m.get("name", "—"))
        self.lbl_stain.setText(m.get("stain", "—"))
        self.lbl_slice.setText(m.get("slice_type", "—"))
        self.lbl_created.setText(created)
        self.lbl_refs.setText(str(m.get("n_refs", 0)))
        self.lbl_map.setText(f"{m.get('mAP50', 0.0):.3f}")

        # Referenzen laden
        self._load_refs_for_model(m)

    def _load_refs_for_model(self, model: dict):
        from analysis.roi_model_registry import get_refs_for_model
        self.ref_list.clear()
        self.ref_preview.setText("Referenz auswählen")

        refs = get_refs_for_model(model)
        for ref in refs:
            img_name = Path(ref["image_path"]).name[:50]
            cx = ref.get("centroid_x", 0)
            cy = ref.get("centroid_y", 0)
            label = (f"#{ref['id']}  {img_name}  "
                     f"cx={cx:.2f} cy={cy:.2f}")
            item = QListWidgetItem(label)
            item.setData(Qt.UserRole, ref)
            exists = Path(ref["image_path"]).exists()
            if not exists:
                item.setForeground(QColor("#f38ba8"))
            self.ref_list.addItem(item)

        count = self.ref_list.count()
        self.model_info_grp.setTitle(
            f"Modell-Details  ({count} Referenzen)")

    def _on_ref_selected(self, current, previous):
        if current is None:
            return
        ref = current.data(Qt.UserRole)
        if ref is None:
            return

        self.btn_redraw_ref.setEnabled(True)
        self.btn_delete_ref.setEnabled(True)

        # Vorschau laden
        self._show_ref_preview(ref)

    def _show_ref_preview(self, ref: dict):
        """Zeigt Vorschau-Bild der Referenz mit ROI-Polygon."""
        img_path = ref.get("image_path", "")
        polygon  = ref.get("polygon_normalized", [])

        if not os.path.exists(img_path):
            self.ref_preview.setText("Bild nicht gefunden")
            return

        try:
            from PIL import Image as PilImage, ImageDraw as PilDraw
            from analysis.brightfield_pipeline import load_as_uint8_rgb

            img = load_as_uint8_rgb(img_path)
            h, w = img.shape[:2]

            # Auf max 300px skalieren
            MAX = 300
            if max(h, w) > MAX:
                scale = MAX / max(h, w)
                img   = np.array(PilImage.fromarray(img).resize(
                    (int(w * scale), int(h * scale)), PilImage.LANCZOS))
                h, w  = img.shape[:2]

            # ROI einzeichnen
            if polygon:
                pil  = PilImage.fromarray(img)
                draw = PilDraw.Draw(pil)
                pts  = [(int(x * w), int(y * h)) for x, y in polygon]
                draw.line(pts + [pts[0]], fill=(0, 255, 100), width=2)
                img  = np.array(pil)

            qimg = QImage(img.tobytes(), w, h, w * 3, QImage.Format_RGB888)
            px   = QPixmap.fromImage(qimg)
            lw   = self.ref_preview.width()
            lh   = self.ref_preview.height()
            self.ref_preview.setPixmap(
                px.scaled(lw, lh, Qt.KeepAspectRatio,
                          Qt.SmoothTransformation))
        except Exception as e:
            self.ref_preview.setText(f"Fehler: {e}")

    # ── Modell-Aktionen ───────────────────────────────────────────────

    def _activate_model(self):
        if not self._selected_model:
            return
        from analysis.roi_model_registry import set_active_model
        set_active_model(self._selected_model["id"])
        self._log_train(f"✔ Aktives Modell: {self._selected_model['name']}")
        self._load_models()

    def _delete_model(self):
        if not self._selected_model:
            return
        reply = QMessageBox.question(
            self, "Modell löschen",
            f"Modell '{self._selected_model['name']}' wirklich löschen?",
            QMessageBox.Yes | QMessageBox.No
        )
        if reply == QMessageBox.Yes:
            from analysis.roi_model_registry import delete_model
            delete_model(self._selected_model["id"])
            self._selected_model = None
            self._load_models()

    # ── Referenz-Aktionen ─────────────────────────────────────────────

    def _delete_reference(self):
        item = self.ref_list.currentItem()
        if not item:
            return
        ref = item.data(Qt.UserRole)

        reply = QMessageBox.question(
            self, "Referenz löschen",
            f"Referenz #{ref['id']} wirklich löschen?",
            QMessageBox.Yes | QMessageBox.No
        )
        if reply == QMessageBox.Yes:
            from analysis.roi_learner import delete_reference
            delete_reference(ref["id"])
            if self._selected_model:
                self._load_refs_for_model(self._selected_model)

    def _redraw_reference(self):
        """Öffnet ROI-Dialog zum Neu-Einzeichnen einer Referenz."""
        item = self.ref_list.currentItem()
        if not item:
            return
        ref      = item.data(Qt.UserRole)
        img_path = ref["image_path"]

        if not os.path.exists(img_path):
            QMessageBox.warning(self, "Fehler",
                                f"Bild nicht gefunden:\n{img_path}")
            return

        from ui.roi_dialog import ROIDialog
        from analysis.brightfield_pipeline import load_as_uint8_rgb

        # Bild laden
        try:
            original = load_as_uint8_rgb(img_path)
            gray     = original.max(axis=-1)
        except Exception as e:
            QMessageBox.warning(self, "Fehler", f"Bild laden: {e}")
            return

        dlg = ROIDialog(img_path, parent=self)
        dlg._dapi_array = gray
        dlg._refresh_canvas()

        # Bestehende ROI laden
        polygon = ref.get("polygon_normalized", [])
        if polygon:
            dlg.canvas.load_polygon(polygon)
            dlg.canvas._closed = True
            dlg._on_polygon_changed()

        def _on_confirmed(pts):
            # Referenz aktualisieren
            from analysis.roi_learner import (load_references,
                                              get_index_path)
            refs = load_references()
            for r in refs:
                if r["id"] == ref["id"]:
                    r["polygon_normalized"] = pts
                    # Metriken neu berechnen
                    arr = np.array(pts)
                    r["centroid_x"] = float(arr[:, 0].mean())
                    r["centroid_y"] = float(arr[:, 1].mean())
                    r["width_rel"]  = float(arr[:, 0].max() -
                                            arr[:, 0].min())
                    r["height_rel"] = float(arr[:, 1].max() -
                                            arr[:, 1].min())
                    break
            import json
            with open(get_index_path(), "w") as f:
                json.dump(refs, f, indent=2)

            if self._selected_model:
                self._load_refs_for_model(self._selected_model)

        dlg.roi_confirmed.connect(_on_confirmed)
        dlg.exec()

    # ── Training ──────────────────────────────────────────────────────

    def _start_training(self):
        name  = self.edit_name.text().strip()
        stain = self.combo_stain.currentText()
        slice_type = self.edit_slice.text().strip() or "Allgemein"

        if not name:
            QMessageBox.warning(self, "Fehler",
                                "Bitte einen Modell-Namen eingeben.")
            return

        from analysis.roi_learner import get_reference_count
        n = get_reference_count()
        if n < 4:
            QMessageBox.warning(
                self, "Zu wenig Referenzen",
                f"Nur {n} Referenzen vorhanden.\n"
                f"Mindestens 4 benötigt (besser 20+)."
            )
            return

        self.btn_train.setEnabled(False)
        self.train_progress.setVisible(True)
        self.train_status.setText("Training läuft...")

        # Training im Hintergrund
        self._train_thread = _TrainingThread(name, stain, slice_type)
        self._train_thread.status.connect(self.train_status.setText)
        self._train_thread.finished.connect(self._on_training_done)
        self._train_thread.start()

    def _on_training_done(self, success: bool, message: str):
        self.train_progress.setVisible(False)
        self.btn_train.setEnabled(True)
        self.train_status.setText(message)

        if success:
            self._load_models()
            self.tabs.setCurrentIndex(0)
            QMessageBox.information(self, "Training abgeschlossen",
                                    message)

    def _log_train(self, msg: str):
        self.train_status.setText(msg)


# ══════════════════════════════════════════════════════════════════════
# Training-Thread
# ══════════════════════════════════════════════════════════════════════

class _TrainingThread(QThread):
    status   = Signal(str)
    finished = Signal(bool, str)

    def __init__(self, name: str, stain: str, slice_type: str):
        super().__init__()
        self.name       = name
        self.stain      = stain
        self.slice_type = slice_type

    def run(self):
        try:
            from analysis.roi_trainer import train, get_training_summary
            from analysis.roi_learner import get_reference_count
            from analysis.roi_model_registry import register_model

            self.status.emit("Exportiere Daten...")
            model_path = train(epochs=100, imgsz=1024)

            summary = get_training_summary() or {}
            n_refs  = get_reference_count()

            register_model(
                name       = self.name,
                stain      = self.stain,
                slice_type = self.slice_type,
                model_path = model_path,
                n_refs     = n_refs,
                mAP50      = summary.get("mAP50", 0.0),
                epochs     = summary.get("epochs_trained", 0),
            )

            msg = (f"✔ Modell '{self.name}' trainiert!\n"
                   f"mAP50: {summary.get('mAP50', 0):.3f}  "
                   f"Referenzen: {n_refs}")
            self.finished.emit(True, msg)

        except Exception as e:
            import traceback
            traceback.print_exc()
            self.finished.emit(False, f"✗ Fehler: {e}")