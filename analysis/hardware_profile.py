import os
import psutil
import torch
import multiprocessing

def evaluate_hardware():
    """
    Evaluiert die verfügbare Hardware und gibt ein Profil zurück
    das Pipeline und Cellpose optimal konfiguriert.
    """
    profile = {}

    # ── CPU ──────────────────────────────────────────────────────────
    cpu_count_physical = psutil.cpu_count(logical=False) or 1
    cpu_count_logical  = psutil.cpu_count(logical=True)  or 1
    ram_gb = psutil.virtual_memory().total / (1024 ** 3)

    profile["cpu_physical"] = cpu_count_physical
    profile["cpu_logical"]  = cpu_count_logical
    profile["ram_gb"]        = ram_gb

    # Torch-Threads: physische Kerne, max 8 (mehr bringt bei Cellpose nichts)
    torch_threads = min(cpu_count_physical, 8)
    profile["torch_threads"] = torch_threads

    # Post-Processing Worker (Watershed etc.): alle physischen Kerne
    profile["pp_workers"] = cpu_count_physical

    # ── GPU ──────────────────────────────────────────────────────────
    profile["gpu_available"] = False
    profile["gpu_name"]      = None
    profile["gpu_vram_gb"]   = 0
    profile["use_gpu"]       = False
    profile["batch_size"]    = 4   # konservativer CPU-Default

    if torch.cuda.is_available():
        try:
            gpu_idx   = 0
            vram_gb   = torch.cuda.get_device_properties(gpu_idx).total_memory / (1024 ** 3)
            gpu_name  = torch.cuda.get_device_properties(gpu_idx).name

            profile["gpu_available"] = True
            profile["gpu_name"]      = gpu_name
            profile["gpu_vram_gb"]   = vram_gb
            profile["use_gpu"]       = True

            # batch_size nach VRAM:
            # < 4 GB  → 8   (kleine GPU / integriert)
            # 4–8 GB  → 16
            # > 8 GB  → 32
            if vram_gb < 4:
                profile["batch_size"] = 8
            elif vram_gb < 8:
                profile["batch_size"] = 16
            else:
                profile["batch_size"] = 32

        except Exception as e:
            print(f"GPU-Erkennung fehlgeschlagen: {e}")

    elif hasattr(torch.backends, "mps") and torch.backends.mps.is_available():
        # Apple Silicon
        profile["gpu_available"] = True
        profile["gpu_name"]      = "Apple MPS"
        profile["use_gpu"]       = True
        profile["batch_size"]    = 16

    else:
        # Reiner CPU-Betrieb: batch_size nach RAM
        if ram_gb >= 32:
            profile["batch_size"] = 8
        elif ram_gb >= 16:
            profile["batch_size"] = 4
        else:
            profile["batch_size"] = 2

    _print_profile(profile)
    return profile


def _print_profile(p):
    print("\n── Hardware Profil ─────────────────────────────────────────")
    print(f"  CPU:         {p['cpu_physical']} physische / {p['cpu_logical']} logische Kerne")
    print(f"  RAM:         {p['ram_gb']:.1f} GB")
    print(f"  GPU:         {p['gpu_name'] or 'keine'}", end="")
    if p["gpu_vram_gb"]:
        print(f"  ({p['gpu_vram_gb']:.1f} GB VRAM)", end="")
    print()
    print(f"  → GPU aktiv: {p['use_gpu']}")
    print(f"  → Batch size:{p['batch_size']}")
    print(f"  → Torch threads: {p['torch_threads']}")
    print(f"  → PP workers:    {p['pp_workers']}")
    print("────────────────────────────────────────────────────────────\n")