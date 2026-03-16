# ui/threshold_dialog.py  – komplett ersetzen

import os
import random
import numpy as np
import io
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches

from PySide6.QtCore import Qt, QThreadPool, QRunnable, QObject, Signal, QWaitCondition, QMutex
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QSlider, QSizePolicy
)
from PySide6.QtGui import QPixmap, QImage

from PIL import Image
from tifffile import imread


def classify_image(image_path):
    try:
        img = imread(image_path)
        if img.ndim == 2:
            return "gray"
        if img.ndim == 3 and img.shape[0] < 10:
            img = img.transpose(1, 2, 0)
        if img.ndim == 4:
            if img.shape[1] < 10:
                img = img.transpose(0, 2, 3, 1)
            img = img.max(axis=0)
        if img.shape[-1] < 3:
            return "gray"

        r = img[..., 0].astype(np.float32).mean()
        g = img[..., 1].astype(np.float32).mean()
        b = img[..., 2].astype(np.float32).mean()
        total = max(r + g + b, 1.0)

        if r / total > 0.5 and b / total < 0.2:
            return "sox9"
        if b / total > 0.5 and r / total < 0.2:
            return "dapi"
        if r / total > 0.25 and b / total > 0.25:
            return "overlay"
        return "gray"
    except Exception as e:
        print(f"Klassifikation fehlgeschlagen für {os.path.basename(image_path)}: {e}")
        return "unknown"


def load_sox9_raw(image_path):
    """
    Lädt den Sox9-Kanal als rohe 16-bit Graustufenwerte.
    Gibt (H, W) float32-Array zurück.
    """
    img = imread(image_path)

    # (C, H, W) → (H, W, C)
    if img.ndim == 3 and img.shape[0] < 10:
        img = img.transpose(1, 2, 0)
    # (Z, C, H, W) → max-projection → (H, W, C)
    if img.ndim == 4:
        if img.shape[1] < 10:
            img = img.transpose(0, 2, 3, 1)
        img = img.max(axis=0)

    # RGB → Rotkanal
    if img.ndim == 3:
        return img[..., 0].astype(np.float32)

    return img.astype(np.float32)


class ThresholdDialog(QDialog):
    def __init__(self, folder, initial_threshold=None, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Sox9 Threshold – ImageJ Style")
        self.setMinimumSize(750, 620)

        self.folder = folder
        self.current_image_path = None
        self.raw = None          # rohe Pixelwerte (H, W) float32
        self.img_min = 0.0
        self.img_max = 65535.0
        self.confirmed_threshold = initial_threshold

        layout = QVBoxLayout()

        # ── Vorschau ─────────────────────────────────────────────────
        self.preview_label = QLabel("Lade...")
        self.preview_label.setAlignment(Qt.AlignCenter)
        self.preview_label.setMinimumHeight(280)
        self.preview_label.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.preview_label.setStyleSheet("background:#111; border:1px solid #555;")
        layout.addWidget(self.preview_label)

        # ── Histogramm ───────────────────────────────────────────────
        self.hist_label = QLabel()
        self.hist_label.setAlignment(Qt.AlignCenter)
        self.hist_label.setFixedHeight(110)
        self.hist_label.setStyleSheet("background:#1a1a1a; border:1px solid #444;")
        layout.addWidget(self.hist_label)

        # ── Slider (arbeitet auf 0–255 Bins wie ImageJ) ───────────────
        slider_layout = QHBoxLayout()
        self.slider = QSlider(Qt.Horizontal)
        self.slider.setRange(0, 255)       # 256 Bins, wie ImageJ default
        self.slider.setValue(128)
        self.slider.valueChanged.connect(self._on_slider)

        self.threshold_label = QLabel("Threshold: –")
        self.threshold_label.setMinimumWidth(160)
        slider_layout.addWidget(QLabel("0"))
        slider_layout.addWidget(self.slider)
        slider_layout.addWidget(QLabel("255"))
        slider_layout.addWidget(self.threshold_label)
        layout.addLayout(slider_layout)

        # ── Buttons ──────────────────────────────────────────────────
        btn_layout = QHBoxLayout()

        self.auto_btn = QPushButton("Auto (Otsu)")
        self.auto_btn.clicked.connect(self._auto_threshold)

        self.random_btn = QPushButton("Anderes Bild")
        self.random_btn.clicked.connect(self._load_random_image)

        self.cancel_btn = QPushButton("Abbrechen")
        self.cancel_btn.clicked.connect(self.reject)

        self.confirm_btn = QPushButton("✔  Threshold bestätigen")
        self.confirm_btn.setStyleSheet(
            "background:#2a7a2a; color:white; font-weight:bold; padding:6px 16px;"
        )
        self.confirm_btn.clicked.connect(self._confirm)

        btn_layout.addWidget(self.auto_btn)
        btn_layout.addWidget(self.random_btn)
        btn_layout.addStretch()
        btn_layout.addWidget(self.cancel_btn)
        btn_layout.addWidget(self.confirm_btn)
        layout.addLayout(btn_layout)

        self.setLayout(layout)
        self._load_random_image()

    # ── Hilfsmethoden ────────────────────────────────────────────────

    def _sox9_images(self):
        if not self.folder:
            return []
        result = []
        for f in os.listdir(self.folder):
            if not f.lower().endswith((".tif", ".tiff", ".png", ".jpg", ".jpeg")):
                continue
            full = os.path.join(self.folder, f)
            if not os.path.isfile(full):
                continue
            if classify_image(full) == "sox9":
                result.append(full)
        return result

    def _bin_to_raw(self, bin_val):
        """Konvertiert Slider-Bin (0–255) → echten 16-bit Pixelwert."""
        return self.img_min + (bin_val / 255.0) * (self.img_max - self.img_min)

    def _raw_to_bin(self, raw_val):
        """Konvertiert echten Pixelwert → Slider-Bin (0–255)."""
        if self.img_max == self.img_min:
            return 0
        return int(np.clip(
            (raw_val - self.img_min) / (self.img_max - self.img_min) * 255, 0, 255
        ))

    # ── Laden ────────────────────────────────────────────────────────

    def _load_random_image(self):
        images = self._sox9_images()
        if not images:
            self.preview_label.setText("Keine Sox9-Bilder gefunden.")
            return
        self.current_image_path = random.choice(images)
        self.raw = load_sox9_raw(self.current_image_path)
        self.img_min = float(self.raw.min())
        self.img_max = float(self.raw.max())

        # Slider-Position: wenn schon ein confirmed Threshold existiert → umrechnen
        if self.confirmed_threshold is not None:
            bin_val = self._raw_to_bin(self.confirmed_threshold)
        else:
            bin_val = self._auto_otsu_bin()

        self.slider.blockSignals(True)
        self.slider.setValue(bin_val)
        self.slider.blockSignals(False)

        self._render(bin_val)

    # ── Slider / Auto ─────────────────────────────────────────────────

    def _on_slider(self, bin_val):
        self._render(bin_val)

    def _auto_otsu_bin(self):
        """Otsu-Schwellenwert auf 256-Bin-Histogramm (wie ImageJ Auto)."""
        hist, _ = np.histogram(self.raw, bins=256,
                                range=(self.img_min, self.img_max))
        total = hist.sum()
        if total == 0:
            return 128

        sum_all = np.dot(np.arange(256), hist)
        sum_bg, w_bg, max_var, threshold = 0.0, 0.0, 0.0, 0

        for t in range(256):
            w_bg += hist[t]
            if w_bg == 0:
                continue
            w_fg = total - w_bg
            if w_fg == 0:
                break
            sum_bg += t * hist[t]
            mean_bg = sum_bg / w_bg
            mean_fg = (sum_all - sum_bg) / w_fg
            var = w_bg * w_fg * (mean_bg - mean_fg) ** 2
            if var > max_var:
                max_var = var
                threshold = t

        return threshold

    def _auto_threshold(self):
        if self.raw is None:
            return
        bin_val = self._auto_otsu_bin()
        self.slider.setValue(bin_val)   # löst _on_slider aus

    # ── Rendern ──────────────────────────────────────────────────────

    def _render(self, bin_val):
        if self.raw is None:
            return

        raw_threshold = self._bin_to_raw(bin_val)
        mask = self.raw >= raw_threshold

        # Aktuellen 16-bit Wert anzeigen
        self.threshold_label.setText(
            f"Threshold: {int(raw_threshold):,}  "
            f"({mask.sum():,} px / {100*mask.mean():.1f} %)"
        )

        # ── Vorschau-Bild (ImageJ-Style: rot auf grau) ────────────────
        norm = ((self.raw - self.img_min) /
                max(1.0, self.img_max - self.img_min) * 255).astype(np.uint8)
        rgb = np.stack([norm, norm, norm], axis=-1)
        rgb[mask] = [255, 0, 0]    # rot für positiv, exakt wie ImageJ

        fig_img, ax = plt.subplots(figsize=(6, 3), dpi=100)
        ax.imshow(rgb, interpolation="nearest")
        ax.set_title(
            os.path.basename(self.current_image_path),
            fontsize=8, color="white"
        )
        ax.axis("off")
        fig_img.patch.set_facecolor("#111")
        plt.tight_layout(pad=0.2)
        self.preview_label.setPixmap(self._fig_to_pixmap(
            fig_img,
            self.preview_label.width(),
            self.preview_label.height()
        ))
        plt.close(fig_img)

        # ── Histogramm mit Threshold-Linie (wie ImageJ) ───────────────
        hist, bin_edges = np.histogram(self.raw, bins=256,
                                        range=(self.img_min, self.img_max))
        fig_hist, ax2 = plt.subplots(figsize=(6, 1.0), dpi=100)
        fig_hist.patch.set_facecolor("#1a1a1a")
        ax2.set_facecolor("#1a1a1a")

        centers = (bin_edges[:-1] + bin_edges[1:]) / 2

        # Balken links vom Threshold grau, rechts rot
        colors = ["#cc2222" if i >= bin_val else "#888888"
                  for i in range(256)]
        ax2.bar(centers, hist, width=(self.img_max - self.img_min) / 256,
                color=colors, linewidth=0)

        # Threshold-Linie
        ax2.axvline(raw_threshold, color="white", linewidth=1.2, linestyle="--")
        ax2.set_xlim(self.img_min, self.img_max)
        ax2.tick_params(colors="white", labelsize=6)
        for spine in ax2.spines.values():
            spine.set_edgecolor("#555")

        plt.tight_layout(pad=0.1)
        self.hist_label.setPixmap(self._fig_to_pixmap(
            fig_hist,
            self.hist_label.width(),
            self.hist_label.height()
        ))
        plt.close(fig_hist)

    @staticmethod
    def _fig_to_pixmap(fig, max_w, max_h):
        buf = io.BytesIO()
        fig.savefig(buf, format="png", facecolor=fig.get_facecolor())
        buf.seek(0)
        pil = Image.open(buf)
        data = pil.tobytes("raw", "RGB")
        qimg = QImage(data, pil.width, pil.height, QImage.Format_RGB888)
        return QPixmap.fromImage(qimg).scaled(
            max(max_w, 100), max(max_h, 50),
            Qt.KeepAspectRatio, Qt.SmoothTransformation
        )

    # ── Bestätigen ───────────────────────────────────────────────────

    def _confirm(self):
        self.confirmed_threshold = self._bin_to_raw(self.slider.value())
        self.accept()