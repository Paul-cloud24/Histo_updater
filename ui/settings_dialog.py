# ui/settings_dialog.py

from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QGridLayout,
    QLabel, QPushButton, QDoubleSpinBox, QSpinBox,
    QGroupBox, QFrame, QTabWidget, QWidget
)
from PySide6.QtCore import Qt


class SettingsDialog(QDialog):

    def __init__(self, params: dict, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Einstellungen")
        self.setMinimumSize(900, 600)
        self.setModal(True)
        self._params = dict(params)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(8)

        self.tabs = QTabWidget()
        self.tab_pipeline = QWidget()
        self.tab_models   = QWidget()
        self._build_pipeline_tab()
        self._build_models_tab()
        self.tabs.addTab(self.tab_pipeline, "Pipeline")
        self.tabs.addTab(self.tab_models,   "Modell-Manager")
        layout.addWidget(self.tabs)

        sep = QFrame()
        sep.setFrameShape(QFrame.HLine)
        sep.setStyleSheet("background:#313244; max-height:1px; border:none;")
        layout.addWidget(sep)

        btn_row = QHBoxLayout()
        self.btn_reset = QPushButton("Zuruecksetzen")
        self.btn_reset.clicked.connect(self._reset)
        btn_cancel = QPushButton("Abbrechen")
        btn_cancel.clicked.connect(self.reject)
        self.btn_ok = QPushButton("Uebernehmen")
        self.btn_ok.setObjectName("primary")
        self.btn_ok.setMinimumHeight(36)
        self.btn_ok.clicked.connect(self._accept)
        btn_row.addWidget(self.btn_reset)
        btn_row.addStretch()
        btn_row.addWidget(btn_cancel)
        btn_row.addWidget(self.btn_ok)
        layout.addLayout(btn_row)

        self.tabs.currentChanged.connect(self._on_tab_changed)

    def _on_tab_changed(self, idx):
        pipeline = (idx == 0)
        self.btn_reset.setVisible(pipeline)
        self.btn_ok.setVisible(pipeline)

    def _build_pipeline_tab(self):
        layout = QVBoxLayout(self.tab_pipeline)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(12)

        grp_class = QGroupBox("Klassifikation")
        grid = QGridLayout(grp_class)
        grid.addWidget(self._label("Positive Fraction"), 0, 0)
        self.spin_frac = QDoubleSpinBox()
        self.spin_frac.setRange(0.01, 1.0)
        self.spin_frac.setSingleStep(0.01)
        self.spin_frac.setDecimals(2)
        self.spin_frac.setValue(self._params.get("positive_fraction", 0.10))
        self.spin_frac.setSuffix("  (0-1)")
        grid.addWidget(self.spin_frac, 0, 1)
        layout.addWidget(grp_class)

        grp_seg = QGroupBox("Segmentierung")
        grid2 = QGridLayout(grp_seg)
        grid2.addWidget(self._label("Min. Kerngroesse (px2)"), 0, 0)
        self.spin_min_area = QSpinBox()
        self.spin_min_area.setRange(1, 5000)
        self.spin_min_area.setSingleStep(5)
        self.spin_min_area.setValue(self._params.get("min_nucleus_area", 40))
        self.spin_min_area.setSuffix(" px2")
        grid2.addWidget(self.spin_min_area, 0, 1)
        grid2.addWidget(self._label("Max. Kerngroesse (px2)"), 1, 0)
        self.spin_max_area = QSpinBox()
        self.spin_max_area.setRange(100, 100_000)
        self.spin_max_area.setSingleStep(100)
        self.spin_max_area.setValue(self._params.get("max_nucleus_area", 3000))
        self.spin_max_area.setSuffix(" px2")
        grid2.addWidget(self.spin_max_area, 1, 1)
        layout.addWidget(grp_seg)
        layout.addStretch()

    def _build_models_tab(self):
        from PySide6.QtWidgets import (
            QHBoxLayout, QVBoxLayout, QListWidget, QListWidgetItem,
            QPushButton, QLabel, QLineEdit, QComboBox, QMessageBox,
            QProgressBar, QSplitter
        )
        from PySide6.QtGui import QColor
        import numpy as np

        layout = QHBoxLayout(self.tab_models)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(8)

        # Linke Spalte: Modell-Liste
        left = QVBoxLayout()
        lbl = QLabel("MODELLE")
        lbl.setStyleSheet("color:#6c7086; font-size:11px; font-weight:600;")
        left.addWidget(lbl)

        self._model_list = QListWidget()
        self._model_list.setFixedWidth(250)
        self._model_list.currentItemChanged.connect(self._on_model_selected)
        left.addWidget(self._model_list, stretch=1)

        mb = QHBoxLayout()
        self._btn_activate = QPushButton("Aktivieren")
        self._btn_activate.setEnabled(False)
        self._btn_activate.clicked.connect(self._activate_model)
        self._btn_del_model = QPushButton("Loeschen")
        self._btn_del_model.setEnabled(False)
        self._btn_del_model.setStyleSheet("color:#f38ba8;")
        self._btn_del_model.clicked.connect(self._delete_model)
        mb.addWidget(self._btn_activate)
        mb.addWidget(self._btn_del_model)
        left.addLayout(mb)
        
        self._btn_edit_model = QPushButton("✏ Bearbeiten")
        self._btn_edit_model.setEnabled(False)
        self._btn_edit_model.clicked.connect(self._edit_model)
        mb.addWidget(self._btn_edit_model)

        # Neues Modell
        sep = QFrame(); sep.setFrameShape(QFrame.HLine)
        sep.setStyleSheet("background:#313244; max-height:1px;")
        left.addWidget(sep)

        lbl2 = QLabel("NEUES MODELL TRAINIEREN")
        lbl2.setStyleSheet("color:#6c7086; font-size:11px; font-weight:600;")
        left.addWidget(lbl2)
        self._edit_name = QLineEdit()
        self._edit_name.setPlaceholderText("Name (z.B. Sox9 Tibia)")
        left.addWidget(self._edit_name)
        self._edit_slice = QLineEdit()
        self._edit_slice.setPlaceholderText("Schnitt (z.B. Tibia)")
        left.addWidget(self._edit_slice)
        self._combo_stain = QComboBox()
        from stains import available_stains
        self._combo_stain.addItems(available_stains())
        left.addWidget(self._combo_stain)
        self._btn_train = QPushButton("Training starten")
        self._btn_train.setObjectName("primary")
        self._btn_train.clicked.connect(self._start_training)
        left.addWidget(self._btn_train)
        
        
        self._train_bar = QProgressBar()
        self._train_bar.setRange(0, 100)
        self._train_bar.setValue(0)
        self._train_bar.setVisible(False)
        self._train_bar.setMaximumHeight(14)
        self._train_bar.setTextVisible(True)
        left.addWidget(self._train_bar)

        self._train_eta = QLabel("")
        self._train_eta.setStyleSheet("color:#89b4fa; font-size:10px;")
        self._train_eta.setAlignment(Qt.AlignCenter)
        left.addWidget(self._train_eta)

        self._train_status = QLabel("")
        self._train_status.setStyleSheet("color:#a6adc8; font-size:10px;")
        self._train_status.setWordWrap(True)
        left.addWidget(self._train_status)

        layout.addLayout(left)

        # Rechte Spalte: Details + Referenzen
        right = QVBoxLayout()

        # Modell-Info
        self._info_grp = QGroupBox("Modell-Details")
        info_grid = QGridLayout(self._info_grp)
        self._lbl_name    = QLabel("—")
        self._lbl_stain   = QLabel("—")
        self._lbl_slice   = QLabel("—")
        self._lbl_created = QLabel("—")
        self._lbl_refs    = QLabel("—")
        self._lbl_map     = QLabel("—")
        for row, (k, v) in enumerate([
            ("Name:", self._lbl_name), ("Faerbung:", self._lbl_stain),
            ("Schnitt:", self._lbl_slice), ("Erstellt:", self._lbl_created),
            ("Referenzen:", self._lbl_refs), ("mAP50:", self._lbl_map),
        ]):
            kl = QLabel(k); kl.setStyleSheet("color:#6c7086; font-size:11px;")
            info_grid.addWidget(kl, row, 0)
            info_grid.addWidget(v, row, 1)
        
        from PySide6.QtWidgets import QTextEdit
        kl = QLabel("Notizen:"); kl.setStyleSheet("color:#6c7086; font-size:11px;")
        info_grid.addWidget(kl, 6, 0, Qt.AlignTop)
        self._txt_notes = QTextEdit()
        self._txt_notes.setMaximumHeight(70)
        self._txt_notes.setPlaceholderText("Notizen zu diesem Modell...")
        self._txt_notes.setEnabled(False)
        self._txt_notes.textChanged.connect(self._save_notes)
        info_grid.addWidget(self._txt_notes, 6, 1)

        # Neue Referenzen seit Training
        kl2 = QLabel("Status:"); kl2.setStyleSheet("color:#6c7086; font-size:11px;")
        info_grid.addWidget(kl2, 7, 0)
        self._lbl_new_refs = QLabel("—")
        info_grid.addWidget(self._lbl_new_refs, 7, 1)
        
        self._btn_retrain = QPushButton("🔄 Neu trainieren")
        self._btn_retrain.setEnabled(False)
        self._btn_retrain.setToolTip("Modell mit allen aktuellen Referenzen neu trainieren")
        self._btn_retrain.clicked.connect(self._retrain_model)
        mb.addWidget(self._btn_retrain)
        
        right.addWidget(self._info_grp)
        
        # Referenzen
        ref_grp = QGroupBox("Referenz-ROIs")
        ref_layout = QVBoxLayout(ref_grp)
        self._ref_list = QListWidget()
        self._ref_list.currentItemChanged.connect(self._on_ref_selected)
        ref_layout.addWidget(self._ref_list, stretch=1)
        self._ref_preview = QLabel("Referenz auswaehlen")
        self._ref_preview.setAlignment(Qt.AlignCenter)
        self._ref_preview.setFixedHeight(130)
        self._ref_preview.setStyleSheet(
            "background:#11111b; border:1px solid #313244; "
            "border-radius:6px; color:#45475a;")
        ref_layout.addWidget(self._ref_preview)
        rb = QHBoxLayout()
        self._btn_redraw = QPushButton("Neu einzeichnen")
        self._btn_redraw.setEnabled(False)
        self._btn_redraw.clicked.connect(self._redraw_ref)
        self._btn_del_ref = QPushButton("Entfernen")
        self._btn_del_ref.setEnabled(False)
        self._btn_del_ref.setStyleSheet("color:#f38ba8;")
        self._btn_del_ref.clicked.connect(self._delete_ref)
        rb.addWidget(self._btn_redraw)
        rb.addWidget(self._btn_del_ref)
        ref_layout.addLayout(rb)
        right.addWidget(ref_grp, stretch=1)
        layout.addLayout(right, stretch=1)
        
        self._selected_model = None
        self._reload_models()

    # ── Modell-Liste ──────────────────────────────────────────────────

    def _reload_models(self):
        from analysis.roi_model_registry import load_registry
        from PySide6.QtWidgets import QListWidgetItem
        from PySide6.QtGui import QColor, QFont
        self._model_list.clear()
        models = load_registry()
        for m in models:
            exists = Path(m["model_path"]).exists()
            active = m.get("active", False)
            label  = f"{'* ' if active else '  '}{m['name']}  [{m.get('stain','?')}]"
            if not exists: label += " (!)"
            item = QListWidgetItem(label)
            item.setData(Qt.UserRole, m)
            if active:
                item.setForeground(QColor("#a6e3a1"))
                f = item.font(); f.setBold(True); item.setFont(f)
            elif not exists:
                item.setForeground(QColor("#f38ba8"))
            self._model_list.addItem(item)
        if self._model_list.count() == 0:
            item = QListWidgetItem("Keine Modelle vorhanden")
            item.setForeground(QColor("#585b70"))
            self._model_list.addItem(item)

    def _on_model_selected(self, current, prev):
        if not current: return
        m = current.data(Qt.UserRole)
        if not m: return
        self._selected_model = m
        self._btn_activate.setEnabled(not m.get("active", False))
        self._btn_del_model.setEnabled(True)
        self._lbl_name.setText(m.get("name", "—"))
        self._lbl_stain.setText(m.get("stain", "—"))
        self._lbl_slice.setText(m.get("slice_type", "—"))
        self._lbl_created.setText(m.get("created", "")[:10])
        self._lbl_refs.setText(str(m.get("n_refs", 0)))
        self._lbl_map.setText(f"{m.get('mAP50', 0.0):.3f}")
        self._load_refs(m)
        self._btn_edit_model.setEnabled(True)
        self._txt_notes.setEnabled(True)
        self._txt_notes.blockSignals(True)
        self._txt_notes.setPlainText(m.get("notes", ""))
        self._txt_notes.blockSignals(False)
        self._btn_retrain.setEnabled(True)
        
        # Neue Referenzen seit Training berechnen
        from analysis.roi_learner import get_reference_count
        n_total    = get_reference_count()
        n_trained  = m.get("n_refs", 0)
        n_new      = max(0, n_total - n_trained)
        
        # Button hervorheben wenn neue Referenzen vorhanden
        if n_new > 0:
            self._btn_retrain.setStyleSheet(
                "QPushButton { color:#fab387; border-color:#fab387; }")
        else:
            self._btn_retrain.setStyleSheet("")

        if n_new == 0:
            self._lbl_new_refs.setText("✔ Aktuell")
            self._lbl_new_refs.setStyleSheet("color:#a6e3a1; font-size:11px;")
        else:
            self._lbl_new_refs.setText(
                f"⚠ {n_new} neue Referenzen seit letztem Training")
            self._lbl_new_refs.setStyleSheet("color:#fab387; font-size:11px;")

    def _activate_model(self):
        if not self._selected_model: return
        from analysis.roi_model_registry import set_active_model
        set_active_model(self._selected_model["id"])
        self._reload_models()

    def _delete_model(self):
        if not self._selected_model: return
        from PySide6.QtWidgets import QMessageBox
        if QMessageBox.question(
                self, "Loeschen",
                f"Modell '{self._selected_model['name']}' loeschen?",
                QMessageBox.Yes | QMessageBox.No) == QMessageBox.Yes:
            from analysis.roi_model_registry import delete_model
            delete_model(self._selected_model["id"])
            self._selected_model = None
            self._reload_models()
            
    def _save_notes(self):
        """Notizen direkt speichern beim Tippen."""
        if not self._selected_model:
            return
        from analysis.roi_model_registry import load_registry, save_registry
        models = load_registry()
        for m in models:
            if m["id"] == self._selected_model["id"]:
                m["notes"] = self._txt_notes.toPlainText()
                self._selected_model = m
                break
        save_registry(models)

    def _edit_model(self):
        """Dialog zum Bearbeiten von Name, Färbung, Schnitt."""
        if not self._selected_model:
            return
        from PySide6.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout,
                                        QGridLayout, QLineEdit, QComboBox,
                                        QPushButton, QLabel)
        dlg = QDialog(self)
        dlg.setWindowTitle("Modell bearbeiten")
        dlg.setFixedSize(380, 220)
        layout = QVBoxLayout(dlg)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(10)

        grid = QGridLayout()
        grid.addWidget(QLabel("Name:"), 0, 0)
        edit_name = QLineEdit(self._selected_model.get("name", ""))
        grid.addWidget(edit_name, 0, 1)

        grid.addWidget(QLabel("Schnitt:"), 1, 0)
        edit_slice = QLineEdit(self._selected_model.get("slice_type", ""))
        grid.addWidget(edit_slice, 1, 1)

        grid.addWidget(QLabel("Färbung:"), 2, 0)
        combo = QComboBox()
        from stains import available_stains
        combo.addItems(available_stains())
        current_stain = self._selected_model.get("stain", "")
        idx = combo.findText(current_stain)
        if idx >= 0:
            combo.setCurrentIndex(idx)
        grid.addWidget(combo, 2, 1)
        layout.addLayout(grid)

        btn_row = QHBoxLayout()
        btn_cancel = QPushButton("Abbrechen")
        btn_cancel.clicked.connect(dlg.reject)
        btn_ok = QPushButton("Speichern")
        btn_ok.setObjectName("primary")
        btn_ok.clicked.connect(dlg.accept)
        btn_row.addStretch()
        btn_row.addWidget(btn_cancel)
        btn_row.addWidget(btn_ok)
        layout.addLayout(btn_row)

        if dlg.exec():
            from analysis.roi_model_registry import load_registry, save_registry
            models = load_registry()
            for m in models:
                if m["id"] == self._selected_model["id"]:
                    m["name"]       = edit_name.text().strip() or m["name"]
                    m["slice_type"] = edit_slice.text().strip() or "Allgemein"
                    m["stain"]      = combo.currentText()
                    self._selected_model = m
                    break
            save_registry(models)
            self._reload_models()
            # Details aktualisieren
            self._lbl_name.setText(self._selected_model["name"])
            self._lbl_stain.setText(self._selected_model["stain"])
            self._lbl_slice.setText(self._selected_model["slice_type"])
            
    def _retrain_model(self):
        if not self._selected_model:
            return
        from PySide6.QtWidgets import QMessageBox
        from analysis.roi_learner import get_reference_count
        n = get_reference_count()
        reply = QMessageBox.question(
            self, "Modell neu trainieren",
            f"Modell '{self._selected_model['name']}' mit allen "
            f"{n} Referenzen neu trainieren?\n\n"
            f"Das bisherige Modell wird überschrieben.",
            QMessageBox.Yes | QMessageBox.No
        )
        if reply != QMessageBox.Yes:
            return

        self._btn_retrain.setEnabled(False)
        self._btn_train.setEnabled(False)
        self._train_bar.setVisible(True)
        self._train_status.setText("Neu-Training läuft...")

        from PySide6.QtCore import QThread, Signal as Sig

        class _RetrainWorker(QThread):
            status   = Sig(str)
            progress = Sig(int, str)   # percent, eta-string
            finished = Sig(bool, str)

            def __init__(self, model):
                super().__init__()
                self.model       = model
                self._epochs     = 100
                self._start_time = None

            def run(self):
                import time, sys, io, re
                from pathlib import Path

                try:
                    from analysis.roi_trainer import train, get_training_summary
                    from analysis.roi_learner import get_reference_count
                    from analysis.roi_model_registry import (
                        load_registry, save_registry)
                    import shutil

                    self.status.emit("Exportiere Daten...")

                    # stdout abfangen um Epochen-Fortschritt zu lesen
                    class _EpochCatcher:
                        def __init__(self_inner, worker, orig):
                            self_inner.worker = worker
                            self_inner.orig   = orig

                        def write(self_inner, text):
                            try:
                                self_inner.orig.write(text)
                                self_inner.orig.flush()
                                m = re.search(r'(\d+)/(\d+)\s+\d+G', text)
                                if m:
                                    cur   = int(m.group(1))
                                    total = int(m.group(2))
                                    pct   = int(cur / total * 100)
                                    if self_inner.worker._start_time and cur > 0:
                                        elapsed = time.time() - \
                                                  self_inner.worker._start_time
                                        eta_s = elapsed / cur * (total - cur)
                                        eta = (f"~{int(eta_s)}s" if eta_s < 60
                                               else f"~{int(eta_s/60)}min")
                                    else:
                                        eta = "..."
                                    self_inner.worker.progress.emit(
                                        pct, f"Epoche {cur}/{total}  ETA {eta}")
                            except Exception:
                                pass

                        def flush(self_inner):
                            try: self_inner.orig.flush()
                            except Exception: pass

                        def fileno(self_inner):
                            raise OSError("no fileno")

                    orig_stdout = sys.stdout
                    sys.stdout  = _EpochCatcher(self, orig_stdout)
                    self._start_time = time.time()

                    try:
                        new_path = train(epochs=100, imgsz=1024)
                    finally:
                        sys.stdout = orig_stdout

                    sm = get_training_summary() or {}
                    n  = get_reference_count()

                    shutil.copy2(new_path, self.model["model_path"])

                    models = load_registry()
                    for m in models:
                        if m["id"] == self.model["id"]:
                            m["n_refs"] = n
                            m["mAP50"]  = sm.get("mAP50", 0.0)
                            m["epochs"] = sm.get("epochs_trained", 0)
                            from datetime import datetime
                            m["updated"] = datetime.now().isoformat()
                            break
                    save_registry(models)

                    self.finished.emit(True,
                        f"✔ Neu trainiert: {n} Referenzen  "
                        f"mAP50={sm.get('mAP50', 0):.3f}")
                except Exception as e:
                    import traceback
                    traceback.print_exc()
                    self.finished.emit(False, f"✗ Fehler: {e}")

        self._retrain_worker = _RetrainWorker(self._selected_model)
        self._retrain_worker.status.connect(self._train_status.setText)
        self._retrain_worker.progress.connect(self._on_train_progress)
        self._retrain_worker.finished.connect(self._on_retrained)
        self._retrain_worker.start()
        
    def _on_train_progress(self, pct: int, eta: str):
        self._train_bar.setValue(pct)
        self._train_bar.setFormat(f"{pct}%")
        self._train_eta.setText(eta)

    def _on_retrained(self, ok: bool, msg: str):
        self._train_bar.setVisible(False)
        self._train_eta.setText("")
        self._btn_train.setEnabled(True)
        self._btn_retrain.setEnabled(True)
        self._btn_retrain.setStyleSheet("")
        self._train_status.setText(msg)
        if ok:
            self._reload_models()
            if self._selected_model:
                self._lbl_refs.setText(str(self._selected_model.get("n_refs", 0)))
                self._lbl_map.setText(f"{self._selected_model.get('mAP50', 0):.3f}")
                self._lbl_new_refs.setText("✔ Aktuell")
                self._lbl_new_refs.setStyleSheet("color:#a6e3a1; font-size:11px;")

    # ── Referenzen ────────────────────────────────────────────────────

    def _load_refs(self, model: dict):
        from analysis.roi_model_registry import get_refs_for_model
        from PySide6.QtWidgets import QListWidgetItem
        from PySide6.QtGui import QColor
        self._ref_list.clear()
        self._ref_preview.setText("Referenz auswaehlen")
        for ref in get_refs_for_model(model):
            name = Path(ref["image_path"]).name[:45]
            item = QListWidgetItem(
                f"#{ref['id']}  {name}  "
                f"cx={ref.get('centroid_x',0):.2f}")
            item.setData(Qt.UserRole, ref)
            if not Path(ref["image_path"]).exists():
                item.setForeground(QColor("#f38ba8"))
            self._ref_list.addItem(item)

    def _on_ref_selected(self, current, prev):
        if not current: return
        ref = current.data(Qt.UserRole)
        if not ref: return
        self._btn_redraw.setEnabled(True)
        self._btn_del_ref.setEnabled(True)
        self._show_ref_preview(ref)

    def _show_ref_preview(self, ref: dict):
        import numpy as np
        from PIL import Image as PilImage
        img_path = ref.get("image_path", "")
        polygon  = ref.get("polygon_normalized", [])
        if not Path(img_path).exists():
            self._ref_preview.setText("Bild nicht gefunden")
            return
        try:
            from analysis.brightfield_pipeline import load_as_uint8_rgb
            from PySide6.QtGui import QImage, QPixmap
            img = load_as_uint8_rgb(img_path)
            h, w = img.shape[:2]
            MAX = 280
            if max(h, w) > MAX:
                s = MAX / max(h, w)
                img = np.array(PilImage.fromarray(img).resize(
                    (int(w*s), int(h*s)), PilImage.LANCZOS))
                h, w = img.shape[:2]
            if polygon:
                from PIL import ImageDraw as PilDraw
                pil = PilImage.fromarray(img)
                pts = [(int(x*w), int(y*h)) for x, y in polygon]
                PilDraw.Draw(pil).line(pts + [pts[0]],
                                       fill=(0, 255, 100), width=2)
                img = np.array(pil)
            qimg = QImage(img.tobytes(), w, h, w*3, QImage.Format_RGB888)
            px   = QPixmap.fromImage(qimg)
            lw, lh = self._ref_preview.width(), self._ref_preview.height()
            self._ref_preview.setPixmap(
                px.scaled(lw, lh, Qt.KeepAspectRatio,
                          Qt.SmoothTransformation))
        except Exception as e:
            self._ref_preview.setText(f"Fehler: {e}")

    def _delete_ref(self):
        item = self._ref_list.currentItem()
        if not item: return
        ref = item.data(Qt.UserRole)
        from PySide6.QtWidgets import QMessageBox
        if QMessageBox.question(
                self, "Loeschen",
                f"Referenz #{ref['id']} loeschen?",
                QMessageBox.Yes | QMessageBox.No) == QMessageBox.Yes:
            from analysis.roi_learner import delete_reference
            delete_reference(ref["id"])
            if self._selected_model:
                self._load_refs(self._selected_model)

    def _redraw_ref(self):
        item = self._ref_list.currentItem()
        if not item: return
        ref      = item.data(Qt.UserRole)
        img_path = ref["image_path"]
        import numpy as np
        from PySide6.QtWidgets import QMessageBox
        if not Path(img_path).exists():
            QMessageBox.warning(self, "Fehler",
                                f"Bild nicht gefunden:\n{img_path}")
            return
        from ui.roi_dialog import ROIDialog
        from analysis.brightfield_pipeline import load_as_uint8_rgb
        try:
            gray = load_as_uint8_rgb(img_path).max(axis=-1)
        except Exception as e:
            QMessageBox.warning(self, "Fehler", str(e)); return
        dlg = ROIDialog(img_path, parent=self)
        dlg._dapi_array = gray
        dlg._refresh_canvas()
        polygon = ref.get("polygon_normalized", [])
        if polygon:
            dlg.canvas.load_polygon(polygon)
            dlg.canvas._closed = True
            dlg._on_polygon_changed()

        def _confirmed(pts):
            from analysis.roi_learner import load_references, get_index_path
            import json
            refs = load_references()
            for r in refs:
                if r["id"] == ref["id"]:
                    arr = np.array(pts)
                    r["polygon_normalized"] = pts
                    r["centroid_x"] = float(arr[:,0].mean())
                    r["centroid_y"] = float(arr[:,1].mean())
                    r["width_rel"]  = float(arr[:,0].max()-arr[:,0].min())
                    r["height_rel"] = float(arr[:,1].max()-arr[:,1].min())
                    break
            with open(get_index_path(), "w") as f:
                json.dump(refs, f, indent=2)
            if self._selected_model:
                self._load_refs(self._selected_model)

        dlg.roi_confirmed.connect(_confirmed)
        dlg.exec()

    # ── Training ──────────────────────────────────────────────────────

    def _start_training(self):
        name  = self._edit_name.text().strip()
        stain = self._combo_stain.currentText()
        sl    = self._edit_slice.text().strip() or "Allgemein"
        from PySide6.QtWidgets import QMessageBox
        if not name:
            QMessageBox.warning(self, "Fehler", "Bitte Modell-Namen eingeben.")
            return
        from analysis.roi_learner import get_reference_count
        if get_reference_count() < 4:
            QMessageBox.warning(self, "Fehler",
                                "Mindestens 4 Referenzen benoetigt.")
            return
        self._btn_train.setEnabled(False)
        self._train_bar.setVisible(True)
        self._train_status.setText("Training laeuft...")

        from PySide6.QtCore import QThread, QObject, Signal as Sig

        class _Worker(QThread):
            status   = Sig(str)
            finished = Sig(bool, str)
            def __init__(self, n, s, sl):
                super().__init__()
                self.n, self.s, self.sl = n, s, sl
            def run(self):
                try:
                    from analysis.roi_trainer import train, get_training_summary
                    from analysis.roi_learner import get_reference_count
                    from analysis.roi_model_registry import register_model
                    self.status.emit("Exportiere Daten...")
                    mp = train(epochs=100, imgsz=1024)
                    sm = get_training_summary() or {}
                    register_model(self.n, self.s, self.sl, mp,
                                   get_reference_count(),
                                   sm.get("mAP50", 0.0),
                                   sm.get("epochs_trained", 0))
                    self.finished.emit(True,
                        f"Modell '{self.n}' trainiert! mAP50={sm.get('mAP50',0):.3f}")
                except Exception as e:
                    self.finished.emit(False, f"Fehler: {e}")

        self._worker = _Worker(name, stain, sl)
        self._worker.status.connect(self._train_status.setText)
        self._worker.finished.connect(self._on_trained)
        self._worker.start()

    def _on_trained(self, ok: bool, msg: str):
        self._train_bar.setVisible(False)
        self._btn_train.setEnabled(True)
        self._train_status.setText(msg)
        if ok:
            self._reload_models()

    # ── Helpers ───────────────────────────────────────────────────────

    @staticmethod
    def _label(title: str) -> QLabel:
        lbl = QLabel(title)
        lbl.setCursor(Qt.WhatsThisCursor)
        return lbl

    def _reset(self):
        self.spin_frac.setValue(0.10)
        self.spin_min_area.setValue(40)
        self.spin_max_area.setValue(3000)

    def _accept(self):
        self._params["positive_fraction"] = round(self.spin_frac.value(), 3)
        self._params["min_nucleus_area"]  = self.spin_min_area.value()
        self._params["max_nucleus_area"]  = self.spin_max_area.value()
        self.accept()

    def get_params(self) -> dict:
        return dict(self._params)


# Import fuer Path
from pathlib import Path