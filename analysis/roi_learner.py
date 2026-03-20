# analysis/roi_learner.py
"""
ROI-Lern-System fuer automatische Knorpel-Segmentierung.

Prinzip:
  1. Nutzer zeichnet ROI manuell → wird als Referenz gespeichert
  2. System lernt relative Knorpelposition aus allen Referenzen
  3. Fuer neue Bilder: Position schaetzen → SAM-Prompt-Punkte generieren
  4. SAM segmentiert Knorpel automatisch → Nutzer bestaetigt/korrigiert

Gespeichert in: AppData/Roaming/HistoAnalyzer/roi_references/
"""

import os
import json
import numpy as np
from pathlib import Path
from datetime import datetime


# ══════════════════════════════════════════════════════════════════════
# Speicherpfad
# ══════════════════════════════════════════════════════════════════════

def get_reference_dir() -> Path:
    """Gibt den zentralen Speicherordner fuer ROI-Referenzen zurueck."""
    base = Path(os.environ.get("APPDATA", Path.home() / "AppData" / "Roaming"))
    ref_dir = base / "HistoAnalyzer" / "roi_references"
    ref_dir.mkdir(parents=True, exist_ok=True)
    return ref_dir


def get_index_path() -> Path:
    return get_reference_dir() / "references.json"


# ══════════════════════════════════════════════════════════════════════
# Referenzen laden / speichern
# ══════════════════════════════════════════════════════════════════════

def load_references() -> list:
    """Laedt alle gespeicherten ROI-Referenzen."""
    path = get_index_path()
    if not path.exists():
        return []
    try:
        with open(path) as f:
            return json.load(f)
    except Exception:
        return []


def save_reference(image_path: str, polygon_normalized: list,
                   image_shape: tuple, stain: str = "unknown"):
    """
    Speichert eine neue ROI-Referenz.

    Args:
        image_path:          Pfad zum Quellbild
        polygon_normalized:  Liste von (x_rel, y_rel) in 0..1
        image_shape:         (height, width) des Originalbilds
        stain:               Faerbungsname (fuer Logging)
    """
    if len(polygon_normalized) < 3:
        return

    refs = load_references()

    # Polygon-Metriken berechnen (faerbungsunabhaengig)
    pts = np.array(polygon_normalized)
    centroid_x = float(pts[:, 0].mean())
    centroid_y = float(pts[:, 1].mean())

    # Bounding Box relativ
    x_min, y_min = float(pts[:, 0].min()), float(pts[:, 1].min())
    x_max, y_max = float(pts[:, 0].max()), float(pts[:, 1].max())
    width_rel  = x_max - x_min
    height_rel = y_max - y_min

    # Innen-Punkte fuer SAM-Prompt (Gitter innerhalb des Polygons)
    interior_points = _sample_interior_points(polygon_normalized, n=5)

    ref = {
        "id":                 len(refs),
        "timestamp":          datetime.now().isoformat(),
        "image_path":         image_path,
        "stain":              stain,
        "image_h":            image_shape[0],
        "image_w":            image_shape[1],
        "polygon_normalized": polygon_normalized,
        "centroid_x":         centroid_x,
        "centroid_y":         centroid_y,
        "bbox_x_min":         x_min,
        "bbox_y_min":         y_min,
        "bbox_x_max":         x_max,
        "bbox_y_max":         y_max,
        "width_rel":          width_rel,
        "height_rel":         height_rel,
        "interior_points":    interior_points,
    }

    refs.append(ref)

    with open(get_index_path(), "w") as f:
        json.dump(refs, f, indent=2)

    print(f"  [ROI-Learner] Referenz #{ref['id']} gespeichert  "
          f"Zentroid=({centroid_x:.2f}, {centroid_y:.2f})  "
          f"n_refs={len(refs)}")
    return ref


def delete_reference(ref_id: int):
    """Loescht eine Referenz anhand ihrer ID."""
    refs = load_references()
    refs = [r for r in refs if r.get("id") != ref_id]
    with open(get_index_path(), "w") as f:
        json.dump(refs, f, indent=2)


def clear_all_references():
    """Loescht alle Referenzen."""
    with open(get_index_path(), "w") as f:
        json.dump([], f)


# ══════════════════════════════════════════════════════════════════════
# Positionsschaetzung
# ══════════════════════════════════════════════════════════════════════

def estimate_roi_position(n_min: int = 2) -> dict | None:
    """
    Schaetzt die Knorpelposition fuer ein neues Bild anhand aller Referenzen.

    Args:
        n_min: Minimale Anzahl Referenzen fuer Schaetzung

    Returns:
        dict mit:
          - centroid_x/y:       geschaetzte relative Position (0..1)
          - width_rel/height_rel: geschaetzte relative Groesse
          - interior_points:    SAM-Prompt-Punkte (normalisiert)
          - confidence:         0..1 (steigt mit mehr Referenzen)
          - n_refs:             Anzahl verwendeter Referenzen
        oder None wenn zu wenig Referenzen
    """
    refs = load_references()
    if len(refs) < n_min:
        print(f"  [ROI-Learner] Zu wenig Referenzen ({len(refs)}/{n_min})")
        return None

    cx_vals    = np.array([r["centroid_x"]  for r in refs])
    cy_vals    = np.array([r["centroid_y"]  for r in refs])
    w_vals     = np.array([r["width_rel"]   for r in refs])
    h_vals     = np.array([r["height_rel"]  for r in refs])

    # Robuster Mittelwert (Median, resistent gegen Ausreisser)
    cx_est = float(np.median(cx_vals))
    cy_est = float(np.median(cy_vals))
    w_est  = float(np.median(w_vals))
    h_est  = float(np.median(h_vals))

    # Streuung als Unsicherheitsmass
    cx_std = float(np.std(cx_vals))
    cy_std = float(np.std(cy_vals))

    # Konfidenz: steigt mit Anzahl Referenzen, sinkt mit Streuung
    # Maximal 1.0 ab 15 Referenzen mit geringer Streuung
    n_factor  = min(len(refs) / 15.0, 1.0)
    std_factor = max(0.0, 1.0 - (cx_std + cy_std) * 3)
    confidence = round(n_factor * 0.6 + std_factor * 0.4, 3)

    # SAM-Prompt: Gitter-Punkte innerhalb der geschaetzten ROI
    prompt_points = _generate_prompt_points(cx_est, cy_est, w_est, h_est)

    print(f"  [ROI-Learner] Schaetzung aus {len(refs)} Referenzen:  "
          f"cx={cx_est:.3f} cy={cy_est:.3f}  "
          f"w={w_est:.3f} h={h_est:.3f}  "
          f"Konfidenz={confidence:.2f}")

    return {
        "centroid_x":    cx_est,
        "centroid_y":    cy_est,
        "width_rel":     w_est,
        "height_rel":    h_est,
        "cx_std":        cx_std,
        "cy_std":        cy_std,
        "confidence":    confidence,
        "n_refs":        len(refs),
        "prompt_points": prompt_points,  # normalisiert 0..1
    }


def get_reference_count() -> int:
    return len(load_references())


# ══════════════════════════════════════════════════════════════════════
# Hilfsfunktionen
# ══════════════════════════════════════════════════════════════════════

def _sample_interior_points(polygon_normalized: list, n: int = 5) -> list:
    """
    Sampelt n Punkte gleichmaessig innerhalb des Polygons.
    Gibt normalisierte (x, y) zurueck.
    """
    from PIL import Image, ImageDraw
    pts = np.array(polygon_normalized)
    x_min, y_min = pts[:, 0].min(), pts[:, 1].min()
    x_max, y_max = pts[:, 0].max(), pts[:, 1].max()

    # Kleines Render-Canvas fuer Punkt-in-Polygon-Test
    RES = 200
    mask_img = Image.new("L", (RES, RES), 0)
    px_pts = [
        (int((x - x_min) / max(x_max - x_min, 1e-6) * (RES - 1)),
         int((y - y_min) / max(y_max - y_min, 1e-6) * (RES - 1)))
        for x, y in polygon_normalized
    ]
    ImageDraw.Draw(mask_img).polygon(px_pts, fill=255)
    mask = np.array(mask_img) > 0

    ys, xs = np.where(mask)
    if len(xs) == 0:
        # Fallback: Zentroid
        return [[float(pts[:, 0].mean()), float(pts[:, 1].mean())]]

    # Gleichmaessig verteilt sampeln
    idx = np.linspace(0, len(xs) - 1, n, dtype=int)
    result = []
    for i in idx:
        # Zurueck auf normalisierte Koordinaten
        nx = float(xs[i] / (RES - 1) * (x_max - x_min) + x_min)
        ny = float(ys[i] / (RES - 1) * (y_max - y_min) + y_min)
        result.append([nx, ny])
    return result


def _generate_prompt_points(cx: float, cy: float,
                             w: float, h: float) -> list:
    """
    Generiert ein 3x3 Gitter von Prompt-Punkten innerhalb der
    geschaetzten ROI-Bounding-Box (mit 20% Einzug).
    """
    margin = 0.2
    x0 = cx - w / 2 * (1 - margin)
    x1 = cx + w / 2 * (1 - margin)
    y0 = cy - h / 2 * (1 - margin)
    y1 = cy + h / 2 * (1 - margin)

    points = []
    for fy in [0.3, 0.5, 0.7]:
        for fx in [0.3, 0.5, 0.7]:
            px = x0 + (x1 - x0) * fx
            py = y0 + (y1 - y0) * fy
            # Clamp auf 0..1
            points.append([
                float(max(0.01, min(0.99, px))),
                float(max(0.01, min(0.99, py)))
            ])
    return points