
# analysis/core_pipeline.py
"""
Generische Fluoreszenz-Analyse Pipeline.
Wird von Sox9Stain, TunelStain und allen zukünftigen Färbungen verwendet.

Prinzip:
  1. Marker-Kanal (R) + DAPI-Kanal (B) laden
  2. ROI anwenden
  3. DAPI-Kerne segmentieren (StarDist → Watershed Fallback)
  4. Marker-Intensität pro Kern messen
  5. Klassifizieren: positiv wenn >= positive_fraction der Pixel > threshold
  6. Export: CSV, Overlay, QC-Plot
"""
import torch
from analysis.hardware_profile import evaluate_hardware
import os
import numpy as np
import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from PIL import Image, ImageDraw
from skimage.measure import regionprops_table, label
from skimage.filters import threshold_otsu
from skimage.morphology import closing, disk
from skimage.segmentation import watershed
from skimage.feature import peak_local_max
from scipy.ndimage import distance_transform_edt
try:
    import imagecodecs
    if not hasattr(imagecodecs, 'lzw_decode'):
        imagecodecs.lzw_decode = imagecodecs.lzw_decompress
except Exception:
    pass


# ══════════════════════════════════════════════════════════════════════
# Ordner-Erkennung
# ══════════════════════════════════════════════════════════════════════

def find_stain_folders(root_folder: str, stain_name: str) -> tuple:
    """
    Findet alle Unterordner die zum Stain gehören.
    Trennt automatisch in Probe-Ordner und Iso-Ordner.

    Args:
        root_folder: Wurzelordner
        stain_name:  z.B. "Sox9", "TUNEL", "Col1"

    Returns:
        (probe_folders, iso_folders) — beide sortiert
    """
    root_abs     = os.path.abspath(root_folder)
    probe_folders = []
    iso_folders   = []
    keyword       = stain_name.lower()

    for entry in os.scandir(root_folder):
        if not entry.is_dir():
            continue
        if os.path.abspath(entry.path) == root_abs:
            continue
        if entry.name == "Results":
            continue

        name_lower = entry.name.lower()
        if keyword not in name_lower:
            continue

        if "iso" in name_lower:
            iso_folders.append(entry.path)
        else:
            probe_folders.append(entry.path)

    probe_folders.sort()
    iso_folders.sort()

    print(f"Gefundene {stain_name}-Ordner: {len(probe_folders)} Proben, "
          f"{len(iso_folders)} Iso-Kontrollen")
    for f in probe_folders:
        print(f"  Probe: {os.path.basename(f)}")
    for f in iso_folders:
        print(f"  Iso:   {os.path.basename(f)}")

    return probe_folders, iso_folders


def classify_image(image_path: str) -> str:
    """Klassifiziert ein Bild anhand der dominanten Farbe."""
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
            return "marker"   # Sox9, TUNEL, Col1 etc. → R-Kanal
        if b / total > 0.5 and r / total < 0.2:
            return "dapi"
        if r / total > 0.25 and b / total > 0.25:
            return "overlay"
        return "gray"
    except Exception as e:
        print(f"Klassifikation fehlgeschlagen: {e}")
        return "unknown"


def find_images_in_folder(folder: str) -> tuple:
    """
    Findet Marker- und DAPI-Bild in einem Ordner.
    Fallback: Kanäle aus Overlay-TIF extrahieren.

    Returns:
        (marker_path, dapi_path)
    """
    marker_path  = None
    dapi_path    = None
    overlay_path = None

    for f in sorted(os.listdir(folder)):
        if not f.lower().endswith((".tif", ".tiff")):
            continue
        if f.startswith("._"):   # macOS Verstecktdateien
            continue
        if "extracted_" in f:    # bereits extrahierte Temp-Files überspringen
            continue
        path = os.path.join(folder, f)
        kind = classify_image(path)

        if kind == "marker" and marker_path is None:
            marker_path = path
        elif kind == "dapi" and dapi_path is None:
            dapi_path = path
        elif kind in ("gray", "overlay") and overlay_path is None:
            overlay_path = path

    # Fallback: Overlay aufsplitten
    if (marker_path is None or dapi_path is None) and overlay_path is not None:
        print(f"  Fallback: extrahiere Kanäle aus "
              f"{os.path.basename(overlay_path)}")
        marker_path, dapi_path = _split_overlay_channels(
            overlay_path, folder)

    if marker_path is None or dapi_path is None:
        raise ValueError(
            f"Unvollständiger Ordner '{os.path.basename(folder)}': "
            f"marker={'✔' if marker_path else '✗'}  "
            f"dapi={'✔' if dapi_path else '✗'} → wird übersprungen."
        )
    return marker_path, dapi_path


def _split_overlay_channels(overlay_path: str, folder: str) -> tuple:
    """Extrahiert R- (Marker) und B-Kanal (DAPI) aus RGB-Overlay."""
    base = os.path.splitext(os.path.basename(overlay_path))[0]
    img  = np.array(Image.open(overlay_path))

    if img.ndim != 3 or img.shape[2] < 3:
        raise ValueError(f"{overlay_path} ist kein RGB-Bild")

    marker_out = os.path.join(folder, f"extracted_{base}_marker.tif")
    dapi_out   = os.path.join(folder, f"extracted_{base}_dapi.tif")

    Image.fromarray(img[..., 0]).save(marker_out)   # R = Marker
    Image.fromarray(img[..., 2]).save(dapi_out)     # B = DAPI

    print(f"  → Marker: {os.path.basename(marker_out)}")
    print(f"  → DAPI:   {os.path.basename(dapi_out)}")
    return marker_out, dapi_out


# ══════════════════════════════════════════════════════════════════════
# Core Pipeline
# ══════════════════════════════════════════════════════════════════════

class CoreStainPipeline:
    """
    Generische Fluoreszenz-Analyse Pipeline.
    Verwendet von Sox9Stain, TunelStain und allen zukünftigen Färbungen.

    Parameter:
        stain_name:        Name der Färbung (für Ausgabedateien)
        positive_label:    Bezeichnung für positive Kerne (z.B. "Sox9+", "TUNEL+")
        negative_label:    Bezeichnung für negative Kerne
        threshold:         Pixel-Threshold für Marker-Kanal (0–255)
        positive_fraction: Mindestanteil positiver Pixel pro Kern (0–1)
        roi_mask:          Optional — bool-Array (h, w)
        use_stardist:      StarDist für Segmentierung verwenden
        worker:            QRunnable für Fortschritts-Signale (optional)
    """

    def __init__(self,
                 stain_name       : str   = "Marker",
                 positive_label   : str   = "positiv",
                 negative_label   : str   = "negativ",
                 threshold        : float = 60.0,
                 positive_fraction: float = 0.10,
                 min_nucleus_area : int   = 40,
                 roi_mask         : np.ndarray = None,
                 use_stardist     : bool  = True,
                 worker           = None):

        self.stain_name        = stain_name
        self.positive_label    = positive_label
        self.negative_label    = negative_label
        self.threshold         = min(int(threshold), 255)
        self.positive_fraction = positive_fraction
        self.min_nucleus_area  = min_nucleus_area
        self.roi_mask          = roi_mask
        self.use_stardist      = use_stardist
        self.worker            = worker
        self.hw = evaluate_hardware()
        torch.set_num_threads(self.hw["torch_threads"])

        # StarDist laden
        self.stardist_model = None
        if use_stardist:
            try:
                from stardist.models import StarDist2D
                print(f"[{stain_name}] Lade StarDist '2D_versatile_fluo'...")
                self.stardist_model = StarDist2D.from_pretrained(
                    "2D_versatile_fluo")
                print(f"[{stain_name}] StarDist geladen ✔")
            except ImportError:
                print(f"[{stain_name}] ⚠ StarDist nicht installiert "
                      f"→ Fallback: Watershed")
                self.use_stardist = False

    # ── Bild laden ────────────────────────────────────────────────────

    def _load_channel(self, image_path: str) -> np.ndarray:
        """Lädt den relevanten Kanal: R für Marker, B für DAPI."""
        try:
            pil = Image.open(image_path)
            img = np.array(pil).astype(np.float32)
        except Exception:
            from tifffile import imread
            img = imread(image_path).astype(np.float32)
            if img.ndim == 3 and img.shape[0] < 10:
                img = img.transpose(1, 2, 0)

        if img.ndim == 2:
            return img

        kind = classify_image(image_path)
        if kind == "marker":
            print(f"  Marker ({self.stain_name}) → R-Kanal "
                  f"(max={img[...,0].max():.0f})")
            return img[..., 0]
        elif kind == "dapi":
            print(f"  DAPI → B-Kanal (max={img[...,2].max():.0f})")
            return img[..., 2]
        else:
            means = [img[..., c].mean() for c in range(img.shape[-1])]
            best  = int(np.argmax(means))
            print(f"  Unbekannt → Kanal {best}")
            return img[..., best]

    # ── Segmentierung ─────────────────────────────────────────────────

    def _segment(self, dapi_img: np.ndarray) -> np.ndarray:
        """Segmentiert DAPI-Kerne. StarDist bevorzugt, Watershed als Fallback."""
        if self.use_stardist and self.stardist_model is not None:
            return self._segment_stardist(dapi_img)
        return self._segment_watershed(dapi_img)

    def _segment_stardist(self, dapi_img: np.ndarray) -> np.ndarray:
        from csbdeep.utils import normalize
        nonzero = dapi_img[dapi_img > 0]
        if len(nonzero) < 100:
            return np.zeros_like(dapi_img, dtype=np.int32)

        img_norm = normalize(dapi_img.astype(np.float32), 1, 99.8)
        img_norm[dapi_img == 0] = 0

        # n_tiles anpassen je nach Bildgröße → verhindert RAM-Overflow
        masks, _ = self.stardist_model.predict_instances(img_norm)
        print(f"  StarDist: {dapi_img.shape[1]}x{dapi_img.shape[0]}px "
            f"({'GPU' if self.hw['use_gpu'] else 'CPU'})")
        
        n = masks.max()
        print(f"  StarDist: {n} Kerne segmentiert")
        return masks.astype(np.int32)

    def _segment_watershed(self, dapi_img: np.ndarray) -> np.ndarray:
        from analysis.auto_params import estimate_nucleus_params

        nonzero = dapi_img[dapi_img > 0]
        if len(nonzero) == 0:
            print("  Watershed: kein Signal")
            return np.zeros_like(dapi_img, dtype=np.int32)

        p1   = np.percentile(nonzero, 1)
        p99  = np.percentile(nonzero, 99)
        norm = np.clip((dapi_img.astype(np.float32) - p1) /
                       max(p99 - p1, 1), 0, 1) * 255

        norm_roi = norm[dapi_img > 0]
        otsu = threshold_otsu(norm_roi)
        p95  = np.percentile(norm_roi, 95)
        thr  = min(max(otsu, p95 * 0.5), 130)

        binary = closing(norm > thr, disk(2))

        # Auto-Parameter
        params       = estimate_nucleus_params(dapi_img)
        min_distance = params["min_distance"]
        min_size     = params["min_size"]
        max_size     = params["max_size"]

        # Größenfilter
        lbl_tmp = label(binary)
        sizes   = np.bincount(lbl_tmp.ravel())
        valid   = np.where((sizes >= min_size) & (sizes <= max_size))[0]
        binary_clean = np.isin(lbl_tmp, valid)

        print(f"  Watershed: Threshold={thr:.1f}  "
              f"{len(valid)} Objekte nach Größenfilter")

        dist    = distance_transform_edt(binary_clean)
        coords  = peak_local_max(dist, min_distance=min_distance,
                                 labels=binary_clean)
        seeds   = np.zeros(dist.shape, dtype=bool)
        seeds[tuple(coords.T)] = True
        markers = label(seeds)
        masks   = watershed(-dist, markers, mask=binary_clean)

        print(f"  Watershed: {dapi_img.shape[1]}x{dapi_img.shape[0]}px "
            f"(CPU, {self.hw['pp_workers']} Kerne)")
        n = masks.max()
        print(f"  Watershed: {n} Kerne segmentiert")
        return masks.astype(np.int32)

    # ── Messen ────────────────────────────────────────────────────────

    def _measure(self, dapi_masks: np.ndarray,
                 marker_img: np.ndarray) -> pd.DataFrame:
        """Misst Marker-Intensität pro DAPI-Kern."""
        props = regionprops_table(
            dapi_masks,
            intensity_image=marker_img,
            properties=("label", "area", "centroid",
                        "mean_intensity", "max_intensity")
        )
        df = pd.DataFrame(props)
        df = df[df["area"] >= self.min_nucleus_area].reset_index(drop=True)

        # Vektorisiert statt Schleife — 100x schneller bei 8000 Kernen
        from skimage.measure import regionprops
        label_to_frac = {}
        for region in regionprops(dapi_masks, intensity_image=marker_img):
            if region.area < self.min_nucleus_area:
                continue
            px   = region.image_intensity.ravel()
            frac = (px >= self.threshold).mean()
            label_to_frac[region.label] = frac

        df["positive_pixel_fraction"] = df["label"].map(label_to_frac).fillna(0)
        df["positive"] = df["positive_pixel_fraction"] >= self.positive_fraction

        print(f"  Threshold: {self.threshold}  "
              f"Gemessen: {len(df)}  "
              f"{self.positive_label}: {df['positive'].sum()}")
        return df

    # ── Export ────────────────────────────────────────────────────────

    def _save_overlay(self, marker_img, dapi_masks, df,
                      output_folder, base) -> str:
        norm = (marker_img / max(1.0, marker_img.max()) * 255).astype(np.uint8)
        overlay = Image.fromarray(norm).convert("RGB")
        draw    = ImageDraw.Draw(overlay)

        for _, row in df.iterrows():
            x, y  = int(row["centroid-1"]), int(row["centroid-0"])
            r     = 10
            color = "lime" if row["positive"] else "#555555"
            draw.ellipse((x-r, y-r, x+r, y+r), outline=color, width=2)

        path = os.path.join(output_folder, f"{base}_overlay.png")
        overlay.save(path)
        return path

    def _save_qc(self, df, output_folder, base) -> str:
        fig, axes = plt.subplots(1, 2, figsize=(10, 4))

        axes[0].hist(df["mean_intensity"], bins=50,
                     color="#89b4fa", alpha=0.8, edgecolor="none")
        axes[0].axvline(self.threshold, color="#f38ba8", linestyle="--",
                        label=f"Threshold = {self.threshold}")
        axes[0].set_title(f"{self.stain_name} Intensität in DAPI-Kernen")
        axes[0].set_xlabel("Mean Intensity")
        axes[0].set_ylabel("Anzahl Kerne")
        axes[0].legend()

        n_pos = int(df["positive"].sum())
        n_neg = len(df) - n_pos
        bars  = axes[1].bar(
            [self.positive_label, self.negative_label],
            [n_pos, n_neg],
            color=["#a6e3a1", "#585b70"]
        )
        for bar, val in zip(bars, [n_pos, n_neg]):
            axes[1].text(
                bar.get_x() + bar.get_width() / 2,
                bar.get_height() + 0.3,
                str(val), ha="center", fontweight="bold", color="white"
            )
        axes[1].set_title(f"Klassifikation  (n={len(df)})")
        axes[1].set_ylabel("Anzahl")

        plt.tight_layout()
        path = os.path.join(output_folder, f"{base}_qc.png")
        plt.savefig(path, dpi=120, facecolor="#1e1e2e")
        plt.close()
        return path

    def _save_csv(self, df, output_folder, base) -> str:
        path = os.path.join(output_folder, f"{base}_results.csv")
        df.to_csv(path, index=False)
        return path

    # ── Haupt-Entry-Point ─────────────────────────────────────────────

    def run(self, marker_path: str, dapi_path: str,
            output_folder: str) -> dict:

        folder_name = os.path.basename(os.path.dirname(marker_path))
        base        = folder_name
        os.makedirs(output_folder, exist_ok=True)

        print(f"\n── [{self.stain_name}] {base} ──")
        print(f"  Marker: {os.path.basename(marker_path)}")
        print(f"  DAPI:   {os.path.basename(dapi_path)}")

        # 1) Laden
        marker_img = self._load_channel(marker_path)
        dapi_img   = self._load_channel(dapi_path)

        # 2) ROI anwenden
        roi_mask = self.roi_mask if self.roi_mask is not None \
                   else np.ones(dapi_img.shape, dtype=bool)
        print(f"  ROI: {roi_mask.sum():,} px "
              f"({100*roi_mask.mean():.1f}% des Bildes)")

        dapi_roi   = dapi_img.copy();   dapi_roi[~roi_mask]   = 0
        marker_roi = marker_img.copy(); marker_roi[~roi_mask] = 0

        # 3) Segmentierung
        print("  DAPI Segmentierung...")
        dapi_masks  = self._segment(dapi_roi)
        n_total     = int(dapi_masks.max())
        print(f"  → {n_total} Kerne gefunden")

        if n_total == 0:
            return {"n_total": 0, "n_positive": 0, "ratio": 0.0,
                    "overlay": None, "csv": None}

        # 4) Messen
        print(f"  {self.stain_name}-Intensität messen...")
        df = self._measure(dapi_masks, marker_roi)

        n_positive = int(df["positive"].sum())
        n_measured = len(df)
        ratio      = n_positive / max(1, n_total) * 100

        print(f"  ── {self.positive_label}: {n_positive}/{n_total} "
              f"= {ratio:.1f}% ──")

        # 5) Export
        csv = self._save_csv(df, output_folder, base)
        qc  = self._save_qc(df, output_folder, base)
        ov  = self._save_overlay(marker_img, dapi_masks, df,
                                 output_folder, base)

        # Summary
        summary = pd.DataFrame([{
            "stain":             self.stain_name,
            "dapi_total":        n_total,
            "dapi_measured":     n_measured,
            self.positive_label: n_positive,
            self.negative_label: n_measured - n_positive,
            "ratio_%":           round(ratio, 2),
            "threshold":         self.threshold,
            "positive_fraction": self.positive_fraction,
        }])
        summary.to_csv(
            os.path.join(output_folder, f"{base}_summary.csv"),
            index=False
        )

        return {
            "n_total":    n_total,
            "n_positive": n_positive,
            "n_negative": n_total - n_positive,
            "ratio":      ratio,
            "csv":        csv,
            "qc_plot":    qc,
            "overlay":    ov,
        }
