# analysis/iso_threshold.py

import os
import re
import numpy as np


def extract_export_number(folder_name: str):
    m = re.search(r'Export-(\d+)', folder_name, re.IGNORECASE)
    return int(m.group(1)) if m else None


def is_iso_folder(folder_name: str) -> bool:
    return "iso" in folder_name.lower()


def pair_sox9_iso(probe_folders: list, iso_folders: list) -> dict:
    """
    Paart Probe- und Iso-Ordner anhand der Export-Nummer.
    Regel: iso_nr = probe_nr + 1

    Returns:
        dict: {probe_folder_path: iso_folder_path or None}
    """
    iso_by_nr = {}
    for iso_path in iso_folders:
        nr = extract_export_number(os.path.basename(iso_path))
        if nr is not None:
            iso_by_nr[nr] = iso_path

    pairs = {}
    for probe_path in probe_folders:
        probe_nr = extract_export_number(os.path.basename(probe_path))
        if probe_nr is None:
            pairs[probe_path] = None
            continue

        iso_path = iso_by_nr.get(probe_nr + 1)
        pairs[probe_path] = iso_path

        if iso_path:
            print(f"  Pair: Export-{probe_nr} ↔ iso Export-{probe_nr+1}")
        else:
            print(f"  ⚠ Kein Iso-Partner für Export-{probe_nr}")

    return pairs


def compute_iso_threshold(iso_folder: str, n_sigma: float = 2.0,
                           roi_mask: np.ndarray = None) -> dict:
    """
    Berechnet den Marker-Threshold aus dem Iso-Kontroll-Bild.

    Threshold = mean(Iso-Signal) + n_sigma * std(Iso-Signal)

    Args:
        iso_folder:  Pfad zum Iso-Ordner
        n_sigma:     Anzahl Standardabweichungen über dem Mittelwert
        roi_mask:    Optional — nur Pixel innerhalb ROI verwenden

    Returns:
        dict mit threshold, mean, std, n_sigma — oder None bei Fehler
    """
    from analysis.core_pipeline import find_images_in_folder
    from PIL import Image

    try:
        marker_path, _ = find_images_in_folder(iso_folder)
    except ValueError as e:
        print(f"  ⚠ Iso-Ordner unvollständig: {e}")
        return None

    img        = np.array(Image.open(marker_path))
    marker_iso = img[..., 0].astype(np.float32) \
                 if img.ndim == 3 else img.astype(np.float32)

    # Nur ROI-Pixel verwenden wenn vorhanden
    if roi_mask is not None and roi_mask.shape == marker_iso.shape:
        pixels = marker_iso[roi_mask & (marker_iso > 0)]
    else:
        pixels = marker_iso[marker_iso > 0]

    if len(pixels) < 100:
        print(f"  ⚠ Zu wenig Pixel in Iso-Kontrolle → Fallback threshold=60")
        return {"threshold": 60, "mean": 0, "std": 0,
                "n_sigma": n_sigma, "method": "fallback"}

    mean = float(np.mean(pixels))
    std  = float(np.std(pixels))
    thr  = float(mean + n_sigma * std)
    thr  = max(10, min(thr, 250))

    print(f"  Iso-Threshold: mean={mean:.1f} + "
          f"{n_sigma}×std={std:.1f} → {thr:.1f}")

    return {
        "threshold": thr,
        "mean":      mean,
        "std":       std,
        "n_sigma":   n_sigma,
        "method":    "iso_control",
    }