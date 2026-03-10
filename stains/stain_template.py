from models.architectures.backbone import HistologyBackbone
from inference.infer_single import SingleStainInference
import os

class StainModel:
    def __init__(self, stain_name, num_classes=2):
        self.stain_name = stain_name
        self.num_classes = num_classes

    def create_model(self):
        return HistologyBackbone(num_classes=self.num_classes)

    def paths(self):
        base = f"data/{self.stain_name}"
        return {
            "tiles": f"{base}/tiles",
            "raw": f"{base}/raw",
            "preprocessed": f"{base}/preprocessed",
            "labels": f"{base}/labels.csv",
            "save_model": f"models/trained/{self.stain_name}.pth",
            "onnx_model": f"models/onnx/{self.stain_name}.onnx"
        }

    def load_for_inference(self):
        p = f"models/trained/{self.stain_name}.pth"
        if not os.path.exists(p):
            raise FileNotFoundError(p)
        return SingleStainInference(p, self.num_classes)
