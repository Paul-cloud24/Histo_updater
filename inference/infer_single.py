import torch
from torchvision import transforms
from PIL import Image
from models.architectures.backbone import HistologyBackbone

class SingleStainInference:
    def __init__(self, model_path, num_classes=2):
        self.model = HistologyBackbone(num_classes=num_classes)
        self.model.load_state_dict(torch.load(model_path, map_location="cpu"))
        self.model.eval()

        self.t = transforms.Compose([transforms.Resize((224,224)), transforms.ToTensor()])

    def predict(self, image_path):
        img = Image.open(image_path).convert("RGB")
        x = self.t(img).unsqueeze(0)
        with torch.no_grad():
            return self.model(x)
