# ui/settings_dialog.py

from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QGridLayout,
    QLabel, QPushButton, QDoubleSpinBox, QSpinBox,
    QGroupBox, QFrame, QTabWidget, QWidget
)
from PySide6.QtCore import Qt
import os


class SettingsDialog(QDialog):

    def __init__(self, params: dict, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Einstellungen")
        self.setMinimumSize(980, 650)
        self.setModal(True)
        self._params = dict(params)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(8)

        self.tabs                   = QTabWidget()
        self.tab_pipeline           = QWidget()
        self.tab_models             = QWidget()
        self.tab_threshold_strategy = QWidget()
        self.tab_sample_exceptions  = QWidget()
        self.tab_help               = QWidget()
        self._build_pipeline_tab()
        self._build_models_tab()
        self._build_threshold_strategy_tab()
        self._build_sample_exceptions_tab()
        self.tabs.addTab(self.tab_pipeline,            "⚙  Pipeline")
        self.tabs.addTab(self.tab_models,              "🤖  Modell-Manager")
        self.tabs.addTab(self.tab_threshold_strategy,  "📊  Threshold-Strategie")
        self.tabs.addTab(self.tab_sample_exceptions,   "⚠  Proben-Ausnahmen")
        self.tabs.addTab(self.tab_help,                "❓  Hilfe & Feedback")
        self._build_help_tab()
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
        self.tabs.setStyleSheet("""
            QTabWidget::pane {
                border: 1px solid #45475a;
                border-radius: 0 6px 6px 6px;
                background: #1e1e2e;
            }
            QTabBar::tab {
                background: #181825;
                color: #585b70;
                border: 1px solid #313244;
                border-bottom: none;
                padding: 8px 18px;
                border-radius: 6px 6px 0 0;
                font-size: 12px;
                margin-right: 2px;
            }
            QTabBar::tab:selected {
                background: #1e3a5f;
                color: #89b4fa;
                font-weight: 700;
                border: 1px solid #89b4fa;
                border-bottom: none;
            }
            QTabBar::tab:hover:!selected {
                background: #262637;
                color: #a6adc8;
            }
        """)

    def _on_tab_changed(self, idx):
        is_models = (idx == 1)
        self.btn_reset.setVisible(idx == 0)
        self.btn_ok.setVisible(not is_models)


    def _wrap_tab_in_scroll(self, tab_widget: QWidget):
        """Wickelt den Inhalt eines Tabs in ein QScrollArea ein."""
        from PySide6.QtWidgets import QScrollArea, QFrame
        # Alle aktuellen Kinder-Widgets und Layout holen
        old_layout = tab_widget.layout()
        if old_layout is None:
            return
        
        # Inner widget mit altem Layout
        inner = QWidget()
        inner.setLayout(old_layout)
        
        # ScrollArea erstellen
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.NoFrame)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        scroll.setStyleSheet(
            "QScrollArea { background: transparent; border: none; }"
            "QScrollBar:vertical { background: #313244; width: 8px; border-radius: 4px; }"
            "QScrollBar::handle:vertical { background: #585b70; border-radius: 4px; min-height: 20px; }"
            "QScrollBar::handle:vertical:hover { background: #89b4fa; }"
            "QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical { height: 0; }"
        )
        scroll.setWidget(inner)
        
        # Neues Layout für den Tab
        new_layout = QVBoxLayout(tab_widget)
        new_layout.setContentsMargins(0, 0, 0, 0)
        new_layout.setSpacing(0)
        new_layout.addWidget(scroll)


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
        # In _build_ui, nach dem min_nucleus_area SpinBox:
        
        # Auto-ROI Timer
        grp_roi = QGroupBox("Auto-ROI")
        grid3 = QGridLayout(grp_roi)
        grid3.setSpacing(8)
        
        grid3.addWidget(self._label(
            "Countdown-Timer (Sekunden)",
            "Zeit bis die vorgeschlagene ROI automatisch\n"
            "übernommen wird und die Analyse startet."
        ), 0, 0)
        self.spin_timer = QSpinBox()
        self.spin_timer.setRange(3, 60)
        self.spin_timer.setSingleStep(1)
        self.spin_timer.setValue(self._params.get("auto_roi_timer", 7))
        self.spin_timer.setSuffix(" s")
        grid3.addWidget(self.spin_timer, 0, 1)
        
        layout.addWidget(grp_roi)
        
        grp_seg = QGroupBox("Segmentierung")
        grid4 = QGridLayout(grp_seg)
        grid4.setSpacing(8)
        
        grid4.addWidget(self._label(
            "Segmentierungsmodell",
            "StarDist: genauer, langsamer (TensorFlow)\n"
            "Watershed: schneller, kein TensorFlow\n"
            "Auto: StarDist wenn ROI vorhanden, sonst Watershed"
        ), 0, 0)
        
        from PySide6.QtWidgets import QComboBox
        self.combo_seg = QComboBox()
        self.combo_seg.addItems(["Auto", "StarDist", "Watershed"])
        current = self._params.get("segmentation_model", "Auto")
        self.combo_seg.setCurrentText(current)
        grid4.addWidget(self.combo_seg, 0, 1)
        
        # Sprache
        grp_lang = QGroupBox("Sprache / Language")
        lang_grid = QGridLayout(grp_lang)
        from PySide6.QtWidgets import QComboBox
        self.combo_lang = QComboBox()
        self.combo_lang.addItems(["Deutsch 🇩🇪", "English 🇬🇧"])
        current_lang = self._params.get("language", "de")
        self.combo_lang.setCurrentIndex(0 if current_lang == "de" else 1)
        lang_grid.addWidget(QLabel("Sprache:"), 0, 0)
        lang_grid.addWidget(self.combo_lang, 0, 1)
        layout.addWidget(grp_lang)
        layout.addWidget(grp_seg)

        # ── Ordnerstruktur ────────────────────────────────────────────
        from PySide6.QtWidgets import QCheckBox, QLineEdit
        grp_folders = QGroupBox("Ordnerstruktur")
        folders_grid = QGridLayout(grp_folders)
        folders_grid.setSpacing(8)

        self.chk_subfolders = QCheckBox("Unterordner analysieren")
        self.chk_subfolders.setChecked(
            self._params.get("use_subfolders", True))
        self.chk_subfolders.setToolTip(
            "An: Jeder Unterordner = eine Probe\n"
            "Aus: Alle Bilder direkt im gewählten Ordner = je eine Probe")
        folders_grid.addWidget(self.chk_subfolders, 0, 0, 1, 2)

        folders_grid.addWidget(self._label(
            "Ordner-Keyword",
            "Nur Unterordner die diesen Text enthalten.\n"
            "Leer = alle Unterordner."
        ), 1, 0)
        self.edit_folder_keyword = QLineEdit()
        self.edit_folder_keyword.setPlaceholderText("leer = alle Unterordner")
        self.edit_folder_keyword.setText(
            self._params.get("folder_keyword", ""))
        folders_grid.addWidget(self.edit_folder_keyword, 1, 1)

        self.chk_iso = QCheckBox("Iso-Kontrollen paaren")
        self.chk_iso.setChecked(
            self._params.get("use_iso_pairing", True))
        self.chk_iso.setToolTip(
            "Automatisch Iso-Kontroll-Ordner/-Bilder finden\n"
            "und für Threshold-Kalibrierung verwenden.")
        folders_grid.addWidget(self.chk_iso, 2, 0, 1, 2)

        folders_grid.addWidget(self._label(
            "Iso-Keyword",
            "Unterordner/Bilder die diesen Text enthalten\n"
            "werden als Iso-Kontrollen behandelt."
        ), 3, 0)
        self.edit_iso_keyword = QLineEdit()
        self.edit_iso_keyword.setPlaceholderText("iso")
        self.edit_iso_keyword.setText(
            self._params.get("iso_keyword", "iso"))
        folders_grid.addWidget(self.edit_iso_keyword, 3, 1)

        def _update_folder_widgets():
            self.edit_folder_keyword.setEnabled(
                self.chk_subfolders.isChecked())
            self.edit_iso_keyword.setEnabled(
                self.chk_iso.isChecked())

        self.chk_subfolders.toggled.connect(_update_folder_widgets)
        self.chk_iso.toggled.connect(_update_folder_widgets)
        _update_folder_widgets()

        layout.addWidget(grp_folders)
        layout.addStretch()
        self._wrap_tab_in_scroll(self.tab_pipeline)

    def _build_threshold_strategy_tab(self):
        from PySide6.QtWidgets import (
            QVBoxLayout, QHBoxLayout, QGroupBox, QGridLayout,
            QRadioButton, QButtonGroup, QSpinBox, QLabel,
            QPushButton, QComboBox
        )
        layout = QVBoxLayout(self.tab_threshold_strategy)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(12)

        # Info
        info = QLabel(
            "Legt fest wie der Threshold aus den Iso-Kontrollen berechnet wird.\n"
            "Diese Einstellung gilt für alle Batch-Analysen."
        )
        info.setWordWrap(True)
        info.setStyleSheet("color:#a6adc8; font-size:11px;")
        layout.addWidget(info)

        # Methoden-Gruppe
        grp_method = QGroupBox("Berechnungsmethode")
        method_layout = QVBoxLayout(grp_method)
        method_layout.setSpacing(10)

        self._thr_group = QButtonGroup(self)

        methods = [
            ("median_all",    "Median aller Iso-Kontrollen  (empfohlen)",
             "Robuster Median über alle Iso-Kontrollen des gleichen Färbezyklus.\n"
             "Ausreißer werden automatisch ignoriert."),
            ("mean_all",      "Mittelwert aller Iso-Kontrollen",
             "Arithmetischer Mittelwert aller Iso-Kontrollen.\n"
             "Empfindlicher gegenüber Ausreißern als der Median."),
            ("median_n",      "Median der N nächsten Iso-Kontrollen",
             "Verwendet nur die N zeitlich/räumlich nächsten Iso-Kontrollen.\n"
             "Nützlich wenn sich Bedingungen über einen Lauf verändern."),
            ("individual",    "Nur die direkt zugehörige Iso-Kontrolle",
             "Jede Probe bekommt den Threshold ihrer eigenen Iso-Kontrolle.\n"
             "Höchste Sensitivität, aber anfällig für schlechte Einzelmessungen."),
            ("manual",        "Manuell gesetzter Threshold",
             "Der im Threshold-Dialog manuell gesetzte Wert wird verwendet.\n"
             "Keine automatische Kalibrierung über Iso-Kontrollen."),
        ]

        current = self._params.get("threshold_strategy", "median_all")

        for key, label, tooltip in methods:
            rb = QRadioButton(label)
            rb.setToolTip(tooltip)
            rb.setProperty("strategy_key", key)
            if key == current:
                rb.setChecked(True)
            rb.setStyleSheet("""
                QRadioButton {
                    color: #a6adc8;
                    padding: 6px 8px;
                    border-radius: 6px;
                    font-size: 12px;
                }
                QRadioButton:hover {
                    background: #313244;
                    color: #cdd6f4;
                }
                QRadioButton:checked {
                    background: #1e3a5f;
                    color: #89b4fa;
                    font-weight: 700;
                    border: 1px solid #89b4fa;
                }
                QRadioButton::indicator {
                    width: 14px;
                    height: 14px;
                }
                QRadioButton::indicator:checked {
                    background: #89b4fa;
                    border-radius: 7px;
                    border: 2px solid #1e1e2e;
                }
                QRadioButton::indicator:unchecked {
                    border: 2px solid #45475a;
                    border-radius: 7px;
                    background: #313244;
                }
            """)
            self._thr_group.addButton(rb)
            method_layout.addWidget(rb)

            # Zusatz-Spinbox für median_n
            if key == "median_n":
                n_row = QHBoxLayout()
                n_row.addSpacing(24)
                n_row.addWidget(QLabel("N ="))
                self.spin_thr_n = QSpinBox()
                self.spin_thr_n.setRange(2, 20)
                self.spin_thr_n.setValue(
                    self._params.get("threshold_n_nearest", 3))
                self.spin_thr_n.setFixedWidth(70)
                self.spin_thr_n.setSuffix(" Iso-Kontrollen")
                self.spin_thr_n.setEnabled(key == current)
                n_row.addWidget(self.spin_thr_n)
                n_row.addStretch()
                method_layout.addLayout(n_row)
                rb.toggled.connect(
                    lambda checked, s=self.spin_thr_n: s.setEnabled(checked))

            # Zusatz-Spinbox für manual
            if key == "manual":
                man_row = QHBoxLayout()
                man_row.addSpacing(24)
                man_row.addWidget(QLabel("Threshold-Wert:"))
                self.spin_manual_thr = QSpinBox()
                self.spin_manual_thr.setRange(1, 255)
                self.spin_manual_thr.setValue(
                    self._params.get("manual_threshold_value", 60))
                self.spin_manual_thr.setFixedWidth(70)
                self.spin_manual_thr.setEnabled(key == current)
                man_row.addWidget(self.spin_manual_thr)
                man_row.addStretch()
                method_layout.addLayout(man_row)
                rb.toggled.connect(
                    lambda checked, s=self.spin_manual_thr:
                    s.setEnabled(checked))

        layout.addWidget(grp_method)

        # Warnschwelle
        grp_warn = QGroupBox("Warnungen bei Abweichung")
        warn_grid = QGridLayout(grp_warn)
        warn_grid.addWidget(self._label(
            "Warnschwelle (%)",
            "Warnung erscheint wenn eine Iso-Kontrolle mehr als X%\n"
            "vom Zyklus-Median abweicht."
        ), 0, 0)
        self.spin_warn_pct = QSpinBox()
        self.spin_warn_pct.setRange(5, 100)
        self.spin_warn_pct.setValue(
            self._params.get("threshold_warn_pct", 20))
        self.spin_warn_pct.setSuffix(" %")
        warn_grid.addWidget(self.spin_warn_pct, 0, 1)

        warn_grid.addWidget(self._label(
            "n_sigma",
            "Anzahl Standardabweichungen über dem Mittelwert\n"
            "für die Iso-Threshold-Berechnung."
        ), 1, 0)
        self.spin_nsigma = QDoubleSpinBox()
        self.spin_nsigma.setRange(0.5, 5.0)
        self.spin_nsigma.setSingleStep(0.5)
        self.spin_nsigma.setDecimals(1)
        self.spin_nsigma.setValue(
            self._params.get("threshold_n_sigma", 2.0))
        warn_grid.addWidget(self.spin_nsigma, 1, 1)
        layout.addWidget(grp_warn)

        # ── Fallback-Threshold ────────────────────────────────────────
        from i18n import t
        grp_fallback = QGroupBox(t("fallback_title"))
        fallback_layout = QVBoxLayout(grp_fallback)
        fallback_layout.setSpacing(8)

        fallback_info = QLabel(
            "Wird verwendet wenn für eine Probe keine Iso-Kontrolle "
            "gefunden werden kann."
        )
        fallback_info.setWordWrap(True)
        fallback_info.setStyleSheet("color:#a6adc8; font-size:11px;")
        fallback_layout.addWidget(fallback_info)

        self._fallback_group = QButtonGroup(self)
        current_fallback = self._params.get("fallback_strategy", "fixed")

        rb_style = """
            QRadioButton {
                color: #a6adc8; padding: 6px 8px;
                border-radius: 6px; font-size: 12px;
            }
            QRadioButton:hover { background: #313244; color: #cdd6f4; }
            QRadioButton:checked {
                background: #1e3a5f; color: #89b4fa;
                font-weight: 700; border: 1px solid #89b4fa;
            }
            QRadioButton::indicator { width: 14px; height: 14px; }
            QRadioButton::indicator:checked {
                background: #89b4fa; border-radius: 7px;
                border: 2px solid #1e1e2e;
            }
            QRadioButton::indicator:unchecked {
                border: 2px solid #45475a; border-radius: 7px;
                background: #313244;
            }
        """

        fallback_methods = [
            ("fixed",    t("fallback_fixed"),
             "Immer denselben festen Wert verwenden."),
            ("otsu",     t("fallback_otsu"),
             "Otsu-Schwellenwert automatisch aus dem Probenbild berechnen."),
            ("mean",     t("fallback_mean"),
             "Mittelwert über alle Proben-Bilder des aktuellen Ordners."),
            ("median",   "Median aller Proben-Bilder",
             "Median über alle Proben-Bilder des aktuellen Ordners."),
            ("filename", t("fallback_filename"),
             "Sucht die Iso-Kontrolle mit dem ähnlichsten Ordnernamen."),
            ("content",  t("fallback_content"),
             "Vergleicht Bildhistogramme um die ähnlichste Iso-Kontrolle\n"
             "zu finden – robuster als Dateiname-Matching."),
        ]

        for key, label, tooltip in fallback_methods:
            rb = QRadioButton(label)
            rb.setToolTip(tooltip)
            rb.setProperty("fallback_key", key)
            rb.setStyleSheet(rb_style)
            if key == current_fallback:
                rb.setChecked(True)
            self._fallback_group.addButton(rb)
            fallback_layout.addWidget(rb)

            if key == "fixed":
                fix_row = QHBoxLayout()
                fix_row.addSpacing(24)
                fix_row.addWidget(QLabel("Wert:"))
                self.spin_fallback_val = QSpinBox()
                self.spin_fallback_val.setRange(1, 255)
                self.spin_fallback_val.setValue(
                    self._params.get("fallback_fixed_value", 60))
                self.spin_fallback_val.setFixedWidth(70)
                self.spin_fallback_val.setEnabled(key == current_fallback)
                fix_row.addWidget(self.spin_fallback_val)
                fix_row.addStretch()
                fallback_layout.addLayout(fix_row)
                rb.toggled.connect(
                    lambda checked, s=self.spin_fallback_val:
                    s.setEnabled(checked))

        layout.addWidget(grp_fallback)

        info_save = QLabel("✔  Änderungen werden mit 'Übernehmen' gespeichert.")
        info_save.setStyleSheet("color:#585b70; font-size:10px;")
        layout.addWidget(info_save)
        layout.addStretch()
        self._wrap_tab_in_scroll(self.tab_threshold_strategy)

    def _save_threshold_strategy(self):
        for btn in self._thr_group.buttons():
            if btn.isChecked():
                self._params["threshold_strategy"] = \
                    btn.property("strategy_key")
                break
        self._params["threshold_n_nearest"] = self.spin_thr_n.value()
        self._params["threshold_warn_pct"]  = self.spin_warn_pct.value()
        self._params["threshold_n_sigma"]   = self.spin_nsigma.value()
        from PySide6.QtWidgets import QMessageBox
        QMessageBox.information(
            self, "Gespeichert",
            f"Threshold-Strategie: "
            f"{self._params['threshold_strategy']}\n"
            f"n_sigma: {self._params['threshold_n_sigma']}\n"
            f"Warnschwelle: {self._params['threshold_warn_pct']}%"
        )

    def _build_models_tab(self):
        from PySide6.QtWidgets import (
            QHBoxLayout, QVBoxLayout, QListWidget, QListWidgetItem,
            QPushButton, QLabel, QLineEdit, QComboBox, QMessageBox,
            QProgressBar, QSplitter, QFrame, QScrollArea, QTextEdit
        )
        from PySide6.QtGui import QColor

        # Haupt-Layout: zwei Spalten nebeneinander
        layout = QHBoxLayout(self.tab_models)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        scroll_style = (
            "QScrollArea { background: transparent; border: none; }"
            "QScrollBar:vertical { background:#313244; width:6px; border-radius:3px; }"
            "QScrollBar::handle:vertical { background:#585b70; border-radius:3px; min-height:20px; }"
            "QScrollBar::handle:vertical:hover { background:#89b4fa; }"
            "QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical { height:0; }"
        )

        # ── LINKE SPALTE ──────────────────────────────────────────────
        left_inner = QWidget()
        left = QVBoxLayout(left_inner)
        left.setContentsMargins(8, 8, 4, 8)
        left.setSpacing(6)

        lbl = QLabel("MODELLE")
        lbl.setStyleSheet("color:#6c7086; font-size:11px; font-weight:600;")
        left.addWidget(lbl)

        self._model_list = QListWidget()
        self._model_list.setMinimumHeight(120)
        self._model_list.currentItemChanged.connect(self._on_model_selected)
        left.addWidget(self._model_list, stretch=1)

        # Modell-Buttons Zeile 1
        mb1 = QHBoxLayout()
        self._btn_export_model = QPushButton("📦 Exportieren")
        self._btn_export_model.setEnabled(False)
        self._btn_export_model.setToolTip("Modell + Referenzen als .zip exportieren")
        self._btn_export_model.clicked.connect(self._export_model)
        mb1.addWidget(self._btn_export_model)
        btn_import = QPushButton("📥 Importieren")
        btn_import.clicked.connect(self._import_model)
        mb1.addWidget(btn_import)
        left.addLayout(mb1)

        # Modell-Buttons Zeile 2
        mb2 = QHBoxLayout()
        self._btn_activate = QPushButton("Aktivieren")
        self._btn_activate.setEnabled(False)
        self._btn_activate.clicked.connect(self._activate_model)
        mb2.addWidget(self._btn_activate)
        self._btn_edit_model = QPushButton("✏ Bearbeiten")
        self._btn_edit_model.setEnabled(False)
        self._btn_edit_model.clicked.connect(self._edit_model)
        mb2.addWidget(self._btn_edit_model)
        self._btn_del_model = QPushButton("Löschen")
        self._btn_del_model.setEnabled(False)
        self._btn_del_model.setStyleSheet("color:#f38ba8;")
        self._btn_del_model.clicked.connect(self._delete_model)
        mb2.addWidget(self._btn_del_model)
        left.addLayout(mb2)

        # mb alias für _btn_retrain (wird später hinzugefügt)
        mb = mb2

        sep2 = QFrame(); sep2.setFrameShape(QFrame.HLine)
        sep2.setStyleSheet("background:#313244; max-height:1px; border:none;")
        left.addWidget(sep2)

        lbl3 = QLabel("REFERENZEN")
        lbl3.setStyleSheet("color:#6c7086; font-size:11px; font-weight:600;")
        left.addWidget(lbl3)
        self._lbl_ref_count = QLabel("0 Referenzen gespeichert")
        self._lbl_ref_count.setStyleSheet("color:#a6adc8; font-size:11px;")
        left.addWidget(self._lbl_ref_count)
        self._update_ref_count()
        btn_clear_refs = QPushButton("🗑  Alle Referenzen löschen")
        btn_clear_refs.setStyleSheet("color:#f38ba8;")
        btn_clear_refs.clicked.connect(self._clear_all_refs)
        left.addWidget(btn_clear_refs)

        sep = QFrame(); sep.setFrameShape(QFrame.HLine)
        sep.setStyleSheet("background:#313244; max-height:1px; border:none;")
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

        # Trainings-Fortschritt Box
        self._train_grp = QFrame()
        self._train_grp.setStyleSheet(
            "QFrame { background:#181825; border:1px solid #313244; "
            "border-radius:8px; }")
        self._train_grp.setVisible(False)
        tg = QVBoxLayout(self._train_grp)
        tg.setSpacing(5)
        tg.setContentsMargins(10, 8, 10, 8)
        self._train_step = QLabel("Exportiere Daten...")
        self._train_step.setStyleSheet(
            "color:#cdd6f4; font-size:11px; font-weight:600; border:none;")
        tg.addWidget(self._train_step)
        self._train_bar = QProgressBar()
        self._train_bar.setRange(0, 100)
        self._train_bar.setValue(0)
        self._train_bar.setTextVisible(False)
        self._train_bar.setFixedHeight(10)
        self._train_bar.setStyleSheet(
            "QProgressBar { background:#313244; border-radius:5px; border:none; }"
            "QProgressBar::chunk { background:#89b4fa; border-radius:5px; }")
        tg.addWidget(self._train_bar)
        epoch_row = QHBoxLayout()
        self._train_epoch_lbl = QLabel("Epoche 0 / 100")
        self._train_epoch_lbl.setStyleSheet(
            "color:#89b4fa; font-size:10px; font-weight:600; border:none;")
        epoch_row.addWidget(self._train_epoch_lbl)
        epoch_row.addStretch()
        self._train_pct_lbl = QLabel("0%")
        self._train_pct_lbl.setStyleSheet(
            "color:#a6adc8; font-size:10px; border:none;")
        epoch_row.addWidget(self._train_pct_lbl)
        tg.addLayout(epoch_row)
        self._train_metrics = QLabel("")
        self._train_metrics.setStyleSheet(
            "color:#6c7086; font-size:10px; border:none;")
        tg.addWidget(self._train_metrics)
        left.addWidget(self._train_grp)

        self._train_eta = QLabel("")
        self._train_eta.setStyleSheet("color:#89b4fa; font-size:10px; border:none;")
        self._train_eta.setAlignment(Qt.AlignCenter)
        left.addWidget(self._train_eta)
        self._train_status = QLabel("")
        self._train_status.setStyleSheet("color:#a6adc8; font-size:10px; border:none;")
        self._train_status.setWordWrap(True)
        left.addWidget(self._train_status)
        left.addStretch()

        left_scroll = QScrollArea()
        left_scroll.setWidgetResizable(True)
        left_scroll.setFrameShape(QFrame.NoFrame)
        left_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        left_scroll.setMinimumWidth(320)
        left_scroll.setMaximumWidth(380)
        left_scroll.setStyleSheet(scroll_style)
        left_scroll.setWidget(left_inner)
        layout.addWidget(left_scroll, stretch=2)

        # Trennlinie
        div = QFrame()
        div.setFrameShape(QFrame.VLine)
        div.setStyleSheet("background:#313244; max-width:1px; border:none;")
        layout.addWidget(div)

        # ── RECHTE SPALTE ─────────────────────────────────────────────
        right_inner = QWidget()
        right = QVBoxLayout(right_inner)
        right.setContentsMargins(8, 8, 8, 8)
        right.setSpacing(8)

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
            ("Name:", self._lbl_name), ("Färbung:", self._lbl_stain),
            ("Schnitt:", self._lbl_slice), ("Erstellt:", self._lbl_created),
            ("Referenzen:", self._lbl_refs), ("mAP50:", self._lbl_map),
        ]):
            kl = QLabel(k)
            kl.setStyleSheet("color:#6c7086; font-size:11px;")
            info_grid.addWidget(kl, row, 0)
            info_grid.addWidget(v, row, 1)

        kl = QLabel("Notizen:")
        kl.setStyleSheet("color:#6c7086; font-size:11px;")
        info_grid.addWidget(kl, 6, 0, Qt.AlignTop)
        self._txt_notes = QTextEdit()
        self._txt_notes.setMaximumHeight(70)
        self._txt_notes.setPlaceholderText("Notizen zu diesem Modell...")
        self._txt_notes.setEnabled(False)
        self._txt_notes.textChanged.connect(self._save_notes)
        info_grid.addWidget(self._txt_notes, 6, 1)

        kl2 = QLabel("Status:")
        kl2.setStyleSheet("color:#6c7086; font-size:11px;")
        info_grid.addWidget(kl2, 7, 0)
        self._lbl_new_refs = QLabel("—")
        info_grid.addWidget(self._lbl_new_refs, 7, 1)

        self._btn_retrain = QPushButton("🔄 Neu trainieren")
        self._btn_retrain.setEnabled(False)
        self._btn_retrain.setToolTip("Modell mit allen aktuellen Referenzen neu trainieren")
        self._btn_retrain.clicked.connect(self._retrain_model)
        info_grid.addWidget(self._btn_retrain, 8, 0, 1, 2)

        right.addWidget(self._info_grp)

        # Referenzen
        ref_grp = QGroupBox("Referenz-ROIs")
        ref_layout = QVBoxLayout(ref_grp)
        self._ref_list = QListWidget()
        self._ref_list.setMinimumHeight(80)
        self._ref_list.currentItemChanged.connect(self._on_ref_selected)
        ref_layout.addWidget(self._ref_list, stretch=1)
        self._ref_preview = QLabel("Referenz auswählen")
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
        right.addStretch()

        right_scroll = QScrollArea()
        right_scroll.setWidgetResizable(True)
        right_scroll.setFrameShape(QFrame.NoFrame)
        right_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        right_scroll.setMinimumWidth(280)
        right_scroll.setStyleSheet(scroll_style)
        right_scroll.setWidget(right_inner)
        layout.addWidget(right_scroll, stretch=3)

        self._selected_model = None
        self._reload_models()

    def _build_sample_exceptions_tab(self):
        from PySide6.QtWidgets import (
            QVBoxLayout, QHBoxLayout, QGroupBox, QGridLayout,
            QTableWidget, QTableWidgetItem, QPushButton,
            QLineEdit, QComboBox, QLabel, QHeaderView,
            QCheckBox
        )
        layout = QVBoxLayout(self.tab_sample_exceptions)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(12)

        info = QLabel(
            "Definiere Ausnahmen für bestimmte Proben.\n"
            "Proben die einem Filter entsprechen bekommen eine "
            "Sonderbehandlung (anderer Threshold, keine ROI, etc.)"
        )
        info.setWordWrap(True)
        info.setStyleSheet("color:#a6adc8; font-size:11px;")
        layout.addWidget(info)

        # Neue Ausnahme hinzufügen
        grp_add = QGroupBox("Neue Ausnahme")
        add_grid = QGridLayout(grp_add)
        add_grid.setSpacing(8)

        add_grid.addWidget(QLabel("Filter-Typ:"), 0, 0)
        self._exc_type = QComboBox()
        self._exc_type.addItems([
            "Text im Namen enthält",
            "Text im Namen beginnt mit",
            "Text im Namen endet mit",
            "Regulärer Ausdruck",
        ])
        add_grid.addWidget(self._exc_type, 0, 1)

        add_grid.addWidget(QLabel("Wert:"), 1, 0)
        self._exc_value = QLineEdit()
        self._exc_value.setPlaceholderText(
            "z.B. 'Ctrl', 'neg', 'Export-5', '^Q2-3.*'")
        add_grid.addWidget(self._exc_value, 1, 1)

        add_grid.addWidget(QLabel("Aktion:"), 2, 0)
        self._exc_action = QComboBox()
        self._exc_action.addItems([
            "Ganzes Bild (keine ROI)",
            "Manueller Threshold",
            "Überspringen (nicht analysieren)",
            "Nur Watershed (kein StarDist)",
        ])
        add_grid.addWidget(self._exc_action, 2, 1)

        # Threshold-Wert (nur sichtbar bei "Manueller Threshold")
        self._exc_thr_label = QLabel("Threshold-Wert:")
        add_grid.addWidget(self._exc_thr_label, 3, 0)
        self._exc_thr_val = QSpinBox()
        self._exc_thr_val.setRange(1, 255)
        self._exc_thr_val.setValue(60)
        self._exc_thr_val.setFixedWidth(80)
        add_grid.addWidget(self._exc_thr_val, 3, 1)
        self._exc_thr_label.setVisible(False)
        self._exc_thr_val.setVisible(False)
        self._exc_action.currentIndexChanged.connect(
            lambda i: (
                self._exc_thr_label.setVisible(i == 1),
                self._exc_thr_val.setVisible(i == 1)
            ))

        add_grid.addWidget(QLabel("Notiz (optional):"), 4, 0)
        self._exc_note = QLineEdit()
        self._exc_note.setPlaceholderText("z.B. 'Negativkontrolle'")
        add_grid.addWidget(self._exc_note, 4, 1)

        btn_add = QPushButton("➕  Ausnahme hinzufügen")
        btn_add.clicked.connect(self._add_exception)
        add_grid.addWidget(btn_add, 5, 0, 1, 2)
        layout.addWidget(grp_add)

        # Tabelle bestehender Ausnahmen
        grp_list = QGroupBox("Aktive Ausnahmen")
        list_layout = QVBoxLayout(grp_list)

        self._exc_table = QTableWidget()
        self._exc_table.setColumnCount(5)
        self._exc_table.setHorizontalHeaderLabels([
            "Filter-Typ", "Wert", "Aktion", "Threshold", "Notiz"])
        self._exc_table.horizontalHeader().setSectionResizeMode(
            QHeaderView.Stretch)
        self._exc_table.setSelectionBehavior(
            QTableWidget.SelectRows)
        self._exc_table.setAlternatingRowColors(True)
        self._exc_table.setEditTriggers(
            QTableWidget.NoEditTriggers)
        list_layout.addWidget(self._exc_table)

        btn_del = QPushButton("🗑  Ausgewählte löschen")
        btn_del.setStyleSheet("color:#f38ba8;")
        btn_del.clicked.connect(self._delete_exception)
        list_layout.addWidget(btn_del)
        layout.addWidget(grp_list, stretch=1)

        self._load_exceptions()
        self._wrap_tab_in_scroll(self.tab_sample_exceptions)

    def _load_exceptions(self):
        exceptions = self._params.get("sample_exceptions", [])
        self._exc_table.setRowCount(len(exceptions))
        for row, exc in enumerate(exceptions):
            self._exc_table.setItem(
                row, 0, QTableWidgetItem(exc.get("filter_type", "")))
            self._exc_table.setItem(
                row, 1, QTableWidgetItem(exc.get("value", "")))
            self._exc_table.setItem(
                row, 2, QTableWidgetItem(exc.get("action", "")))
            thr = str(exc.get("threshold", "")) if exc.get("threshold") else "—"
            self._exc_table.setItem(row, 3, QTableWidgetItem(thr))
            self._exc_table.setItem(
                row, 4, QTableWidgetItem(exc.get("note", "")))

    def _add_exception(self):
        value = self._exc_value.text().strip()
        if not value:
            from PySide6.QtWidgets import QMessageBox
            QMessageBox.warning(self, "Fehler", "Bitte einen Wert eingeben.")
            return

        # Regex validieren
        filter_type = self._exc_type.currentText()
        if "Regulärer Ausdruck" in filter_type:
            import re
            try:
                re.compile(value)
            except re.error as e:
                from PySide6.QtWidgets import QMessageBox
                QMessageBox.warning(
                    self, "Ungültiger Regex", f"Fehler: {e}")
                return

        exc = {
            "filter_type": filter_type,
            "value":       value,
            "action":      self._exc_action.currentText(),
            "note":        self._exc_note.text().strip(),
        }
        if self._exc_action.currentIndex() == 1:
            exc["threshold"] = self._exc_thr_val.value()

        exceptions = self._params.get("sample_exceptions", [])
        exceptions.append(exc)
        self._params["sample_exceptions"] = exceptions
        self._load_exceptions()
        self._exc_value.clear()
        self._exc_note.clear()

    def _delete_exception(self):
        rows = sorted(set(
            i.row() for i in self._exc_table.selectedItems()),
            reverse=True)
        exceptions = self._params.get("sample_exceptions", [])
        for row in rows:
            if 0 <= row < len(exceptions):
                exceptions.pop(row)
        self._params["sample_exceptions"] = exceptions
        self._load_exceptions()
        
    def _update_ref_count(self):
        try:
            from analysis.roi_learner import get_reference_count
            n = get_reference_count()
            self._lbl_ref_count.setText(f"{n} Referenzen gespeichert")
        except Exception:
            pass

    def _clear_all_refs(self):
        from PySide6.QtWidgets import QMessageBox
        from analysis.roi_learner import get_reference_count
        n = get_reference_count()
        if QMessageBox.question(
                self, "Alle Referenzen löschen",
                f"Wirklich alle {n} Referenzen löschen?\n\n"
                "Die trainierten Modelle bleiben erhalten.",
                QMessageBox.Yes | QMessageBox.No) == QMessageBox.Yes:
            from analysis.roi_learner import clear_all_references
            clear_all_references()
            self._update_ref_count()
            self._reload_models()
        
    def _build_help_tab(self):
        from PySide6.QtWidgets import QVBoxLayout, QHBoxLayout, QTextEdit
        layout = QVBoxLayout(self.tab_help)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(12)

        # Info-Box
        info = QLabel(
            "Bei Fehlern oder Verbesserungsvorschlaegen kannst du direkt "
            "einen GitHub-Issue erstellen. Die System-Informationen werden "
            "automatisch eingefuegt."
        )
        info.setWordWrap(True)
        info.setStyleSheet("color:#a6adc8; font-size:11px;")
        layout.addWidget(info)

        # System-Info Vorschau
        grp = QGroupBox("System-Informationen (werden automatisch eingefuegt)")
        grp_layout = QVBoxLayout(grp)
        self._sysinfo_view = QTextEdit()
        self._sysinfo_view.setReadOnly(True)
        self._sysinfo_view.setMaximumHeight(180)
        self._sysinfo_view.setStyleSheet(
            "font-family: 'Consolas', monospace; font-size:9px;")
        self._sysinfo_view.setPlainText(self._collect_sysinfo())
        grp_layout.addWidget(self._sysinfo_view)
        layout.addWidget(grp)

        # Fehlerbeschreibung
        grp2 = QGroupBox("Fehlerbeschreibung (optional, wird dem Issue hinzugefuegt)")
        grp2_layout = QVBoxLayout(grp2)
        self._issue_desc = QTextEdit()
        self._issue_desc.setPlaceholderText(
            "Was ist passiert?\n"
            "Was hast du erwartet?\n"
            "Schritte zur Reproduktion:\n"
            "  1. Ordner waehlen\n"
            "  2. ..."
        )
        self._issue_desc.setMaximumHeight(120)
        grp2_layout.addWidget(self._issue_desc)
        layout.addWidget(grp2)

        layout.addStretch()

        # Buttons
        btn_row = QHBoxLayout()

        btn_copy = QPushButton("📋  System-Info kopieren")
        btn_copy.clicked.connect(self._copy_sysinfo)

        btn_issue = QPushButton("🐛  Feedback / Issue senden")
        btn_issue.setObjectName("primary")
        btn_issue.setMinimumHeight(40)
        btn_issue.clicked.connect(self._open_github_issue)

        btn_row.addWidget(btn_copy)
        btn_row.addStretch()
        btn_row.addWidget(btn_issue)
        layout.addLayout(btn_row)
        self._wrap_tab_in_scroll(self.tab_help)

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
        self._btn_export_model.setEnabled(True)
        
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
            
    def _export_model(self):
        if not self._selected_model:
            return
        from PySide6.QtWidgets import QFileDialog, QMessageBox
        import zipfile, json
        from pathlib import Path
        from analysis.roi_model_registry import get_refs_for_model
        from analysis.roi_learner import get_image_cache_dir

        name = self._selected_model.get("name", "modell").replace(" ", "_")
        dest, _ = QFileDialog.getSaveFileName(
            self, "Modell exportieren",
            f"{name}.histomodel",
            "HistoAnalyzer Modell (*.histomodel)"
        )
        if not dest:
            return

        try:
            model_path = Path(self._selected_model["model_path"])
            refs       = get_refs_for_model(self._selected_model)
            img_cache  = get_image_cache_dir()

            with zipfile.ZipFile(dest, "w", zipfile.ZIP_DEFLATED) as zf:
                
                # Modell-Gewichte
                if model_path.exists():
                    zf.write(model_path, "roi_model.pt")

                # Bilder exportieren
                n_images = 0
                refs_export = []
                for r in refs:
                    r_copy = dict(r)
                    
                    # Gecachtes Bild bevorzugen
                    cached = r.get("cached_image_path", "")
                    original = r.get("image_path", "")
                    
                    img_to_export = None
                    if cached and Path(cached).exists():
                        img_to_export = Path(cached)
                        img_name = f"images/{img_to_export.name}"
                    elif original and Path(original).exists():
                        # Original komprimieren
                        img_to_export = Path(original)
                        img_name = f"images/ref_{r['id']:04d}_original.jpg"
                    
                    if img_to_export:
                        try:
                            # Komprimiert als JPEG exportieren
                            from PIL import Image as PilImage
                            import numpy as np
                            from analysis.brightfield_pipeline import load_as_uint8_rgb
                            img = load_as_uint8_rgb(str(img_to_export))
                            MAX = 2048
                            h, w = img.shape[:2]
                            if max(h, w) > MAX:
                                s = MAX / max(h, w)
                                img = np.array(PilImage.fromarray(img).resize(
                                    (int(w*s), int(h*s)), PilImage.LANCZOS))
                            import io
                            buf = io.BytesIO()
                            PilImage.fromarray(img).save(buf, format="JPEG",
                                                         quality=85, optimize=True)
                            zf.writestr(img_name, buf.getvalue())
                            r_copy["exported_image"] = img_name
                            n_images += 1
                        except Exception as e:
                            print(f"  [Export] Bild übersprungen: {e}")
                    
                    refs_export.append(r_copy)

                # Referenzen
                zf.writestr("references.json",
                            json.dumps(refs_export, indent=2))

                # Metadaten
                from datetime import datetime
                info = dict(self._selected_model)
                info["export_date"] = datetime.now().isoformat()
                info["n_images_exported"] = n_images
                zf.writestr("model_info.json",
                            json.dumps(info, indent=2))

            size_mb = Path(dest).stat().st_size / 1024 / 1024
            QMessageBox.information(
                self, "Export erfolgreich",
                f"Modell exportiert nach:\n{dest}\n\n"
                f"Enthält:\n"
                f"  • Modell-Gewichte\n"
                f"  • {len(refs)} ROI-Referenzen\n"
                f"  • {n_images} Bilder\n"
                f"  • Dateigröße: {size_mb:.1f} MB"
            )
        except Exception as e:
            QMessageBox.warning(self, "Fehler", f"Export fehlgeschlagen:\n{e}")
            
    def _import_model(self):
        from PySide6.QtWidgets import QFileDialog, QMessageBox, QInputDialog
        import zipfile, json, shutil
        from pathlib import Path

        src, _ = QFileDialog.getOpenFileName(
            self, "Modell importieren", "",
            "Alle Modell-Formate (*.histomodel *.pt);;"
            "HistoAnalyzer Modell (*.histomodel);;"
            "YOLO Gewichte (*.pt)"
        )
        if not src:
            return

        src = Path(src)

        # ── Direkter .pt Import ───────────────────────────────────────
        if src.suffix.lower() == ".pt":
            try:
                from analysis.roi_model_registry import (
                    get_models_dir, load_registry, save_registry)
                from datetime import datetime

                name, ok = QInputDialog.getText(
                    self, "Modell benennen",
                    "Name für dieses Modell:",
                    text=src.stem)
                if not ok or not name.strip():
                    return

                models_dir = get_models_dir()
                existing   = load_registry()
                new_id     = f"model_{len(existing)+1:03d}"
                dest_pt    = models_dir / f"{new_id}.pt"

                shutil.copy2(src, dest_pt)

                for m in existing:
                    m["active"] = False

                info = {
                    "id":         new_id,
                    "name":       name.strip(),
                    "stain":      "Unbekannt",
                    "slice_type": "Allgemein",
                    "model_path": str(dest_pt),
                    "active":     True,
                    "n_refs":     0,
                    "mAP50":      0.0,
                    "created":    datetime.now().isoformat(),
                    "notes":      f"Importiert von {src.name}",
                }
                existing.append(info)
                save_registry(existing)
                self._reload_models()
                QMessageBox.information(
                    self, "Import erfolgreich",
                    f"Modell '{name}' importiert!\n"
                    f"Quelle: {src}\n"
                    f"Gespeichert als: {dest_pt}"
                )
            except Exception as e:
                QMessageBox.warning(self, "Fehler",
                                    f"Import fehlgeschlagen:\n{e}")
            return

        # ── .histomodel Import (ZIP) ───────────────────────────────────
        try:
            with zipfile.ZipFile(src, "r") as zf:
                names = zf.namelist()

                if "model_info.json" not in names:
                    raise ValueError("Ungültige .histomodel Datei")

                info = json.loads(zf.read("model_info.json"))
                refs = json.loads(zf.read("references.json")) \
                       if "references.json" in names else []

                from analysis.roi_model_registry import (
                    get_models_dir, load_registry, save_registry)
                from analysis.roi_learner import (
                    load_references, get_index_path, get_image_cache_dir)

                models_dir = get_models_dir()
                img_cache  = get_image_cache_dir()
                existing   = load_registry()
                new_id     = f"model_{len(existing)+1:03d}"
                dest_pt    = models_dir / f"{new_id}.pt"

                if "roi_model.pt" in names:
                    zf.extract("roi_model.pt", str(models_dir))
                    (models_dir / "roi_model.pt").rename(dest_pt)

                img_names = [n for n in names if n.startswith("images/")]
                for img_name in img_names:
                    out_path = img_cache / Path(img_name).name
                    out_path.write_bytes(zf.read(img_name))

                if refs:
                    all_refs  = load_references()
                    next_id   = max((r["id"] for r in all_refs),
                                    default=-1) + 1
                    for r in refs:
                        r["id"] = next_id
                        next_id += 1
                        exported = r.get("exported_image", "")
                        if exported:
                            local_img = img_cache / Path(exported).name
                            if local_img.exists():
                                r["cached_image_path"] = str(local_img)
                        all_refs.append(r)
                    with open(get_index_path(), "w") as f:
                        json.dump(all_refs, f, indent=2)
                    if existing:
                        existing[-1]["ref_ids"] = [r["id"] for r in refs]

                info["id"]         = new_id
                info["model_path"] = str(dest_pt)
                info["active"]     = True
                for m in existing:
                    m["active"] = False
                existing.append(info)
                save_registry(existing)

            self._reload_models()
            QMessageBox.information(
                self, "Import erfolgreich",
                f"Modell '{info.get('name', '?')}' importiert!\n"
                f"{len(refs)} Referenzen übernommen.\n"
                f"{len(img_names)} Bilder importiert."
            )

        except Exception as e:
            QMessageBox.warning(self, "Fehler", f"Import fehlgeschlagen:\n{e}")
            
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

                    if os.path.abspath(new_path) != os.path.abspath(self.model["model_path"]):
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
                    err_str = str(e)
                    tb_str  = traceback.format_exc()
                    is_plot_error = any(kw in err_str or kw in tb_str for kw in (
                        "PyDataFrame", "PySeries", "plot_results",
                        "plot_metrics", "UnboundLocalError", "ax[",
                        "DataFrame", "pandas", "results.csv",
                        "ultralytics\\utils\\plotting",
                        "ultralytics/utils/plotting",
                    ))
                    try:
                        from analysis.roi_trainer import get_runs_dir
                        _best = list(get_runs_dir().rglob("best.pt"))
                        if _best:
                            is_plot_error = True
                    except Exception:
                        pass

                    if is_plot_error:
                        try:
                            from analysis.roi_trainer import (
                                get_runs_dir, get_model_path,
                                get_training_summary)
                            from analysis.roi_learner import get_reference_count
                            import shutil
                            runs_dir = get_runs_dir()
                            candidates = sorted(
                                runs_dir.rglob("best.pt"),
                                key=lambda f: f.stat().st_mtime,
                                reverse=True)
                            for pt in candidates:
                                if pt.stat().st_size > 100_000:
                                    shutil.copy2(pt, self.model["model_path"])
                                    sm = get_training_summary() or {}
                                    n  = get_reference_count()
                                    models = load_registry()
                                    for m in models:
                                        if m["id"] == self.model["id"]:
                                            m["n_refs"]  = n
                                            m["mAP50"]   = sm.get("mAP50", 0.0)
                                            m["epochs"]  = sm.get("epochs_trained", 0)
                                            from datetime import datetime
                                            m["updated"] = datetime.now().isoformat()
                                            break
                                    save_registry(models)
                                    self.finished.emit(True,
                                        f"✔ Neu trainiert  "
                                        f"mAP50={sm.get('mAP50', 0):.3f}")
                                    return
                            self.finished.emit(False,
                                f"✗ Plotting-Fehler + kein Modell: {e}")
                        except Exception as e2:
                            self.finished.emit(False, f"✗ Fehler: {e} / {e2}")
                    else:
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
                
    def _collect_sysinfo(self) -> str:
        import platform, sys
        try:
            from version import VERSION
        except Exception:
            VERSION = "unbekannt"
        try:
            from analysis.roi_model_registry import get_active_model
            model = get_active_model()
            model_info = f"{model['name']} (mAP50={model.get('mAP50',0):.3f})" \
                         if model else "kein Modell"
        except Exception:
            model_info = "unbekannt"

        lines = [
            f"HistoAnalyzer Version : {VERSION}",
            f"Betriebssystem        : {platform.system()} {platform.release()} ({platform.version()})",
            f"Python                : {sys.version.split()[0]}",
            f"Plattform             : {platform.machine()}",
            f"Aktives ROI-Modell    : {model_info}",
        ]

        # Installierte Pakete
        for pkg in ["PySide6", "numpy", "ultralytics", "stardist", "torch"]:
            try:
                import importlib.metadata
                v = importlib.metadata.version(pkg)
                lines.append(f"{pkg:<22}: {v}")
            except Exception:
                lines.append(f"{pkg:<22}: nicht installiert")

        return "\n".join(lines)

    def _copy_sysinfo(self):
        from PySide6.QtWidgets import QApplication
        QApplication.clipboard().setText(self._collect_sysinfo())
        self.sender().setText("✔  Kopiert!")

    def _open_github_issue(self):
        import urllib.request, json, base64
        from version import VERSION
        from PySide6.QtWidgets import QMessageBox

        sysinfo = self._collect_sysinfo()
        desc    = self._issue_desc.toPlainText().strip()

        body = (
            "## Beschreibung\n"
            f"{desc if desc else '(keine Beschreibung angegeben)'}\n\n"
            "## System-Informationen\n"
            "```\n"
            f"{sysinfo}\n"
            "```\n"
        )

        title = f"[Feedback] HistoAnalyzer {VERSION}"
        if desc:
            # Erste Zeile der Beschreibung als Titel
            first_line = desc.split('\n')[0][:60]
            title = f"[Feedback] {first_line}"

        payload = json.dumps({
            "title": title,
            "body":  body,
            "labels": ["user-feedback"],
        }).encode("utf-8")

        try:
            _t = base64.b64decode(
                "Z2hwX3g1NlB0OFlOa01VOFZzREN1OGVnc2oyMExRYkhxYTRBazF2RA=="
            ).decode()
            req = urllib.request.Request(
                "https://api.github.com/repos/Paul-cloud24/Histo_updater/issues",
                data=payload,
                headers={
                    "Authorization": f"token {_t}",
                    "Accept":        "application/vnd.github+json",
                    "Content-Type":  "application/json",
                    "User-Agent":    "HistoAnalyzer",
                },
                method="POST"
            )
            with urllib.request.urlopen(req, timeout=10) as resp:
                result = json.loads(resp.read())
                issue_url = result.get("html_url", "")

            QMessageBox.information(
                self, "✔ Issue erstellt",
                f"Dein Feedback wurde erfolgreich übermittelt!\n\n"
                f"Issue: {issue_url}"
            )
            # Felder leeren
            self._issue_desc.clear()

        except Exception as e:
            # Fallback: Browser öffnen
            import urllib.parse, webbrowser
            params = urllib.parse.urlencode({
                "title": title,
                "body":  body,
                "labels": "user-feedback",
            })
            url = f"https://github.com/Paul-cloud24/Histo_updater/issues/new?{params}"
            webbrowser.open(url)
            QMessageBox.warning(
                self, "Direkt-Upload fehlgeschlagen",
                f"Automatische Übermittlung fehlgeschlagen ({e}).\n"
                f"Browser wurde geöffnet als Fallback."
            )

    # ── Referenzen ────────────────────────────────────────────────────

    def _load_refs(self, model: dict):
        from analysis.roi_model_registry import get_refs_for_model
        from PySide6.QtWidgets import QListWidgetItem
        from PySide6.QtGui import QColor
        from pathlib import Path
        self._ref_list.clear()
        self._ref_preview.setText("Referenz auswaehlen")
        for ref in get_refs_for_model(model):
            name = Path(ref.get("image_path", "?")).name[:45]
            item = QListWidgetItem(
                f"#{ref['id']}  {name}  "
                f"cx={ref.get('centroid_x',0):.2f}")
            item.setData(Qt.UserRole, ref)
            
            # Rot nur wenn weder Original noch Cache verfügbar
            cached   = ref.get("cached_image_path", "")
            original = ref.get("image_path", "")
            has_image = (cached and Path(cached).exists()) or \
                        (original and Path(original).exists())
            if not has_image:
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
        from pathlib import Path

        # Bestes verfügbares Bild finden
        img_path = ""
        cached = ref.get("cached_image_path", "")
        original = ref.get("image_path", "")
        
        if cached and Path(cached).exists():
            img_path = cached
        elif original and Path(original).exists():
            img_path = original

        if not img_path:
            self._ref_preview.setText("Bild nicht verfügbar")
            return

        polygon = ref.get("polygon_normalized", [])
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
        self._train_grp.setVisible(True)
        self._train_bar.setValue(0)
        self._train_step.setText("Exportiere ROI-Daten...")
        self._train_epoch_lbl.setText("Epoche 0 / 100")
        self._train_pct_lbl.setText("0%")
        self._train_metrics.setText("")
        self._train_status.setText("")

        from PySide6.QtCore import QThread, QObject, Signal as Sig

        class _Worker(QThread):
            status   = Sig(str)
            progress = Sig(int, int, dict)   # epoch, total, metrics
            finished = Sig(bool, str)

            def __init__(self, n, s, sl):
                super().__init__()
                self.n, self.s, self.sl = n, s, sl

            def run(self):
                try:
                    from analysis.roi_trainer import train, get_training_summary
                    from analysis.roi_learner import get_reference_count
                    from analysis.roi_model_registry import register_model
                    self.status.emit("Exportiere ROI-Daten...")

                    def _on_progress(epoch, total, metrics):
                        self.progress.emit(epoch, total, metrics)

                    mp = train(epochs=100, imgsz=1024,
                               progress_callback=_on_progress)
                    sm = get_training_summary() or {}
                    register_model(self.n, self.s, self.sl, mp,
                                   get_reference_count(),
                                   sm.get("mAP50", 0.0),
                                   sm.get("epochs_trained", 0))
                    self.finished.emit(True,
                        f"Modell '{self.n}' trainiert!  "
                        f"mAP50={sm.get('mAP50', 0):.3f}")
                except Exception as e:
                    import traceback
                    err_str  = str(e)
                    tb_str   = traceback.format_exc()
                    # Prüfen ob der Fehler aus YOLO-internem Plotting kommt
                    # (training selbst war erfolgreich, best.pt ist gespeichert)
                    is_plot_error = any(kw in err_str or kw in tb_str for kw in (
                        "PyDataFrame", "PySeries", "plot_results",
                        "plot_metrics", "UnboundLocalError", "ax[",
                        "DataFrame", "pandas", "results.csv",
                        "ultralytics\\utils\\plotting",
                        "ultralytics/utils/plotting",
                    ))
                    # Zusätzlich: wenn best.pt existiert → Plotting-Fehler
                    try:
                        from analysis.roi_trainer import get_runs_dir
                        _best = list(get_runs_dir().rglob("best.pt"))
                        if _best:
                            is_plot_error = True
                    except Exception:
                        pass

                    if is_plot_error:
                        try:
                            from analysis.roi_trainer import (
                                get_runs_dir, get_model_path,
                                get_training_summary)
                            from analysis.roi_learner import get_reference_count
                            from analysis.roi_model_registry import register_model
                            import shutil
                            runs_dir = get_runs_dir()
                            candidates = sorted(
                                runs_dir.rglob("best.pt"),
                                key=lambda f: f.stat().st_mtime,
                                reverse=True)
                            for pt in candidates:
                                if pt.stat().st_size > 100_000:
                                    dest = get_model_path()
                                    shutil.copy2(pt, dest)
                                    sm = get_training_summary() or {}
                                    register_model(
                                        self.n, self.s, self.sl,
                                        str(dest),
                                        get_reference_count(),
                                        sm.get("mAP50", 0.0),
                                        sm.get("epochs_trained", 0))
                                    self.finished.emit(True,
                                        f"Modell '{self.n}' gespeichert ✔  "
                                        f"mAP50={sm.get('mAP50', 0):.3f}")
                                    return
                            self.finished.emit(False,
                                f"Plotting-Fehler + kein Modell: {e}")
                        except Exception as e2:
                            self.finished.emit(False,
                                f"Fehler: {e}\nRettung: {e2}")
                    else:
                        traceback.print_exc()
                        self.finished.emit(False,
                            f"Fehler: {e}\n{traceback.format_exc()}")

        self._worker = _Worker(name, stain, sl)
        self._worker.status.connect(self._train_status.setText)
        self._worker.progress.connect(self._on_train_epoch)
        self._worker.finished.connect(self._on_trained)
        self._worker.start()

    def _on_train_epoch(self, epoch: int, total: int, metrics: dict):
        """Wird nach jeder Trainings-Epoche aufgerufen."""
        pct      = int(epoch / max(total, 1) * 100)
        map50    = metrics.get("mAP50", 0.0)
        box_loss = metrics.get("box_loss", 0.0)
        self._train_bar.setValue(pct)
        self._train_step.setText(f"Training läuft...")
        self._train_epoch_lbl.setText(f"Epoche {epoch} / {total}")
        self._train_pct_lbl.setText(f"{pct}%")
        self._train_metrics.setText(
            f"mAP50 = {map50:.3f}    box_loss = {box_loss:.3f}")

    def _on_trained(self, ok: bool, msg: str):
        self._btn_train.setEnabled(True)
        if ok:
            self._train_bar.setValue(100)
            self._train_step.setText("✔ Training abgeschlossen!")
            self._train_epoch_lbl.setText("")
            self._train_pct_lbl.setText("100%")
        else:
            self._train_grp.setVisible(False)
        self._train_status.setText(msg)
        if ok:
            self._reload_models()

    # ── Helpers ───────────────────────────────────────────────────────

    @staticmethod
    def _label(title: str, tooltip: str = "") -> QLabel:
        lbl = QLabel(title)
        if tooltip:
            lbl.setToolTip(tooltip)
        lbl.setCursor(Qt.WhatsThisCursor)
        return lbl

    def _reset(self):
        self.spin_frac.setValue(0.10)
        self.spin_min_area.setValue(40)
        self.spin_max_area.setValue(3000)
        self.spin_timer.setValue(7)
        self.combo_seg.setCurrentText("Auto")
        try:
            self.chk_subfolders.setChecked(True)
            self.edit_folder_keyword.setText("")
            self.chk_iso.setChecked(True)
            self.edit_iso_keyword.setText("iso")
        except Exception:
            pass

    def _accept(self):
        self._params["positive_fraction"]  = round(self.spin_frac.value(), 3)
        self._params["min_nucleus_area"]   = self.spin_min_area.value()
        self._params["max_nucleus_area"]   = self.spin_max_area.value()
        self._params["auto_roi_timer"]     = self.spin_timer.value()
        self._params["segmentation_model"] = self.combo_seg.currentText()

        # Ordnerstruktur
        try:
            self._params["use_subfolders"]  = self.chk_subfolders.isChecked()
            self._params["folder_keyword"]  = self.edit_folder_keyword.text().strip()
            self._params["use_iso_pairing"] = self.chk_iso.isChecked()
            self._params["iso_keyword"]     = self.edit_iso_keyword.text().strip() or "iso"
        except Exception:
            pass

        # Threshold-Strategie
        try:
            for btn in self._thr_group.buttons():
                if btn.isChecked():
                    self._params["threshold_strategy"] = \
                        btn.property("strategy_key")
                    break
            self._params["threshold_n_nearest"]    = self.spin_thr_n.value()
            self._params["threshold_warn_pct"]     = self.spin_warn_pct.value()
            self._params["threshold_n_sigma"]      = self.spin_nsigma.value()
            self._params["manual_threshold_value"] = self.spin_manual_thr.value()
        except Exception:
            pass

        # Fallback-Threshold Strategie
        try:
            for btn in self._fallback_group.buttons():
                if btn.isChecked():
                    self._params["fallback_strategy"] = \
                        btn.property("fallback_key")
                    break
            self._params["fallback_fixed_value"] = \
                self.spin_fallback_val.value()
        except Exception:
            pass

        # Sprache
        try:
            old_lang = self._params.get("language", "de")
            new_lang = "de" if self.combo_lang.currentIndex() == 0 else "en"
            self._params["language"] = new_lang

            from i18n import set_language, save_language
            save_language(new_lang)
            set_language(new_lang)

            if new_lang != old_lang:
                from PySide6.QtWidgets import QMessageBox
                title = ("Sprache geändert" if new_lang == "de"
                         else "Language changed")
                text  = ("Die Sprache wird nach einem Neustart angewendet.\n"
                         "Jetzt neu starten?\n\n"
                         "The language will be applied after a restart.\n"
                         "Restart now?")
                reply = QMessageBox.question(
                    self, title, text,
                    QMessageBox.Yes | QMessageBox.No
                )
                if reply == QMessageBox.Yes:
                    import subprocess, sys, os
                    subprocess.Popen([sys.executable] + sys.argv)
                    os.kill(os.getpid(), 9)
        except Exception:
            pass

        self.accept()

    def get_params(self) -> dict:
        return dict(self._params)


# Import fuer Path
from pathlib import Path
