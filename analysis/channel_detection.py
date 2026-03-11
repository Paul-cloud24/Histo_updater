from tifffile import TiffFile
from .channel_config import CHANNEL_CONFIG

from tifffile import imread
import numpy as np

from tifffile import TiffFile
import xml.etree.ElementTree as ET


def detect_channels(image_path, stain_type):

    config = CHANNEL_CONFIG[stain_type]

    channel_names = get_channel_names(image_path)

    mapping = {}

    for i, name in enumerate(channel_names):

        for key, keywords in config.items():

            for word in keywords:

                if word.lower() in name.lower():

                    mapping[key] = i
    
    print("Gefundene Kanäle:", channel_names)
    print("Mapping:", mapping)

    return mapping


def extract_channels(image_path, stain_type):
    img = imread(image_path)
    mapping = detect_channels(image_path, stain_type)

    # Bug 2: mapping könnte "dapi" oder "marker"-Key nicht enthalten
    # → explizit prüfen statt len(mapping) >= 2
    if "dapi" in mapping and len(mapping) >= 2:
        dapi_idx = mapping["dapi"]

        # zweiten Kanal (nicht DAPI) aus mapping holen
        marker_key = next(k for k in mapping if k != "dapi")
        marker_idx = mapping[marker_key]

        # Robustheit: Channel-Achse ermitteln
        # tifffile lädt meistens als (C, H, W) oder (H, W, C)
        if img.ndim == 3:
            # (C, H, W) wenn C klein ist (< 10), sonst (H, W, C)
            if img.shape[0] < 10:
                dapi   = img[dapi_idx]
                marker = img[marker_idx]
            else:
                dapi   = img[..., dapi_idx]
                marker = img[..., marker_idx]
            return np.stack([dapi, marker], axis=-1)

        elif img.ndim == 4:
            # z.B. (Z, C, H, W) → max-projection über Z
            if img.shape[1] < 10:
                dapi   = img[:, dapi_idx].max(axis=0)
                marker = img[:, marker_idx].max(axis=0)
                return np.stack([dapi, marker], axis=-1)

    # Fallback wenn keine Metadaten
    print("Keine Kanalmetadaten gefunden → Fallback")

    if img.ndim == 3:
        # (C, H, W) → transpose zu (H, W, C)
        if img.shape[0] < 10:
            return img[:2].transpose(1, 2, 0)
        return img[..., :2]

    if img.ndim == 4:
        # (Z, C, H, W) → max-projection, erste 2 Kanäle
        return img[:, :2].max(axis=0).transpose(1, 2, 0)

    return img

def get_channel_names(image_path):

    with TiffFile(image_path) as tif:

        ome = tif.ome_metadata

        if ome is None:
            return []

        root = ET.fromstring(ome)
        ns = root.tag.split("}")[0] + "}" if "}" in root.tag else ""
        channels = []

        for ch in root.iter():
            name = ch.attrib.get("Name") or ch.attrib.get("ID", "")                
            if name:     
                channels.append(name)

        return channels