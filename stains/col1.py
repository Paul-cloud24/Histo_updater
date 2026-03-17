# stains/col1.py
from stains.base_stain import BaseStain

class Col1Stain(BaseStain):
    name     = "Kollagen Typ 1"
    version  = "0.1"
    method   = "rule_based"
    channels = ["col1", "dapi"]

    def analyze(self, sox9_path, dapi_path, output_folder,
                roi_mask=None, threshold=None, **kwargs):
        raise NotImplementedError(
            "Col1-Analyse noch nicht implementiert.\n"
            "Geplant: regelbasiert → StarDist fine-tuning"
        )