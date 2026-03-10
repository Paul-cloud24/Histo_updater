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

                if word.lower() in name.slower():

                    mapping[key] = i
    
    print("Gefundene Kanäle:", channel_names)
    print("Mapping:", mapping)

    return mapping


def extract_channels(image_path, stain_type):

    img = imread(image_path)

    mapping = detect_channels(image_path, stain_type)

    if len(mapping) >= 2:

        dapi = img[..., mapping["dapi"]]
        marker = img[..., list(mapping.values())[1]]

        return np.stack([dapi, marker], axis=-1)

    # Fallback wenn keine Metadaten
    print("Keine Kanalmetadaten gefunden → Fallback")

    if img.ndim == 3:
        return img[..., :2]

    return img

def get_channel_names(image_path):

    with TiffFile(image_path) as tif:

        ome = tif.ome_metadata

        if ome is None:
            return []

        root = ET.fromstring(ome)

        channels = []

        for ch in root.iter():
            if "Channel" in ch.tag:
                name = ch.attrib.get("Name")
                if name:
                    channels.append(name)

        return channels