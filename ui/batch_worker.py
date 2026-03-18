# ui/batch_worker.py — generisch für alle Färbungen

import os
import traceback
from PySide6.QtCore import QRunnable, QObject, Signal


class BatchSignals(QObject):
    progress     = Signal(int)
    progress_tile= Signal(int) 
    folder_done  = Signal(str, dict)
    folder_error = Signal(str, str)
    finished     = Signal(str, str)
    log          = Signal(str)
    preview       = Signal(str, str)   # Feature 3: Marker-Bild vor Analyse
    overlay       = Signal(str)   # Feature 3: Overlay nach Analyse


class BatchWorker(QRunnable):
    """
    Generischer Batch-Worker für alle Färbungen.
    Verwendet find_stain_folders() aus core_pipeline.
    """

    def __init__(self, root_folder: str, stain_name: str,
                 threshold: int, use_roi: bool = False, pipeline_params: dict = None):
        super().__init__()
        self.root_folder = root_folder
        self.stain_name  = stain_name   # z.B. "Sox9", "TUNEL"
        self.threshold   = threshold
        self.use_roi     = use_roi
        self.pipeline_params = pipeline_params or {}
        self.signals     = BatchSignals()

    def run(self):
        from analysis.core_pipeline  import (find_stain_folders,
                                              find_images_in_folder,
                                              CoreStainPipeline)
        from analysis.iso_threshold  import pair_sox9_iso, compute_iso_threshold
        from stains                  import get_stain
        from ui.roi_dialog           import ROIDialog
        from PIL import Image
        import numpy as np

        results_root = os.path.join(self.root_folder, "Results")
        os.makedirs(os.path.join(results_root, "Overlays"), exist_ok=True)
        os.makedirs(os.path.join(results_root, "ROIs"),     exist_ok=True)

        # Ordner finden
        probe_folders, iso_folders = find_stain_folders(
            self.root_folder, self.stain_name)

        if not probe_folders:
            self.signals.log.emit(
                f"⚠ Keine {self.stain_name}-Ordner gefunden.")
            self.signals.finished.emit("", "")
            return

        # Iso-Pairing
        from analysis.iso_threshold import pair_sox9_iso
        pairs = pair_sox9_iso(probe_folders, iso_folders)

        results   = []
        n_folders = len(probe_folders)

        for i, folder in enumerate(probe_folders):
            folder_name = os.path.basename(folder)
            self.signals.log.emit(
                f"\n── [{i+1}/{n_folders}] {folder_name} ──")

            try:
                self.signals.progress_tile.emit(10)

                # Stain-Instanz holen (vor find_images, da Von Kossa kein DAPI braucht)
                stain_key = next(
                    (k for k in ["Sox9/DAPI", "TUNEL/DAPI", "Col1", "Col2",
                                 "Safranin O", "MMP13", "Von Kossa"]
                     if self.stain_name.lower() in k.lower()),
                    None
                )
                if stain_key is None:
                    raise ValueError(
                        f"Unbekannte Färbung: {self.stain_name}")
                stain = get_stain(stain_key)

                # Von Kossa: kein DAPI, nur ein RGB-Brightfield-Bild
                is_brightfield = (stain_key == "Von Kossa")

                if is_brightfield:
                    from analysis.brightfield_pipeline import find_brightfield_image
                    marker_path = find_brightfield_image(folder)
                    dapi_path   = marker_path   # Dummy – wird nicht verwendet
                else:
                    marker_path, dapi_path = find_images_in_folder(folder)

                self.signals.preview.emit(marker_path, dapi_path)  # Feature 3

                # ROI
                self.signals.progress_tile.emit(20)
                roi_ref_path = marker_path  # Von Kossa: ROI über Brightfield-Bild
                if self.use_roi:
                    ref_arr = np.array(Image.open(roi_ref_path))
                    ref_h, ref_w = ref_arr.shape[:2]
                    roi_mask = ROIDialog.load_roi_mask(
                        roi_ref_path, ref_h, ref_w)
                    roi_used = roi_mask is not None
                    if not roi_used:
                        self.signals.log.emit("  ℹ Keine ROI → ganzes Bild")
                else:
                    roi_mask = None
                    roi_used = False

                # Threshold kalibrieren (Iso nur für Fluoreszenz)
                if is_brightfield:
                    threshold  = self.threshold
                    thr_method = "manual"
                    self.signals.log.emit(
                        f"  Darkness-Threshold={threshold}")
                else:
                    iso_folder = pairs.get(folder)
                    if iso_folder:
                        self.signals.log.emit(
                            f"  Iso: {os.path.basename(iso_folder)}")
                        iso_res    = compute_iso_threshold(
                            iso_folder, n_sigma=2.0, roi_mask=roi_mask)
                        threshold  = iso_res["threshold"] if iso_res \
                                     else self.threshold
                        thr_method = "iso"
                    else:
                        threshold  = self.threshold
                        thr_method = "manual"
                        self.signals.log.emit(
                            f"  ⚠ Kein Iso-Partner → Threshold={threshold}")
                    self.signals.log.emit(
                        f"  Threshold={threshold:.1f} ({thr_method})")

                self.signals.progress_tile.emit(30)
                result = stain.analyze(
                    marker_path=marker_path,
                    dapi_path=dapi_path,
                    output_folder=results_root,
                    roi_mask=roi_mask,
                    threshold=threshold,
                    threshold_method=thr_method,
                    **self.pipeline_params,         # Feature 1
                )

                result["folder_name"]      = folder_name
                result["roi_used"]         = roi_used
                result["threshold_used"]   = round(threshold, 1)
                result["threshold_method"] = thr_method
                result["status"]           = "ok"

                roi_json = ROIDialog._get_json_path(dapi_path)
                result["roi_json"] = roi_json \
                    if os.path.exists(roi_json) else None

                n_pos = result.get("n_positive",
                        result.get("n_apoptotic", 0))
                ratio = result.get("ratio",
                        result.get("apoptosis_%", 0))
                self.signals.log.emit(
                    f"  ✔ DAPI: {result['n_total']}  "
                    f"positiv: {n_pos}  Ratio: {ratio:.1f}%"
                )

                if result.get("overlay"):
                    self.signals.overlay.emit(result["overlay"])

                self.signals.folder_done.emit(folder_name, result)

            except Exception as e:
                self.signals.log.emit(
                    f"  ✗ Fehler: {e}\n{traceback.format_exc()}")
                self.signals.folder_error.emit(folder_name, str(e))
                results.append({
                    "folder_name": folder_name, "n_total": 0,
                    "n_positive": 0, "ratio": 0.0,
                    "roi_used": False, "status": f"error: {e}",
                    "overlay": None, "roi_json": None,
                })
                continue

            results.append(result)
            self.signals.progress.emit(
                int((i + 1) / n_folders * 100))

        # Ergebnisse sammeln
        self.signals.log.emit("\n── Ergebnisse zusammenführen ──")
        from analysis.batch_runner import collect_results
        csv_path, plot_path = collect_results(self.root_folder, results)
        self.signals.finished.emit(csv_path or "", plot_path or "")