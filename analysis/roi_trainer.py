# analysis/roi_trainer.py
"""
YOLOv8-Seg Training fuer automatische Knorpel-Segmentierung.

- Nutzt automatisch GPU wenn vorhanden, sonst CPU
- Basis-Modell: yolov8n-seg (klein, schnell, gut fuer wenig Daten)
- Trainiertes Modell wird gespeichert in:
    AppData/HistoAnalyzer/models/roi_model.pt
"""

import os
from pathlib import Path


def get_model_path() -> Path:
    base = Path(os.environ.get("APPDATA", Path.home() / "AppData" / "Roaming"))
    d    = base / "HistoAnalyzer" / "models"
    d.mkdir(parents=True, exist_ok=True)
    return d / "roi_model.pt"


def get_runs_dir() -> Path:
    base = Path(os.environ.get("APPDATA", Path.home() / "AppData" / "Roaming"))
    return base / "HistoAnalyzer" / "yolo_runs"


def is_model_trained() -> bool:
    p = get_model_path()
    return p.exists() and p.stat().st_size > 1_000_000


def detect_device() -> str:
    """Gibt 'cuda:0' oder 'cpu' zurück."""
    try:
        import torch
        if torch.cuda.is_available():
            name = torch.cuda.get_device_name(0)
            print(f"  [Trainer] GPU gefunden: {name}")
            return "0"   # YOLO erwartet "0" für cuda:0
    except Exception:
        pass
    print("  [Trainer] Kein GPU → CPU")
    return "cpu"


def train(epochs: int = 100,
          imgsz: int = 1024,
          batch:  int = -1,
          progress_callback=None) -> str:
    """
    Trainiert YOLOv8-Seg auf den exportierten ROI-Daten.

    Args:
        epochs:            Trainings-Epochen (100 gut für ~100 Bilder)
        imgsz:             Bildgröße für Training
        batch:             Batch-Größe (-1 = auto)
        progress_callback: optional fn(epoch: int, total: int, metrics: dict)

    Returns:
        Pfad zum trainierten Modell
    """
    try:
        from ultralytics import YOLO
    except ImportError:
        raise ImportError(
            "ultralytics nicht installiert.\n"
            "Bitte ausführen: pip install ultralytics"
        )

    from analysis.roi_exporter import export_all_references, get_dataset_dir

    # 1) Daten exportieren
    print("  [Trainer] Exportiere ROI-Daten...")
    export_info = export_all_references(val_split=0.2, max_size=imgsz)

    n_total = export_info["n_total"]
    if n_total < 4:
        raise ValueError(
            f"Zu wenig Daten: {n_total} Bilder. "
            f"Mindestens 4 ROIs benötigt (besser 20+)."
        )

    print(f"  [Trainer] {export_info['n_train']} Train / "
          f"{export_info['n_val']} Val")

    # 2) Device
    device = detect_device()

    # 3) Batch-Größe anpassen
    if batch == -1:
        batch = 4 if device == "cpu" else 8

    # 4) Modell laden (Basis: yolov8n-seg — klein und schnell)
    print("  [Trainer] Lade Basis-Modell yolov8n-seg...")
    model = YOLO("yolov8n-seg.pt")

    # 5) Training
    runs_dir = get_runs_dir()
    print(f"  [Trainer] Starte Training: {epochs} Epochen, "
          f"imgsz={imgsz}, batch={batch}, device={device}")

    results = model.train(
        data    = export_info["yaml_path"],
        epochs  = epochs,
        imgsz   = imgsz,
        batch   = batch,
        device  = device,
        project = str(runs_dir),
        name    = "roi_seg",
        exist_ok= True,
        verbose = True,
        # Augmentierung — wichtig bei wenig Daten
        flipud  = 0.3,
        fliplr  = 0.5,
        degrees = 15,
        scale   = 0.3,
        mosaic  = 0.5,
        # Früh-Stopp
        patience= 20,
    )

    # 6) Bestes Modell kopieren
    best_model = runs_dir / "roi_seg" / "weights" / "best.pt"
    if not best_model.exists():
        # Fallback: last.pt
        best_model = runs_dir / "roi_seg" / "weights" / "last.pt"

    if best_model.exists():
        import shutil
        dest = get_model_path()
        shutil.copy2(best_model, dest)
        print(f"  [Trainer] Modell gespeichert: {dest}")
        return str(dest)
    else:
        raise FileNotFoundError(
            "Trainiertes Modell nicht gefunden. "
            "Bitte Training-Log prüfen."
        )


def get_training_summary() -> dict | None:
    """Gibt Trainings-Metriken des letzten Runs zurück."""
    results_csv = (get_runs_dir() / "roi_seg" / "results.csv")
    if not results_csv.exists():
        return None
    try:
        import pandas as pd
        df   = pd.read_csv(results_csv)
        last = df.iloc[-1]
        return {
            "epochs_trained": len(df),
            "box_loss":       round(float(last.get("val/box_loss", 0)), 4),
            "seg_loss":       round(float(last.get("val/seg_loss", 0)), 4),
            "mAP50":          round(float(last.get("metrics/mAP50(M)", 0)), 4),
        }
    except Exception:
        return None