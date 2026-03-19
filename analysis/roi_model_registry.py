# analysis/roi_model_registry.py
"""
Verwaltung mehrerer ROI-Modelle.

Jedes Modell hat:
  - name:       Anzeigename (z.B. "Sox9 Tibia", "Von Kossa Femur")
  - stain:      Faerbungsname
  - slice_type: Gewebetyp / Schnitt (z.B. "Tibia", "Femur", "Allgemein")
  - model_path: Pfad zur .pt Datei
  - created:    Datum
  - n_refs:     Anzahl Trainingsreferenzen
  - mAP50:      Trainings-Metrik
  - active:     ob dieses Modell aktuell aktiv ist

Gespeichert in: AppData/HistoAnalyzer/models/registry.json
"""

import os
import json
import shutil
from pathlib import Path
from datetime import datetime


def get_models_dir() -> Path:
    base = Path(os.environ.get("APPDATA", Path.home() / "AppData" / "Roaming"))
    d = base / "HistoAnalyzer" / "models"
    d.mkdir(parents=True, exist_ok=True)
    return d


def get_registry_path() -> Path:
    return get_models_dir() / "registry.json"


def load_registry() -> list:
    """Laedt alle gespeicherten Modelle."""
    path = get_registry_path()
    if not path.exists():
        # Migration: altes roi_model.pt einbinden falls vorhanden
        return _migrate_legacy_model()
    try:
        with open(path) as f:
            return json.load(f)
    except Exception:
        return []


def save_registry(models: list):
    with open(get_registry_path(), "w") as f:
        json.dump(models, f, indent=2)


def _migrate_legacy_model() -> list:
    """Migriert das alte roi_model.pt ins neue Registry-Format."""
    legacy = get_models_dir() / "roi_model.pt"
    if not legacy.exists():
        return []

    # Metriken aus altem Training holen
    from analysis.roi_trainer import get_training_summary
    summary = get_training_summary() or {}

    # Referenzanzahl ermitteln
    try:
        from analysis.roi_learner import get_reference_count
        n_refs = get_reference_count()
    except Exception:
        n_refs = 0

    model = {
        "id":         "model_001",
        "name":       "Standard ROI-Modell",
        "stain":      "Alle",
        "slice_type": "Allgemein",
        "model_path": str(legacy),
        "created":    datetime.now().isoformat(),
        "n_refs":     n_refs,
        "mAP50":      summary.get("mAP50", 0.0),
        "epochs":     summary.get("epochs_trained", 0),
        "active":     True,
        "ref_ids":    [],   # IDs der verknuepften ROI-Referenzen
    }

    models = [model]
    save_registry(models)
    print(f"  [Registry] Legacy-Modell migriert: {legacy}")
    return models


def register_model(name: str, stain: str, slice_type: str,
                   model_path: str, n_refs: int,
                   mAP50: float = 0.0, epochs: int = 0) -> dict:
    """Registriert ein neues Modell."""
    models = load_registry()

    # Alle anderen deaktivieren
    for m in models:
        m["active"] = False

    # Eindeutige ID
    model_id = f"model_{len(models) + 1:03d}"

    # Datei in models-Ordner kopieren
    dest = get_models_dir() / f"{model_id}.pt"
    if str(model_path) != str(dest):
        shutil.copy2(model_path, dest)

    # Referenz-IDs aus aktuellem Learner holen
    try:
        from analysis.roi_learner import load_references
        refs = load_references()
        ref_ids = [r["id"] for r in refs]
    except Exception:
        ref_ids = []

    model = {
        "id":         model_id,
        "name":       name,
        "stain":      stain,
        "slice_type": slice_type,
        "model_path": str(dest),
        "created":    datetime.now().isoformat(),
        "n_refs":     n_refs,
        "mAP50":      mAP50,
        "epochs":     epochs,
        "active":     True,
        "ref_ids":    ref_ids,
    }

    models.append(model)
    save_registry(models)
    print(f"  [Registry] Modell registriert: {name} ({model_id})")
    return model


def get_active_model() -> dict | None:
    """Gibt das aktive Modell zurueck."""
    models = load_registry()
    for m in models:
        if m.get("active"):
            if Path(m["model_path"]).exists():
                return m
    # Fallback: letztes verfuegbares
    for m in reversed(models):
        if Path(m["model_path"]).exists():
            return m
    return None


def set_active_model(model_id: str):
    """Setzt ein Modell als aktiv."""
    models = load_registry()
    for m in models:
        m["active"] = (m["id"] == model_id)
    save_registry(models)


def delete_model(model_id: str):
    """Loescht ein Modell aus der Registry (und die .pt Datei)."""
    models = load_registry()
    to_delete = next((m for m in models if m["id"] == model_id), None)
    if to_delete:
        # .pt Datei loeschen
        try:
            Path(to_delete["model_path"]).unlink()
        except Exception:
            pass
        models = [m for m in models if m["id"] != model_id]
        # Falls aktives geloescht: letztes aktivieren
        if models and not any(m.get("active") for m in models):
            models[-1]["active"] = True
        save_registry(models)


def get_refs_for_model(model: dict) -> list:
    """Gibt alle ROI-Referenzen eines Modells zurueck."""
    from analysis.roi_learner import load_references
    all_refs = load_references()
    ref_ids  = set(model.get("ref_ids", []))
    if not ref_ids:
        return all_refs   # Altes Modell: alle Referenzen zeigen
    return [r for r in all_refs if r["id"] in ref_ids]