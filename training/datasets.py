from torch.utils.data import Dataset
from PIL import Image
import pandas as pd
import os

class StainDataset(Dataset):
    def __init__(self, tiles_dir, labels_csv, transform=None):
        self.tiles_dir = tiles_dir
        self.df = pd.read_csv(labels_csv)
        self.transform = transform

    def __len__(self):
        return len(self.df)

    def __getitem__(self, idx):
        r = self.df.iloc[idx]
        img = Image.open(os.path.join(self.tiles_dir, r.filename)).convert("RGB")
        if self.transform:
            img = self.transform(img)
        return img, r.label
