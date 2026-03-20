# analysis/sam_segmenter.py
"""
MobileSAM Integration fuer automatische Knorpel-Segmentierung.

MobileSAM ist ~40MB, laeuft auf CPU in ~2-3 Sekunden pro Bild.
Wird beim ersten Aufruf automatisch heruntergeladen.

Weights-Speicherort: AppData/Roaming/HistoAnalyzer/models/mobile_sam.pt
"""

import os
import numpy as np
from pathlib import Path


MODEL_URL  = "https://github.com/ChaoningZhang/MobileSAM/raw/master/weights/mobile_sam.pt"
MODEL_SIZE = 40_000_000   # ~40 MB


def get_model_path() -> Path:
    base = Path(os.environ.get("APPDATA", Path.home() / "AppData" / "Roaming"))
    model_dir = base / "HistoAnalyzer" / "models"
    model_dir.mkdir(parents=True, exist_ok=True)
    return model_dir / "mobile_sam.pt"


def is_model_available() -> bool:
    p = get_model_path()
    return p.exists() and p.stat().st_size > MODEL_SIZE // 2


def download_model(progress_callback=None) -> bool:
    """
    Laedt MobileSAM-Weights herunter.

    Args:
        progress_callback: optional fn(percent: int)

    Returns:
        True bei Erfolg
    """
    import urllib.request

    dest = get_model_path()
    print(f"  [SAM] Download: {MODEL_URL}")
    print(f"  [SAM] Ziel:     {dest}")

    try:
        def _reporthook(count, block_size, total_size):
            if total_size > 0 and progress_callback:
                pct = min(int(count * block_size / total_size * 100), 100)
                progress_callback(pct)

        urllib.request.urlretrieve(MODEL_URL, dest, reporthook=_reporthook)
        print(f"  [SAM] Download abgeschlossen ({dest.stat().st_size // 1024} KB)")
        return True
    except Exception as e:
        print(f"  [SAM] Download fehlgeschlagen: {e}")
        if dest.exists():
            dest.unlink()
        return False


# ══════════════════════════════════════════════════════════════════════
# SAM Segmenter
# ══════════════════════════════════════════════════════════════════════

class SAMSegmenter:
    """
    Wrapper um MobileSAM fuer interaktive Knorpel-Segmentierung.

    Verwendung:
        seg = SAMSegmenter()
        seg.load_model()
        seg.set_image(rgb_array)
        mask = seg.predict_from_points(prompt_points_normalized)
    """

    def __init__(self):
        self._model     = None
        self._predictor = None
        self._img_h     = None
        self._img_w     = None

    def load_model(self) -> bool:
        if self._predictor is not None:
            return True

        if not is_model_available():
            print("  [SAM] Modell nicht gefunden — bitte zuerst herunterladen")
            return False

        try:
            import warnings
            warnings.filterwarnings("ignore", category=FutureWarning)
            warnings.filterwarnings("ignore", category=UserWarning)

            from mobile_sam import sam_model_registry, SamPredictor
            print("  [SAM] Lade MobileSAM...")
            self._model = sam_model_registry["vit_t"](
                checkpoint=str(get_model_path())
            )
            self._model.eval()
            self._predictor = SamPredictor(self._model)
            print("  [SAM] Modell geladen ✔")
            return True
        except ImportError:
            print("  [SAM] mobile_sam nicht installiert → pip install mobile-sam")
            return False
        except Exception as e:
            print(f"  [SAM] Ladefehler: {e}")
            return False

    def set_image(self, rgb: np.ndarray):
        """Setzt das Bild fuer die Segmentierung (uint8 H x W x 3)."""
        if self._predictor is None:
            raise RuntimeError("Modell nicht geladen")
        self._img_h, self._img_w = rgb.shape[:2]
        self._predictor.set_image(rgb)

    def predict_from_points(self,
                             prompt_points_normalized: list,
                             foreground: bool = True) -> np.ndarray | None:
        """
        Segmentiert anhand normalisierter Prompt-Punkte.

        Args:
            prompt_points_normalized: Liste von [x_rel, y_rel] in 0..1
            foreground:               True = Punkte sind im Objekt

        Returns:
            bool-Maske (H x W) oder None bei Fehler
        """
        if self._predictor is None or self._img_h is None:
            return None

        try:
            pts_px = np.array([
                [x * self._img_w, y * self._img_h]
                for x, y in prompt_points_normalized
            ], dtype=np.float32)

            labels = np.ones(len(pts_px), dtype=np.int32) if foreground \
                     else np.zeros(len(pts_px), dtype=np.int32)

            masks, scores, _ = self._predictor.predict(
                point_coords=pts_px,
                point_labels=labels,
                multimask_output=True,
            )

            # Beste Maske (hoechster Score) zurueckgeben
            best_idx = int(np.argmax(scores))
            print(f"  [SAM] {len(masks)} Masken  "
                  f"bester Score={scores[best_idx]:.3f}  "
                  f"Flaeche={masks[best_idx].sum():,} px")
            return masks[best_idx].astype(bool)

        except Exception as e:
            print(f"  [SAM] Vorhersage fehlgeschlagen: {e}")
            return None

    def predict_from_box(self,
                         x_min_rel: float, y_min_rel: float,
                         x_max_rel: float, y_max_rel: float) -> np.ndarray | None:
        """
        Segmentiert anhand einer Bounding-Box (normalisiert 0..1).
        Alternativ zu Punkt-Prompts — oft stabiler bei grossen Regionen.
        """
        if self._predictor is None or self._img_h is None:
            return None

        try:
            box = np.array([
                x_min_rel * self._img_w,
                y_min_rel * self._img_h,
                x_max_rel * self._img_w,
                y_max_rel * self._img_h,
            ], dtype=np.float32)

            masks, scores, _ = self._predictor.predict(
                box=box[None],
                multimask_output=True,
            )

            best_idx = int(np.argmax(scores))
            print(f"  [SAM] Box-Prompt  "
                  f"Score={scores[best_idx]:.3f}  "
                  f"Flaeche={masks[best_idx].sum():,} px")
            return masks[best_idx].astype(bool)

        except Exception as e:
            print(f"  [SAM] Box-Vorhersage fehlgeschlagen: {e}")
            return None

    def mask_to_polygon(self, mask: np.ndarray,
                        simplify_tolerance: float = 2.0) -> list:
        """
        Konvertiert eine binaere Maske in ein vereinfachtes Polygon.

        Returns:
            Liste von (x_rel, y_rel) normalisiert 0..1
        """
        from skimage.measure import find_contours
        h, w = mask.shape

        contours = find_contours(mask.astype(float), 0.5)
        if not contours:
            return []

        # Groesste Kontur nehmen
        contour = max(contours, key=len)

        # Polygon vereinfachen (Ramer-Douglas-Peucker)
        pts = _rdp_simplify(contour, simplify_tolerance)

        # Normalisieren: contour ist (row, col) = (y, x)
        normalized = [
            [float(col / w), float(row / h)]
            for row, col in pts
        ]
        return normalized


# ══════════════════════════════════════════════════════════════════════
# Hilfsfunktionen
# ══════════════════════════════════════════════════════════════════════

def _rdp_simplify(points: np.ndarray, tolerance: float) -> np.ndarray:
    """
    Ramer-Douglas-Peucker Algorithmus zur Polygon-Vereinfachung.
    Reduziert Punkte bei gleichbleibender Form.
    """
    if len(points) < 3:
        return points

    # Rekursive Implementation
    def _rdp(pts, tol):
        if len(pts) < 3:
            return pts
        start, end = pts[0], pts[-1]
        # Senkrechter Abstand aller Punkte zur Linie start→end
        d = _perpendicular_distances(pts[1:-1], start, end)
        max_idx = np.argmax(d)
        if d[max_idx] > tol:
            left  = _rdp(pts[:max_idx + 2], tol)
            right = _rdp(pts[max_idx + 1:], tol)
            return np.vstack([left[:-1], right])
        return np.array([start, end])

    return _rdp(points, tolerance)


def _perpendicular_distances(pts, start, end) -> np.ndarray:
    """Berechnet senkrechte Abstaende von pts zur Linie start→end."""
    if np.allclose(start, end):
        return np.linalg.norm(pts - start, axis=1)
    line_vec  = end - start
    line_len  = np.linalg.norm(line_vec)
    line_unit = line_vec / line_len
    vecs      = pts - start
    proj      = np.dot(vecs, line_unit)
    proj      = np.clip(proj, 0, line_len)
    proj_pts  = start + np.outer(proj, line_unit)
    return np.linalg.norm(pts - proj_pts, axis=1)


# ══════════════════════════════════════════════════════════════════════
# Convenience-Funktion fuer den Dialog
# ══════════════════════════════════════════════════════════════════════

def run_sam_suggestion(rgb: np.ndarray,
                       estimate: dict,
                       segmenter: "SAMSegmenter") -> dict | None:
    """
    Fuehrt SAM-Segmentierung mit geschaetzter Position aus.

    Args:
        rgb:        uint8 H x W x 3
        estimate:   Ergebnis von roi_learner.estimate_roi_position()
        segmenter:  Geladener SAMSegmenter

    Returns:
        dict mit mask (bool H x W) und polygon_normalized (liste)
        oder None bei Fehler
    """
    segmenter.set_image(rgb)

    # Strategie 1: Punkt-Prompts (Gitter im geschaetzten Bereich)
    prompt_pts = estimate.get("prompt_points", [])
    mask = None

    if prompt_pts:
        mask = segmenter.predict_from_points(prompt_pts, foreground=True)

    # Strategie 2: Bounding-Box als Fallback
    if mask is None or mask.sum() == 0:
        cx = estimate["centroid_x"]
        cy = estimate["centroid_y"]
        w  = estimate["width_rel"]
        h  = estimate["height_rel"]
        mask = segmenter.predict_from_box(
            cx - w / 2, cy - h / 2,
            cx + w / 2, cy + h / 2,
        )

    if mask is None or mask.sum() == 0:
        return None

    polygon = segmenter.mask_to_polygon(mask, simplify_tolerance=3.0)
    if len(polygon) < 3:
        return None

    return {
        "mask":               mask,
        "polygon_normalized": polygon,
        "confidence":         estimate.get("confidence", 0.0),
        "n_refs":             estimate.get("n_refs", 0),
    }