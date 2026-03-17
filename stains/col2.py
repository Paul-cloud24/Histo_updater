# stains/col2.py
from stains.base_stain import BaseStain

class Col2Stain(BaseStain):
    name     = "Kollagen Typ 2"
    version  = "0.1"
    method   = "rule_based"
    channels = ["col2", "dapi"]

    def analyze(self, sox9_path, dapi_path, output_folder,
                roi_mask=None, threshold=None, **kwargs):
        raise NotImplementedError(
            "Col2-Analyse noch nicht implementiert.\n"
            "Geplant: regelbasiert → StarDist fine-tuning"
        )