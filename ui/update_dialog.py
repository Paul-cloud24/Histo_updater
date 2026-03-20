# ui/update_dialog.py
import os
import sys
from version import UPDATE_REPO, UPDATE_BRANCH

from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout,
    QLabel, QPushButton, QProgressBar, QTextEdit, QFrame
)


class UpdateDialog(QDialog):
    def __init__(self, new_version: str, changelog: str,
                 files: list, update_repo: str,
                 app_root: str, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Update verfügbar")
        self.setMinimumWidth(440)
        self.setModal(True)

        self.files       = files
        self.update_repo = update_repo
        self.app_root    = app_root
        self.new_version = new_version

        layout = QVBoxLayout(self)
        layout.setSpacing(12)
        layout.setContentsMargins(16, 16, 16, 16)

        lbl = QLabel(f"🎉  Version {new_version} ist verfügbar!")
        lbl.setStyleSheet("font-size:14px; font-weight:700; color:#89b4fa;")
        layout.addWidget(lbl)

        n = len(files)
        lbl_files = QLabel(
            f"{n} Datei{'en' if n != 1 else ''} werden aktualisiert:")
        lbl_files.setStyleSheet("color:#6c7086; font-size:11px;")
        layout.addWidget(lbl_files)

        txt = QTextEdit()
        txt.setReadOnly(True)
        txt.setFixedHeight(90)
        txt.setPlainText("\n".join(files) if files else "—")
        layout.addWidget(txt)

        if changelog:
            sep = QFrame()
            sep.setFrameShape(QFrame.HLine)
            sep.setStyleSheet(
                "background:#313244; max-height:1px; border:none;")
            layout.addWidget(sep)
            layout.addWidget(QLabel("Was ist neu:"))
            cl = QTextEdit()
            cl.setReadOnly(True)
            cl.setFixedHeight(80)
            cl.setPlainText(changelog)
            layout.addWidget(cl)

        self.progress = QProgressBar()
        self.progress.setValue(0)
        self.progress.setVisible(False)
        layout.addWidget(self.progress)

        self.status_lbl = QLabel("")
        self.status_lbl.setStyleSheet("color:#6c7086; font-size:11px;")
        layout.addWidget(self.status_lbl)

        btn_row = QHBoxLayout()
        self.btn_later   = QPushButton("Später")
        self.btn_later.clicked.connect(self.reject)
        self.btn_install = QPushButton("⬇  Aktualisieren & neu starten")
        self.btn_install.setObjectName("primary")
        self.btn_install.setMinimumHeight(38)
        self.btn_install.clicked.connect(self._start_update)
        btn_row.addWidget(self.btn_later)
        btn_row.addWidget(self.btn_install)
        layout.addLayout(btn_row)

    def _start_update(self):
        from ui.updater import FileUpdater
        from version import UPDATE_BRANCH 
        self.btn_install.setEnabled(False)
        self.btn_later.setEnabled(False)
        self.progress.setVisible(True)
        self.status_lbl.setText("Lade Dateien...")

        self._worker = FileUpdater(
            update_repo=self.update_repo,
            files=self.files,
            app_root=self.app_root,
        )
        self._worker.progress.connect(self._on_progress)
        self._worker.done.connect(self._on_done)
        self._worker.error.connect(self._on_error)
        self._worker.run_async()

    def _on_progress(self, pct: int, filename: str):
        self.progress.setValue(pct)
        self.status_lbl.setText(f"↓  {filename}")

    def _on_done(self):
        self.progress.setValue(100)
        self.status_lbl.setText("✔  Neustart...")
        python = sys.executable
        os.execv(python, [python] + sys.argv)

    def _on_error(self, msg: str):
        self.progress.setVisible(False)
        self.status_lbl.setText(f"❌  {msg}")
        self.btn_later.setEnabled(True)
        self.btn_install.setEnabled(True)