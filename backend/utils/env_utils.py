from pathlib import Path
import os
from typing import Optional


def ensure_loaded_backend_env(env_path: Optional[Path] = None) -> None:
    """Ensure keys from backend/.env are present in os.environ.

    This reads the file and sets missing keys into the process environment. It
    is safe to call multiple times.
    """
    try:
        base = Path(__file__).parent
        p = env_path or (base / ".env")
        if not p.exists():
            return
        # read lines and set only keys that are missing (do not overwrite already exported values)
        with p.open("r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith("#") or "=" not in line:
                    continue
                k, v = line.split("=", 1)
                k = k.strip()
                v = v.strip().strip('"').strip("'")
                # Only set if not already in environment
                if k and (os.getenv(k) is None):
                    os.environ[k] = v
    except Exception:
        # best-effort: never raise here
        return
