# stains/safranin_o.py
from stains.base_stain import BaseStain

class SafraninStain(BaseStain):
    name     = "Safranin O"
    version  = "0.1"
    method   = "rule_based"
    channels = ["safranin", "dapi"]

    def analyze(self, sox9_path, dapi_path, output_folder,
                roi_mask=None, threshold=None, **kwargs):
        raise NotImplementedError(
            "Safranin O-Analyse noch nicht implementiert.\n"
            "Geplant: Flächenmessung der Safranin-Färbung (kein Zellkern-Counting)"
        )