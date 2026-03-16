# stains/base_stain.py
from abc import ABC, abstractmethod
import numpy as np

class BaseStain(ABC):
    name         : str  = "Unbekannt"
    version      : str  = "0.1"
    method       : str  = "rule_based"
    channels     : list = ["dapi"]
    output_cols  : list = ["n_total", "n_positive", "n_negative", "ratio_%"]

    @abstractmethod
    def analyze(self, sox9_path, dapi_path, output_folder,
                roi_mask=None, threshold=None, **kwargs) -> dict:
        raise NotImplementedError

    def get_threshold_dialog(self, folder, parent=None):
        return None

    def get_roi_dialog(self, dapi_path, parent=None):
        return None

    def supports_iso_calibration(self):
        return False

    def compute_threshold_from_iso(self, iso_folder, roi_mask=None):
        raise NotImplementedError

    def __repr__(self):
        return f"<{self.__class__.__name__} method={self.method} v={self.version}>"