import os
import numpy as np
import pandas as pd
import torch
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

from cellpose import models
from skimage.measure import regionprops_table, label
from skimage.morphology import remove_small_objects, binary_erosion, disk
from skimage.segmentation import watershed
from skimage.feature import peak_local_max
from scipy.ndimage import distance_transform_edt
from PIL import Image, ImageDraw

from .channel_detection import extract_channels

torch.set_num_threads(os.cpu_count())


class Sox9Pipeline:

    def __init__(self, worker=None, dapi_channel=0, sox9_channel=1,
                 threshold=10000, dapi_threshold=None,
                 min_nucleus_area=50):
        self.worker = worker
        self.dapi_channel = dapi_channel
        self.sox9_channel = sox9_channel
        self.threshold = threshold          # Sox9 threshold (16-bit)
        self.dapi_threshold = dapi_threshold  # None → auto
        self.min_nucleus_area = min_nucleus_area

        self.tile_size = 384
        self.tile_overlap = 16
        self.batch_size = 1

        self.current_tile = 0
        self.total_tiles = 0

        print("Lade Cellpose Modell...")
        self.model = models.Cellpose(gpu=False, model_type="nuclei")
        print("Cellpose Modell geladen")

    # ── Image loading ────────────────────────────────────────────────
    def load_image(self, path):
        img = extract_channels(path, "sox9_dapi")
        print("Bildshape:", img.shape)
        if img.ndim < 3:
            raise ValueError("Image must have ≥2 channels")
        return img

    # ── Padding ──────────────────────────────────────────────────────
    def pad_tile(self, tile):
        size = self.tile_size
        h, w = tile.shape
        padded = np.zeros((size, size), dtype=tile.dtype)
        padded[:h, :w] = tile
        return padded

    # ── Cellpose segmentation (tiled) ────────────────────────────────
    def segment_nuclei(self, img):
        dapi = img[..., self.dapi_channel]
        h, w = dapi.shape
        tile, overlap = self.tile_size, self.tile_overlap
        step = tile - overlap

        tiles, tile_images = [], []
        for y in range(0, h, step):
            for x in range(0, w, step):
                y_end, x_end = min(y + tile, h), min(x + tile, w)
                t = self.pad_tile(dapi[y:y_end, x:x_end])
                tiles.append((y, x, y_end, x_end))
                tile_images.append(t)

        self.total_tiles = len(tiles)
        self.current_tile = 0
        print(f"Segmentierung startet | Tiles: {self.total_tiles}")

        masks_total = np.zeros((h, w), dtype=np.int32)
        label_offset = 0

        for i in range(0, len(tile_images), self.batch_size):
            batch = tile_images[i:i + self.batch_size]
            masks_batch, _, _, _ = self.model.eval(
                batch, channels=[0, 0], diameter=30,
                augment=False, rescale=0.5
            )
            for j, tile_mask in enumerate(masks_batch):
                idx = i + j
                y, x, y_end, x_end = tiles[idx]
                tile_mask = tile_mask[:y_end - y, :x_end - x].astype(np.int32)
                tile_mask[tile_mask > 0] += label_offset
                region = masks_total[y:y_end, x:x_end]
                new_px = (region == 0) & (tile_mask > 0)
                region[new_px] = tile_mask[new_px]
                masks_total[y:y_end, x:x_end] = region
                label_offset = masks_total.max()
                self.current_tile += 1
                if self.worker is not None:
                    self.worker.current_tile = self.current_tile
                    self.worker.total_tiles = self.total_tiles
                print(f"Tile {self.current_tile}/{self.total_tiles}")

        return masks_total

    # ── Sox9 binary mask ─────────────────────────────────────────────
    def sox9_binary_mask(self, img):
        """Threshold → binary Sox9 mask."""
        sox9 = img[..., self.sox9_channel]
        return sox9 >= self.threshold

    # ── Watershed clump splitting ─────────────────────────────────────
    def watershed_split(self, binary_mask):
        """
        Separate touching/overlapping nuclei using distance-transform
        watershed. Returns a label image.
        """
        # distance transform on the binary mask
        dist = distance_transform_edt(binary_mask)

        # local maxima as seed points
        coords = peak_local_max(
            dist,
            min_distance=10,       # minimum pixel distance between seeds
            labels=binary_mask
        )
        seed_mask = np.zeros(dist.shape, dtype=bool)
        seed_mask[tuple(coords.T)] = True
        markers = label(seed_mask)

        # watershed flood from seeds, constrained to binary_mask
        labels_ws = watershed(-dist, markers, mask=binary_mask)
        return labels_ws

    # ── Morphological cleanup ────────────────────────────────────────
    def morphological_cleanup(self, label_img):
        """
        Remove small objects and apply erosion to reduce noise.
        Returns cleaned label image.
        """
        # remove objects below area threshold
        binary = label_img > 0
        cleaned = remove_small_objects(binary, min_size=self.min_nucleus_area)

        # re-label after cleanup
        cleaned_labels = label(cleaned)
        return cleaned_labels

    # ── DAPI mask ────────────────────────────────────────────────────
    def dapi_binary_mask(self, img):
        """
        Build a binary DAPI mask. Uses auto-threshold (mean + 1σ)
        unless self.dapi_threshold is set manually.
        """
        dapi = img[..., self.dapi_channel].astype(np.float32)
        if self.dapi_threshold is not None:
            thr = self.dapi_threshold
        else:
            thr = dapi.mean() + dapi.std()
            print(f"DAPI auto-threshold: {thr:.1f}")
        return dapi >= thr

    # ── Intensity measurement ────────────────────────────────────────
    def measure_intensity(self, img, masks):
        sox9 = img[..., self.sox9_channel]
        props = regionprops_table(
            masks, intensity_image=sox9,
            properties=("label", "area", "centroid",
                        "mean_intensity", "max_intensity")
        )
        return pd.DataFrame(props)

    # ── DAPI validation ──────────────────────────────────────────────
    def validate_with_dapi(self, img, df, sox9_labels):
        """
        Intersect Sox9+ nuclei with DAPI mask.
        Only nuclei that are BOTH Sox9+ AND DAPI+ are counted.
        Adds column 'dapi_positive' and 'sox9_dapi_positive' to df.
        """
        dapi_mask = self.dapi_binary_mask(img)

        dapi_positive = []
        for _, row in df.iterrows():
            nuc_mask = sox9_labels == row["label"]
            overlap = (nuc_mask & dapi_mask).sum()
            nuc_area = nuc_mask.sum()
            # nucleus is DAPI+ if >50 % of its area overlaps DAPI mask
            dapi_positive.append(overlap / max(1, nuc_area) > 0.5)

        df["dapi_positive"] = dapi_positive
        df["sox9_dapi_positive"] = df["sox9_positive"] & df["dapi_positive"]
        return df

    # ── Classify ─────────────────────────────────────────────────────
    def classify(self, df, threshold):
        df["sox9_positive"] = df["mean_intensity"] >= threshold
        return df

    # ── Overlay ──────────────────────────────────────────────────────
    def overlay(self, img, df, output_folder, base_name):
        sox9 = img[..., self.sox9_channel]
        overlay = Image.fromarray(
            (sox9 / max(1, sox9.max()) * 255).astype(np.uint8)
        ).convert("RGB")
        draw = ImageDraw.Draw(overlay)

        for _, row in df.iterrows():
            x = int(row["centroid-1"])
            y = int(row["centroid-0"])
            r = 8
            if row.get("sox9_dapi_positive", row["sox9_positive"]):
                # green = validated (Sox9+ AND DAPI+)
                color = "lime"
            elif row["sox9_positive"]:
                # yellow = Sox9+ but DAPI-
                color = "yellow"
            else:
                continue
            draw.ellipse((x - r, y - r, x + r, y + r), outline=color, width=2)

        os.makedirs(output_folder, exist_ok=True)
        path = os.path.join(output_folder, f"{base_name}_overlay.png")
        overlay.save(path)
        return path

    # ── CSV export ───────────────────────────────────────────────────
    def export_csv(self, df, output_folder, base_name):
        os.makedirs(output_folder, exist_ok=True)
        csv_path = os.path.join(output_folder, f"{base_name}_sox9.csv")
        df.to_csv(csv_path, index=False)
        return csv_path

    # ── QC plot ──────────────────────────────────────────────────────
    def qc_plot(self, df, output_folder, base_name, threshold):
        os.makedirs(output_folder, exist_ok=True)
        fig, axes = plt.subplots(1, 2, figsize=(10, 4))

        axes[0].hist(df["mean_intensity"], bins=40, alpha=0.7, color="steelblue")
        axes[0].axvline(threshold, color="red", linestyle="--", label=f"Thr={threshold}")
        axes[0].set_title("Sox9 intensity distribution")
        axes[0].set_xlabel("Mean intensity")
        axes[0].set_ylabel("Count")
        axes[0].legend()

        if "sox9_dapi_positive" in df.columns:
            counts = {
                "Sox9+ DAPI+": df["sox9_dapi_positive"].sum(),
                "Sox9+ DAPI-": (df["sox9_positive"] & ~df["dapi_positive"]).sum(),
                "Sox9-": (~df["sox9_positive"]).sum(),
            }
            axes[1].bar(counts.keys(), counts.values(),
                        color=["lime", "yellow", "gray"])
            axes[1].set_title("Nucleus classification")
            axes[1].set_ylabel("Count")

        plt.tight_layout()
        out = os.path.join(output_folder, f"{base_name}_qc.png")
        plt.savefig(out, dpi=120)
        plt.close()
        return out

    # ── Main run ─────────────────────────────────────────────────────
    def run(self, image_path, output_folder):
        img = self.load_image(image_path)
        base = os.path.splitext(os.path.basename(image_path))[0]

        # Output-Unterordner: output_folder/results/
        results_folder = os.path.join(output_folder, "results")
        os.makedirs(results_folder, exist_ok=True)

        # 1) Cellpose segmentation (DAPI-based)
        masks = self.segment_nuclei(img)

        # 2) Sox9 binary mask → Watershed → Cleanup
        sox9_bin = self.sox9_binary_mask(img)
        sox9_ws = self.watershed_split(sox9_bin)
        sox9_clean = self.morphological_cleanup(sox9_ws)

        # 3) Measure intensity on cleaned nuclei
        df = self.measure_intensity(img, sox9_clean)
        df = self.classify(df, self.threshold)

        # 4) DAPI validation
        df = self.validate_with_dapi(img, df, sox9_clean)

        # 5) Export
        csv = self.export_csv(df, results_folder, base)
        qc  = self.qc_plot(df, results_folder, base, self.threshold)
        ov  = self.overlay(img, df, results_folder, base)

        n_sox9_dapi = int(df["sox9_dapi_positive"].sum())
        n_sox9_only = int((df["sox9_positive"] & ~df["dapi_positive"]).sum())
        print(f"{base}: Sox9+DAPI+={n_sox9_dapi}, Sox9+DAPI-={n_sox9_only}")
        print(f"Ergebnisse gespeichert in: {results_folder}")

        return {"csv": csv, "qc_plot": qc, "overlay": ov, "results_folder": results_folder}