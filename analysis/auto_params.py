# analysis/auto_params.py

import numpy as np
from scipy.ndimage import distance_transform_edt, label
from skimage.filters import threshold_otsu
from skimage.morphology import closing, disk


def estimate_nucleus_params(channel_img: np.ndarray) -> dict:
    """
    Schätzt optimale Segmentierungsparameter automatisch aus dem Bild.

    Ablauf:
      1. Schnelle Vorsegmentierung (Otsu auf Nicht-Null-Pixeln)
      2. Größenverteilung der gefundenen Objekte analysieren
      3. Plausible Einzel-Kerne isolieren (IQR-basierter Filter)
      4. Aus Median-Kerngröße → min_distance, min_size, max_size ableiten

    Args:
        channel_img: (H, W) float32 oder uint8, bereits ROI-maskiert
                     (schwarze Pixel = außerhalb ROI)

    Returns:
        dict mit:
          min_distance  – für peak_local_max (Watershed)
          min_size      – minimale Kerngröße in Pixeln
          max_size      – maximale Kerngröße in Pixeln (Cluster-Grenze)
          median_area   – geschätzte Median-Kernfläche
          nucleus_diam  – geschätzter Kerndurchmesser in Pixeln
    """

    # ── 1) Schnelle Vorsegmentierung ─────────────────────────────────
    nonzero = channel_img[channel_img > 0]
    if len(nonzero) < 100:
        # Kein Signal → sichere Defaults zurückgeben
        return _default_params()

    p1  = np.percentile(nonzero, 1)
    p99 = np.percentile(nonzero, 99)
    norm = np.clip((channel_img.astype(np.float32) - p1) / max(p99 - p1, 1),
                   0, 1) * 255

    norm_roi = norm[channel_img > 0]
    otsu = threshold_otsu(norm_roi)
    p95  = np.percentile(norm_roi, 95)
    thr  = min(max(otsu, p95 * 0.5), 130)

    binary = closing(norm > thr, disk(2))

    # ── 2) Alle Objekte labeln und Größen messen ─────────────────────
    labeled, _ = label(binary)
    if labeled.max() == 0:
        return _default_params()

    sizes = np.bincount(labeled.ravel())[1:]  # Index 0 = Hintergrund

    # ── 3) Plausible Einzel-Kerne isolieren ──────────────────────────
    # Grober Filter: 10px–2000px (schließt Rauschen und große Cluster aus)
    rough = sizes[(sizes >= 10) & (sizes <= 2000)]
    if len(rough) < 10:
        return _default_params()

    # IQR-basierter Filter: nur Objekte im "normalen" Bereich
    q25 = np.percentile(rough, 25)
    q75 = np.percentile(rough, 75)
    iqr = q75 - q25
    lower = max(10, q25 - 1.5 * iqr)
    upper = q75 + 1.5 * iqr

    single_nuclei = rough[(rough >= lower) & (rough <= upper)]
    if len(single_nuclei) < 5:
        single_nuclei = rough  # Fallback: alle grob plausiblen

    # ── 4) Parameter ableiten ────────────────────────────────────────
    median_area  = float(np.median(single_nuclei))
    nucleus_diam = 2.0 * np.sqrt(median_area / np.pi)  # Kreis-Annahme

    # min_distance: ~40% des Radius — trennt eng beieinander liegende Kerne
    min_distance = max(2, int(nucleus_diam * 0.4))

    # min_size: untere 10% der IQR-gefilterten Verteilung
    min_size = max(10, int(np.percentile(single_nuclei, 10) * 0.5))

    # max_size: typischer Kern × 4 (4 Kerne zusammengewachsen = Cluster)
    max_size = int(median_area * 4.0)

    params = {
        "min_distance": min_distance,
        "min_size":     min_size,
        "max_size":     max_size,
        "median_area":  round(median_area, 1),
        "nucleus_diam": round(nucleus_diam, 1),
        "n_sample":     len(single_nuclei),
    }

    print(f"  Auto-Parameter geschätzt aus {len(single_nuclei)} Kernen:")
    print(f"    Median-Fläche:   {median_area:.0f} px²")
    print(f"    Kerndurchmesser: {nucleus_diam:.1f} px")
    print(f"    min_distance:    {min_distance}")
    print(f"    min_size:        {min_size}")
    print(f"    max_size:        {max_size}")

    return params


def _default_params() -> dict:
    """Sichere Defaults wenn automatische Schätzung fehlschlägt."""
    print("  Auto-Parameter: kein Signal → verwende Defaults")
    return {
        "min_distance": 4,
        "min_size":     30,
        "max_size":     500,
        "median_area":  50.0,
        "nucleus_diam": 8.0,
        "n_sample":     0,
    }