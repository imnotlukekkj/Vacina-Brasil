import json
import re
from pathlib import Path
from typing import List, Dict, Any, Optional


class Normalizer:
    def __init__(self, mappings_path: str = "backend/mappings.json"):
        self.mappings_path = Path(mappings_path)
        self.mappings = self.load_mappings()

    def load_mappings(self) -> List[Dict[str, Any]]:
        if not self.mappings_path.exists():
            return []
        with self.mappings_path.open("r", encoding="utf-8") as f:
            data = json.load(f)
        # order by priority asc
        return sorted(data, key=lambda x: x.get("priority", 100))

    def normalize_sigla(self, tx_sigla: Optional[str]) -> Optional[str]:
        if not tx_sigla:
            return None
        s = tx_sigla.strip().upper()
        s = re.sub(r"^SES[\-\s./]*", "", s)
        m = re.search(r"([A-Z]{2})$", s)
        if m:
            return m.group(1)
        return s[:2] if s else None

    def normalize_insumo(self, tx_insumo: Optional[str]) -> Optional[str]:
        if not tx_insumo:
            return None
        tx = tx_insumo.strip()
        for m in self.mappings:
            pat = m.get("pattern") or ""
            try:
                if pat and re.search(pat, tx, flags=re.IGNORECASE):
                    return m.get("vacina_normalizada")
            except re.error:
                if pat and (pat.lower() in tx.lower()):
                    return m.get("vacina_normalizada")

        # special case for DILUENTE (try to extract vaccine name)
        tx_upper = tx.upper()
        if "DILUENTE" in tx_upper:
            m0 = re.search(r"VACINA(?:\s*(?:P/|PARA|CONTRA)\s*)?(.*)$", tx_upper)
            candidate = None
            if m0:
                candidate = m0.group(1).strip()
            else:
                candidate = re.sub(r".*DILUENTE.*?", "", tx_upper).strip()
            if candidate:
                candidate = re.sub(r"[\-\(\)\,\d]", "", candidate).strip()
                for m in self.mappings:
                    pat = m.get("pattern") or ""
                    try:
                        if pat and re.search(pat, candidate, flags=re.IGNORECASE):
                            return m.get("vacina_normalizada")
                    except re.error:
                        if pat and (pat.lower() in candidate.lower()):
                            return m.get("vacina_normalizada")

        # fallback SARS-COV2
        if re.search(r"SARS[- ]?COV2|COVID[- ]?19", tx, flags=re.IGNORECASE):
            return "Covid-19"

        return None


_default_normalizer: Optional[Normalizer] = None


def get_default_normalizer() -> Normalizer:
    global _default_normalizer
    if _default_normalizer is None:
        _default_normalizer = Normalizer()
    return _default_normalizer


if __name__ == "__main__":
    n = get_default_normalizer()
    print(f"Loaded {len(n.mappings)} mappings")
