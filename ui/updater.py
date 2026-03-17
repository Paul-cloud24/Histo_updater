# ui/updater.py
import json
import os
import sys
import threading
import urllib.request
from PySide6.QtCore import QObject, Signal


GITHUB_RAW = "https://raw.githubusercontent.com"


class UpdateChecker(QObject):
    update_available = Signal(str, str, list)  # (version, changelog, files)
    up_to_date       = Signal()
    error            = Signal(str)

    def __init__(self, current_version: str, update_repo: str):
        super().__init__()
        self.current_version = current_version
        self.update_repo     = update_repo

    def check_async(self):
        t = threading.Thread(target=self._check, daemon=True)
        t.start()

    def _check(self):
        try:
            url  = f"{GITHUB_RAW}/{self.update_repo}/main/version.json"
            data = json.loads(self._fetch(url))

            latest    = data.get("version", "0.0.0")
            changelog = data.get("changelog", "")
            files     = data.get("files", [])

            if self._is_newer(latest, self.current_version):
                self.update_available.emit(latest, changelog, files)
            else:
                self.up_to_date.emit()

        except Exception as e:
            self.error.emit(str(e))

    def _fetch(self, url: str) -> bytes:
        req = urllib.request.Request(
            url, headers={"User-Agent": "HistoAnalyzer"})
        with urllib.request.urlopen(req, timeout=8) as resp:
            return resp.read()

    @staticmethod
    def _is_newer(latest: str, current: str) -> bool:
        def parse(v):
            try:
                return tuple(int(x) for x in v.split("."))
            except Exception:
                return (0,)
        return parse(latest) > parse(current)


class FileUpdater(QObject):
    progress = Signal(int, str)   # (prozent, dateiname)
    done     = Signal()
    error    = Signal(str)

    def __init__(self, update_repo: str, files: list, app_root: str):
        super().__init__()
        self.update_repo = update_repo
        self.files       = files
        self.app_root    = app_root   # Verzeichnis wo main.py liegt

    def run_async(self):
        t = threading.Thread(target=self._run, daemon=True)
        t.start()

    def _run(self):
        try:
            n = len(self.files)
            for i, rel_path in enumerate(self.files):
                self.progress.emit(
                    int(i / n * 90),
                    rel_path
                )
                url      = f"{GITHUB_RAW}/{self.update_repo}/main/{rel_path}"
                req      = urllib.request.Request(
                    url, headers={"User-Agent": "HistoAnalyzer"})
                with urllib.request.urlopen(req, timeout=10) as resp:
                    content = resp.read()

                # Lokal speichern
                dest = os.path.join(self.app_root, rel_path.replace("/", os.sep))
                os.makedirs(os.path.dirname(dest), exist_ok=True)
                with open(dest, "wb") as f:
                    f.write(content)

            self.progress.emit(100, "Fertig")
            self.done.emit()

        except Exception as e:
            self.error.emit(str(e))
            