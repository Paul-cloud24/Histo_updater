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
        if os.path.abspath(entry.path) == root_abs:
            continue
        if "sox9" in entry.name.lower():
            folders.append(entry.path)
    folders.sort()
    print(f"Gefundene Sox9-Ordner: {len(folders)}")
    for f in folders:
        print(f"  {os.path.basename(f)}")
    return folders


# ══════════════════════════════════════════════════════════════════════
# Hauptfunktion
# ══════════════════════════════════════════════════════════════════════

def collect_results(root_folder: str, results: list) -> tuple:
    """
    Sammelt alle Ergebnisse und erstellt:
      Results/
        Overlays/        — Overlay-PNGs pro Probe
        ROIs/            — ROI-JSONs pro Probe
        Heatmaps/        — Heatmap pro Probe + kombinierte Übersicht
        results.csv      — Zusammenfassung aller Proben
        results_plot.png — Balkendiagramm
    """
    out_root    = os.path.join(root_folder, "Results")
    out_overlay = os.path.join(out_root, "Overlays")
    out_roi     = os.path.join(out_root, "ROIs")
    out_heatmap = os.path.join(out_root, "Heatmaps")

    for d in [out_overlay, out_roi, out_heatmap]:
        os.makedirs(d, exist_ok=True)

    # Färbungstyp aus erstem Ergebnis ermitteln
    stain_name   = results[0].get("stain", "") if results else ""
    is_area_stain = stain_name in ("Von Kossa", "Kollagen Typ 1",
                                   "Kollagen Typ 2", "Safranin O")

    rows            = []
    heatmap_data    = []   # für kombinierte Heatmap

    for r in results:
        folder_name = r.get("folder_name", "unbekannt")

        # ── Overlay kopieren ──────────────────────────────────────────
        if r.get("overlay") and os.path.exists(r["overlay"]):
            shutil.copy2(r["overlay"],
                         os.path.join(out_overlay,
                                      f"{folder_name}_overlay.png"))

        # ── ROI-JSON kopieren ─────────────────────────────────────────
        if r.get("roi_json") and os.path.exists(r["roi_json"]):
            shutil.copy2(r["roi_json"],
                         os.path.join(out_roi,
                                      f"{folder_name}_roi.json"))

        # ── Heatmap pro Probe ─────────────────────────────────────────
        hm_path = None
        if is_area_stain:
            hm_path = _make_area_heatmap(r, out_heatmap, folder_name)
        else:
            hm_path = _make_cell_heatmap(r, out_heatmap, folder_name)

        if hm_path:
            heatmap_data.append({
                "name":    folder_name,
                "path":    hm_path,
                "result":  r,
            })

        # ── CSV-Zeile ─────────────────────────────────────────────────
        if is_area_stain:
            rows.append({
                "Probe":              folder_name,
                "Gewebe_px":          r.get("tissue_area_px",      0),
                "Mineralisiert_px":   r.get("mineralized_area_px", 0),
                "Mineralisiert_%":    round(r.get("mineralized_%", 0.0), 4),
                "ROI_vorhanden":      "ja" if r.get("roi_used") else "nein",
                "Status":             r.get("status", "ok"),
            })
        else:
            n_total = r.get("n_total", 0)
            n_pos   = r.get("n_positive", r.get("n_apoptotic", 0))
            rows.append({
                "Probe":          folder_name,
                "DAPI_Kerne":     n_total,
                "Positiv":        n_pos,
                "Negativ":        n_total - n_pos,
                "Ratio_%":        round(r.get("ratio", 0.0), 2),
                "Threshold":      r.get("threshold_used", "—"),
                "ROI_vorhanden":  "ja" if r.get("roi_used") else "nein",
                "Status":         r.get("status", "ok"),
            })

    # ── Gesamt-CSV ────────────────────────────────────────────────────
    df = pd.DataFrame(rows)
    csv_path = os.path.join(out_root, "results.csv")
    df.to_csv(csv_path, index=False, sep=";", decimal=",")
    print(f"CSV gespeichert: {csv_path}")

    # ── Balkendiagramm ────────────────────────────────────────────────
    plot_path = _make_summary_plot(df, out_root, is_area_stain, stain_name)

    # ── Kombinierte Heatmap ───────────────────────────────────────────
    if len(heatmap_data) > 1:
        _make_combined_heatmap(heatmap_data, out_heatmap,
                               is_area_stain, stain_name)

    return csv_path, plot_path


# ══════════════════════════════════════════════════════════════════════
# Heatmaps — Kernfärbungen (Sox9, MMP13, TUNEL)
# ══════════════════════════════════════════════════════════════════════

def _make_cell_heatmap(result: dict, out_dir: str,
                       name: str) -> str | None:
    """
    Heatmap der doppelt-positiven Zellen (DAPI + Marker).
    Liest Zentroid-Koordinaten aus der Einzel-CSV.
    """
    csv_path = result.get("csv")
    if not csv_path or not os.path.exists(csv_path):
        return None

    try:
        df = pd.read_csv(csv_path)
    except Exception as e:
        print(f"  [Heatmap] CSV lesen fehlgeschlagen: {e}")
        return None

    # Nur positive Kerne
    if "positive" not in df.columns:
        return None
    pos = df[df["positive"] == True]
    if pos.empty:
        print(f"  [Heatmap] {name}: keine positiven Kerne")
        return None

    x = pos["centroid-1"].values
    y = pos["centroid-0"].values

    # Bildgröße aus Overlay schätzen
    img_w, img_h = _get_image_size(result)

    fig, ax = plt.subplots(figsize=(8, 6))
    fig.patch.set_facecolor("#1e1e2e")
    ax.set_facecolor("#11111b")

    # Overlay als Hintergrund (falls vorhanden)
    overlay_path = result.get("overlay")
    if overlay_path and os.path.exists(overlay_path):
        bg = np.array(Image.open(overlay_path).convert("RGB"))
        ax.imshow(bg, alpha=0.4)
        img_h, img_w = bg.shape[:2]

    # 2D-Histogramm als Heatmap
    bins = 40
    h, xe, ye = np.histogram2d(x, y,
                                bins=bins,
                                range=[[0, img_w], [0, img_h]])
    im = ax.imshow(h.T, extent=[0, img_w, img_h, 0],
                   cmap="hot", alpha=0.7, interpolation="gaussian")
    plt.colorbar(im, ax=ax, label="Zellen / Bin")

    ax.set_title(f"{name}  —  positive Zellen Dichte\n"
                 f"n={len(pos)}  ({len(pos)/max(len(df),1)*100:.1f}%)",
                 color="#cdd6f4")
    ax.axis("off")
    plt.tight_layout()

    out = os.path.join(out_dir, f"{name}_heatmap.png")
    plt.savefig(out, dpi=120, facecolor="#1e1e2e")
    plt.close()
    print(f"  [Heatmap] {name}: gespeichert")
    return out


# ══════════════════════════════════════════════════════════════════════
# Heatmaps — Flächenfärbungen (Von Kossa, Col1/2)
# ══════════════════════════════════════════════════════════════════════

def _make_area_heatmap(result: dict, out_dir: str,
                       name: str) -> str | None:
    """
    Heatmap der mineralisierten/gefärbten Fläche.
    Verwendet das Overlay-Bild direkt.
    """
    overlay_path = result.get("overlay")
    if not overlay_path or not os.path.exists(overlay_path):
        return None

    try:
        img = np.array(Image.open(overlay_path).convert("RGB"))
    except Exception:
        return None

    # Gelbe Pixel (Ablagerungen bei Von Kossa) als Maske
    # Gelb = R > 200, G > 180, B < 80
    r, g, b = img[..., 0], img[..., 1], img[..., 2]
    deposit = (r > 200) & (g > 180) & (b < 80)

    if not deposit.any():
        return None

    # In Blöcke aufteilen und Dichte berechnen
    block = 40
    h, w  = img.shape[:2]
    density = np.zeros((h // block + 1, w // block + 1))
    for by in range(density.shape[0]):
        for bx in range(density.shape[1]):
            patch = deposit[by*block:(by+1)*block,
                            bx*block:(bx+1)*block]
            density[by, bx] = patch.mean() if patch.size > 0 else 0

    fig, ax = plt.subplots(figsize=(8, 6))
    fig.patch.set_facecolor("#1e1e2e")
    ax.imshow(img, alpha=0.5)
    im = ax.imshow(density,
                   extent=[0, w, h, 0],
                   cmap="YlOrRd", alpha=0.65,
                   interpolation="gaussian",
                   vmin=0, vmax=1)
    plt.colorbar(im, ax=ax, label="Mineralisierungsdichte")
    ax.set_title(f"{name}  —  Mineralisierungsdichte\n"
                 f"{result.get('mineralized_%', 0):.2f}% mineralisiert",
                 color="#cdd6f4")
    ax.axis("off")
    plt.tight_layout()

    out = os.path.join(out_dir, f"{name}_heatmap.png")
    plt.savefig(out, dpi=120, facecolor="#1e1e2e")
    plt.close()
    print(f"  [Heatmap] {name}: gespeichert")
    return out


# ══════════════════════════════════════════════════════════════════════
# Kombinierte Heatmap aller Proben
# ══════════════════════════════════════════════════════════════════════

def _make_combined_heatmap(heatmap_data: list, out_dir: str,
                           is_area_stain: bool, stain_name: str):
    """Zeigt alle Einzel-Heatmaps in einer Übersicht."""
    n    = len(heatmap_data)
    cols = min(n, 4)
    rows = (n + cols - 1) // cols

    fig, axes = plt.subplots(rows, cols,
                             figsize=(cols * 5, rows * 4))
    fig.patch.set_facecolor("#1e1e2e")

    # axes immer als 2D-Liste behandeln
    if n == 1:
        axes = [[axes]]
    elif rows == 1:
        axes = [axes]

    for idx, entry in enumerate(heatmap_data):
        row, col = divmod(idx, cols)
        ax = axes[row][col]
        ax.set_facecolor("#11111b")

        if os.path.exists(entry["path"]):
            img = np.array(Image.open(entry["path"]))
            ax.imshow(img)
        ax.set_title(entry["name"], color="#cdd6f4", fontsize=9)
        ax.axis("off")

    # Leere Subplots ausblenden
    for idx in range(n, rows * cols):
        row, col = divmod(idx, cols)
        axes[row][col].set_visible(False)

    plt.suptitle(f"{stain_name}  —  Heatmap Übersicht  (n={n})",
                 color="#cdd6f4", fontsize=13, y=1.01)
    plt.tight_layout()

    out = os.path.join(out_dir, "combined_heatmap.png")
    plt.savefig(out, dpi=100, facecolor="#1e1e2e", bbox_inches="tight")
    plt.close()
    print(f"  [Heatmap] Kombiniert gespeichert: {out}")


# ══════════════════════════════════════════════════════════════════════
# Zusammenfassungs-Plot
# ══════════════════════════════════════════════════════════════════════

def _make_summary_plot(df: pd.DataFrame, out_root: str,
                       is_area_stain: bool, stain_name: str) -> str | None:
    ok = df[df["Status"] == "ok"].copy()
    if ok.empty:
        return None

    fig, axes = plt.subplots(1, 2,
                             figsize=(max(8, len(ok) * 1.4 + 2), 6))
    fig.patch.set_facecolor("#1e1e2e")
    for ax in axes:
        ax.set_facecolor("#11111b")
        ax.tick_params(colors="#a6adc8")
        for spine in ax.spines.values():
            spine.set_edgecolor("#45475a")

    x     = np.arange(len(ok))
    names = ok["Probe"].tolist()

    if is_area_stain:
        # Flächenfärbung: mineralisiert vs. nicht
        mineral = ok["Mineralisiert_px"].values
        rest    = ok["Gewebe_px"].values - mineral
        axes[0].bar(x, mineral, label="Mineralisiert", color="#f9e2af")
        axes[0].bar(x, rest, bottom=mineral,
                    label="Nicht mineralisiert", color="#89b4fa")
        axes[0].set_title("Absolute Flächen (px)", color="#cdd6f4")
        axes[0].legend(facecolor="#313244", labelcolor="#cdd6f4")

        axes[1].bar(x, ok["Mineralisiert_%"], color="#f9e2af")
        axes[1].set_ylabel("Mineralisiert [%]", color="#a6adc8")
        axes[1].set_title("Mineralisierungsgrad", color="#cdd6f4")
        axes[1].set_ylim(0, max(ok["Mineralisiert_%"].max() * 1.2, 5))
    else:
        # Kernfärbung: positiv vs. negativ
        axes[0].bar(x, ok["Positiv"],  label="Positiv",  color="#a6e3a1")
        axes[0].bar(x, ok["Negativ"],  bottom=ok["Positiv"],
                    label="Negativ",  color="#585b70")
        axes[0].set_title("Absolute Kernzahlen", color="#cdd6f4")
        axes[0].legend(facecolor="#313244", labelcolor="#cdd6f4")

        colors = ["#a6e3a1" if v >= 50 else "#f38ba8"
                  for v in ok["Ratio_%"]]
        axes[1].bar(x, ok["Ratio_%"], color=colors)
        axes[1].axhline(50, color="#6c7086", linestyle="--", linewidth=0.8)
        axes[1].set_ylabel("Positiv / DAPI [%]", color="#a6adc8")
        axes[1].set_title("Ratio", color="#cdd6f4")
        axes[1].set_ylim(0, 100)

    for ax in axes:
        ax.set_xticks(x)
        ax.set_xticklabels(names, rotation=45, ha="right",
                           fontsize=8, color="#a6adc8")
        ax.set_ylabel(ax.get_ylabel() or "Anzahl", color="#a6adc8")

    plt.suptitle(f"{stain_name}  —  Batch-Analyse",
                 color="#cdd6f4", fontsize=13, y=1.01)
    plt.tight_layout()

    out = os.path.join(out_root, "results_plot.png")
    plt.savefig(out, dpi=120, facecolor="#1e1e2e", bbox_inches="tight")
    plt.close()
    print(f"Plot gespeichert: {out}")
    return out


# ══════════════════════════════════════════════════════════════════════
# Hilfsfunktionen
# ══════════════════════════════════════════════════════════════════════

def _get_image_size(result: dict) -> tuple:
    """Schätzt Bildgröße aus Overlay oder gibt Default zurück."""
    overlay = result.get("overlay")
    if overlay and os.path.exists(overlay):
        try:
            img = Image.open(overlay)
            return img.size  # (w, h)
        except Exception:
            pass
    return 1024, 1024