# analysis/roi_predictor.py
"""
YOLOv8-Seg Inference fuer automatische Knorpel-ROI-Vorhersage.

Gibt ein Polygon (normalisiert 0..1) fuer ein neues Bild zurueck.
"""

import os
import numpy as np
from pathlib import Path


def is_model_available() -> bool:
    from analysis.roi_trainer import get_model_path
    p = get_model_path()
    return p.exists() and p.stat().st_size > 1_000_000


class ROIPredictor:
    """
    Laedt das trainierte YOLOv8-Seg Modell und macht Vorhersagen.

    Verwendung:
        pred = ROIPredictor()
        pred.load()
        result = pred.predict(rgb_array)
        polygon = result["polygon_normalized"]
    """

    def __init__(self):
        self._model = None

    def load(self) -> bool:
        if self._model is not None:
            return True
        try:
            from ultralytics import YOLO
            from analysis.roi_model_registry import get_active_model
            active = get_active_model()
            if not active:
                print("  [Predictor] Kein aktives Modell in Registry")
                return False
            path = Path(active["model_path"])
            if not path.exists():
                print(f"  [Predictor] Modelldatei fehlt: {path}")
                return False
            print(f"  [Predictor] Lade Modell: {active['name']} ({path})")
            self._model = YOLO(str(path))
            print("  [Predictor] Modell geladen ✔")
            return True
        except ImportError:
            print("  [Predictor] ultralytics nicht installiert")
            return False
        except Exception as e:
            print(f"  [Predictor] Ladefehler: {e}")
            return False

    def predict(self, rgb: np.ndarray,
                conf_threshold: float = 0.01) -> dict | None:
        """
        Vorhersage fuer ein RGB-Bild.

        Args:
            rgb:            uint8 H x W x 3
            conf_threshold: Mindest-Konfidenz (0..1)

        Returns:
            dict mit:
              - polygon_normalized: Liste von [x_rel, y_rel]
              - mask:               bool H x W
              - confidence:         float
            oder None wenn nichts gefunden
        """
        if self._model is None:
            return None

        try:
            from PIL import Image as PilImage
            h, w = rgb.shape[:2]
            # Bild auf max 1024px skalieren für Inferenz
            MAX_INFER = 1024
            scale = 1.0
            if max(h, w) > MAX_INFER:
                scale   = MAX_INFER / max(h, w)
                new_w   = int(w * scale)
                new_h   = int(h * scale)
                rgb_inf = np.array(
                    PilImage.fromarray(rgb).resize(
                        (new_w, new_h), PilImage.LANCZOS))
                print(f"  [Predictor] Bild skaliert: {w}x{h} → {new_w}x{new_h}")
            else:
                rgb_inf = rgb
                
            results = self._model(
                rgb_inf,
                conf=conf_threshold,
                verbose=True,       
                imgsz=MAX_INFER,
            )

            if not results or len(results) == 0:
                print("  [Predictor] Keine Ergebnisse")
                return None

            result = results[0]
            print(f"  [Predictor] boxes={len(result.boxes) if result.boxes else 0}  "
                  f"masks={'ja' if result.masks else 'nein'}")

            if result.masks is None or len(result.masks) == 0:
                print("  [Predictor] Keine Maske — conf zu hoch oder Modell unsicher")
                return None

            result = results[0]

            # Segmentierungsmasken prüfen
            if result.masks is None or len(result.masks) == 0:
                print("  [Predictor] Keine Maske gefunden")
                return None

            # Beste Vorhersage (höchster Konfidenz-Score)
            scores = result.boxes.conf.cpu().numpy()
            best   = int(np.argmax(scores))
            conf   = float(scores[best])

            print(f"  [Predictor] {len(scores)} Masken  "
                  f"beste Konfidenz={conf:.3f}")

            # Maske extrahieren
            mask_tensor = result.masks.data[best].cpu().numpy()
            # YOLO gibt Maske in reduzierter Größe — auf Originalgröße skalieren
            from PIL import Image as PilImage
            mask_pil = PilImage.fromarray(
                (mask_tensor * 255).astype(np.uint8))
            mask_pil = mask_pil.resize((w, h), PilImage.NEAREST)
            mask     = np.array(mask_pil) > 127

            # Polygon aus Maske extrahieren
            polygon = _mask_to_polygon(mask, simplify_tolerance=3.0)

            if len(polygon) < 3:
                print("  [Predictor] Polygon zu kurz")
                return None

            print(f"  [Predictor] Polygon: {len(polygon)} Punkte  "
                  f"Fläche: {mask.mean()*100:.1f}%")

            return {
                "polygon_normalized": polygon,
                "mask":               mask,
                "confidence":         conf,
            }

        except Exception as e:
            print(f"  [Predictor] Vorhersage fehlgeschlagen: {e}")
            import traceback
            traceback.print_exc()
            return None


# ── Hilfsfunktionen ───────────────────────────────────────────────────

def _mask_to_polygon(mask: np.ndarray,
                     simplify_tolerance: float = 2.0) -> list:
    """Konvertiert bool-Maske → vereinfachtes normalisiertes Polygon."""
    from skimage.measure import find_contours
    h, w = mask.shape

    contours = find_contours(mask.astype(float), 0.5)
    if not contours:
        return []

    # Größte Kontur
    contour = max(contours, key=len)

    # RDP-Vereinfachung
    pts = _rdp_simplify(contour, simplify_tolerance)

    # Normalisieren: contour = (row, col) = (y, x)
    return [
        [float(col / w), float(row / h)]
        for row, col in pts
    ]


def _rdp_simplify(points: np.ndarray, tol: float) -> np.ndarray:
    if len(points) < 3:
        return points

    def _rdp(pts, t):
        if len(pts) < 3:
            return pts
        start, end = pts[0], pts[-1]
        d = _perp_dist(pts[1:-1], start, end)
        idx = np.argmax(d)
        if d[idx] > t:
            l = _rdp(pts[:idx + 2], t)
            r = _rdp(pts[idx + 1:], t)
            return np.vstack([l[:-1], r])
        return np.array([start, end])

    return _rdp(points, tol)


def _perp_dist(pts, start, end):
    if np.allclose(start, end):
        return np.linalg.norm(pts - start, axis=1)
    v   = end - start
    vl  = np.linalg.norm(v)
    vu  = v / vl
    d   = pts - start
    p   = np.clip(np.dot(d, vu), 0, vl)
    pp  = start + np.outer(p, vu)
    return np.linalg.norm(pts - pp, axis=1)