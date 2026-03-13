# analysis/batch_runner.py

import os
import json
import shutil
import numpy as np
import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from PIL import Image


def find_sox9_folders(root_folder: str) -> list:
    root_abs = os.path.abspath(root_folder)
    folders  = []
    for entry in os.scandir(root_folder):
        if not entry.is_dir():
            continue
        # Wurzelordner selbst nie einschließen
        if os.path.abspath(entry.path) == root_abs:
            continue
        if "sox9" in entry.name.lower():
            folders.append(entry.path)
    folders.sort()
    print(f"Gefundene Sox9-Ordner: {len(folders)}")
    for f in folders:
        print(f"  {os.path.basename(f)}")
    return folders


def collect_results(root_folder: str, results: list) -> tuple:
    """
    Sammelt alle Ergebnisse, kopiert Overlays + ROIs in den Results-Ordner
    und erstellt CSV + Plot.

    Args:
        root_folder: Wurzelordner (vom Benutzer gewählt)
        results: Liste von dicts mit Analyse-Ergebnissen pro Ordner

    Returns:
        (csv_path, plot_path)
    """
    out_root   = os.path.join(root_folder, "Results")
    out_overlay = os.path.join(out_root, "Overlays")
    out_roi     = os.path.join(out_root, "ROIs")

    os.makedirs(out_overlay, exist_ok=True)
    os.makedirs(out_roi,     exist_ok=True)

    rows = []
    for r in results:
        folder_name = r["folder_name"]

        # Overlay kopieren
        if r.get("overlay") and os.path.exists(r["overlay"]):
            dst = os.path.join(out_overlay,
                               f"{folder_name}_overlay.png")
            shutil.copy2(r["overlay"], dst)

        # ROI-JSON kopieren
        if r.get("roi_json") and os.path.exists(r["roi_json"]):
            dst = os.path.join(out_roi,
                               f"{folder_name}_roi.json")
            shutil.copy2(r["roi_json"], dst)

        # CSV-Zeile
        rows.append({
            "Probe":              folder_name,
            "DAPI_Kerne":         r.get("n_dapi_total",  0),
            "Sox9_positiv":       r.get("n_positive",    0),
            "Sox9_negativ":       r.get("n_dapi_total",  0) - r.get("n_positive", 0),
            "Sox9_DAPI_Ratio_%":  round(r.get("ratio",   0.0), 2),
            "ROI_vorhanden":      "ja" if r.get("roi_used") else "nein",
            "Status":             r.get("status", "ok"),
        })

    df = pd.DataFrame(rows)
    csv_path = os.path.join(out_root, "results.csv")
    df.to_csv(csv_path, index=False, sep=";", decimal=",")
    print(f"CSV gespeichert: {csv_path}")

    # Plot
    plot_path = _make_plot(df, out_root)

    return csv_path, plot_path


def _make_plot(df: pd.DataFrame, out_root: str) -> str:
    """Balkendiagramm: Sox9+/- pro Probe."""
    ok = df[df["Status"] == "ok"].copy()
    if ok.empty:
        return None

    fig, axes = plt.subplots(1, 2, figsize=(max(8, len(ok) * 1.2 + 2), 6))

    x     = np.arange(len(ok))
    names = ok["Probe"].tolist()
    width = 0.35

    # Linkes Bild: absolute Kernzahlen gestapelt
    axes[0].bar(x, ok["Sox9_positiv"], width,
                label="Sox9+", color="#2ecc71")
    axes[0].bar(x, ok["Sox9_negativ"], width,
                bottom=ok["Sox9_positiv"],
                label="Sox9-", color="#95a5a6")
    axes[0].set_xticks(x)
    axes[0].set_xticklabels(names, rotation=45, ha="right", fontsize=8)
    axes[0].set_ylabel("Anzahl Kerne (DAPI)")
    axes[0].set_title("Absolute Kernzahlen")
    axes[0].legend()

    # Rechtes Bild: Ratio %
    colors = ["#2ecc71" if v >= 50 else "#e74c3c"
              for v in ok["Sox9_DAPI_Ratio_%"]]
    axes[1].bar(x, ok["Sox9_DAPI_Ratio_%"], color=colors)
    axes[1].axhline(50, color="gray", linestyle="--", linewidth=0.8,
                    label="50%")
    axes[1].set_xticks(x)
    axes[1].set_xticklabels(names, rotation=45, ha="right", fontsize=8)
    axes[1].set_ylabel("Sox9+ / DAPI [%]")
    axes[1].set_title("Sox9+/DAPI Ratio")
    axes[1].set_ylim(0, 100)
    axes[1].legend()

    plt.suptitle("Sox9/DAPI Batch-Analyse", fontsize=13, y=1.01)
    plt.tight_layout()

    plot_path = os.path.join(out_root, "results_plot.png")
    plt.savefig(plot_path, dpi=120, bbox_inches="tight")
    plt.close()
    print(f"Plot gespeichert: {plot_path}")
    return plot_path