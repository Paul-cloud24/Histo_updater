# analysis/roi.py

import numpy as np


def compute_roi_mask(h, w,
                     A=(0, 9), B=(10, 1),
                     C=(0, 2), D=(10, 5)):
    """
    Berechnet die ROI-Maske für einen Knochenzylinder-Schnitt.

    Koordinatensystem: (0,0) = unten links, 10x10
    Rote Linie:  A → B  (obere Grenze, Coverlayer-Trennung)
    Gelbe Linie: C → D  (untere Grenze, Knochen-Trennung)
    ROI = großes Dreieck links vom Schnittpunkt beider Linien.

    Parameter (alle im 10x10 Koordinatensystem):
        A: Startpunkt rote Linie  (default: linker Rand, 90% hoch)
        B: Endpunkt rote Linie    (default: rechter Rand, 10% hoch)
        C: Startpunkt gelbe Linie (default: linker Rand, 20% hoch)
        D: Endpunkt gelbe Linie   (default: rechter Rand, 50% hoch)

    Returns:
        roi_mask: np.ndarray (h, w) bool
    """

    def to_px(coord_x, coord_y):
        px_x = int(coord_x / 10 * w)
        px_y = int((1 - coord_y / 10) * h)
        px_x = max(0, min(w - 1, px_x))
        px_y = max(0, min(h - 1, px_y))
        return px_x, px_y

    Ax, Ay = to_px(*A)
    Bx, By = to_px(*B)
    Cx, Cy = to_px(*C)
    Dx, Dy = to_px(*D)

    # Schnittpunkt der beiden Linien berechnen
    # Rote:  y(x) = Ay + x/w * (By - Ay)
    # Gelbe: y(x) = Cy + x/w * (Dy - Cy)
    # Gleichsetzen → x_intersect
    denom = (By - Ay) - (Dy - Cy)
    if denom != 0:
        intersect_x = int((Cy - Ay) / denom * w)
    else:
        intersect_x = w  # parallel → kein Schnittpunkt

    intersect_x = max(0, min(w, intersect_x))

    # ROI aufbauen: nur bis zum Schnittpunkt (linkes/größeres Dreieck)
    roi_mask = np.zeros((h, w), dtype=bool)

    for x in range(intersect_x):
        t        = x / max(w - 1, 1)
        y_red    = int(Ay + t * (By - Ay))
        y_yellow = int(Cy + t * (Dy - Cy))
        y_start  = min(y_red, y_yellow)
        y_end    = max(y_red, y_yellow)
        if y_end > y_start:
            roi_mask[y_start:y_end, x] = True

    return roi_mask


def apply_roi(dapi_masks, sox9_img, roi_mask):
    """
    Filtert Kerne und Sox9-Signal auf die ROI ein.

    Args:
        dapi_masks: (h, w) int32 Label-Bild von Cellpose/Watershed
        sox9_img:   (h, w) float32 Sox9-Kanal
        roi_mask:   (h, w) bool ROI-Maske

    Returns:
        dapi_masks_roi: Label-Bild, nur Kerne innerhalb ROI
        sox9_img_roi:   Sox9-Signal, außerhalb ROI = 0
    """
    # Kerne die mehrheitlich (>50%) in der ROI liegen behalten
    import pandas as pd
    from skimage.measure import regionprops_table

    props = regionprops_table(dapi_masks, properties=("label", "area"))
    labels_in_roi = []

    for lbl in props["label"]:
        nucleus = dapi_masks == lbl
        overlap = (nucleus & roi_mask).sum()
        if overlap / max(nucleus.sum(), 1) > 0.5:
            labels_in_roi.append(lbl)

    # Neues Label-Bild nur mit ROI-Kernen
    dapi_masks_roi = np.isin(dapi_masks, labels_in_roi).astype(np.int32) * dapi_masks

    # Sox9 außerhalb ROI maskieren
    sox9_img_roi = sox9_img.copy()
    sox9_img_roi[~roi_mask] = 0

    return dapi_masks_roi, sox9_img_roi


def save_roi_preview(sox9_img, roi_mask, output_path,
                     A=(0,9), B=(10,1), C=(0,2), D=(10,5)):
    """Speichert ein Vorschaubild der ROI."""
    from PIL import Image, ImageDraw
    import os

    h, w = sox9_img.shape
    norm = (sox9_img / max(1.0, sox9_img.max()) * 255).astype(np.uint8)
    rgb  = np.stack([norm, norm//3, norm//3], axis=-1)

    # ROI grün einfärben
    rgb[roi_mask, 1] = np.clip(rgb[roi_mask, 1].astype(int) + 120, 0, 255).astype(np.uint8)
    rgb[roi_mask, 0] = np.clip(rgb[roi_mask, 0].astype(int) - 30,  0, 255).astype(np.uint8)

    img_pil = Image.fromarray(rgb)
    draw    = ImageDraw.Draw(img_pil)

    def to_px(coord_x, coord_y):
        return (int(coord_x/10*w),
                int((1 - coord_y/10)*h))

    Ap, Bp = to_px(*A), to_px(*B)
    Cp, Dp = to_px(*C), to_px(*D)

    draw.line([Ap, Bp], fill=(255, 50,  50), width=max(2, h//200))
    draw.line([Cp, Dp], fill=(255, 220,  0), width=max(2, h//200))

    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    img_pil.save(output_path)