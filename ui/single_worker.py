# ui/single_worker.py

import traceback
import numpy as np
from PySide6.QtCore import QRunnable, QObject, Signal


class SingleWorkerSignals(QObject):
    log      = Signal(str)
    finished = Signal(str)
    error    = Signal(str)
    overlay  = Signal(str)


class SingleWorker(QRunnable):
    """
    Analysiert einen einzelnen Ordner im Hintergrund-Thread.
    Verwendet für Einzelordner-Analyse (kein Batch).
    """

    def __init__(self, stain, marker_path: str, dapi_path: str,
                 output_folder: str, roi_mask=None, threshold: int = 60, pipeline_params: dict = None):
        super().__init__()
        self.stain         = stain
        self.marker_path   = marker_path
        self.dapi_path     = dapi_path
        self.output_folder = output_folder
        self.roi_mask      = roi_mask
        self.threshold     = threshold
        self.pipeline_params = pipeline_params or {}
        self.signals       = SingleWorkerSignals()

    def run(self):
        try:
            self.signals.log.emit(
                f"── {self.stain.name} Analyse ──")
            self.signals.log.emit(
                f"  Marker: {self.marker_path.split('/')[-1]}")
            self.signals.log.emit(
                f"  DAPI:   {self.dapi_path.split('/')[-1]}")

            result = self.stain.analyze(
                marker_path=self.marker_path,
                dapi_path=self.dapi_path,
                output_folder=self.output_folder,
                roi_mask=self.roi_mask,
                threshold=self.threshold,
                **self.pipeline_params,  # pos_frac, min_area …
            )

            n_total   = result.get("n_total", 0)
            n_pos     = result.get("n_positive",
                        result.get("n_apoptotic", 0))
            ratio     = result.get("ratio",
                        result.get("apoptosis_%", 0.0))

            self.signals.log.emit(
                f"  ✔ DAPI: {n_total}  "
                f"positiv: {n_pos}  "
                f"Ratio: {ratio:.1f}%"
            )

            if result.get("overlay"):
                self.signals.log.emit(
                    f"  Overlay: {result['overlay']}")
            if result.get("csv"):
                self.signals.log.emit(
                    f"  CSV:     {result['csv']}")

            self.signals.finished.emit(
                f"DAPI: {n_total}  |  positiv: {n_pos}  "
                f"|  Ratio: {ratio:.1f}%"
            )

        except Exception as e:
            self.signals.log.emit(f"  ✗ Fehler: {e}")
            self.signals.error.emit(str(e))
            self.signals.finished.emit(f"Fehler: {e}")