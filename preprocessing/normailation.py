from staintools import StainNormalizer
import numpy as np
from PIL import Image

def normalize_image(img, target):
    n = StainNormalizer(method="macenko")
    n.fit(np.array(target))
    return Image.fromarray(n.transform(np.array(img)))
