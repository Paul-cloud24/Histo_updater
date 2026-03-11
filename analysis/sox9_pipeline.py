import os
import numpy as np
import pandas as pd
import torch
import matplotlib.pyplot as plt
import matplotlib
matplotlib.use("Agg")

from cellpose import models
from skimage.measure import regionprops_table
from PIL import Image, ImageDraw

from .channel_detection import extract_channels

torch.set_num_threads(os.cpu_count())


class Sox9Pipeline:

    def __init__(self, worker=None, dapi_channel=0, sox9_channel=1):

        self.worker = worker
        self.dapi_channel = dapi_channel
        self.sox9_channel = sox9_channel

        self.tile_size = 384
        self.tile_overlap = 16
        self.batch_size = 1

        self.current_tile = 0
        self.total_tiles = 0

        print("Lade Cellpose Modell...")

        
        self.model = models.Cellpose(
            gpu=False,
            model_type="nuclei",
        )
        

        print("Cellpose Modell geladen")

    # --------------------------------------------------

    def load_image(self, path):

        img = extract_channels(path, "sox9_dapi")

        print("Bildshape:", img.shape)

        if img.ndim < 3:
            raise ValueError("Image must have ≥2 channels")

        return img

    # --------------------------------------------------

    def pad_tile(self, tile):

        size = self.tile_size
        h, w = tile.shape

        padded = np.zeros((size, size), dtype=tile.dtype)
        padded[:h, :w] = tile

        return padded

    # --------------------------------------------------

    def segment_nuclei(self, img):

        dapi = img[..., self.dapi_channel]

        h, w = dapi.shape

        tile = self.tile_size
        overlap = self.tile_overlap
        step = tile - overlap

        tiles = []
        tile_images = []

        for y in range(0, h, step):
            for x in range(0, w, step):

                y_end = min(y + tile, h)
                x_end = min(x + tile, w)

                tile_img = dapi[y:y_end, x:x_end]
                tile_img = self.pad_tile(tile_img)

                tiles.append((y, x, y_end, x_end))
                tile_images.append(tile_img)

        self.total_tiles = len(tiles)
        self.current_tile = 0

        print("Segmentierung startet")
        print("Tiles:", self.total_tiles)

        masks_total = np.zeros((h, w), dtype=np.int32)
        label_offset = 0

        for i in range(0, len(tile_images), self.batch_size):

            batch = tile_images[i:i+self.batch_size]

            masks_batch, flows, styles, diams = self.model.eval(
                batch,
                channels=[0,0],
                diameter=30,
                augment=False,
                rescale=0.5
            )

            for j, tile_mask in enumerate(masks_batch):

                idx = i + j
                y, x, y_end, x_end = tiles[idx]

                tile_mask = tile_mask[:y_end-y, :x_end-x]

                tile_mask[tile_mask > 0] += label_offset

                region = masks_total[y:y_end, x:x_end]

                new_pixels = (region == 0) & (tile_mask > 0)
                region[new_pixels] = tile_mask[new_pixels]

                masks_total[y:y_end, x:x_end] = region

                label_offset = masks_total.max()

                self.current_tile += 1

                if self.worker is not None:
                    self.worker.current_tile = self.current_tile
                    self.worker.total_tiles = self.total_tiles

                print(f"Tile {self.current_tile}/{self.total_tiles}")

        return masks_total

    # --------------------------------------------------

    def measure_intensity(self, img, masks):

        sox9 = img[..., self.sox9_channel]

        props = regionprops_table(
            masks,
            intensity_image=sox9,
            properties=("label", "area", "centroid",
                        "mean_intensity", "max_intensity")
        )

        return pd.DataFrame(props)

    # --------------------------------------------------

    def auto_threshold(self, df):

        m = df["mean_intensity"].mean()
        s = df["mean_intensity"].std()

        return m + 2 * s

    # --------------------------------------------------

    def classify(self, df, threshold):

        df["sox9_positive"] = df["mean_intensity"] >= threshold

        return df

    # --------------------------------------------------

    def overlay(self, img, df, output_folder, base_name):

        sox9 = img[..., self.sox9_channel]

        overlay = Image.fromarray(
            (sox9 / max(1, sox9.max()) * 255).astype(np.uint8)
        ).convert("RGB")

        draw = ImageDraw.Draw(overlay)

        for _, row in df.iterrows():

            if row["sox9_positive"]:

                x = int(row["centroid-1"])
                y = int(row["centroid-0"])

                r = 8

                draw.ellipse(
                    (x-r, y-r, x+r, y+r),
                    outline="red",
                    width=2
                )

        os.makedirs(output_folder, exist_ok=True)

        path = os.path.join(output_folder, f"{base_name}_overlay.png")

        overlay.save(path)

        return path
    # --------------------------------------------------
    def export_csv(self, df, output_folder, base_name):
        os.makedirs(output_folder, exist_ok=True)
        csv_path = os.path.join(output_folder, f"{base_name}_sox9.csv")
        df.to_csv(csv_path, index=False)
        return csv_path

    # --------------------------------------------------
    def qc_plot(self, df, output_folder, base_name, threshold):
        os.makedirs(output_folder, exist_ok=True)

        plt.figure()
        plt.hist(df["mean_intensity"], bins=40, alpha=0.7)
        plt.axvline(threshold, color="red", linestyle="--")
        plt.title("Sox9 intensity distribution")
        plt.xlabel("Mean intensity")
        plt.ylabel("Count")

        out = os.path.join(output_folder, f"{base_name}_qc.png")
        plt.savefig(out, dpi=120)
        plt.close()
        return out

    # --------------------------------------------------
    def run(self, image_path, output_folder):
        img = self.load_image(image_path)
        base = os.path.splitext(os.path.basename(image_path))[0]

        masks = self.segment_nuclei(img)
        df = self.measure_intensity(img, masks)
        thr = self.auto_threshold(df)
        df = self.classify(df, thr)

        csv = self.export_csv(df, output_folder, base)
        qc  = self.qc_plot(df, output_folder, base, thr)
        ov  = self.overlay(img, masks, df, output_folder, base)

        return {
            "csv": csv,
            "qc_plot": qc,
            "overlay": ov
        }
