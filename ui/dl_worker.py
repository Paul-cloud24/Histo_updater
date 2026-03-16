import os
from PySide6.QtCore import Qt, QThreadPool, QRunnable, QObject, Signal, QWaitCondition, QMutex
class DLWorkerSignals(QObject):
    progress = Signal(int)     # 0–100%
    finished = Signal(str)     # final result text
class DLWorker(QRunnable):
    """
    Worker für klassische DL-Stain-Analyse.
    Läuft im Hintergrund über QThreadPool.
    """
    def __init__(self, folder, stain_model):
        super().__init__()
        self.folder = folder
        self.stain_model = stain_model
        self.signals = DLWorkerSignals()
    def run(self):
        model = self.stain_model.load_for_inference()
        # Alle passenden Bilder laden
        images = [
            f for f in os.listdir(self.folder)
            if f.lower().endswith((".png", ".jpg", ".jpeg", ".tif"))
        ]
        total = len(images)
        if total == 0:
            self.signals.finished.emit("Keine geeigneten Bilder gefunden.")
            return
        results = []
        for i, img_name in enumerate(images):
            full_path = os.path.join(self.folder, img_name)
            pred = model.predict(full_path)
            cls = pred.argmax(1).item()
            results.append((img_name, cls))
            progress = int((i + 1) / total * 100)
            self.signals.progress.emit(progress)
        # Ergebnistext erzeugen
        text = "\n".join([f"{x[0]} → Klasse {x[1]}" for x in results])
        self.signals.finished.emit(text)