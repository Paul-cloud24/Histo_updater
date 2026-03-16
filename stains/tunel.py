# stains/tunel.py
from stains.base_stain import BaseStain

class TunelStain(BaseStain):
    name     = "TUNEL"
    version  = "0.1"
    method   = "rule_based"
    channels = ["tunel", "dapi"]

    def analyze(self, sox9_path, dapi_path, output_folder,
                roi_mask=None, threshold=None, **kwargs):
        raise NotImplementedError(
            "TUNEL-Analyse noch nicht implementiert.\n"
            "Geplant: apoptotische Kerne zählen (TUNEL+ / DAPI gesamt)"
        )