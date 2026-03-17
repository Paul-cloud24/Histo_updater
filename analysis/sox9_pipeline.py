# analysis/sox9_pipeline.py
'''
import os
from cv2 import normalize
import numpy as np
import pandas as pd
import torch
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from concurrent.futures import ThreadPoolExecutor

from cellpose import models
from skimage.measure import regionprops_table, label
from skimage.filters import threshold_otsu
from skimage.morphology import remove_small_objects, closing, disk
from skimage.segmentation import watershed
from skimage.feature import peak_local_max
from skimage.measure import label
from scipy.ndimage import distance_transform_edt
from skimage.morphology import remove_small_objects
from PIL import Image, ImageDraw

from .hardware_profile import evaluate_hardware

def classify_image(image_path):
    from tifffile import imread
    try:
        img = imread(image_path)
        if img.ndim == 2:
            return "gray"
        if img.ndim == 3 and img.shape[0] < 10:
            img = img.transpose(1, 2, 0)
        if img.ndim == 4:
            if img.shape[1] < 10:
                img = img.transpose(0, 2, 3, 1)
            img = img.max(axis=0)
        if img.shape[-1] < 3:
            return "gray"

        r = img[..., 0].astype(np.float32).mean()
        g = img[..., 1].astype(np.float32).mean()
        b = img[..., 2].astype(np.float32).mean()
        total = max(r + g + b, 1.0)

        if r / total > 0.5 and b / total < 0.2:
            return "sox9"
        if b / total > 0.5 and r / total < 0.2:
            return "dapi"
        if r / total > 0.25 and b / total > 0.25:
            return "overlay"
        return "gray"
    except Exception as e:
        print(f"Klassifikation fehlgeschlagen: {e}")
        return "unknown"

def _split_overlay_channels(overlay_path: str, folder: str):
    """
    Extrahiert R- und B-Kanal aus einem RGB-Overlay-TIFF
    und speichert sie als temporäre Einzelkanal-TIFs.
    """
    from PIL import Image as PilImage
    import numpy as np

    base    = os.path.splitext(os.path.basename(overlay_path))[0]
    img     = np.array(PilImage.open(overlay_path))

    if img.ndim != 3 or img.shape[2] < 3:
        raise ValueError(f"Overlay {overlay_path} ist kein RGB-Bild")

    sox9_arr = img[..., 0]   # R-Kanal = Sox9
    dapi_arr = img[..., 2]   # B-Kanal = DAPI

    # Als temp-TIF speichern (im selben Ordner, Prefix "extracted_")
    sox9_out = os.path.join(folder, f"extracted_{base}_sox9.tif")
    dapi_out = os.path.join(folder, f"extracted_{base}_dapi.tif")

    PilImage.fromarray(sox9_arr).save(sox9_out)
    PilImage.fromarray(dapi_arr).save(dapi_out)

    print(f"  → Sox9-Kanal: {os.path.basename(sox9_out)}")
    print(f"  → DAPI-Kanal:  {os.path.basename(dapi_out)}")

    return sox9_out, dapi_out
'''