# stains/von_kossa.py
"""
Von-Kossa-Färbung — Flächenbasierte Mineralisierungsanalyse.

Methode:
  Brightfield RGB → Dunkel-Segmentierung → Flächenverhältnis

Ausgabe:
  - mineralized_%       : Anteil der mineralisierten Fläche am Gewebe
  - mineralized_area_px : Absolute Ablagerungsfläche in Pixeln
  - tissue_area_px      : Gesamte Gewebsfläche in Pixeln

Typische Threshold-Werte:
  darkness_threshold   = 80   (schwarze Ablagerungen)
  background_threshold = 220  (weißer Hintergrund)
"""

from stains.base_stain import BaseStain


class VonKossaStain(BaseStain):
    implemented  = True
    name         = "Von Kossa"
    version      = "1.0"
    method       = "rule_based"
    channels     = ["brightfield_rgb"]
    output_cols  = [
        "tissue_area_px",
        "mineralized_area_px",
        "mineralized_%",
    ]

    def __init__(self,
                 darkness_threshold   : int = 80,
                 background_threshold : int = 220,
                 min_deposit_area     : int = 50):
        self.darkness_threshold   = darkness_threshold
        self.background_threshold = background_threshold
        self.min_deposit_area     = min_deposit_area

    def analyze(self, marker_path, dapi_path, output_folder,
                roi_mask=None, threshold=None, **kwargs) -> dict:
        """
        Analysiert ein Von-Kossa-Brightfield-Bild.

        Hinweis:
            marker_path  → RGB-Brightfield-Bild (Von-Kossa-Färbung)
            dapi_path    → wird ignoriert (kein DAPI bei Hellfeld)
            threshold    → wird als darkness_threshold interpretiert (falls übergeben)
        """
        from analysis.brightfield_pipeline import BrightfieldPipeline

        # Threshold-Override: wenn ein Wert aus dem Dialog kommt,
        # wird er als darkness_threshold verwendet
        dark_thr = int(threshold) if threshold is not None \
                   else self.darkness_threshold
        bg_thr   = kwargs.get("background_threshold", self.background_threshold)
        min_area = kwargs.get("min_deposit_area",     self.min_deposit_area)

        pipeline = BrightfieldPipeline(
            stain_name           = "Von Kossa",
            darkness_threshold   = dark_thr,
            background_threshold = bg_thr,
            min_deposit_area     = min_area,
            roi_mask             = roi_mask,
        )

        return pipeline.run(marker_path, output_folder)

    # ── UI-Hooks ──────────────────────────────────────────────────────

    def get_threshold_dialog(self, folder, parent=None):
        """
        Öffnet einen Threshold-Dialog für den Darkness-Threshold.
        Zeigt das RGB-Bild mit Live-Vorschau der Ablagerungssegmentierung.
        """
        from ui.kossa_threshold_dialog import KossaThresholdDialog
        return KossaThresholdDialog(
            folder=folder,
            initial_threshold=self.darkness_threshold,
            parent=parent
        )

    def get_roi_dialog(self, dapi_path, parent=None):
        """
        Gibt ROI-Dialog zurück — nutzt das Brightfield-Bild statt DAPI.
        dapi_path wird hier als Brightfield-Pfad übergeben (Konvention aus app.py).
        """
        from ui.roi_dialog import ROIDialog
        return ROIDialog(dapi_path, parent=parent)

    def supports_iso_calibration(self):
        return False
