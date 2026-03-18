# analysis/brightfield_pipeline.py
"""
Hellfeld-Analyse Pipeline fuer Von-Kossa-Faerbung.

Prinzip:
  1. RGB-Bild laden (auch 16-bit TIF wird normalisiert)
  2. Optional ROI anwenden
  3. Schwarze Mineralablagerungen segmentieren
  4. Flaechenmessung: mineralisierte Flaeche / Gewebsflaeche
  5. Export: CSV, Overlay, QC-Plot
"""

import os
import numpy as np
import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from PIL import Image
from skimage.morphology import remove_small_objects, closing, disk
from skimage.measure import label


# ══════════════════════════════════════════════════════════════════════
# Bildladen
# ══════════════════════════════════════════════════════════════════════

def load_as_uint8_rgb(image_path: str) -> np.ndarray:
    """
    Laedt ein Bild als uint8 RGB-Array.
    Unterstuetzt 8-bit und 16-bit TIF, Graustufen, Multi-Channel.
    Normalisiert immer auf 0-255.
    """
    try:
        from tifffile import imread as tiff_imread
        raw = tiff_imread(image_path)
    except Exception:
        raw = np.array(Image.open(image_path))

    # Multi-Frame / Z-Stack: erstes Frame nehmen
    if raw.ndim == 4:
        raw = raw[0]

    # Channel-first → Channel-last
    if raw.ndim == 3 and raw.shape[0] in (1, 2, 3, 4):
        raw = raw.transpose(1, 2, 0)

    # Auf float32 normalisieren
    raw_f = raw.astype(np.float32)
    vmin  = raw_f.min()
    vmax  = raw_f.max()
    if vmax > vmin:
        norm = (raw_f - vmin) / (vmax - vmin) * 255.0
    else:
        norm = np.zeros_like(raw_f)

    norm8 = norm.clip(0, 255).astype(np.uint8)

    # Graustufen → RGB
    if norm8.ndim == 2:
        norm8 = np.stack([norm8, norm8, norm8], axis=-1)

    # Alpha-Kanal entfernen
    if norm8.ndim == 3 and norm8.shape[2] == 4:
        norm8 = norm8[..., :3]

    # Sicherstellen 3-Kanal
    if norm8.ndim == 3 and norm8.shape[2] == 1:
        norm8 = np.concatenate([norm8, norm8, norm8], axis=-1)

    print(f"  Bild geladen: {norm8.shape[1]}x{norm8.shape[0]} px  "
          f"dtype={raw.dtype}  "
          f"original range=[{int(vmin)}, {int(vmax)}]")
    return norm8


def find_brightfield_image(folder: str) -> str:
    """Findet das erste Bild im Ordner (.tif/.tiff/.png/.jpg)."""
    extensions = (".tif", ".tiff", ".png", ".jpg", ".jpeg")
    candidates = []
    for f in sorted(os.listdir(folder)):
        if f.startswith("._"):
            continue
        if not f.lower().endswith(extensions):
            continue
        candidates.append(os.path.join(folder, f))

    if not candidates:
        raise ValueError(
            f"Kein Bild in '{os.path.basename(folder)}' gefunden. "
            f"Erwartet: {', '.join(extensions)}"
        )
    return candidates[0]


# ══════════════════════════════════════════════════════════════════════
# Segmentierung
# ══════════════════════════════════════════════════════════════════════

def segment_von_kossa(
    rgb: np.ndarray,
    darkness_threshold: int = 80,
    min_deposit_area: int = 50,
) -> np.ndarray:
    """
    Segmentiert Von-Kossa-Ablagerungen (schwarz) im uint8 RGB-Bild.
    Verwendet max(R,G,B) < threshold — robuster als alle-Kanaele-Ansatz.
    """
    max_channel = rgb.max(axis=-1).astype(np.float32)
    dark_mask   = max_channel < darkness_threshold

    print(f"  Darkness-Threshold: {darkness_threshold}  "
          f"→ {dark_mask.sum():,} dunkle Pixel "
          f"({100*dark_mask.mean():.2f}% des Bildes)")

    dark_closed = closing(dark_mask, disk(2))
    labeled     = label(dark_closed)
    clean       = remove_small_objects(labeled > 0, min_size=min_deposit_area)

    return clean.astype(bool)


def segment_tissue(
    rgb: np.ndarray,
    background_threshold: int = 220,
) -> np.ndarray:
    """
    Segmentiert die Gewebsflaeche.
    Hintergrund = Pixel wo MIN(R,G,B) > background_threshold (sehr helle/weisse Pixel).
    """
    min_channel = rgb.min(axis=-1).astype(np.float32)
    background  = min_channel > background_threshold
    tissue      = closing(~background, disk(3))

    print(f"  Background-Threshold: {background_threshold}  "
          f"→ Gewebe: {tissue.sum():,} px "
          f"({100*tissue.mean():.1f}% des Bildes)")

    return tissue.astype(bool)


# ══════════════════════════════════════════════════════════════════════
# Brightfield Pipeline
# ══════════════════════════════════════════════════════════════════════

class BrightfieldPipeline:

    def __init__(self,
                 stain_name           : str        = "Von Kossa",
                 darkness_threshold   : int        = 80,
                 background_threshold : int        = 220,
                 min_deposit_area     : int        = 50,
                 roi_mask             : np.ndarray = None):

        self.stain_name           = stain_name
        self.darkness_threshold   = darkness_threshold
        self.background_threshold = background_threshold
        self.min_deposit_area     = min_deposit_area
        self.roi_mask             = roi_mask

    def _save_overlay(self, rgb, deposit_mask, tissue_mask,
                      output_folder, base) -> str:
        overlay = rgb.copy()
        overlay[deposit_mask] = [255, 210, 0]
        path = os.path.join(output_folder, f"{base}_overlay.png")
        Image.fromarray(overlay).save(path)
        return path

    def _save_qc(self, rgb, deposit_mask, tissue_mask,
                 deposit_pct, output_folder, base) -> str:
        fig, axes = plt.subplots(1, 3, figsize=(14, 4))
        fig.patch.set_facecolor("#1e1e2e")

        axes[0].imshow(rgb)
        axes[0].set_title("Original", color="#cdd6f4")
        axes[0].axis("off")

        mask_vis = np.zeros((*rgb.shape[:2], 3), dtype=np.uint8)
        mask_vis[tissue_mask & ~deposit_mask] = [60, 120, 180]
        mask_vis[deposit_mask]               = [255, 210, 0]
        axes[1].imshow(mask_vis)
        axes[1].set_title("Segmentierung\n🟡 Ablagerung  🔵 Gewebe",
                          color="#cdd6f4", fontsize=9)
        axes[1].axis("off")

        deposit_area = int(deposit_mask.sum())
        tissue_area  = int(tissue_mask.sum())
        other_area   = max(tissue_area - deposit_area, 0)

        bars = axes[2].bar(
            ["Mineralisiert", "Nicht mineralisiert"],
            [deposit_area, other_area],
            color=["#f9e2af", "#89b4fa"]
        )
        for bar, val in zip(bars, [deposit_area, other_area]):
            axes[2].text(
                bar.get_x() + bar.get_width() / 2,
                bar.get_height() + max(tissue_area * 0.01, 1),
                f"{val:,} px", ha="center", fontsize=8,
                color="#cdd6f4", fontweight="bold"
            )
        axes[2].set_title(
            f"Von Kossa  –  {deposit_pct:.2f}% mineralisiert",
            color="#cdd6f4"
        )
        axes[2].set_ylabel("Fläche (px)", color="#a6adc8")
        axes[2].tick_params(colors="#a6adc8")
        axes[2].set_facecolor("#11111b")
        for spine in axes[2].spines.values():
            spine.set_edgecolor("#45475a")

        plt.tight_layout()
        path = os.path.join(output_folder, f"{base}_qc.png")
        plt.savefig(path, dpi=120, facecolor="#1e1e2e")
        plt.close()
        return path

    def _save_csv(self, result_dict, output_folder, base) -> str:
        df   = pd.DataFrame([result_dict])
        path = os.path.join(output_folder, f"{base}_results.csv")
        df.to_csv(path, index=False)
        return path

    def run(self, image_path: str, output_folder: str) -> dict:
        folder_name = os.path.basename(os.path.dirname(image_path))
        base        = folder_name
        os.makedirs(output_folder, exist_ok=True)

        print(f"\n── [{self.stain_name}] {base} ──")
        print(f"  Bild: {os.path.basename(image_path)}")

        # 1) Laden + normalisieren
        rgb = load_as_uint8_rgb(image_path)

        # 2) ROI
        if self.roi_mask is not None:
            roi       = self.roi_mask
            rgb_roi   = rgb.copy()
            rgb_roi[~roi] = 255
            print(f"  ROI: {roi.sum():,} px ({100*roi.mean():.1f}%)")
        else:
            roi     = None
            rgb_roi = rgb

        # 3) Segmentierung
        deposit_mask = segment_von_kossa(
            rgb_roi,
            darkness_threshold=self.darkness_threshold,
            min_deposit_area=self.min_deposit_area,
        )
        tissue_mask = segment_tissue(
            rgb_roi,
            background_threshold=self.background_threshold,
        )

        if roi is not None:
            tissue_mask  &= roi
            deposit_mask &= roi

        # 4) Messen
        deposit_area_px = int(deposit_mask.sum())
        tissue_area_px  = int(tissue_mask.sum())
        total_px        = int(rgb.shape[0] * rgb.shape[1])
        mineralized_pct = (deposit_area_px / tissue_area_px * 100
                           if tissue_area_px > 0 else 0.0)

        print(f"  Gewebe:        {tissue_area_px:,} px")
        print(f"  Ablagerungen:  {deposit_area_px:,} px")
        print(f"  Mineralisiert: {mineralized_pct:.2f}%")

        # 5) Export
        result_dict = {
            "stain":                self.stain_name,
            "image":                os.path.basename(image_path),
            "total_px":             total_px,
            "tissue_area_px":       tissue_area_px,
            "mineralized_area_px":  deposit_area_px,
            "mineralized_%":        round(mineralized_pct, 4),
            "darkness_threshold":   self.darkness_threshold,
            "background_threshold": self.background_threshold,
        }

        csv = self._save_csv(result_dict, output_folder, base)
        qc  = self._save_qc(rgb, deposit_mask, tissue_mask,
                             mineralized_pct, output_folder, base)
        ov  = self._save_overlay(rgb, deposit_mask, tissue_mask,
                                  output_folder, base)

        return {
            "n_total":             tissue_area_px,
            "n_positive":          deposit_area_px,
            "n_negative":          tissue_area_px - deposit_area_px,
            "ratio":               mineralized_pct,
            "tissue_area_px":      tissue_area_px,
            "mineralized_area_px": deposit_area_px,
            "mineralized_%":       round(mineralized_pct, 4),
            "overlay":             ov,
            "qc_plot":             qc,
            "csv":                 csv,
        }