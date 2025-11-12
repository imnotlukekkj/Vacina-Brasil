from typing import Any, Optional, Dict, Tuple
import os
import re
import httpx
from ..utils.env_utils import ensure_loaded_backend_env

try:
    from supabase import create_client
except Exception:  # pragma: no cover - optional dependency
    create_client = None  # type: ignore


def get_supabase_client():
    """Return a supabase client if SDK is installed and env vars are set.
    Reads environment variables at call time.
    """
    ensure_loaded_backend_env()
    if not create_client:
        return None
    SUPABASE_URL = os.getenv("SUPABASE_URL")
    SUPABASE_SERVICE_ROLE_KEY = os.getenv("SUPABASE_SERVICE_ROLE_KEY")
    if not SUPABASE_URL or not SUPABASE_SERVICE_ROLE_KEY:
        return None
    return create_client(SUPABASE_URL, SUPABASE_SERVICE_ROLE_KEY)


async def http_rpc_call(rpc_url: str, headers: dict, body: dict) -> Tuple[int, Any]:
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


def _coerce_number_for_extract(v: Any) -> Optional[float]:
    if v is None:
        return None
    if isinstance(v, (int, float)):
        return float(v)
    if isinstance(v, str):
        s = v.strip().replace('\u00A0', '')
        if "." in s and "," in s:
            s = s.replace('.', '').replace(',', '.')
        try:
            return float(s)
        except Exception:
            cleaned = re.sub(r"[^0-9.\-]", "", s)
            try:
                return float(cleaned) if cleaned not in ("", "-", ".") else None
            except Exception:
                return None
    try:
        return float(v)
    except Exception:
        return None


def normalize_row(item: Any) -> Optional[Dict[str, Any]]:
    """Normalize a single RPC row into {"ano": int, "quantidade": float, "tipo_dado": str}.
    Ported from router to centralize RPC normalization.
    """
    if item is None:
        return None

    if isinstance(item, dict):
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
        return None

    try:
        ano_int = int(ano) if ano is not None else None
    except Exception:
        try:
            ano_int = int(float(ano))  # type: ignore
        except Exception:
            ano_int = None

    quantidade_num = _coerce_number_for_extract(quantidade)
    tipo_str = str(tipo) if tipo is not None else None

    if ano_int is None and quantidade_num is None and tipo_str is None:
        return None

    return {"ano": ano_int, "quantidade": quantidade_num, "tipo_dado": tipo_str}


def extract_number_from_rpc_result(data: Any) -> Optional[float]:
    """Extract a numeric value from various RPC result shapes."""
    if data is None:
        return None

    if isinstance(data, (int, float)):
        return float(data)

    keys = ("sum", "soma", "quantidade", "total", "value", "qtde", "quant")

    if isinstance(data, list):
        if len(data) == 0:
            return None
        first = data[0]
        if isinstance(first, dict):
            for key in keys:
                if key in first and first.get(key) is not None:
                    v = first.get(key)
                    val = _coerce_number_for_extract(v)
                    if val is not None:
                        return val
            try:
                v = next(iter(first.values()))
                return _coerce_number_for_extract(v)
            except Exception:
                pass
        try:
            return _coerce_number_for_extract(first)
        except Exception:
            pass
        for elem in data:
            if isinstance(elem, dict):
                for key in keys:
                    if key in elem and elem.get(key) is not None:
                        val = _coerce_number_for_extract(elem.get(key))
                        if val is not None:
                            return val
        return None

    if isinstance(data, dict):
        for key in keys:
            if key in data and data.get(key) is not None:
                return _coerce_number_for_extract(data.get(key))
        try:
            v = next(iter(data.values()))
            return extract_number_from_rpc_result(v)
        except Exception:
            return None

    return None


async def rpc_get_historico_e_previsao_raw(client, supabase_url: str, service_key: str, params_plain: Dict[str, Any], params_underscored: Dict[str, Any]):
    """Return (data, raw) where data is the RPC array (or wrapped) for
    obter_historico_e_previsao_vacinacao. Tries SDK then HTTP fallback.
    """
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
            if hasattr(resp, "data"):
                data = getattr(resp, "data")
            elif isinstance(resp, dict):
                data = resp.get("data") or resp.get("result") or resp.get("body")
            else:
                data = resp

    if data is None:
        rpc_url = f"{supabase_url.rstrip('/')}/rest/v1/rpc/{rpc_name}"
        headers = {
            "apikey": service_key,
            "Authorization": f"Bearer {service_key}",
            "Accept": "application/json",
            "Content-Type": "application/json",
        }
        status, parsed = await http_rpc_call(rpc_url, headers, params_plain)
        if status in (200, 201):
            data = parsed
            return data, parsed
        else:
            alt = {}
            if params_plain.get("insumo_nome") is not None:
                alt["_insumo_nome"] = params_plain.get("insumo_nome")
            if params_plain.get("mes") is not None:
                alt["_mes"] = params_plain.get("mes")
            if params_plain.get("uf") is not None:
                alt["_uf"] = params_plain.get("uf")
            if alt:
                status2, parsed2 = await http_rpc_call(rpc_url, headers, alt)
                if status2 in (200, 201):
                    data = parsed2
                    return data, parsed2
                else:
                    return None, {"error": "http_rpc_failed", "status": status2, "details": parsed2}
            else:
                return None, {"error": "http_rpc_failed", "status": status, "details": parsed}

    return data, data


async def rpc_obter_soma_por_ano_value(client, supabase_url: str, service_key: str, params_plain: Dict[str, Any], params_underscored: Dict[str, Any]) -> Tuple[Optional[float], Any]:
    soma_value: Optional[float] = None
    soma_rpc_raw: Any = None
    soma_rpc = "obter_soma_por_ano"

    if client is not None:
        try:
            resp = client.rpc(soma_rpc, params_underscored).execute()
        except Exception:
            try:
                resp = client.rpc(soma_rpc, params_plain).execute()
            except Exception:
                resp = None

        if resp is not None:
            soma_rpc_raw = resp
            if hasattr(resp, "data"):
                soma_value = extract_number_from_rpc_result(getattr(resp, "data"))
            elif isinstance(resp, dict):
                soma_value = extract_number_from_rpc_result(resp.get("data") or resp.get("result") or resp)
            else:
                soma_value = extract_number_from_rpc_result(resp)

    if soma_value is None:
        rpc_url = f"{supabase_url.rstrip('/')}/rest/v1/rpc/{soma_rpc}"
        headers = {
            "apikey": service_key,
            "Authorization": f"Bearer {service_key}",
            "Accept": "application/json",
            "Content-Type": "application/json",
        }
        status, parsed = await http_rpc_call(rpc_url, headers, params_plain)
        if status in (200, 201):
            soma_rpc_raw = parsed
            soma_value = extract_number_from_rpc_result(parsed)
        else:
            status2, parsed2 = await http_rpc_call(rpc_url, headers, params_underscored)
            if status2 in (200, 201):
                soma_rpc_raw = parsed2
                soma_value = extract_number_from_rpc_result(parsed2)
            else:
                # RPC attempts failed. Try a PostgREST table fallback: query the data table
                # and sum QTDE values matching the filters. This helps when the DB
                # doesn't expose the RPC but the table is available via PostgREST.
                try:
                    table = os.getenv("DATA_TABLE", "distribuicao")
                    table_url = f"{supabase_url.rstrip('/')}/rest/v1/{table}"
                    params = {"select": "QTDE"}
                    if params_plain.get("ano"):
                        params["ANO"] = f"eq.{params_plain.get('ano')}"
                    if params_plain.get("mes"):
                        params["MES"] = f"eq.{params_plain.get('mes')}"
                    if params_plain.get("uf"):
                        params["TX_SIGLA"] = f"ilike.*{params_plain.get('uf')}*"
                    if params_plain.get("insumo_nome"):
                        params["TX_INSUMO"] = f"ilike.*{params_plain.get('insumo_nome')}*"

                    async with httpx.AsyncClient(timeout=30.0) as client:
                        resp = await client.get(table_url, params=params, headers={
                            "apikey": service_key,
                            "Authorization": f"Bearer {service_key}",
                            "Accept": "application/json",
                        })
                    if resp.status_code == 200:
                        parsed_rows = resp.json()
                        soma_rpc_raw = parsed_rows
                        total = 0.0
                        for row in parsed_rows:
                            try:
                                v = row.get("QTDE")
                                if v is None:
                                    continue
                                total += float(v)
                            except Exception:
                                continue
                        return total, soma_rpc_raw
                except Exception:
                    pass
                return None, {"error": "rpc_failed", "status": status2, "details": parsed2}

    return soma_value, soma_rpc_raw


async def rpc_obter_projecao_ano(client, supabase_url: str, service_key: str, params_plain: Dict[str, Any], params_underscored: Dict[str, Any], year: int = 2025) -> Tuple[Optional[float], Any]:
    proj_value: Optional[float] = None
    previsao_rpc_raw: Any = None
    previsao_rpc = "obter_historico_e_previsao_vacinacao"

    if client is not None:
        try:
            resp = client.rpc(previsao_rpc, params_underscored).execute()
        except Exception:
            try:
                resp = client.rpc(previsao_rpc, params_plain).execute()
            except Exception:
                resp = None

        if resp is not None:
            previsao_rpc_raw = resp
            if hasattr(resp, "data"):
                rpc_data = getattr(resp, "data")
            elif isinstance(resp, dict):
                rpc_data = resp.get("data") or resp.get("result") or resp
            else:
                rpc_data = resp
            if isinstance(rpc_data, list):
                for item in rpc_data:
                    nr = normalize_row(item)
                    if nr and nr.get("ano") == year:
                        proj_value = nr.get("quantidade")
                        break

    if proj_value is None:
        rpc_url = f"{supabase_url.rstrip('/')}/rest/v1/rpc/{previsao_rpc}"
        headers = {
            "apikey": service_key,
            "Authorization": f"Bearer {service_key}",
            "Accept": "application/json",
            "Content-Type": "application/json",
        }
        status, parsed = await http_rpc_call(rpc_url, headers, params_plain)
        if status in (200, 201) and isinstance(parsed, list):
            previsao_rpc_raw = parsed
            for item in parsed:
                nr = normalize_row(item)
                if nr and nr.get("ano") == year:
                    proj_value = nr.get("quantidade")
                    break
        else:
            status2, parsed2 = await http_rpc_call(rpc_url, headers, params_underscored)
            if status2 in (200, 201) and isinstance(parsed2, list):
                previsao_rpc_raw = parsed2
                for item in parsed2:
                    nr = normalize_row(item)
                    if nr and nr.get("ano") == year:
                        proj_value = nr.get("quantidade")
                        break
            else:
                if proj_value is None and (status not in (200,201) and ('status2' in locals() and status2 not in (200,201))):
                    return None, {"error": "rpc_failed", "status": status2 if 'status2' in locals() else status, "details": parsed2 if 'parsed2' in locals() else parsed}

    return proj_value, previsao_rpc_raw
