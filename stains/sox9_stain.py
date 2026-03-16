# stains/sox9_stain.py
import numpy as np
from stains.base_stain import BaseStain

class Sox9Stain(BaseStain):
    name     = "Sox9/DAPI"
    version  = "1.1"
    method   = "stardist"
    channels = ["sox9", "dapi"]
    output_cols = [
        "n_total", "n_positive", "n_negative",
        "ratio_%", "threshold", "threshold_method"
    ]

    def __init__(self, threshold: float = 60.0, n_sigma: float = 2.0):
        self.threshold = threshold
        self.n_sigma   = n_sigma

    def analyze(self, sox9_path, dapi_path, output_folder,
                roi_mask=None, threshold=None, **kwargs) -> dict:
        from analysis.sox9_pipeline import Sox9Pipeline
        thr = threshold if threshold is not None else self.threshold
        pipeline = Sox9Pipeline(
            worker=None,
            threshold=thr,
            roi_mask=roi_mask,
            use_stardist=True,
        )
        result = pipeline.run(
            sox9_path=sox9_path,
            dapi_path=dapi_path,
            output_folder=output_folder,
        )
        return {
            "n_total":          result["n_dapi_total"],
            "n_positive":       result["n_positive"],
            "n_negative":       result["n_dapi_total"] - result["n_positive"],
            "ratio_%":          round(result["ratio"], 2),
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