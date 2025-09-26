import os, sys
from pathlib import Path

def resource_path(relative_path: str) -> str:
    base_path = getattr(sys, '_MEIPASS', os.path.abspath("."))
    return os.path.join(base_path, relative_path)

def is_text_like(p: Path, exts) -> bool:
    return p.is_file() and p.suffix.lower() in {e.lower() for e in exts}
