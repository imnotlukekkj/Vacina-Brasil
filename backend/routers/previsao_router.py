from fastapi import APIRouter, Query
from fastapi.responses import JSONResponse
from fastapi import HTTPException
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
    http_rpc_call,
    normalize_row,
    extract_number_from_rpc_result,
    rpc_get_historico_e_previsao_raw,
    rpc_obter_soma_por_ano_value,
    rpc_obter_projecao_ano,
    rpc_median_projection_totals,
)
from ..schemas.previsao_schemas import ComparisonResponse

router = APIRouter()


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
    params["select"] = "TX_SIGLA,TX_INSUMO,ANO,MES,QTDE"
    if filters.get("ano"):
        params["ANO"] = f"eq.{filters.get('ano')}"
    if filters.get("mes"):
        params["MES"] = f"eq.{filters.get('mes')}"
    if filters.get("uf"):
        params["TX_SIGLA"] = f"ilike.*{filters.get('uf')}*"
    if filters.get("fabricante"):
        params["TX_INSUMO"] = f"ilike.*{filters.get('fabricante')}*"

    headers = {
        "apikey": SUPABASE_SERVICE_ROLE_KEY,
        "Authorization": f"Bearer {SUPABASE_SERVICE_ROLE_KEY}",
        "Accept": "application/json",
    }

    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            resp = await client.get(url, params=params, headers=headers)
        if resp.status_code != 200:
            print(f"Supabase request failed: {resp.status_code} {resp.text}")
            return []
        data = resp.json()
    except Exception:
        return []

    result: List[Dict[str, Any]] = []
    for r in data:
        result.append({
            "TX_SIGLA": r.get("TX_SIGLA"),
            "TX_INSUMO": r.get("TX_INSUMO"),
            "ANO": r.get("ANO"),
            "MES": r.get("MES"),
            "QTDE": r.get("QTDE"),
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
    # When frontend sends a normalized fabricante name (e.g. 'Covid-19') the raw
    # TX_INSUMO values in the DB may not contain that exact substring (they
    # might contain 'SARS-COV2 - ...' or manufacturer names). To avoid missing
    # results at the DB layer we fetch rows without the raw TX_INSUMO filter and
    # apply normalization-based filtering in Python below.
    db_filters: Dict[str, Optional[str]] = {"ano": ano, "mes": mes, "uf": uf, "fabricante": None}
    rows = await _fetch_rows(table, db_filters)
    normalizer = get_default_normalizer()
    for r in rows:
        r.setdefault("tx_insumo_norm", normalizer.normalize_insumo(r.get("TX_INSUMO")))
        r.setdefault("tx_sigla_norm", normalizer.normalize_sigla(r.get("TX_SIGLA")))

    def row_matches(r):
        if ano and str(r.get("ANO")) != str(ano):
            return False
        if mes and str(r.get("MES")).zfill(2) != str(mes).zfill(2):
            return False
        if uf and (r.get("tx_sigla_norm") != uf):
            return False
        if fabricante and (r.get("tx_insumo_norm") != fabricante):
            return False
        return True

    matched = [r for r in rows if row_matches(r)]
    total = sum(int(r.get("QTDE") or 0) for r in matched)
    periodo = None
    return JSONResponse(status_code=200, content={"total_doses": total, "periodo": periodo})


@router.get("/api/timeseries")
async def api_timeseries(ano: Optional[str] = Query(None), mes: Optional[str] = Query(None), uf: Optional[str] = Query(None), fabricante: Optional[str] = Query(None)):
    table = os.getenv("DATA_TABLE", "distribuicao")
    # See comment above in api_overview: avoid passing fabricante to DB filters
    # so normalization can be applied reliably in Python.
    table = os.getenv("DATA_TABLE", "distribuicao")
    rows = await _fetch_rows(table, {"ano": ano, "mes": mes, "uf": uf, "fabricante": None})
    normalizer = get_default_normalizer()
    for r in rows:
        r.setdefault("tx_insumo_norm", normalizer.normalize_insumo(r.get("TX_INSUMO")))
        r.setdefault("tx_sigla_norm", normalizer.normalize_sigla(r.get("TX_SIGLA")))

    def row_matches(r):
        if uf and (r.get("tx_sigla_norm") != uf):
            return False
        if fabricante and (r.get("tx_insumo_norm") != fabricante):
            return False
        return True

    matched = [r for r in rows if row_matches(r)]
    buckets: Dict[str, int] = {}
    for r in matched:
        ano_val = int(r.get('ANO') or 0)
        mes_val = int(r.get('MES') or 0)
        key = f"{ano_val:04d}-{mes_val:02d}"
        buckets.setdefault(key, 0)
        buckets[key] += int(r.get("QTDE") or 0)

    result = [{"data": k, "doses_distribuidas": v} for k, v in sorted(buckets.items())]
    return JSONResponse(status_code=200, content=result)


@router.get("/api/ranking/ufs")
async def api_ranking_ufs(ano: Optional[str] = Query(None), mes: Optional[str] = Query(None), fabricante: Optional[str] = Query(None)):
    table = os.getenv("DATA_TABLE", "distribuicao")
    # Avoid pre-filtering by TX_INSUMO at the DB level; normalize then filter
    # in-memory to catch pattern-based matches (e.g. SARS-COV2 -> Covid-19)
    table = os.getenv("DATA_TABLE", "distribuicao")
    rows = await _fetch_rows(table, {"ano": ano, "mes": mes, "fabricante": None})
    normalizer = get_default_normalizer()
    for r in rows:
        r.setdefault("tx_insumo_norm", normalizer.normalize_insumo(r.get("TX_INSUMO")))
        r.setdefault("tx_sigla_norm", normalizer.normalize_sigla(r.get("TX_SIGLA")))

    def row_matches(r):
        if ano and str(r.get("ANO")) != str(ano):
            return False
        if mes and str(r.get("MES")).zfill(2) != str(mes).zfill(2):
            return False
        if fabricante and (r.get("tx_insumo_norm") != fabricante):
            return False
        return True

    matched = [r for r in rows if row_matches(r)]
    buckets: Dict[str, int] = {}
    for r in matched:
        ufv = str(r.get("tx_sigla_norm") or r.get("TX_SIGLA") or "UNK")
        buckets.setdefault(ufv, 0)
        buckets[ufv] += int(r.get("QTDE") or 0)

    res = [{"uf": k, "sigla": k, "doses_distribuidas": v} for k, v in sorted(buckets.items(), key=lambda x: -x[1])]
    return JSONResponse(status_code=200, content=res)


@router.get("/api/forecast")
async def api_forecast(ano: Optional[str] = Query(None), mes: Optional[str] = Query(None), uf: Optional[str] = Query(None), fabricante: Optional[str] = Query(None)):
    # Behavior: if no filters provided, return empty list
    if not any([ano, mes, uf, fabricante]):
        return JSONResponse(status_code=200, content=[])

    fetch_filters = {}
    if mes:
        fetch_filters["mes"] = mes
    if uf:
        fetch_filters["uf"] = uf
    if fabricante:
        fetch_filters["fabricante"] = fabricante

    # For ano-based forecast we want multi-year data, so do not include ano in fetch
    # Avoid filtering by fabricante/insumo at DB call; normalization-based
    # filtering will be applied below to support pattern matches.
    rows = await _fetch_rows(os.getenv("DATA_TABLE", "distribuicao"), {k: v for k, v in fetch_filters.items() if k != "fabricante"})
    normalizer = get_default_normalizer()
    for r in rows:
        r.setdefault("tx_insumo_norm", normalizer.normalize_insumo(r.get("TX_INSUMO")))
        r.setdefault("tx_sigla_norm", normalizer.normalize_sigla(r.get("TX_SIGLA")))

    uf_norm = normalizer.normalize_sigla(uf) if uf else None
    fabricante_norm = normalizer.normalize_insumo(fabricante) if fabricante else None

    def row_matches(r):
        if uf:
            if uf_norm:
                if (r.get("tx_sigla_norm") != uf_norm):
                    return False
            else:
                if not r.get("TX_SIGLA") or uf.lower() not in r.get("TX_SIGLA", "").lower():
                    return False
        if fabricante:
            if fabricante_norm:
                if (r.get("tx_insumo_norm") != fabricante_norm):
                    return False
            else:
                if not r.get("TX_INSUMO") or fabricante.lower() not in r.get("TX_INSUMO", "").lower():
                    return False
        return True

    filtered = [r for r in rows if row_matches(r)]
    # If mes provided, compute monthly average across years for that month, else annual totals median
    if mes:
        # group by year for the specific month
        vals = []
        for r in filtered:
            if int(r.get("MES") or 0) == int(mes):
                try:
                    vals.append(float(r.get("QTDE") or 0))
                except Exception:
                    continue
        if not vals:
            return JSONResponse(status_code=200, content=[])
        avg = sum(vals) / len(vals)
        return JSONResponse(status_code=200, content=[{"data": f"2025-{int(mes):02d}", "doses_previstas": avg}])
    else:
        # annual totals across years
        totals_by_year: Dict[int, float] = {}
        for r in filtered:
            y = int(r.get("ANO") or 0)
            totals_by_year.setdefault(y, 0.0)
            try:
                totals_by_year[y] += float(r.get("QTDE") or 0)
            except Exception:
                continue
        if not totals_by_year:
            return JSONResponse(status_code=200, content=[])
        # simple projection: average of annual totals
        years = sorted(totals_by_year.keys())
        avg = sum(totals_by_year[y] for y in years) / len(years)
        return JSONResponse(status_code=200, content=[{"data": "2025", "doses_previstas": avg}])


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

    # Prepare params for obter_soma_por_ano: per spec pass _ano=2024
    soma_rpc = "obter_soma_por_ano"
    params_plain_soma: Dict[str, Any] = {"ano": 2024}
    params_underscored_soma: Dict[str, Any] = {"_ano": 2024}
    if insumo_nome_trim:
        params_plain_soma["insumo_nome"] = insumo_nome_trim
        insumo_pattern = _find_insumo_pattern(normalizer, fabricante_norm, insumo_nome_trim)
        params_underscored_soma["_insumo_nome"] = insumo_pattern or (fabricante_norm or insumo_nome_trim)
    if uf_trim:
        params_plain_soma["uf"] = uf_trim
        params_underscored_soma["_uf"] = uf_trim
    if mes is not None:
        try:
            mes_int = int(mes)
        except Exception:
            return JSONResponse(status_code=400, content={"erro": "Parâmetro 'mes' inválido. Deve ser um número inteiro (1-12)."})
        params_plain_soma["mes"] = mes_int
        params_underscored_soma["_mes"] = mes_int

    # Prepare params for obter_comparacao_dados. Per new RPC contract we must
    # always include the plain parameter `insumo_nome` (it may be None).
    params_plain_prev: Dict[str, Any] = {}
    params_underscored_prev: Dict[str, Any] = {}
    # Determine the value to send for insumo: prefer pattern (if found), then
    # fabricante_norm, then the original trimmed input; if no insumo provided,
    # explicitly set to None so the RPC receives the parameter name.
    if insumo_nome_trim:
        insumo_to_send = insumo_pattern or (fabricante_norm or insumo_nome_trim)
    else:
        insumo_to_send = None
    params_plain_prev["insumo_nome"] = insumo_to_send
    params_underscored_prev["_insumo_nome"] = insumo_to_send
    if uf_trim:
        params_plain_prev["uf"] = uf_trim
        params_underscored_prev["_uf"] = uf_trim
    if mes is not None:
        params_plain_prev["mes"] = mes_int
        params_underscored_prev["_mes"] = mes_int

    client = get_supabase_client()

    # raw rpc payloads (for debugging when requested)
    soma_rpc_raw: Any = None
    previsao_rpc_raw: Any = None

    # --- Call 1: obter_soma_por_ano (historico 2024)
    soma_value, soma_rpc_raw = await rpc_obter_soma_por_ano_value(client, SUPABASE_URL, SUPABASE_SERVICE_ROLE_KEY, params_plain_soma, params_underscored_soma)
    if isinstance(soma_rpc_raw, dict) and soma_rpc_raw.get("error") == "rpc_failed":
        return JSONResponse(status_code=502, content={"erro": "Falha ao chamar RPC obter_soma_por_ano no Supabase.", "details": soma_rpc_raw})

    # --- Call 2: obter_historico_e_previsao_vacinacao (extrair 2025)
    # If no insumo was provided, the DB RPC may not have a signature that
    # accepts a 'TOTAL' sentinel. In that case avoid calling the RPC for
    # projection and rely on the soma (historical total) only. This prevents
    # returning 502 errors when the DB function does not support totalization.
    proj_value = None
    previsao_rpc_raw = []
    if insumo_nome_trim:
        proj_value, previsao_rpc_raw = await rpc_obter_projecao_ano(client, SUPABASE_URL, SUPABASE_SERVICE_ROLE_KEY, params_plain_prev, params_underscored_prev, year=2025)
        if isinstance(previsao_rpc_raw, dict) and previsao_rpc_raw.get("error") == "rpc_failed":
            # Treat RPC failure for projection as non-fatal when comparing totals;
            # set proj_value to None and continue so the response returns the
            # historical soma and a null projection rather than HTTP 502.
            proj_value = None
            previsao_rpc_raw = []

    # If totals mode (no insumo) and projection RPC didn't return a value,
    # compute a stable fallback using the median of annual totals (2020-2024).
    if proj_value is None and not insumo_nome_trim:
        try:
            med_val, med_raw = await rpc_median_projection_totals(client, SUPABASE_URL, SUPABASE_SERVICE_ROLE_KEY, params_plain_soma, params_underscored_soma)
            if med_val is not None:
                proj_value = med_val
                previsao_rpc_raw = med_raw or []
        except Exception:
            # non-fatal: leave proj_value as None
            pass

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
                    try:
                        # Prefer a recent-years average as a conservative fallback (e.g. mean of 2022-2024)
                        recent_years = [2022, 2023, 2024]
                        recent_vals = []
                        recent_raw = []
                        for y in recent_years:
                            try:
                                sv, sraw = await rpc_obter_soma_por_ano_value(client, SUPABASE_URL, SUPABASE_SERVICE_ROLE_KEY, {**params_plain_soma, "ano": y}, {**params_underscored_soma, "_ano": y})
                            except Exception:
                                sv, sraw = None, None
                            recent_raw.append({"ano": y, "raw": sraw})
                            if sv is not None:
                                try:
                                    recent_vals.append(float(sv))
                                except Exception:
                                    continue

                        if recent_vals:
                            avg_recent = sum(recent_vals) / len(recent_vals)
                            proj_value = avg_recent
                            proj_unit = "anual"
                            resp_payload["dados_comparacao"][1]["quantidade"] = proj_value
                            resp_payload["projecao_unidade"] = proj_unit
                            if debug:
                                resp_payload.setdefault("rpc_raw_fallback", recent_raw)
                        else:
                            # fallback to median if recent average not available
                            med_val, med_raw = await rpc_median_projection_totals(client, SUPABASE_URL, SUPABASE_SERVICE_ROLE_KEY, params_plain_soma, params_underscored_soma)
                            if med_val is not None:
                                proj_value = med_val
                                proj_unit = "anual"
                                resp_payload["dados_comparacao"][1]["quantidade"] = proj_value
                                resp_payload["projecao_unidade"] = proj_unit
                                if debug:
                                    resp_payload.setdefault("rpc_raw_fallback", med_raw)
                    except Exception:
                        # non-fatal: keep original proj_value
                        pass
    except Exception:
        # keep original behavior on unexpected errors
        pass

    if debug:
        resp_payload_debug = dict(resp_payload)
        resp_payload_debug["rpc_raw_soma"] = soma_rpc_raw
        resp_payload_debug["rpc_raw_previsao"] = previsao_rpc_raw
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
