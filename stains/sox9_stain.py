# stains/sox9_stain.py
from stains.base_stain import BaseStain

class Sox9Stain(BaseStain):
    implemented = True,
    name     = "Sox9/DAPI"
    version  = "2.0"
    method   = "stardist"
    channels = ["sox9", "dapi"]
    output_cols = ["n_total", "n_positive", "n_negative",
                   "ratio_%", "threshold", "threshold_method"]

    def __init__(self, threshold=60.0, n_sigma=2.0):
        self.threshold = threshold
        self.n_sigma   = n_sigma

    def analyze(self, marker_path, dapi_path, output_folder,
                roi_mask=None, threshold=None, **kwargs):
        from analysis.core_pipeline import CoreStainPipeline
        thr = threshold if threshold is not None else self.threshold
        pipeline = CoreStainPipeline(
            stain_name="Sox9",
            positive_label="Sox9+",
            negative_label="Sox9-",
            threshold=thr,
            roi_mask=roi_mask,
            use_stardist=roi_mask is not None,
            positive_fraction=kwargs.get("positive_fraction", 0.10),
            min_nucleus_area =kwargs.get("min_nucleus_area",  40),
        )
        result = pipeline.run(marker_path, dapi_path, output_folder)
        result["threshold"]        = round(thr, 1)
        result["threshold_method"] = kwargs.get("threshold_method", "manual")
        return result

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