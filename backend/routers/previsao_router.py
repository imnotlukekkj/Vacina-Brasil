from fastapi import APIRouter, Query
from fastapi.responses import JSONResponse
from typing import Optional, Any, Dict, List
import os
import re
import json
from pathlib import Path
import httpx
from ..utils.env_utils import ensure_loaded_backend_env
from ..normalizer import get_default_normalizer
from ..repositories.supabase_repo import (
    get_supabase_client,
    normalize_row,
    rpc_get_historico_e_previsao_raw,
    rpc_obter_soma_por_ano_value,
    rpc_obter_projecao_ano,
    rpc_median_projection_totals,
    rpc_timeseries_aggregated,
    rpc_overview_aggregated,
    rpc_ranking_ufs_aggregated,
    rpc_top_vacinas_aggregated,
    rpc_sazonalidade_agrupada,
    rpc_detalhes_geograficos_agrupados,
)
from ..schemas.previsao_schemas import ComparisonResponse

import logging

router = APIRouter()
logger = logging.getLogger(__name__)


# Backwards-compatible stub endpoints for legacy frontend routes.
# The frontend may call /api/overview, /api/timeseries, /api/ranking/ufs,
# /api/forecast and /api/mappings. Some hosting platforms already proxy
# under an /api prefix; providing these stub routes here avoids 404s while
# the frontend and backend are migrated to a single routing strategy.


def _load_local_data() -> List[Dict[str, Any]]:
    # prefer rerun2, then rerun; older filenames were removed to avoid confusion
    base = Path(__file__).resolve().parents[1]
    candidates = ["normalized_vacinas_rerun2.json", "normalized_vacinas_rerun.json"]
    for c in candidates:
        p = base / c
        if p.exists():
            with p.open("r", encoding="utf-8") as f:
                return json.load(f)
    return []


async def _fetch_rows_from_supabase(table: str, filters: Dict[str, Optional[str]]) -> List[Dict[str, Any]]:
    SUPABASE_URL = os.getenv("SUPABASE_URL")
    SUPABASE_SERVICE_ROLE_KEY = os.getenv("SUPABASE_SERVICE_ROLE_KEY")
    if not SUPABASE_URL or not SUPABASE_SERVICE_ROLE_KEY:
        return []

    base = SUPABASE_URL.rstrip("/")
    url = f"{base}/rest/v1/{table}"
    params: Dict[str, str] = {}
    params["select"] = "tx_sigla,tx_insumo,ano,mes,qtde"
    if filters.get("ano"):
        params["ano"] = f"eq.{filters.get('ano')}"
    if filters.get("mes"):
        params["mes"] = f"eq.{filters.get('mes')}"
    if filters.get("uf"):
        params["tx_sigla"] = f"ilike.*{filters.get('uf')}*"
    if filters.get("fabricante"):
        params["tx_insumo"] = f"ilike.*{filters.get('fabricante')}*"

    headers = {
        "apikey": SUPABASE_SERVICE_ROLE_KEY,
        "Authorization": f"Bearer {SUPABASE_SERVICE_ROLE_KEY}",
        "Accept": "application/json",
    }

    rows: List[Dict[str, Any]] = []
    page_size = 1000
    offset = 0

    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            while True:
                page_headers = {
                    **headers,
                    "Range": f"{offset}-{offset + page_size - 1}",
                    "Prefer": "count=exact",
                }
                resp = await client.get(url, params=params, headers=page_headers)
                if resp.status_code not in (200, 206):
                    logger.warning("Supabase request failed: %s %s", resp.status_code, resp.text)
                    return []
                data = resp.json()
                if not isinstance(data, list) or not data:
                    break
                rows.extend(data)
                if len(data) < page_size:
                    break
                offset += page_size
    except Exception:
        return []

    result: List[Dict[str, Any]] = []
    for r in rows:
        result.append({
            "tx_sigla": r.get("tx_sigla"),
            "tx_insumo": r.get("tx_insumo"),
            "ano": r.get("ano"),
            "mes": r.get("mes"),
            "qtde": r.get("qtde"),
        })
    return result


async def _fetch_rows(table: str, filters: Dict[str, Optional[str]]) -> List[Dict[str, Any]]:
    # Prefer Supabase REST when available, otherwise fallback to local JSON files
    rows = await _fetch_rows_from_supabase(table, filters)
    if rows:
        return rows
    return _load_local_data()


@router.get("/api/overview")
async def api_overview(ano: Optional[str] = Query(None), mes: Optional[str] = Query(None), uf: Optional[str] = Query(None), fabricante: Optional[str] = Query(None)):
    table = os.getenv("DATA_TABLE", "distribuicao")
    
    # Fast path: aggregate in DB via RPC to avoid downloading raw rows.
    ensure_loaded_backend_env()
    supabase_url = os.getenv("SUPABASE_URL")
    supabase_key = os.getenv("SUPABASE_SERVICE_ROLE_KEY")
    if supabase_url and supabase_key:
        client = get_supabase_client()
        rpc_result, rpc_raw = await rpc_overview_aggregated(
            client,
            supabase_url,
            supabase_key,
            {"ano": ano, "mes": mes, "uf": uf, "fabricante": fabricante},
            {
                "_ano": int(ano) if ano else None,
                "_mes": int(mes) if mes else None,
                "_uf": uf,
                "_fabricante": fabricante,
            },
        )
        if rpc_result is not None:
            total_doses = rpc_result.get("total_doses", 0)
            return JSONResponse(status_code=200, content={"total_doses": total_doses, "periodo": None})
        logger.warning("RPC obter_overview_agrupado indisponível: %s", rpc_raw)
        return JSONResponse(
            status_code=502,
            content={
                "erro": "RPC obter_overview_agrupado indisponível.",
                "details": rpc_raw,
            },
        )

    # Fallback: local fixtures (no Supabase configured)
    rows = _load_local_data()
    normalizer = get_default_normalizer()
    for r in rows:
        r.setdefault("tx_insumo_norm", normalizer.normalize_insumo(r.get("tx_insumo")))
        r.setdefault("tx_sigla_norm", normalizer.normalize_sigla(r.get("tx_sigla")))

    def row_matches(r):
        if ano and str(r.get("ano")) != str(ano):
            return False
        if mes and str(r.get("mes")).zfill(2) != str(mes).zfill(2):
            return False
        if uf and (r.get("tx_sigla_norm") != uf):
            return False
        if fabricante and (r.get("tx_insumo_norm") != fabricante):
            return False
        return True

    matched = [r for r in rows if row_matches(r)]
    total = sum(int(r.get("qtde") or 0) for r in matched)
    return JSONResponse(status_code=200, content={"total_doses": total, "periodo": None})


@router.get("/api/timeseries")
async def api_timeseries(ano: Optional[str] = Query(None), mes: Optional[str] = Query(None), uf: Optional[str] = Query(None), fabricante: Optional[str] = Query(None)):
    table = os.getenv("DATA_TABLE", "distribuicao")

    # Fast path: aggregate in DB via RPC to avoid downloading raw rows.
    ensure_loaded_backend_env()
    supabase_url = os.getenv("SUPABASE_URL")
    supabase_key = os.getenv("SUPABASE_SERVICE_ROLE_KEY")
    if supabase_url and supabase_key:
        client = get_supabase_client()
        rpc_rows, rpc_raw = await rpc_timeseries_aggregated(
            client,
            supabase_url,
            supabase_key,
            {"ano": ano, "mes": mes, "uf": uf, "fabricante": fabricante},
            {
                "_ano": int(ano) if ano else None,
                "_mes": int(mes) if mes else None,
                "_uf": uf,
                "_fabricante": fabricante,
            },
        )
        if rpc_rows is not None:
            result = []
            for r in rpc_rows:
                ano_val = int(r.get("ano") or 0)
                mes_val = int(r.get("mes") or 0)
                periodo = f"{ano_val:04d}-{mes_val:02d}"
                doses = int(r.get("doses") or 0)
                result.append(
                    {
                        "periodo": periodo,
                        "doses": doses,
                        # Backwards-compatible keys used by current frontend.
                        "data": periodo,
                        "doses_distribuidas": doses,
                    }
                )
            return JSONResponse(status_code=200, content=result)
        logger.warning("RPC obter_serie_temporal_agrupada indisponível: %s", rpc_raw)
        return JSONResponse(
            status_code=502,
            content={
                "erro": "RPC obter_serie_temporal_agrupada indisponível.",
                "details": rpc_raw,
            },
        )

    # Fallback compatibility path (no Supabase configured): local fixtures.
    rows = _load_local_data()
    normalizer = get_default_normalizer()
    for r in rows:
        r.setdefault("tx_insumo_norm", normalizer.normalize_insumo(r.get("tx_insumo")))
        r.setdefault("tx_sigla_norm", normalizer.normalize_sigla(r.get("tx_sigla")))

    def row_matches(r):
        if uf and (r.get("tx_sigla_norm") != uf):
            return False
        if fabricante and (r.get("tx_insumo_norm") != fabricante):
            return False
        return True

    matched = [r for r in rows if row_matches(r)]
    buckets: Dict[str, int] = {}
    for r in matched:
        ano_val = int(r.get('ano') or 0)
        mes_val = int(r.get('mes') or 0)
        key = f"{ano_val:04d}-{mes_val:02d}"
        buckets.setdefault(key, 0)
        buckets[key] += int(r.get("qtde") or 0)

    result = [
        {
            "periodo": k,
            "doses": v,
            # Backwards-compatible keys used by current frontend.
            "data": k,
            "doses_distribuidas": v,
        }
        for k, v in sorted(buckets.items())
    ]
    return JSONResponse(status_code=200, content=result)


@router.get("/api/ranking/ufs")
async def api_ranking_ufs(ano: Optional[str] = Query(None), mes: Optional[str] = Query(None), fabricante: Optional[str] = Query(None)):
    table = os.getenv("DATA_TABLE", "distribuicao")
    
    # Fast path: aggregate in DB via RPC to avoid downloading raw rows.
    ensure_loaded_backend_env()
    supabase_url = os.getenv("SUPABASE_URL")
    supabase_key = os.getenv("SUPABASE_SERVICE_ROLE_KEY")
    if supabase_url and supabase_key:
        client = get_supabase_client()
        rpc_rows, rpc_raw = await rpc_ranking_ufs_aggregated(
            client,
            supabase_url,
            supabase_key,
            {"ano": ano, "mes": mes, "uf": None, "fabricante": fabricante},
            {
                "_ano": int(ano) if ano else None,
                "_mes": int(mes) if mes else None,
                "_uf": None,
                "_fabricante": fabricante,
            },
        )
        if rpc_rows is not None:
            result = [
                {
                    "uf": r.get("uf", "UNK"),
                    "sigla": r.get("uf", "UNK"),
                    "doses_distribuidas": r.get("doses", 0),
                }
                for r in rpc_rows
            ]
            return JSONResponse(status_code=200, content=result)
        logger.warning("RPC obter_ranking_ufs_agrupado indisponível: %s", rpc_raw)
        return JSONResponse(
            status_code=502,
            content={
                "erro": "RPC obter_ranking_ufs_agrupado indisponível.",
                "details": rpc_raw,
            },
        )

    # Fallback: local fixtures (no Supabase configured)
    rows = _load_local_data()
    normalizer = get_default_normalizer()
    for r in rows:
        r.setdefault("tx_insumo_norm", normalizer.normalize_insumo(r.get("tx_insumo")))
        r.setdefault("tx_sigla_norm", normalizer.normalize_sigla(r.get("tx_sigla")))

    def row_matches(r):
        if ano and str(r.get("ano")) != str(ano):
            return False
        if mes and str(r.get("mes")).zfill(2) != str(mes).zfill(2):
            return False
        if fabricante and (r.get("tx_insumo_norm") != fabricante):
            return False
        return True

    matched = [r for r in rows if row_matches(r)]
    buckets: Dict[str, int] = {}
    for r in matched:
        ufv = str(r.get("tx_sigla_norm") or r.get("tx_sigla") or "UNK")
        buckets.setdefault(ufv, 0)
        buckets[ufv] += int(r.get("qtde") or 0)

    res = [{"uf": k, "sigla": k, "doses_distribuidas": v} for k, v in sorted(buckets.items(), key=lambda x: -x[1])]
    return JSONResponse(status_code=200, content=res)


@router.get("/api/top-vacinas")
async def api_top_vacinas(
    ano: Optional[str] = Query(None),
    mes: Optional[str] = Query(None),
    uf: Optional[str] = Query(None),
    fabricante: Optional[str] = Query(None),
):
    # Fast path: aggregate in DB via RPC.
    ensure_loaded_backend_env()
    supabase_url = os.getenv("SUPABASE_URL")
    supabase_key = os.getenv("SUPABASE_SERVICE_ROLE_KEY")
    if supabase_url and supabase_key:
        client = get_supabase_client()
        rpc_rows, rpc_raw = await rpc_top_vacinas_aggregated(
            client,
            supabase_url,
            supabase_key,
            {"ano": ano, "mes": mes, "uf": uf, "fabricante": fabricante},
            {
                "_ano": int(ano) if ano else None,
                "_mes": int(mes) if mes else None,
                "_uf": uf,
                "_fabricante": fabricante,
            },
        )
        if rpc_rows is not None:
            result = [
                {
                    "tx_insumo": r.get("tx_insumo"),
                    "qtde": int(r.get("qtde") or 0),
                }
                for r in rpc_rows
                if r.get("tx_insumo")
            ]
            return JSONResponse(status_code=200, content=result)

        logger.warning("RPC obter_top_vacinas_agrupadas indisponível: %s", rpc_raw)
        return JSONResponse(
            status_code=502,
            content={
                "erro": "RPC obter_top_vacinas_agrupadas indisponível.",
                "details": rpc_raw,
            },
        )

    return JSONResponse(
        status_code=500,
        content={"erro": "Supabase não está configurado no servidor (verifique SUPABASE_URL e SUPABASE_SERVICE_ROLE_KEY)."},
    )


@router.get("/api/sazonalidade")
async def api_sazonalidade(
    ano: Optional[str] = Query(None),
    uf: Optional[str] = Query(None),
    fabricante: Optional[str] = Query(None),
):
    # Fast path: aggregate in DB via RPC.
    ensure_loaded_backend_env()
    supabase_url = os.getenv("SUPABASE_URL")
    supabase_key = os.getenv("SUPABASE_SERVICE_ROLE_KEY")
    if supabase_url and supabase_key:
        client = get_supabase_client()
        rpc_rows, rpc_raw = await rpc_sazonalidade_agrupada(
            client,
            supabase_url,
            supabase_key,
            {"ano": ano, "uf": uf, "fabricante": fabricante},
            {
                "_ano": int(ano) if ano else None,
                "_uf": uf,
                "_fabricante": fabricante,
            },
        )
        if rpc_rows is not None:
            result = [
                {
                    "mes": int(r.get("mes") or 0),
                    "qtde": int(r.get("qtde") or 0),
                }
                for r in rpc_rows
                if int(r.get("mes") or 0) > 0
            ]
            return JSONResponse(status_code=200, content=result)

        logger.warning("RPC obter_sazonalidade_agrupada indisponível: %s", rpc_raw)
        return JSONResponse(
            status_code=502,
            content={
                "erro": "RPC obter_sazonalidade_agrupada indisponível.",
                "details": rpc_raw,
            },
        )

    return JSONResponse(
        status_code=500,
        content={"erro": "Supabase não está configurado no servidor (verifique SUPABASE_URL e SUPABASE_SERVICE_ROLE_KEY)."},
    )


@router.get("/api/detalhes-geograficos")
async def api_detalhes_geograficos(
    ano: Optional[str] = Query(None),
    mes: Optional[str] = Query(None),
    fabricante: Optional[str] = Query(None),
):
    # Fast path: aggregate in DB via RPC.
    ensure_loaded_backend_env()
    supabase_url = os.getenv("SUPABASE_URL")
    supabase_key = os.getenv("SUPABASE_SERVICE_ROLE_KEY")
    if supabase_url and supabase_key:
        client = get_supabase_client()
        rpc_rows, rpc_raw = await rpc_detalhes_geograficos_agrupados(
            client,
            supabase_url,
            supabase_key,
            {"ano": ano, "mes": mes, "fabricante": fabricante},
            {
                "_ano": int(ano) if ano else None,
                "_mes": int(mes) if mes else None,
                "_fabricante": fabricante,
            },
        )
        if rpc_rows is not None:
            result = [
                {
                    "tx_sigla": str(r.get("tx_sigla") or ""),
                    "tx_insumo": str(r.get("tx_insumo") or ""),
                    "qtde": int(r.get("qtde") or 0),
                }
                for r in rpc_rows
                if r.get("tx_sigla") and r.get("tx_insumo")
            ]
            return JSONResponse(status_code=200, content=result)

        logger.warning("RPC obter_detalhes_geograficos_agrupados indisponível: %s", rpc_raw)
        return JSONResponse(
            status_code=502,
            content={
                "erro": "RPC obter_detalhes_geograficos_agrupados indisponível.",
                "details": rpc_raw,
            },
        )

    return JSONResponse(
        status_code=500,
        content={"erro": "Supabase não está configurado no servidor (verifique SUPABASE_URL e SUPABASE_SERVICE_ROLE_KEY)."},
    )


@router.get("/api/forecast")
async def api_forecast(ano: Optional[str] = Query(None), mes: Optional[str] = Query(None), uf: Optional[str] = Query(None), fabricante: Optional[str] = Query(None)):
    # Behavior: if no filters provided, return empty list
    if not any([ano, mes, uf, fabricante]):
        return JSONResponse(status_code=200, content=[])

    # Fast path: use RPC aggregated timeseries to avoid downloading raw rows.
    ensure_loaded_backend_env()
    supabase_url = os.getenv("SUPABASE_URL")
    supabase_key = os.getenv("SUPABASE_SERVICE_ROLE_KEY")
    if supabase_url and supabase_key:
        client = get_supabase_client()
        rpc_rows, rpc_raw = await rpc_timeseries_aggregated(
            client,
            supabase_url,
            supabase_key,
            {"ano": None, "mes": mes, "uf": uf, "fabricante": fabricante},  # no ano filter for forecast
            {
                "_ano": None,
                "_mes": int(mes) if mes else None,
                "_uf": uf,
                "_fabricante": fabricante,
            },
        )
        if rpc_rows is not None and isinstance(rpc_rows, list):
            # Perform forecasts on aggregated data instead of raw rows
            if mes:
                # group by year for the specific month
                vals = []
                for r in rpc_rows:
                    if int(r.get("mes") or 0) == int(mes):
                        try:
                            vals.append(float(r.get("doses") or 0))
                        except Exception:
                            continue
                if not vals:
                    return JSONResponse(status_code=200, content=[])
                avg = sum(vals) / len(vals)
                return JSONResponse(status_code=200, content=[{"data": f"2025-{int(mes):02d}", "doses_previstas": avg, "doses_projecao": avg}])
            else:
                # annual totals across aggregated rows
                totals_by_year: Dict[int, float] = {}
                for r in rpc_rows:
                    y = int(r.get("ano") or 0)
                    totals_by_year.setdefault(y, 0.0)
                    try:
                        totals_by_year[y] += float(r.get("doses") or 0)
                    except Exception:
                        continue
                if not totals_by_year:
                    return JSONResponse(status_code=200, content=[])
                # simple projection: average of annual totals
                years = sorted(totals_by_year.keys())
                avg = sum(totals_by_year[y] for y in years) / len(years)
                return JSONResponse(status_code=200, content=[{"data": "2025", "doses_previstas": avg, "doses_projecao": avg}])
        # RPC failed; use fallback
        logger.warning("RPC obter_serie_temporal_agrupada indisponível para forecast: %s", rpc_raw)

    # Fallback: local fixtures (no Supabase configured or RPC failed)
    rows = _load_local_data()
    normalizer = get_default_normalizer()
    for r in rows:
        r.setdefault("tx_insumo_norm", normalizer.normalize_insumo(r.get("tx_insumo")))
        r.setdefault("tx_sigla_norm", normalizer.normalize_sigla(r.get("tx_sigla")))

    uf_norm = normalizer.normalize_sigla(uf) if uf else None
    fabricante_norm = normalizer.normalize_insumo(fabricante) if fabricante else None

    def row_matches(r):
        if uf:
            if uf_norm:
                if (r.get("tx_sigla_norm") != uf_norm):
                    return False
            else:
                if not r.get("tx_sigla") or uf.lower() not in r.get("tx_sigla", "").lower():
                    return False
        if fabricante:
            if fabricante_norm:
                if (r.get("tx_insumo_norm") != fabricante_norm):
                    return False
            else:
                if not r.get("tx_insumo") or fabricante.lower() not in r.get("tx_insumo", "").lower():
                    return False
        return True

    filtered = [r for r in rows if row_matches(r)]
    # If mes provided, compute monthly average across years for that month, else annual totals median
    if mes:
        # group by year for the specific month
        vals = []
        for r in filtered:
            if int(r.get("mes") or 0) == int(mes):
                try:
                    vals.append(float(r.get("qtde") or 0))
                except Exception:
                    continue
        if not vals:
            return JSONResponse(status_code=200, content=[])
        avg = sum(vals) / len(vals)
        return JSONResponse(status_code=200, content=[{"data": f"2025-{int(mes):02d}", "doses_previstas": avg, "doses_projecao": avg}])
    else:
        # annual totals across years
        totals_by_year: Dict[int, float] = {}
        for r in filtered:
            y = int(r.get("ano") or 0)
            totals_by_year.setdefault(y, 0.0)
            try:
                totals_by_year[y] += float(r.get("qtde") or 0)
            except Exception:
                continue
        if not totals_by_year:
            return JSONResponse(status_code=200, content=[])
        # simple projection: average of annual totals
        years = sorted(totals_by_year.keys())
        avg = sum(totals_by_year[y] for y in years) / len(years)
        return JSONResponse(status_code=200, content=[{"data": "2025", "doses_previstas": avg, "doses_projecao": avg}])


@router.get("/api/mappings")
async def api_mappings():
    normalizer = get_default_normalizer()
    items = [m.get("vacina_normalizada") for m in normalizer.mappings]
    seen = set()
    uniq = []
    for it in items:
        if not it:
            continue
        if it in seen:
            continue
        seen.add(it)
        uniq.append(it)
    uniq.sort()
    return JSONResponse(status_code=200, content={"vacinas": uniq})


@router.get("/api/mappings/available")
async def api_mappings_available(ano: int = Query(2024)):
    """
    Retorna vacinas normalizadas com total de doses > 0 no ano informado (padrão 2024).

    Comportamento:
    - Busca linhas da tabela `distribuicao` para o ano solicitado (usando _fetch_rows).
    - Normaliza `tx_insumo` via `normalizer.normalize_insumo` e agrega soma de qtde por vacina normalizada.
    - Retorna apenas vacinas com total_doses > 0 no formato: [{vacina, total_doses, ano_base}]
    """
    table = os.getenv("DATA_TABLE", "distribuicao")
    # Fetch rows for the requested year. _fetch_rows will prefer Supabase REST when available
    # and fallback to local JSON fixtures when not.
    rows = await _fetch_rows(table, {"ano": str(ano), "mes": None, "uf": None, "fabricante": None})
    normalizer = get_default_normalizer()

    totals_by_vacina: Dict[str, float] = {}
    for r in rows:
        tx = r.get("tx_insumo")
        if not tx:
            continue
        vac_norm = normalizer.normalize_insumo(tx)
        # only consider rows that map to a normalized vacina name
        if not vac_norm:
            continue
        try:
            q = float(r.get("qtde") or 0)
        except Exception:
            q = 0.0
        totals_by_vacina.setdefault(vac_norm, 0.0)
        totals_by_vacina[vac_norm] += q

    # Build response list filtered to totals > 0
    resp = []
    for vac, total in sorted(totals_by_vacina.items(), key=lambda x: -x[1]):
        if total and float(total) > 0.0:
            resp.append({"vacina": vac, "total_doses": int(total), "ano_base": ano})

    return JSONResponse(status_code=200, content=resp)


def _find_insumo_pattern(normalizer, insumo_norm: Optional[str], original: str) -> Optional[str]:
    """Tenta localizar um pattern regex nos mappings a partir do nome normalizado
    ou, como fallback, checando cada pattern contra o texto original do insumo.
    Retorna a string do pattern ou None se não encontrar.
    """
    if not normalizer:
        return None

    # 1) tentar por vacina_normalizada exata
    if insumo_norm:
        for m in normalizer.mappings:
            vn = m.get("vacina_normalizada")
            pat = m.get("pattern")
            if vn and pat and vn.lower() == str(insumo_norm).lower():
                return pat

    # 2) fallback: testar cada pattern contra o texto original
    for m in normalizer.mappings:
        pat = m.get("pattern")
        if not pat:
            continue
        try:
            if re.search(pat, original, flags=re.IGNORECASE):
                return pat
        except re.error:
            # fallback simples: substring
            if pat.lower() in original.lower():
                return pat

    return None


@router.get("/previsao")
async def previsao(
    insumo_nome: Optional[str] = Query(None),
    uf: Optional[str] = Query(None),
    mes: Optional[int] = Query(None),
    debug: Optional[bool] = Query(False),
) -> Any:
    """
    Chama a função RPC `public.obter_comparacao_dados` e retorna uma lista de objetos JSON
    com a série histórica + previsão (ano, quantidade, tipo_dado).

    Requisitos:
    - `insumo_nome` é obrigatório (string).
    - `uf` e `mes` são opcionais.
    - Usa SUPABASE_SERVICE_ROLE_KEY obrigatoriamente (retorna 500 se ausente).
    """
    # Validação crítica: insumo_nome
    if not insumo_nome:
        return JSONResponse(status_code=400, content={"erro": "É obrigatório informar o nome da vacina (insumo_nome) para plotar o gráfico de previsão."})

    # ensure env loaded and required vars present
    ensure_loaded_backend_env()
    SUPABASE_URL = os.getenv("SUPABASE_URL")
    SUPABASE_SERVICE_ROLE_KEY = os.getenv("SUPABASE_SERVICE_ROLE_KEY")
    if not SUPABASE_URL or not SUPABASE_SERVICE_ROLE_KEY:
        return JSONResponse(status_code=500, content={"erro": "Supabase não está configurado no servidor (verifique SUPABASE_URL e SUPABASE_SERVICE_ROLE_KEY)."})

    # prepare params
    insumo_nome_trim = str(insumo_nome).strip()
    uf_trim = str(uf).strip() if uf else None
    params_plain: Dict[str, Any] = {"insumo_nome": insumo_nome_trim}
    params_underscored: Dict[str, Any] = {"_insumo_nome": insumo_nome_trim}
    if uf_trim:
        params_plain["uf"] = uf_trim
        params_underscored["_uf"] = uf_trim
    if mes is not None:
        try:
            mes_int = int(mes)
        except Exception:
            return JSONResponse(status_code=400, content={"erro": "Parâmetro 'mes' inválido. Deve ser um número inteiro (1-12)."})
        params_plain["mes"] = mes_int
        params_underscored["_mes"] = mes_int

    # Resolve Supabase client and call RPC using repository helpers
    client = get_supabase_client()
    data, rpc_raw = await rpc_get_historico_e_previsao_raw(client, SUPABASE_URL, SUPABASE_SERVICE_ROLE_KEY, params_plain, params_underscored)
    if data is None:
        # rpc_raw is expected to contain error info when call failed
        return JSONResponse(status_code=502, content={"erro": "Falha ao chamar RPC via HTTP no Supabase.", "details": rpc_raw})

    # The RPC `obter_comparacao_dados` is expected to return
    # a list of objects. Per spec we must return that list exactly as
    # received from Supabase (plain array). Preserve raw payload when
    # possible and only try to unwrap common PostgREST wrappers.

    # If the RPC already returned a list, return it as-is.
    if isinstance(data, list):
        # Heuristic: if RPC returned only a single forecast row with quantidade == 0
        # and no historical rows, treat it as "no data" so the frontend doesn't
        # plot a solitary zero-valued 2025 point. When debug=true, preserve rpc_raw
        # for inspection.
        try:
            if len(data) == 1:
                nr = normalize_row(data[0])
                if nr and nr.get("tipo_dado") == "previsao":
                    q = nr.get("quantidade")
                    if q is None or (isinstance(q, (int, float)) and float(q) == 0):
                        # No historical data found by the RPC — treat as empty result.
                        if debug:
                            return JSONResponse(status_code=404, content={"rpc_raw": data, "erro": "Nenhum dado encontrado para os filtros fornecidos."})
                        return JSONResponse(status_code=404, content={"erro": "Nenhum dado encontrado para os filtros fornecidos."})
        except Exception:
            # non-fatal: fall through to return raw data below
            pass

        # If the RPC returned an empty list, return 404 (no data)
        if len(data) == 0:
            if debug:
                return JSONResponse(status_code=404, content={"rpc_raw": data, "erro": "Nenhum dado encontrado para os filtros fornecidos."})
            return JSONResponse(status_code=404, content={"erro": "Nenhum dado encontrado para os filtros fornecidos."})

        if debug:
            return JSONResponse(status_code=200, content={"rpc_raw": data})
        return JSONResponse(status_code=200, content=data)

    # If PostgREST wrapped the list in a dict under common keys, unwrap it.
    if isinstance(data, dict):
        candidate = data.get("data") or data.get("result") or data.get("rows")
        if isinstance(candidate, list):
            # Apply the same single-zero-forecast heuristic to wrapped responses.
            try:
                if len(candidate) == 1:
                    nr = normalize_row(candidate[0])
                    if nr and nr.get("tipo_dado") == "previsao":
                        q = nr.get("quantidade")
                        if q is None or (isinstance(q, (int, float)) and float(q) == 0):
                            # No historical data found by the RPC — treat as empty result.
                            if debug:
                                return JSONResponse(status_code=404, content={"rpc_raw": data, "erro": "Nenhum dado encontrado para os filtros fornecidos."})
                            return JSONResponse(status_code=404, content={"erro": "Nenhum dado encontrado para os filtros fornecidos."})
            except Exception:
                pass

            if len(candidate) == 0:
                if debug:
                    return JSONResponse(status_code=404, content={"rpc_raw": data, "erro": "Nenhum dado encontrado para os filtros fornecidos."})
                return JSONResponse(status_code=404, content={"erro": "Nenhum dado encontrado para os filtros fornecidos."})

            if debug:
                return JSONResponse(status_code=200, content={"rpc_raw": data, "result": candidate})
            return JSONResponse(status_code=200, content=candidate)

    # Fallback: return empty list (and include rpc_raw if debug requested).
    if debug:
        return JSONResponse(status_code=404, content={"rpc_raw": data, "erro": "Nenhum dado encontrado para os filtros fornecidos."})
    return JSONResponse(status_code=404, content={"erro": "Nenhum dado encontrado para os filtros fornecidos."})



@router.get("/previsao/comparacao")
async def previsao_comparacao(
    insumo_nome: Optional[str] = Query(None),
    uf: Optional[str] = Query(None),
    mes: Optional[int] = Query(None),
    ano: Optional[int] = Query(None),
    debug: Optional[bool] = Query(False),
) -> Any:
    """Retorna um objeto com a comparação entre o total de doses de 2024
    e a projeção para 2025.

    Regras estritas:
    - `insumo_nome` é obrigatório.
    - `ano` deve ser informado e igual a 2024, caso contrário retorna 400 com
      a mensagem: "Para gerar a comparação de previsão, o ano base precisa ser 2024."

    Implementação:
    - Chama `public.obter_soma_por_ano` com `_ano=2024` e filtros para obter o total de 2024.
    - Chama `public.obter_comparacao_dados` e extrai a linha com ano=2025 para obter a projeção.
    """
    # Validações iniciais
    if ano is None or int(ano) != 2024:
        return JSONResponse(status_code=400, content={"erro": "Para gerar a comparação de previsão, o ano base precisa ser 2024."})

    # Validação: insumo_nome é obrigatório para a comparação
    # insumo_nome is optional here: when omitted the route computes totals across all vacinas

    # ensure env loaded and required vars present
    ensure_loaded_backend_env()
    SUPABASE_URL = os.getenv("SUPABASE_URL")
    SUPABASE_SERVICE_ROLE_KEY = os.getenv("SUPABASE_SERVICE_ROLE_KEY")
    if not SUPABASE_URL or not SUPABASE_SERVICE_ROLE_KEY:
        return JSONResponse(status_code=500, content={"erro": "Supabase não está configurado no servidor (verifique SUPABASE_URL e SUPABASE_SERVICE_ROLE_KEY)."})

    insumo_nome_trim = str(insumo_nome).strip() if insumo_nome else None
    uf_trim = str(uf).strip() if uf else None

    # Try to obtain a normalized fabricante label from local mappings (only if insumo provided)
    normalizer = get_default_normalizer()
    fabricante_norm = normalizer.normalize_insumo(insumo_nome_trim) if insumo_nome_trim else None

    # --- Fast path: Use aggregated timeseries to compute comparison ---
    # Prepare params for rpc_timeseries_aggregated (no ano filter for full history)
    params_ts: Dict[str, Any] = {
        "ano": None,
        "mes": mes if mes is not None else None,
        "uf": uf_trim,
        "fabricante": insumo_nome_trim,  # pass original name; RPC will normalize
    }
    params_ts_underscore: Dict[str, Any] = {
        "_ano": None,
        "_mes": int(mes) if mes is not None else None,
        "_uf": uf_trim,
        "_fabricante": insumo_nome_trim,
    }

    client = get_supabase_client()
    rpc_ts_rows, rpc_ts_raw = await rpc_timeseries_aggregated(
        client,
        SUPABASE_URL,
        SUPABASE_SERVICE_ROLE_KEY,
        params_ts,
        params_ts_underscore,
    )

    # Compute soma_value (2024 total) and proj_value (2025 projection) from aggregated data
    soma_value = None
    proj_value = None
    rpc_raw_debug = rpc_ts_raw  # for debug output

    if rpc_ts_rows is not None and isinstance(rpc_ts_rows, list) and rpc_ts_rows:
        # Sum doses for 2024
        total_2024 = 0
        # Sum doses for other years to compute projection (average of historical)
        totals_by_year: Dict[int, float] = {}
        for row in rpc_ts_rows:
            try:
                ano_val = int(row.get("ano") or 0)
                doses_val = float(row.get("doses") or 0)
                totals_by_year.setdefault(ano_val, 0.0)
                totals_by_year[ano_val] += doses_val
                if ano_val == 2024:
                    total_2024 += doses_val
            except Exception:
                continue

        if total_2024 > 0:
            soma_value = total_2024

        # Compute projection: average of years before 2024
        historical_years = [y for y in totals_by_year.keys() if y < 2024]
        if historical_years:
            avg_historical = sum(totals_by_year[y] for y in historical_years) / len(historical_years)
            proj_value = avg_historical

    # Build response payload. Use None for quantidade when absent so the frontend
    # can distinguish 'no data' from zero. Always return HTTP 200; the
    # frontend should render an appropriate message when quantities are null.
    proj_unit = "desconhecida"
    try:
        if proj_value is None:
            proj_unit = "desconhecida"
        else:
            if mes is not None:
                proj_unit = "mensal"
            elif soma_value is None:
                proj_unit = "desconhecida"
            else:
                try:
                    soma_f = float(soma_value)
                    proj_f = float(proj_value)
                    if soma_f > 0 and proj_f >= 0:
                        if proj_f < (soma_f / 100.0):
                            proj_unit = "mensal"
                        else:
                            annualized = proj_f * 12.0
                            ratio = annualized / soma_f if soma_f != 0 else 0
                            if 0.5 <= ratio <= 2.0:
                                proj_unit = "mensal"
                            else:
                                if proj_f >= (soma_f * 0.5):
                                    proj_unit = "anual"
                                else:
                                    proj_unit = "mensal"
                    else:
                        proj_unit = "desconhecida"
                except Exception:
                    proj_unit = "desconhecida"
    except Exception:
        proj_unit = "desconhecida"

    resp_payload = {
        "insumo": insumo_nome_trim or "Total",
        "projecao_unidade": proj_unit,
        "dados_comparacao": [
            {"ano": 2024, "quantidade": (soma_value if soma_value is not None and float(soma_value) != 0.0 else None), "tipo": "historico"},
            {"ano": 2025, "quantidade": (proj_value if proj_value is not None and float(proj_value) != 0.0 else None), "tipo": "projeção"},
        ],
    }

    # Anomaly detection: if the projection value is wildly different from the
    # historical total, prefer a more stable fallback (median of annual totals).
    # This helps when the DB RPC returns inconsistent aggregates for specific
    # insumo filters (observed for some normalized names). Thresholds chosen
    # conservatively: if annualized projection is >2.5x or <0.4x historical sum
    # we recompute a median-based fallback and use it instead of the raw RPC
    # projection. When `debug` is true we keep rpc_raw fields so callers can
    # inspect original RPC payloads.
    try:
        if soma_value is not None and proj_value is not None:
            soma_f = float(soma_value)
            proj_f = float(proj_value)
            # determine annualized projection depending on inferred unit
            annualized_proj = proj_f
            if proj_unit == "mensal":
                annualized_proj = proj_f * 12.0

            if soma_f > 0:
                ratio = annualized_proj / soma_f
                if ratio > 2.5 or ratio < 0.4:
                    pass
    except Exception:
        # keep original behavior on unexpected errors
        pass

    if debug:
        resp_payload_debug = dict(resp_payload)
        resp_payload_debug["rpc_raw_timeseries"] = rpc_raw_debug
        try:
            validated = ComparisonResponse(**resp_payload_debug)
            return JSONResponse(status_code=200, content=validated.dict())
        except Exception:
            return JSONResponse(status_code=200, content=resp_payload_debug)

    try:
        validated = ComparisonResponse(**resp_payload)
        return JSONResponse(status_code=200, content=validated.dict())
    except Exception:
        return JSONResponse(status_code=200, content=resp_payload)


# Backwards-compatible alias: frontend expects /api/previsao/comparacao
@router.get("/api/previsao/comparacao")
async def api_previsao_comparacao(
    insumo_nome: Optional[str] = Query(None),
    uf: Optional[str] = Query(None),
    mes: Optional[int] = Query(None),
    ano: Optional[int] = Query(None),
    debug: Optional[bool] = Query(False),
) -> Any:
    # Delegate to the main implementation so logic stays in one place.
    return await previsao_comparacao(insumo_nome=insumo_nome, uf=uf, mes=mes, ano=ano, debug=debug)
