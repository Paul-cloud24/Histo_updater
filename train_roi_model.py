# train_roi_model.py
"""
Standalone-Skript zum Trainieren des ROI-Modells.

Ausfuehren:
    python train_roi_model.py
    python train_roi_model.py --epochs 150 --imgsz 1024
"""

import argparse
import sys
import os

# Projektpfad hinzufuegen
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))


def main():
    parser = argparse.ArgumentParser(
        description="Trainiert YOLOv8-Seg fuer Knorpel-ROI-Erkennung"
    )
    parser.add_argument("--epochs", type=int, default=100,
                        help="Anzahl Trainings-Epochen (default: 100)")
    parser.add_argument("--imgsz",  type=int, default=1024,
                        help="Bildgröße für Training (default: 1024)")
    parser.add_argument("--batch",  type=int, default=-1,
                        help="Batch-Größe (-1 = auto)")
    parser.add_argument("--export-only", action="store_true",
                        help="Nur Daten exportieren, nicht trainieren")
    args = parser.parse_args()

    print("=" * 60)
    print("  Histo Analyzer — ROI Modell Training")
    print("=" * 60)

    # Referenzen prüfen
    from analysis.roi_learner import get_reference_count
    n = get_reference_count()
    print(f"\n  Gespeicherte ROI-Referenzen: {n}")

    if n < 4:
        print(f"\n  FEHLER: Zu wenig Referenzen ({n}).")
        print("  Bitte zuerst mindestens 4 ROIs im Programm einzeichnen")
        print("  und mit '💾 Als Referenz speichern' sichern.")
        sys.exit(1)

    if n < 20:
        print(f"\n  WARNUNG: Nur {n} Referenzen — Ergebnis evtl. ungenau.")
        print("  Empfehlung: mindestens 20, besser 50+ Referenzen.")

    # Export
    print("\n  Exportiere Daten ins YOLO-Format...")
    from analysis.roi_exporter import export_all_references
    try:
        info = export_all_references(val_split=0.2, max_size=args.imgsz)
        print(f"  Train: {info['n_train']}  Val: {info['n_val']}")
        print(f"  Dataset: {info['dataset_dir']}")
    except Exception as e:
        print(f"\n  FEHLER beim Export: {e}")
        sys.exit(1)

    if args.export_only:
        print("\n  --export-only: Training übersprungen.")
        sys.exit(0)

    # ultralytics prüfen
    try:
        import ultralytics
        print(f"\n  ultralytics {ultralytics.__version__} gefunden ✔")
    except ImportError:
        print("\n  FEHLER: ultralytics nicht installiert.")
        print("  Bitte ausführen: pip install ultralytics")
        sys.exit(1)

    # Training
    print(f"\n  Starte Training ({args.epochs} Epochen)...")
    print("  (Dies kann 10-60 Minuten dauern)")
    print("-" * 60)

    from analysis.roi_trainer import train
    try:
        model_path = train(
            epochs=args.epochs,
            imgsz=args.imgsz,
            batch=args.batch,
        )
        print("-" * 60)
        print(f"\n  ✔ Training abgeschlossen!")
        print(f"  Modell gespeichert: {model_path}")
    except Exception as e:
        print(f"\n  FEHLER beim Training: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

    # Metriken
    from analysis.roi_trainer import get_training_summary
    summary = get_training_summary()
    if summary:
        print(f"\n  Trainings-Metriken:")
        print(f"    Epochen:  {summary['epochs_trained']}")
        print(f"    mAP50:    {summary['mAP50']}")
        print(f"    Box-Loss: {summary['box_loss']}")
        print(f"    Seg-Loss: {summary['seg_loss']}")

    print("\n  Das Modell ist jetzt aktiv.")
    print("  Klicke in der App auf '🤖 Auto-ROI' um es zu verwenden.")
    print("=" * 60)


if __name__ == "__main__":
    main()