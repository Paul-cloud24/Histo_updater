# empty
# stains/__init__.py
from stains.base_stain  import BaseStain
from stains.sox9_stain  import Sox9Stain
from stains.col1        import Col1Stain
from stains.col2        import Col2Stain
from stains.safranin_o  import SafraninStain
from stains.tunel       import TunelStain

STAIN_REGISTRY = {
    "Sox9/DAPI":  Sox9Stain,
    "Col1":       Col1Stain,
    "Col2":       Col2Stain,
    "Safranin O": SafraninStain,
    "TUNEL":      TunelStain,
}

def get_stain(name: str) -> BaseStain:
    cls = STAIN_REGISTRY.get(name)
    if cls is None:
        raise ValueError(f"Unbekannte Färbung: {name}")
    return cls()

def available_stains() -> list:
    return list(STAIN_REGISTRY.keys())