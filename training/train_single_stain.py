import torch
from torch.utils.data import DataLoader
from training.datasets import StainDataset
from training.transforms import get_train_transforms
from models.architectures.backbone import HistologyBackbone

def train_stain(tiles_dir, labels_csv, save_path, num_classes=2, epochs=10):
    ds = StainDataset(tiles_dir, labels_csv, get_train_transforms())
    dl = DataLoader(ds, batch_size=32, shuffle=True)

    model = HistologyBackbone(num_classes=num_classes)
    model.train()

    opt = torch.optim.Adam(model.parameters(), lr=1e-4)
    loss_fn = torch.nn.CrossEntropyLoss()

    for e in range(epochs):
        for x, y in dl:
            pred = model(x)
            loss = loss_fn(pred, y)
            opt.zero_grad()
            loss.backward()
            opt.step()

    torch.save(model.state_dict(), save_path)
    return model
