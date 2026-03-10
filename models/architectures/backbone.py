import torch.nn as nn
from torchvision import models

class HistologyBackbone(nn.Module):
    def __init__(self, num_classes=2, dropout=0.35):
        super().__init__()
        self.base = models.efficientnet_b0(weights="IMAGENET1K_V1")
        in_features = self.base.classifier[1].in_features

        self.base.classifier = nn.Sequential(
            nn.Dropout(dropout),
            nn.Linear(in_features, num_classes)
        )

    def forward(self, x):
        return self.base(x)
