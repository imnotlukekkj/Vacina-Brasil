from fastapi import APIRouter, Query
from fastapi.responses import JSONResponse
from typing import Optional, Any, Dict, List
import os
import httpx
from backend.env_utils import ensure_loaded_backend_env

try:
    from supabase import create_client
except Exception:  # pragma: no cover - graceful fallback if supabase client lib not installed
    create_client = None  # type: ignore

router = APIRouter()


def _get_supabase_client():
    """Return a supabase client if the SDK is installed and env vars are set.
    Reads environment variables at call time so you can export them without restarting the server.
    This function requires SUPABASE_SERVICE_ROLE_KEY to be present: the RPC needs elevated permissions.
    """
    ensure_loaded_backend_env()
    if not create_client:
        return None
    SUPABASE_URL = os.getenv("SUPABASE_URL")
    SUPABASE_SERVICE_ROLE_KEY = os.getenv("SUPABASE_SERVICE_ROLE_KEY")
    if not SUPABASE_URL or not SUPABASE_SERVICE_ROLE_KEY:
        return None
    return create_client(SUPABASE_URL, SUPABASE_SERVICE_ROLE_KEY)


async def _http_rpc_call(rpc_url: str, headers: dict, body: dict):
    try:
        async with httpx.AsyncClient(timeout=30.0) as httpcli:
            resp = await httpcli.post(rpc_url, json=body, headers=headers)
        try:
            parsed = resp.json()
        except Exception:
            parsed = resp.text
        return resp.status_code, parsed
    except Exception as e:
        return 502, str(e)


def _normalize_row(item: Any) -> Optional[Dict[str, Any]]:
    """Normalize a single RPC row into {"ano": int, "quantidade": float, "tipo_dado": str}.
    The RPC may return objects (dicts) or tuples/lists; try multiple heuristics.
    """
    if item is None:
        return None

    # If it's already a dict with helpful keys
    if isinstance(item, dict):
        # common key names
        ano_keys = ("ano", "year", "f0", "0", "ano_val")
        qty_keys = ("quantidade", "quant", "qtde", "f1", "1", "quantidade_val")
        tipo_keys = ("tipo_dado", "tipo", "f2", "2")

        def _pick(keys):
            for k in keys:
                if k in item and item.get(k) is not None:
                    return item.get(k)
            return None

        ano = _pick(ano_keys)
        quantidade = _pick(qty_keys)
        tipo = _pick(tipo_keys)

        # If keys not found, try to infer by value order
        if ano is None or quantidade is None:
            vals = list(item.values())
            if len(vals) >= 2:
                if ano is None:
                    ano = vals[0]
                if quantidade is None and len(vals) >= 2:
                    quantidade = vals[1]
                if tipo is None and len(vals) >= 3:
                    tipo = vals[2]

    elif isinstance(item, (list, tuple)):
        if len(item) >= 2:
            ano = item[0]
            quantidade = item[1]
            tipo = item[2] if len(item) > 2 else None
        else:
            return None
    else:
        # unknown item type
        return None

    # coerce types
    try:
        ano_int = int(ano) if ano is not None else None
    except Exception:
        try:
            ano_int = int(float(ano)) # type: ignore
        except Exception:
            ano_int = None
    try:
        quantidade_num = float(quantidade) if quantidade is not None else None
    except Exception:
        quantidade_num = None
    tipo_str = str(tipo) if tipo is not None else None

    if ano_int is None and quantidade_num is None and tipo_str is None:
        return None

    return {"ano": ano_int, "quantidade": quantidade_num, "tipo_dado": tipo_str}


@router.get("/previsao")
async def previsao(
    insumo_nome: Optional[str] = Query(None),
    uf: Optional[str] = Query(None),
    mes: Optional[int] = Query(None),
    debug: Optional[bool] = Query(False),
) -> Any:
    """
    Chama a função RPC `public.obter_historico_e_previsao_vacinacao` e retorna uma lista de objetos JSON
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

    # Try SDK client first
    client = _get_supabase_client()
    data = None
    rpc_name = "obter_historico_e_previsao_vacinacao"

    if client is not None:
        try:
            resp = client.rpc(rpc_name, params_underscored).execute()
        except Exception:
            try:
                resp = client.rpc(rpc_name, params_plain).execute()
            except Exception:
                resp = None

        if resp is not None:
            # supabase-py response shapes may vary between versions
            if hasattr(resp, "data"):
                data = getattr(resp, "data")
            elif isinstance(resp, dict):
                data = resp.get("data") or resp.get("result") or resp.get("body")
            else:
                data = resp

    # If SDK not available or returned no data, use HTTP PostgREST RPC
    if data is None:
        rpc_url = f"{SUPABASE_URL.rstrip('/')}/rest/v1/rpc/{rpc_name}"
        headers = {
            "apikey": SUPABASE_SERVICE_ROLE_KEY,
            "Authorization": f"Bearer {SUPABASE_SERVICE_ROLE_KEY}",
            "Accept": "application/json",
            "Content-Type": "application/json",
        }
        # try plain then underscored
        status, parsed = await _http_rpc_call(rpc_url, headers, params_plain)
        if status in (200, 201):
            data = parsed
        else:
            # retry with underscored params
            alt = {}
            if params_plain.get("insumo_nome") is not None:
                alt["_insumo_nome"] = params_plain.get("insumo_nome")
            if params_plain.get("mes") is not None:
                alt["_mes"] = params_plain.get("mes")
            if params_plain.get("uf") is not None:
                alt["_uf"] = params_plain.get("uf")
            if alt:
                status2, parsed2 = await _http_rpc_call(rpc_url, headers, alt)
                if status2 in (200, 201):
                    data = parsed2
                else:
                    return JSONResponse(status_code=502, content={"erro": "Falha ao chamar RPC via HTTP no Supabase.", "status_code": status2, "details": parsed2})
            else:
                return JSONResponse(status_code=502, content={"erro": "Falha ao chamar RPC via HTTP no Supabase.", "status_code": status, "details": parsed})

    # The RPC `obter_historico_e_previsao_vacinacao` is expected to return
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
                nr = _normalize_row(data[0])
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
                    nr = _normalize_row(candidate[0])
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
