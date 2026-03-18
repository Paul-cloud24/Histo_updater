# analysis/roi_exporter.py
"""
Konvertiert gespeicherte ROI-JSONs ins YOLO-Segmentierungsformat.

YOLO-Segmentierung erwartet pro Bild eine .txt Datei:
  <class_id> <x1> <y1> <x2> <y2> ... (normalisiert 0..1)

Ausgabe-Struktur:
  AppData/HistoAnalyzer/yolo_dataset/
    images/
      train/   (80%)
      val/     (20%)
    labels/
      train/
      val/
    dataset.yaml
"""

import os
import json
import shutil
import random
import numpy as np
from pathlib import Path
from PIL import Image


def get_dataset_dir() -> Path:
    base = Path(os.environ.get("APPDATA", Path.home() / "AppData" / "Roaming"))
    d = base / "HistoAnalyzer" / "yolo_dataset"
    d.mkdir(parents=True, exist_ok=True)
    return d


def export_all_references(val_split: float = 0.2,
                          max_size: int = 1024) -> dict:
    """
    Liest alle gespeicherten ROI-Referenzen und exportiert sie
    als YOLO-Segmentierungsdatensatz.

    Args:
        val_split:  Anteil Validierungsdaten (0.0 - 1.0)
        max_size:   Maximale Bildgröße (längere Seite), Bilder werden skaliert

    Returns:
        dict mit dataset_dir, n_train, n_val, yaml_path
    """
    from analysis.roi_learner import load_references
    refs = load_references()

    if not refs:
        raise ValueError("Keine ROI-Referenzen gefunden. "
                         "Bitte zuerst ROIs einzeichnen und speichern.")

    # Nur Referenzen mit existierenden Bildern
    valid = []
    for r in refs:
        if os.path.exists(r["image_path"]) and \
           len(r.get("polygon_normalized", [])) >= 3:
            valid.append(r)
        else:
            print(f"  [Export] Übersprungen (Bild fehlt): "
                  f"{r.get('image_path', '?')}")

    if not valid:
        raise ValueError("Keine gültigen Referenzen mit vorhandenen Bildern.")

    print(f"  [Export] {len(valid)} gültige Referenzen gefunden")

    # Duplikate entfernen (gleicher image_path → nur letzte behalten)
    seen = {}
    for r in valid:
        seen[r["image_path"]] = r
    valid = list(seen.values())
    print(f"  [Export] {len(valid)} nach Duplikat-Entfernung")

    # Mischen und aufteilen
    random.shuffle(valid)
    n_val   = max(1, int(len(valid) * val_split))
    n_train = len(valid) - n_val
    splits  = {"train": valid[:n_train], "val": valid[n_train:]}

    # Ordner anlegen
    dataset_dir = get_dataset_dir()
    for split in ["train", "val"]:
        (dataset_dir / "images" / split).mkdir(parents=True, exist_ok=True)
        (dataset_dir / "labels" / split).mkdir(parents=True, exist_ok=True)

    counts = {"train": 0, "val": 0}

    for split, refs_split in splits.items():
        for ref in refs_split:
            try:
                _export_one(ref, dataset_dir, split, max_size)
                counts[split] += 1
            except Exception as e:
                print(f"  [Export] Fehler bei {ref['image_path']}: {e}")

    # dataset.yaml schreiben
    yaml_path = dataset_dir / "dataset.yaml"
    yaml_path.write_text(
        f"path: {dataset_dir}\n"
        f"train: images/train\n"
        f"val:   images/val\n"
        f"nc: 1\n"
        f"names: ['cartilage']\n"
    )

    print(f"  [Export] Train: {counts['train']}  Val: {counts['val']}")
    print(f"  [Export] Dataset: {dataset_dir}")
    print(f"  [Export] YAML: {yaml_path}")

    return {
        "dataset_dir": str(dataset_dir),
        "yaml_path":   str(yaml_path),
        "n_train":     counts["train"],
        "n_val":       counts["val"],
        "n_total":     counts["train"] + counts["val"],
    }


def _export_one(ref: dict, dataset_dir: Path,
                split: str, max_size: int):
    """Exportiert ein einzelnes Bild + Label ins YOLO-Format."""
    img_path = ref["image_path"]
    polygon  = ref["polygon_normalized"]

    # Bild laden und skalieren
    img = _load_image_rgb(img_path)
    h, w = img.shape[:2]

    # Skalieren falls nötig
    scale = 1.0
    if max(h, w) > max_size:
        scale = max_size / max(h, w)
        new_w = int(w * scale)
        new_h = int(h * scale)
        img   = np.array(
            Image.fromarray(img).resize((new_w, new_h), Image.LANCZOS))
        h, w  = new_h, new_w

    # Dateiname (eindeutig aus Pfad)
    stem = Path(img_path).stem[:60]   # max 60 Zeichen
    # Kollisionen vermeiden
    img_out   = dataset_dir / "images" / split / f"{stem}.jpg"
    label_out = dataset_dir / "labels" / split / f"{stem}.txt"

    # Bild speichern
    Image.fromarray(img).save(str(img_out), quality=92)

    # YOLO-Label schreiben
    # Format: <class_id> x1 y1 x2 y2 ... (alle normalisiert)
    pts_flat = []
    for x_rel, y_rel in polygon:
        pts_flat.append(f"{x_rel:.6f}")
        pts_flat.append(f"{y_rel:.6f}")

    label_out.write_text("0 " + " ".join(pts_flat) + "\n")


def _load_image_rgb(image_path: str) -> np.ndarray:
    """Lädt ein Bild als uint8 RGB — unterstützt 16-bit TIF."""
    try:
        from tifffile import imread as tiff_imread
        raw = tiff_imread(image_path)
    except Exception:
        raw = np.array(Image.open(image_path))

    if raw.ndim == 4:
        raw = raw[0]
    if raw.ndim == 3 and raw.shape[0] in (1, 2, 3, 4):
        raw = raw.transpose(1, 2, 0)

    raw_f = raw.astype(np.float32)
    vmin, vmax = raw_f.min(), raw_f.max()
    if vmax > vmin:
        norm = (raw_f - vmin) / (vmax - vmin) * 255.0
    else:
        norm = np.zeros_like(raw_f)
    norm8 = norm.clip(0, 255).astype(np.uint8)

    if norm8.ndim == 2:
        norm8 = np.stack([norm8, norm8, norm8], axis=-1)
    if norm8.ndim == 3 and norm8.shape[2] == 4:
        norm8 = norm8[..., :3]
    if norm8.ndim == 3 and norm8.shape[2] == 1:
        norm8 = np.concatenate([norm8, norm8, norm8], axis=-1)

    return norm8