# stains/mmp13.py
#
# MMP13 (Matrix-Metalloprotease 13) / DAPI — Fluoreszenz-Färbung
#
# Biologie:
#   MMP13 ist eine Kollagenase, die Knorpel-/Knochenmatrix abbaut.
#   Positiv = Zelle exprimiert MMP13 → erhöhte Matrixdegradation.
#   Relevant z.B. bei Osteoarthritis, Frakturheilung, Tumorinvasion.
#
# Analyse-Strategie:
#   Wie Sox9/TUNEL: DAPI-Kerne segmentieren, dann MMP13-Kanal (R)
#   pro Kern messen und als MMP13+ / MMP13- klassifizieren.
#   Default-Threshold etwas höher als TUNEL (50), da MMP13-Signal
#   typischerweise diffuser im Zytoplasma liegt (nicht nukleär).
#   positive_fraction niedrig (0.08), weil das Signal oft partiell ist.

from stains.base_stain import BaseStain


class MMP13Stain(BaseStain):
    implemented = True
    name        = "MMP13/DAPI"
    version     = "1.0"
    method      = "stardist"
    channels    = ["mmp13", "dapi"]
    output_cols = [
        "n_total",
        "n_mmp13_pos",
        "n_mmp13_neg",
        "mmp13_ratio_%",
        "mean_intensity_pos",
        "threshold",
        "threshold_method",
    ]

    def __init__(self, threshold=50.0, n_sigma=2.0, positive_fraction=0.08):
        self.threshold         = threshold
        self.n_sigma           = n_sigma
        self.positive_fraction = positive_fraction

    def analyze(self, marker_path, dapi_path, output_folder,
                roi_mask=None, threshold=None, **kwargs):
        from analysis.core_pipeline import CoreStainPipeline
        thr = threshold if threshold is not None else self.threshold

        pipeline = CoreStainPipeline(
            stain_name        = "MMP13",
            positive_label    = "MMP13+",
            negative_label    = "MMP13-",
            threshold         = thr,
            positive_fraction = kwargs.get("positive_fraction", self.positive_fraction),
            min_nucleus_area  = kwargs.get("min_nucleus_area", 40),
            roi_mask          = roi_mask,
            use_stardist      = True,
        )
        result = pipeline.run(marker_path, dapi_path, output_folder)

        mean_pos = 0.0
        try:
            import pandas as pd, os
            csv_path = result.get("csv")
            if csv_path and os.path.exists(csv_path):
                df = pd.read_csv(csv_path)
                pos_rows = df[df["positive"] == True]
                if len(pos_rows) > 0:
                    mean_pos = round(float(pos_rows["mean_intensity"].mean()), 2)
        except Exception:
            pass

        return {
            "n_total":            result["n_total"],
            "n_positive":         result["n_positive"],
            "n_negative":         result["n_negative"],
            "ratio":              result["ratio"],
            "n_mmp13_pos":        result["n_positive"],
            "n_mmp13_neg":        result["n_negative"],
            "mmp13_ratio_%":      round(result["ratio"], 2),
            "mean_intensity_pos": mean_pos,
            "threshold":          round(thr, 1),
            "threshold_method":   kwargs.get("threshold_method", "manual"),
            "overlay":            result.get("overlay"),
            "csv":                result.get("csv"),
            "qc_plot":            result.get("qc_plot"),
        }

    def get_threshold_dialog(self, folder, parent=None):
        from ui.threshold_dialog import ThresholdDialog
        return ThresholdDialog(folder=folder,
                               initial_threshold=int(self.threshold),
                               parent=parent)

    def get_roi_dialog(self, dapi_path, parent=None):
        from ui.roi_dialog import ROIDialog
        return ROIDialog(dapi_path, parent=parent)

    def supports_iso_calibration(self):
        return True

    def compute_threshold_from_iso(self, iso_folder, roi_mask=None):
        from analysis.iso_threshold import compute_iso_threshold
        result = compute_iso_threshold(iso_folder, n_sigma=self.n_sigma,
                                       roi_mask=roi_mask)
        return result["threshold"] if result else self.threshold