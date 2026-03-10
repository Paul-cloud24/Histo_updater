from models.architectures.backbone import HistologyBackbone
from inference.infer_single import SingleStainInference
import os

class BaseStain:
    def __init__(self, name, num_classes=2, tile_size=256, normalize=False):
        self.name = name
        self.num_classes = num_classes
        self.tile_size = tile_size
        self.normalize = normalize

    def create_model(self):
        return HistologyBackbone(num_classes=self.num_classes)

    def paths(self):
        base = f"data/{self.name}"
        return {
            "raw": f"{base}/raw",
            "tiles": f"{base}/tiles",
            "preprocessed": f"{base}/preprocessed",
            "labels": f"{base}/labels.csv",
            "save_model": f"models/trained/{self.name}.pth",
            "onnx_model": f"models/onnx/{self.name}.onnx",
        }

    def load_for_inference(self):
        model_path = f"models/trained/{self.name}.pth"
        if not os.path.exists(model_path):
            raise FileNotFoundError(f"Missing model: {model_path}")
        return SingleStainInference(model_path, num_classes=self.num_classes)
