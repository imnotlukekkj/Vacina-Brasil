#!/usr/bin/env python3
"""
Script simples para normalizar registros JSON (campo TX_INSUMO) usando os mapeamentos em mappings.json.

Uso:
    python backend/etl_normalize.py --input data.json --output <output.json>

O script aplica os padrões na ordem de `priority` (menor primeiro). Usa regex case-insensitive.
"""
import argparse
import json
import re
from pathlib import Path
import logging

logger = logging.getLogger(__name__)


def load_mappings(path: Path):
    with path.open("r", encoding="utf-8") as f:
        data = json.load(f)
    # ordenar por priority
    return sorted(data, key=lambda x: x.get("priority", 100))


def normalize_record(rec, mappings):
    # normalizar a sigla (ex: 'SES-PR' -> 'PR') e expor em 'tx_sigla_norm'
    def _normalize_tx_sigla(r):
        txs = r.get("TX_SIGLA") or r.get("tx_sigla") or ""
        if not txs:
            r["tx_sigla_norm"] = None
            return r
        txs = txs.strip().upper()
        # remover prefixos comuns como 'SES-' ou 'SES '
        txs = re.sub(r"^SES[\-\s./]*", "", txs)
        # pegar último par de letras (código UF) se existir
        m = re.search(r"([A-Z]{2})$", txs)
        if m:
            r["tx_sigla_norm"] = m.group(1)
        else:
            # fallback: usar os dois primeiros caracteres
            r["tx_sigla_norm"] = txs[:2] if len(txs) >= 2 else txs
        return r

    _normalize_tx_sigla(rec)

    tx = rec.get("TX_INSUMO") or rec.get("tx_insumo") or ""
    if not tx:
        rec["tx_insumo_norm"] = None
        return rec
    # tentativa direta por patterns
    for m in mappings:
        pattern = m.get("pattern")
        try:
            if re.search(pattern, tx, flags=re.IGNORECASE):
                rec["tx_insumo_norm"] = m.get("vacina_normalizada")
                return rec
        except re.error:
            if pattern.lower() in tx.lower():
                rec["tx_insumo_norm"] = m.get("vacina_normalizada")
                return rec

    # tratamento especial para DILUENTES: tentar extrair o nome da vacina e re-match
    tx_upper = tx.upper()
    if "DILUENTE" in tx_upper:
        # remover prefixos conhecidos e tentar extrair parte que indica a vacina
        # exemplos: "DILUENTE P/VACINA BCG", "DILUENTE PARA VACINA CONTRA VARICELA"
        # regex para capturar o que vem após 'VACINA' ou 'P/VACINA' ou 'PARA VACINA'
        m = re.search(r"VACINA(?:\s*(?:P/|PARA|CONTRA)\s*)?(.*)$", tx_upper, flags=re.IGNORECASE)
        candidate = None
        if m:
            candidate = m.group(1).strip()
        else:
            # fallback: remove 'DILUENTE' e use o resto
            candidate = re.sub(r".*DILUENTE.*?","", tx_upper, flags=re.IGNORECASE).strip()

        if candidate:
            # limpar palavras extras
            candidate = re.sub(r"[\-\(\)\,\d]","", candidate).strip()
            # tentar matching com os mappings usando candidate
            for m2 in mappings:
                pat = m2.get("pattern")
                try:
                    if re.search(pat, candidate, flags=re.IGNORECASE):
                        rec["tx_insumo_norm"] = m2.get("vacina_normalizada")
                        return rec
                except re.error:
                    if pat.lower() in candidate.lower():
                        rec["tx_insumo_norm"] = m2.get("vacina_normalizada")
                        return rec

    # fallback adicional: mapear SARS-COV2 variantes para Covid-19 se aparecer como 'SARS-COV2 - XXX'
    if re.search(r"SARS[- ]?COV2|COVID[- ]?19", tx, flags=re.IGNORECASE):
        rec["tx_insumo_norm"] = "Covid-19"
        return rec

    rec["tx_insumo_norm"] = None
    return rec


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--mappings", default="backend/mappings.json")
    p.add_argument("--input", required=True)
    p.add_argument("--output", required=True)
    args = p.parse_args()

    mappings = load_mappings(Path(args.mappings))

    with open(args.input, "r", encoding="utf-8") as f:
        data = json.load(f)

    out = [normalize_record(dict(rec), mappings) for rec in data]

    with open(args.output, "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, indent=2)

    logger.info("Wrote %d records to %s", len(out), args.output)


if __name__ == "__main__":
    main()
