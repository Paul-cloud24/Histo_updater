# ui/batch_worker.py
from analysis.sox9_pipeline import Sox9Pipeline, find_images_in_folder
from analysis.batch_runner  import find_sox9_folders, collect_results
from ui.roi_dialog          import ROIDialog
from PIL import Image
import numpy as np
import os
import traceback
from PySide6.QtCore import Qt, QThreadPool, QRunnable, QObject, Signal, QWaitCondition, QMutex

class BatchSignals(QObject):
    progress        = Signal(int)         # 0–100 Gesamtfortschritt
    folder_done     = Signal(str, dict)   # folder_name, result
    folder_error    = Signal(str, str)    # folder_name, error
    finished        = Signal(str, str)    # csv_path, plot_path
    log             = Signal(str)         # Terminal-Log
    roi_needed      = Signal(str, str)    # folder_name, dapi_path → UI öffnet Dialog


class BatchWorker(QRunnable):
    """
    Führt Sox9/DAPI Analyse für alle Sox9-Unterordner aus.
    Pausiert automatisch wenn ein Ordner keine ROI hat und wartet
    bis der Benutzer sie im ROI-Dialog eingezeichnet hat.
    """

    def __init__(self, root_folder: str, threshold: int, use_roi: bool = False):
        super().__init__()
        self.root_folder = root_folder
        self.threshold   = threshold
        self.signals     = BatchSignals()
        self.use_roi = use_roi

        # Synchronisation Worker ↔ UI
        self._mutex     = QMutex()
        self._condition = QWaitCondition()
        self._roi_ready = False   # wird von UI auf True gesetzt nach ROI-Dialog

    def roi_confirmed(self):
        """Wird vom UI-Thread aufgerufen sobald ROI gespeichert wurde."""
        self._mutex.lock()
        self._roi_ready = True
        self._condition.wakeAll()
        self._mutex.unlock()

    def _wait_for_roi(self):
        """Blockiert den Worker-Thread bis roi_confirmed() aufgerufen wird."""
        self._mutex.lock()
        self._roi_ready = False
        while not self._roi_ready:
            self._condition.wait(self._mutex)
        self._mutex.unlock()

    def run(self):

        # Am Anfang von run() — Results-Ordner einmalig anlegen
        results_root = os.path.join(self.root_folder, "Results")
        os.makedirs(os.path.join(results_root, "Overlays"), exist_ok=True)
        os.makedirs(os.path.join(results_root, "ROIs"),     exist_ok=True)
        
        folders   = find_sox9_folders(self.root_folder)
        if not folders:
            self.signals.log.emit("⚠ Keine Sox9-Unterordner gefunden.")
            self.signals.finished.emit("", "")
            return

        results   = []
        n_folders = len(folders)

        for i, folder in enumerate(folders):
            folder_name = os.path.basename(folder)
            self.signals.log.emit(f"\n── [{i+1}/{n_folders}] {folder_name} ──")

            try:
                sox9_path, dapi_path = find_images_in_folder(folder)

                # ROI prüfen
                dapi_arr  = np.array(Image.open(dapi_path))
                dapi_h, dapi_w = dapi_arr.shape[:2]
                if self.use_roi:
                    roi_mask = ROIDialog.load_roi_mask(dapi_path, dapi_h, dapi_w)
                    roi_used = roi_mask is not None
                    if not roi_used:
                        self.signals.log.emit(f"  ℹ Keine ROI gefunden → ganzes Bild")
                else:
                    roi_mask = None
                    roi_used = False
                    self.signals.log.emit(f"  ℹ Modus: Ganzes Bild")


                # Pipeline ausführen
                pipeline = Sox9Pipeline(
                    worker=None,
                    threshold=self.threshold,
                    roi_mask=roi_mask,
                )
                result = pipeline.run(
                    sox9_path=sox9_path,
                    dapi_path=dapi_path,
                    output_folder=results_root,
                )

                result["folder_name"] = folder_name
                result["roi_used"]    = roi_used
                result["status"]      = "ok"

                roi_json = ROIDialog._get_json_path(dapi_path)
                result["roi_json"] = roi_json if os.path.exists(roi_json) else None

                self.signals.log.emit(
                    f"  ✔ DAPI: {result['n_dapi_total']}  "
                    f"Sox9+: {result['n_positive']}  "
                    f"Ratio: {result['ratio']:.1f}%"
                )
                self.signals.folder_done.emit(folder_name, result)

            except Exception as e:
                self.signals.log.emit(f"  ✗ Fehler: {e}\n{traceback.format_exc()}")
                self.signals.folder_error.emit(folder_name, str(e))
                result = {
                    "folder_name":  folder_name,
                    "n_dapi_total": 0, "n_positive": 0,
                    "ratio":        0.0, "roi_used": False,
                    "status":       f"error: {e}",
                    "overlay":      None, "roi_json": None,
                }

            results.append(result)
            self.signals.progress.emit(int((i + 1) / n_folders * 100))

        # Alle Ordner fertig → sammeln
        self.signals.log.emit("\n── Ergebnisse zusammenführen ──")
        csv_path, plot_path = collect_results(self.root_folder, results)
        self.signals.finished.emit(csv_path or "", plot_path or "")