# analysis/sox9_pipeline.py

import os
import numpy as np
import pandas as pd
import torch
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from concurrent.futures import ThreadPoolExecutor

from cellpose import models
from skimage.measure import regionprops_table, label
from skimage.filters import threshold_otsu
from skimage.morphology import remove_small_objects, closing, disk
from skimage.segmentation import watershed
from skimage.feature import peak_local_max
from skimage.measure import label
from scipy.ndimage import distance_transform_edt
from skimage.morphology import remove_small_objects
from PIL import Image, ImageDraw

from .hardware_profile import evaluate_hardware
from .roi import compute_roi_mask, apply_roi, save_roi_preview
from ui.roi_dialog import ROIDialog


# ── Diese beiden Funktionen aus deiner alten Pipeline übernehmen ─────

def classify_image(image_path):
    from tifffile import imread
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
        print(f"Klassifikation fehlgeschlagen: {e}")
        return "unknown"


def find_images_in_folder(folder: str):
    sox9_path = None
    dapi_path = None
    overlay_path = None  # c1-2.tif

    for f in sorted(os.listdir(folder)):
        if not f.lower().endswith((".tif", ".tiff")):
            continue
        if f.startswith("._"):   # macOS-Verstecktdateien
            continue
        path = os.path.join(folder, f)
        kind = classify_image(path)
        if kind == "sox9" and sox9_path is None:
            sox9_path = path
        elif kind == "dapi" and dapi_path is None:
            dapi_path = path
        elif kind == "gray" and overlay_path is None:
            overlay_path = path

    # Fallback: nur c1-2.tif vorhanden → R=Sox9, B=DAPI direkt extrahieren
    if (sox9_path is None or dapi_path is None) and overlay_path is not None:
        print(f"  Fallback: extrahiere Kanäle aus {os.path.basename(overlay_path)}")
        sox9_path, dapi_path = _split_overlay_channels(overlay_path, folder)

    if sox9_path is None or dapi_path is None:
        raise ValueError(
            f"Unvollständiger Ordner '{os.path.basename(folder)}': "
            f"sox9={'✔' if sox9_path else '✗'}  "
            f"dapi={'✔' if dapi_path else '✗'} → wird übersprungen."
        )
    return sox9_path, dapi_path


def _split_overlay_channels(overlay_path: str, folder: str):
    """
    Extrahiert R- und B-Kanal aus einem RGB-Overlay-TIFF
    und speichert sie als temporäre Einzelkanal-TIFs.
    """
    from PIL import Image as PilImage
    import numpy as np

    base    = os.path.splitext(os.path.basename(overlay_path))[0]
    img     = np.array(PilImage.open(overlay_path))

    if img.ndim != 3 or img.shape[2] < 3:
        raise ValueError(f"Overlay {overlay_path} ist kein RGB-Bild")

    sox9_arr = img[..., 0]   # R-Kanal = Sox9
    dapi_arr = img[..., 2]   # B-Kanal = DAPI

    # Als temp-TIF speichern (im selben Ordner, Prefix "extracted_")
    sox9_out = os.path.join(folder, f"extracted_{base}_sox9.tif")
    dapi_out = os.path.join(folder, f"extracted_{base}_dapi.tif")

    PilImage.fromarray(sox9_arr).save(sox9_out)
    PilImage.fromarray(dapi_arr).save(dapi_out)

    print(f"  → Sox9-Kanal: {os.path.basename(sox9_out)}")
    print(f"  → DAPI-Kanal:  {os.path.basename(dapi_out)}")

    return sox9_out, dapi_out
class Sox9Pipeline:

    def __init__(self, worker=None, threshold = 60,roi_mask=None,
                 min_nucleus_area=40, positive_fraction=0.10, nucleus_diameter=10, use_cellpose=False):
        self.worker           = worker
        self.threshold        = min(int(threshold),255)
        self.min_nucleus_area = min_nucleus_area
        self.positive_fraction = positive_fraction
        self.nucleus_diameter = nucleus_diameter
        self.use_cellpose = use_cellpose

        self.tile_size    = 512
        self.tile_overlap = 32
        self.current_tile = 0
        self.total_tiles  = 0

        self.roi_mask = roi_mask 

        self.hw = evaluate_hardware()
        torch.set_num_threads(self.hw["torch_threads"])

        if use_cellpose:
            print("Lade Cellpose 2.2 Modell...")
            self.model = models.Cellpose(gpu=self.hw["use_gpu"], model_type="nuclei")
            print("Cellpose Modell geladen")
        else:
            print("Segmentierung: Threshold+Watershed (kein Cellpose)")
            self.model = None

    # ── Bild laden ───────────────────────────────────────────────────

    def _load_channel(self, image_path):
        """
        Lädt den biologisch relevanten Kanal:
        - Sox9-Bild (rot):  R-Kanal
        - DAPI-Bild (blau): B-Kanal
        Erkennung über Farbklassifikation, nicht über Helligkeit.
        """
        from PIL import Image as PILImage
        from tifffile import imread as tiff_imread

        # Laden — Pillow für RGB-TIFFs, tifffile für echte 16-bit
        try:
            pil = PILImage.open(image_path)
            img = np.array(pil).astype(np.float32)
        except Exception:
            img = tiff_imread(image_path).astype(np.float32)
            if img.ndim == 3 and img.shape[0] < 10:
                img = img.transpose(1, 2, 0)
            if img.ndim == 4:
                if img.shape[1] < 10:
                    img = img.transpose(0, 2, 3, 1)
                img = img.max(axis=0)

        if img.ndim == 2:
            return img  # bereits Graustufen

        # Farbklassifikation → richtigen Kanal wählen
        kind = classify_image(image_path)

        if kind == "sox9":
            # Sox9 = rot → R-Kanal (Index 0)
            print(f"  _load_channel: Sox9 → R-Kanal  (max={img[...,0].max():.0f})")
            return img[..., 0]

        elif kind == "dapi":
            # DAPI = blau → B-Kanal (Index 2)
            print(f"  _load_channel: DAPI  → B-Kanal  (max={img[...,2].max():.0f})")
            return img[..., 2]

        else:
            # Fallback: hellsten Kanal
            means = [img[..., c].mean() for c in range(img.shape[-1])]
            best  = int(np.argmax(means))
            print(f"  _load_channel: unbekannt → Kanal {best} (mean={means[best]:.1f})")
            return img[..., best]

    # ── Tile-Padding ─────────────────────────────────────────────────

    def _pad_tile(self, tile):
        padded = np.zeros((self.tile_size, self.tile_size), dtype=tile.dtype)
        padded[:tile.shape[0], :tile.shape[1]] = tile
        return padded

    # ── Cellpose 2.2 Segmentierung ───────────────────────────────────

    def _segment(self, channel_img, label_prefix=""):
        """
        Für hochkontrast-Spot-Bilder (DAPI bei 10x):
        Percentile-Normierung → Otsu-Threshold → Watershed
        Das ist zuverlässiger als Cellpose bei sehr dunklem Hintergrund.
        """
        h, w = channel_img.shape
        step = self.tile_size - self.tile_overlap

        # ── 1) Percentile-Normierung ─────────────────────────────────────
        nonzero = channel_img[channel_img > 0]

        if len(nonzero) == 0:
            print(f"{label_prefix } | Warnung: Alle Pixel sind 0 → keine Segmentierung möglich")
            return np.zeros_like(channel_img, dtype=np.int32)
        
        p1  = np.percentile(nonzero, 1)
        p99 = np.percentile(nonzero, 99)
        print(f"{label_prefix} | Normierung p1={p1:.0f} p99={p99:.0f} → "
          f"norm mean={nonzero.mean():.1f}")
        
        norm = np.clip((channel_img.astype(np.float32) - p1) / max(p99 - p1, 1), 0, 1)*255

        # 2) Threshold — Otsu als Untergrenze, aber mind. p95 des normierten Bildes
        #    verhindert dass große Gewebebereiche als Kerne erkannt werden

        norm_roi = norm[channel_img > 0]
        otsu = threshold_otsu(norm_roi)
        p95  = np.percentile(norm_roi, 95)
        thr  = max(otsu, p95 * 0.5)   # nimm den höheren der beiden
        thr  = min(thr, 130)           # aber nie über 130 (sonst zu wenig Kerne)
        binary = norm > thr
        binary = closing(binary, disk(2))
        print(f"{label_prefix} | Threshold={thr:.1f} → "
            f"{binary.sum():,} positive Pixel ({100*binary.mean():.2f}%)")

        # 3) Größenfilter: nur echte Kern-Größen behalten (30–500 px bei 10x)
        labeled_tmp = label(binary)
        sizes = np.bincount(labeled_tmp.ravel())
        valid_labels = np.where((sizes >= 30) & (sizes <= 500))[0]
        binary_clean = np.isin(labeled_tmp, valid_labels)

        n_removed = labeled_tmp.max() - len(valid_labels)
        print(f"{label_prefix} | Größenfilter (30–500px): "
            f"{len(valid_labels)} behalten, {n_removed} entfernt")
        from analysis.auto_params import estimate_nucleus_params

        # Parameter automatisch schätzen
        params = estimate_nucleus_params(channel_img)
        min_distance = params["min_distance"]
        min_size     = params["min_size"]
        max_size     = params["max_size"]

        # Größenfilter mit auto-Werten
        valid_labels = np.where((sizes >= min_size) & (sizes <= max_size))[0]
        # ── 4) Watershed zum Trennen überlappender Kerne ─────────────────
        dist    = distance_transform_edt(binary)
        coords  = peak_local_max(dist, min_distance=min_distance, labels=binary_clean)
        seeds   = np.zeros(dist.shape, dtype=bool)
        seeds[tuple(coords.T)] = True
        markers = label(seeds)
        masks   = watershed(-dist, markers, mask=binary).astype(np.int32)

        n = masks.max()
        print(f"{label_prefix} | {n} Kerne segmentiert")

        if self.worker:
            self.worker.current_tile = 1
            self.worker.total_tiles  = 1

        return masks

    # ── Sox9 in DAPI-Kernen messen ───────────────────────────────────

    def _measure_sox9_in_dapi_nuclei(self, dapi_masks, sox9_img, positive_fraction=0.1):
        """
        Misst Sox9-Intensität innerhalb jedes DAPI-Kerns.

        positive_fraction=0.1 bedeutet: ein Kern gilt als Sox9+ wenn
        mindestens 10% seiner Pixel über dem Threshold liegen.
        Das entspricht am ehesten dem was du im ImageJ-Preview siehst.
        """
        props = regionprops_table(
            dapi_masks,
            intensity_image=sox9_img,
            properties=(
                "label", "area", "centroid",
                "mean_intensity", "max_intensity", "min_intensity",
            )
        )
        df = pd.DataFrame(props)
        df = df[df["area"] >= self.min_nucleus_area].reset_index(drop=True)

        # Für jeden Kern: wie viel % der Pixel liegen über Threshold?
        positive_pixel_fractions = []
        for nucleus_label in df["label"]:
            nucleus_pixels = sox9_img[dapi_masks == nucleus_label]
            frac = (nucleus_pixels >= self.threshold).mean()
            positive_pixel_fractions.append(frac)

        df["positive_pixel_fraction"] = positive_pixel_fractions

        # Sox9+ wenn mindestens positive_fraction der Pixel über Threshold
        df["sox9_positive"] = df["positive_pixel_fraction"] >= positive_fraction

        # Diagnostik
        print(f"  Threshold:              {self.threshold:.0f}")
        print(f"  Positive-Pixel-Anteil:  >={positive_fraction*100:.0f}% der Kernfläche")
        print(f"  mean_intensity Median:  {df['mean_intensity'].median():.0f}")
        print(f"  max_intensity Median:   {df['max_intensity'].median():.0f}")

        return df

    # ── Overlay ──────────────────────────────────────────────────────

    def _save_overlay(self, sox9_img, dapi_masks, df, output_folder, base_name):
        norm = (sox9_img / max(1.0, sox9_img.max()) * 255).astype(np.uint8)
        overlay = Image.fromarray(norm).convert("RGB")
        draw    = ImageDraw.Draw(overlay)

        for _, row in df.iterrows():
            x, y = int(row["centroid-1"]), int(row["centroid-0"])
            r     = 10
            color = "lime" if row["sox9_positive"] else "#555555"
            draw.ellipse((x-r, y-r, x+r, y+r), outline=color, width=2)

        path = os.path.join(output_folder, f"{base_name}_overlay.png")
        overlay.save(path)
        return path

    # ── QC-Plot ──────────────────────────────────────────────────────

    def _save_qc(self, df, output_folder, base_name):
        fig, axes = plt.subplots(1, 2, figsize=(10, 4))

        axes[0].hist(df["mean_intensity"], bins=50,
                     color="steelblue", alpha=0.8, edgecolor="white")
        axes[0].axvline(self.threshold, color="red", linestyle="--",
                        label=f"Threshold = {self.threshold:.0f}")
        axes[0].set_title("Sox9-Intensität in DAPI-Kernen")
        axes[0].set_xlabel("Mean Sox9 intensity")
        axes[0].set_ylabel("Anzahl Kerne")
        axes[0].legend()

        n_pos = int(df["sox9_positive"].sum())
        n_neg = len(df) - n_pos
        bars  = axes[1].bar(
            ["Sox9+\n(DAPI-validiert)", "Sox9-"],
            [n_pos, n_neg],
            color=["#22bb22", "#555555"]
        )
        for bar, val in zip(bars, [n_pos, n_neg]):
            axes[1].text(
                bar.get_x() + bar.get_width() / 2,
                bar.get_height() + 0.3,
                str(val), ha="center", fontweight="bold"
            )
        axes[1].set_title(f"Klassifikation  (gesamt: {len(df)} Kerne)")
        axes[1].set_ylabel("Anzahl")

        plt.tight_layout()
        path = os.path.join(output_folder, f"{base_name}_qc.png")
        plt.savefig(path, dpi=120)
        plt.close()
        return path

    # ── CSV ──────────────────────────────────────────────────────────

    def _save_csv(self, df, output_folder, base_name):
        path = os.path.join(output_folder, f"{base_name}_results.csv")
        df.to_csv(path, index=False)
        return path

    # ── Haupt-Entry-Point ────────────────────────────────────────────

    def run(self, sox9_path, dapi_path, output_folder):
        folder_name = os.path.basename(os.path.dirname(sox9_path))
        base        = folder_name   

        results_folder = output_folder   
        os.makedirs(results_folder, exist_ok=True)

        print(f"\n── Analyse: {base} ──")
        print(f"  Sox9: {os.path.basename(sox9_path)}")
        print(f"  DAPI: {os.path.basename(dapi_path)}")

        # 1) Laden
        sox9_img = self._load_channel(sox9_path)
        dapi_img = self._load_channel(dapi_path)

        # 2) ROI zuerst berechnen
        roi_mask = ROIDialog.load_roi_mask(dapi_path, h=dapi_img.shape[0], w=dapi_img.shape[1])
        if roi_mask is None:
            roi_mask = np.ones(dapi_img.shape, dtype=bool)  # kein ROI = ganzes Bild

        save_roi_preview(sox9_img, roi_mask,
                     os.path.join(results_folder, f"{base}_roi.png"))
        print(f"ROI: {roi_mask.sum():,} px ({100*roi_mask.mean():.1f}% des Bildes)")

        # 3) Beide Bilder auf ROI zuschneiden — BEVOR Segmentierung läuft
        dapi_roi = dapi_img.copy()
        sox9_roi = sox9_img.copy()
        dapi_roi[~roi_mask] = 0   # außerhalb ROI = schwarz → Cellpose/Watershed ignoriert das
        sox9_roi[~roi_mask] = 0

        # 4) Segmentierung NUR auf ROI-Daten
        print("DAPI Segmentierung (nur ROI)...")
        dapi_masks = self._segment(dapi_roi, label_prefix="DAPI")
        n_nuclei   = int(dapi_masks.max())
        print(f"  → {n_nuclei} Kerne in ROI gefunden")

        if n_nuclei == 0:
            self.signals.finished("Keine Kerne in der ROI gefunden.")
            return
        
        # 5) Sox9-Intensität in DAPI-Kernen messen
        print("Sox9-Intensität messen...")
        df = self._measure_sox9_in_dapi_nuclei(dapi_masks, sox9_img,
                                            positive_fraction=self.positive_fraction)
        df["sox9_positive"] = df["positive_pixel_fraction"] >= self.positive_fraction

        n_sox9_pos  = int(df["sox9_positive"].sum())
        n_dapi_total = int(dapi_masks.max())
        n_measured  = len(df)   # nach min_nucleus_area Filter
        ratio       = n_sox9_pos / max(1, n_dapi_total) * 100

        print(f"  DAPI gesamt (segmentiert): {n_dapi_total}")
        print(f"  Davon gemessen (≥{self.min_nucleus_area}px): {n_measured}")
        print(f"  Sox9+:                     {n_sox9_pos}")
        print(f"  ── Sox9+/DAPI-Ratio:       {n_sox9_pos}/{n_dapi_total} = {ratio:.1f}% ──")

        # Ratio in CSV als Zusammenfassung
        summary = pd.DataFrame([{
            "dapi_total":        n_dapi_total,
            "dapi_measured":     n_measured,
            "sox9_positive":     n_sox9_pos,
            "sox9_negative":     n_measured - n_sox9_pos,
            "sox9_dapi_ratio_%": round(ratio, 2),
            "threshold_used":    self.threshold,
            "positive_fraction": self.positive_fraction,
        }])

        os.makedirs(results_folder, exist_ok=True)
        csv = self._save_csv(df, results_folder, base)
        qc  = self._save_qc(df, results_folder, base)
        ov  = self._save_overlay(sox9_img, dapi_masks, df, results_folder, base)

        summary = pd.DataFrame([{
            "dapi_total":        n_dapi_total,
            "dapi_measured":     n_measured,
            "sox9_positive":     n_sox9_pos,
            "sox9_negative":     n_measured - n_sox9_pos,
            "sox9_dapi_ratio_%": round(ratio, 2),
            "threshold_used":    self.threshold,
            "positive_fraction": self.positive_fraction,
        }])
        summary_path = os.path.join(results_folder, f"{base}_summary.csv")
        summary.to_csv(summary_path, index=False)

        return {
            "csv": csv, "qc_plot": qc, "overlay": ov,
            "n_dapi_total":  n_dapi_total,
            "n_positive":    n_sox9_pos,
            "ratio":         ratio,
        }