# stains/tunel.py
from stains.base_stain import BaseStain

class TunelStain(BaseStain):
    implemented = True,
    name     = "TUNEL/DAPI"
    version  = "1.0"
    method   = "stardist"
    channels = ["tunel", "dapi"]
    output_cols = ["n_total", "n_apoptotic", "n_viable",
                   "apoptosis_%", "threshold", "threshold_method"]

    def __init__(self, threshold=40.0, n_sigma=2.0,
                 positive_fraction=0.10):
        self.threshold         = threshold
        self.n_sigma           = n_sigma
        self.positive_fraction = positive_fraction

    def analyze(self, marker_path, dapi_path, output_folder,
                roi_mask=None, threshold=None, **kwargs):
        from analysis.core_pipeline import CoreStainPipeline
        thr = threshold if threshold is not None else self.threshold
        pipeline = CoreStainPipeline(
            stain_name="TUNEL",
            positive_label="TUNEL+",
            negative_label="TUNEL-",
            threshold=thr,
            positive_fraction=self.positive_fraction,
            roi_mask=roi_mask,
            use_stardist=False,
        )
        result = pipeline.run(marker_path, dapi_path, output_folder)
        # Ausgabe umbenennen für TUNEL-Semantik
        return {
            "n_total":          result["n_total"],
            "n_apoptotic":      result["n_positive"],
            "n_viable":         result["n_negative"],
            "apoptosis_%":      round(result["ratio"], 2),
            "threshold":        round(thr, 1),
            "threshold_method": kwargs.get("threshold_method", "manual"),
            "overlay":          result.get("overlay"),
            "csv":              result.get("csv"),
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