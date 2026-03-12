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


def find_images_in_folder(folder):
    sox9_path = None
    dapi_path = None
    for f in os.listdir(folder):
        if not f.lower().endswith((".tif", ".tiff", ".png", ".jpg", ".jpeg")):
            continue
        full = os.path.join(folder, f)
        if not os.path.isfile(full):
            continue
        kind = classify_image(full)
        print(f"  {f} → {kind}")
        if kind == "sox9" and sox9_path is None:
            sox9_path = full
        elif kind == "dapi" and dapi_path is None:
            dapi_path = full
    return sox9_path, dapi_path

class Sox9Pipeline:

    def __init__(self, worker=None, threshold=10000,
                 min_nucleus_area=50, positive_fraction=0.10, nucleus_diameter=60, use_cellpose=False):
        self.worker           = worker
        self.threshold        = threshold
        self.min_nucleus_area = min_nucleus_area
        self.positive_fraction = positive_fraction
        self.nucleus_diameter = nucleus_diameter
        self.use_cellpose = use_cellpose

        self.tile_size    = 512
        self.tile_overlap = 32
        self.current_tile = 0
        self.total_tiles  = 0

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
        p1  = np.percentile(channel_img, 1)
        p99 = np.percentile(channel_img, 99)
        norm = np.clip((channel_img - p1) / max(p99 - p1, 1) * 255, 0, 255)
        print(f"{label_prefix} | Normierung p1={p1:.0f} p99={p99:.0f} "
            f"→ norm mean={norm.mean():.1f}")

        # 2) Threshold — Otsu als Untergrenze, aber mind. p95 des normierten Bildes
        #    verhindert dass große Gewebebereiche als Kerne erkannt werden
        otsu = threshold_otsu(norm)
        p95  = np.percentile(norm[norm > 0], 95)
        thr  = max(otsu, p95 * 0.5)   # nimm den höheren der beiden
        thr  = min(thr, 130)           # aber nie über 130 (sonst zu wenig Kerne)
        binary = norm > thr
        binary = closing(binary, disk(2))
        print(f"{label_prefix} | Threshold={thr:.1f} → "
            f"{binary.sum():,} positive Pixel ({100*binary.mean():.2f}%)")

        # 3) Größenfilter: nur echte Kern-Größen behalten (50–5000 px bei 10x)
        labeled_tmp = label(binary)
        sizes = np.bincount(labeled_tmp.ravel())
        valid_labels = np.where((sizes >= 50) & (sizes <= 5000))[0]
        binary_clean = np.isin(labeled_tmp, valid_labels)

        n_removed = labeled_tmp.max() - len(valid_labels)
        print(f"{label_prefix} | Größenfilter (50–5000px): "
            f"{len(valid_labels)} behalten, {n_removed} entfernt")
        
        # ── 4) Watershed zum Trennen überlappender Kerne ─────────────────
        dist    = distance_transform_edt(binary)
        coords  = peak_local_max(dist, min_distance=8, labels=binary)
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
        base           = os.path.splitext(os.path.basename(sox9_path))[0]
        results_folder = os.path.join(output_folder, "results")
        os.makedirs(results_folder, exist_ok=True)

        print(f"\n── Analyse: {base} ──")
        print(f"  Sox9: {os.path.basename(sox9_path)}")
        print(f"  DAPI: {os.path.basename(dapi_path)}")

        # 1) Laden
        sox9_img = self._load_channel(sox9_path)
        dapi_img = self._load_channel(dapi_path)

        # 2) Cellpose nur auf DAPI
        print("DAPI Segmentierung (Cellpose 2.2)...")
        dapi_masks = self._segment(dapi_img, label_prefix="DAPI")
        n_dapi_total   = int(dapi_masks.max())
        print(f"  → {n_dapi_total} Kerne gefunden")

        if n_dapi_total == 0:
            print("  Keine Kerne gefunden, Analyse abgebrochen.")
            return {"n_dapi_total": 0, "n_positive": 0}

        # 3) Sox9-Intensität in DAPI-Kernen messen
        print("Sox9-Intensität messen...")
        df = self._measure_sox9_in_dapi_nuclei(dapi_masks, sox9_img,
                                            positive_fraction=self.positive_fraction)
        df["sox9_positive"] = df["positive_pixel_fraction"] >= self.positive_fraction

        n_sox9_pos  = int(df["sox9_positive"].sum())
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