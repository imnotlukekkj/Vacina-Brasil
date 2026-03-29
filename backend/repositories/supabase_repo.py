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
        # Normalize incoming keys to lowercase so RPC payloads are case-insensitive.
        item_normalized = {str(k).lower(): v for k, v in item.items()}
        ano_keys = ("ano", "year", "f0", "0", "ano_val")
        qty_keys = ("quantidade", "quant", "qtde", "f1", "1", "quantidade_val")
        tipo_keys = ("tipo_dado", "tipo", "f2", "2")

        def _pick(keys):
            for k in keys:
                if k in item_normalized and item_normalized.get(k) is not None:
                    return item_normalized.get(k)
            return None

        ano = _pick(ano_keys)
        quantidade = _pick(qty_keys)
        tipo = _pick(tipo_keys)

        if ano is None or quantidade is None:
            vals = list(item_normalized.values())
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
            first_normalized = {str(k).lower(): v for k, v in first.items()}
            for key in keys:
                if key in first_normalized and first_normalized.get(key) is not None:
                    v = first_normalized.get(key)
                    val = _coerce_number_for_extract(v)
                    if val is not None:
                        return val
            try:
                v = next(iter(first_normalized.values()))
                return _coerce_number_for_extract(v)
            except Exception:
                pass
        try:
            return _coerce_number_for_extract(first)
        except Exception:
            pass
        for elem in data:
            if isinstance(elem, dict):
                elem_normalized = {str(k).lower(): v for k, v in elem.items()}
                for key in keys:
                    if key in elem_normalized and elem_normalized.get(key) is not None:
                        val = _coerce_number_for_extract(elem_normalized.get(key))
                        if val is not None:
                            return val
        return None

    if isinstance(data, dict):
        data_normalized = {str(k).lower(): v for k, v in data.items()}
        for key in keys:
            if key in data_normalized and data_normalized.get(key) is not None:
                return _coerce_number_for_extract(data_normalized.get(key))
        try:
            v = next(iter(data_normalized.values()))
            return extract_number_from_rpc_result(v)
        except Exception:
            return None

    return None


async def rpc_get_historico_e_previsao_raw(client, supabase_url: str, service_key: str, params_plain: Dict[str, Any], params_underscored: Dict[str, Any]):
    """Return (data, raw) where data is the RPC array (or wrapped) for
    the new RPC `obter_comparacao_dados`.

    Important: the RPC must always be called with the parameter `insumo_nome` (it
    may be `None`). To satisfy that requirement we ensure the plain payload
    contains the `insumo_nome` key even when its value is `None`.
    Tries SDK then HTTP fallback.
    """
    data = None
    rpc_name = "obter_comparacao_dados"

    def _strip_none_keep(d: Dict[str, Any], keep_keys: Optional[set] = None) -> Dict[str, Any]:
        keep_keys = keep_keys or set()
        out: Dict[str, Any] = {}
        for k, v in (d or {}).items():
            if v is None and k not in keep_keys:
                continue
            out[k] = v
        return out

    # Work on copies to avoid mutating caller dicts.
    params_plain_copy = dict(params_plain or {})
    params_underscored_copy = dict(params_underscored or {})

    # Ensure the plain RPC param `insumo_nome` is always present (may be None).
    if "insumo_nome" not in params_plain_copy:
        # If caller supplied an underscored variant, try to map it, else None.
        params_plain_copy["insumo_nome"] = params_underscored_copy.get("_insumo_nome") if "_insumo_nome" in params_underscored_copy else None

    # Keep underscored param as well for SDK attempts (map from plain if missing)
    if "_insumo_nome" not in params_underscored_copy:
        params_underscored_copy["_insumo_nome"] = params_plain_copy.get("insumo_nome")

    # When stripping None values, preserve the insumo key (even if None) so
    # the HTTP RPC receives the parameter name explicitly.
    underscored_payload = _strip_none_keep(params_underscored_copy, keep_keys={"_insumo_nome"})
    plain_payload = _strip_none_keep(params_plain_copy, keep_keys={"insumo_nome"})

    if client is not None:
        try:
            # Try underscored payload first (SDK sometimes expects underscored names)
            resp = client.rpc(rpc_name, underscored_payload if underscored_payload else None).execute()
        except Exception:
            try:
                resp = client.rpc(rpc_name, plain_payload if plain_payload else None).execute()
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
        status, parsed = await http_rpc_call(rpc_url, headers, plain_payload)
        if status in (200, 201):
            data = parsed
            return data, parsed
        else:
            # As a fallback try underscored payload (if it differs)
            if underscored_payload and underscored_payload != plain_payload:
                status2, parsed2 = await http_rpc_call(rpc_url, headers, underscored_payload)
                if status2 in (200, 201):
                    data = parsed2
                    return data, parsed2
                else:
                    return None, {"error": "http_rpc_failed", "status": status2, "details": parsed2}
            return None, {"error": "http_rpc_failed", "status": status, "details": parsed}

    return data, data


async def rpc_obter_soma_por_ano_value(client, supabase_url: str, service_key: str, params_plain: Dict[str, Any], params_underscored: Dict[str, Any]) -> Tuple[Optional[float], Any]:
    soma_value: Optional[float] = None
    soma_rpc_raw: Any = None
    soma_rpc = "obter_soma_por_ano"

    def _strip_none(d: Dict[str, Any]) -> Dict[str, Any]:
        return {k: v for k, v in (d or {}).items() if v is not None}

    underscored_payload = _strip_none(params_underscored)
    plain_payload = _strip_none(params_plain)

    if client is not None:
        try:
            resp = client.rpc(soma_rpc, underscored_payload if underscored_payload else None).execute()
        except Exception:
            try:
                resp = client.rpc(soma_rpc, plain_payload if plain_payload else None).execute()
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
        status, parsed = await http_rpc_call(rpc_url, headers, plain_payload)
        if status in (200, 201):
            soma_rpc_raw = parsed
            soma_value = extract_number_from_rpc_result(parsed)
        else:
            status2, parsed2 = await http_rpc_call(rpc_url, headers, underscored_payload)
            if status2 in (200, 201):
                soma_rpc_raw = parsed2
                soma_value = extract_number_from_rpc_result(parsed2)
            else:
                # RPC attempts failed. Try a PostgREST table fallback: query the data table
                # and sum qtde values matching the filters. This helps when the DB
                # doesn't expose the RPC but the table is available via PostgREST.
                try:
                    table = os.getenv("DATA_TABLE", "distribuicao")
                    table_url = f"{supabase_url.rstrip('/')}/rest/v1/{table}"
                    params = {"select": "qtde"}
                    if params_plain.get("ano"):
                        params["ano"] = f"eq.{params_plain.get('ano')}"
                    if params_plain.get("mes"):
                        params["mes"] = f"eq.{params_plain.get('mes')}"
                    if params_plain.get("uf"):
                        params["tx_sigla"] = f"ilike.*{params_plain.get('uf')}*"
                    if params_plain.get("insumo_nome"):
                        params["tx_insumo"] = f"ilike.*{params_plain.get('insumo_nome')}*"

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
                                v = row.get("qtde")
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
    previsao_rpc = "obter_comparacao_dados"

    def _strip_none_keep(d: Dict[str, Any], keep_keys: Optional[set] = None) -> Dict[str, Any]:
        keep_keys = keep_keys or set()
        out: Dict[str, Any] = {}
        for k, v in (d or {}).items():
            if v is None and k not in keep_keys:
                continue
            out[k] = v
        return out

    # Work on copies to avoid mutating caller dicts.
    params_plain_copy = dict(params_plain or {})
    params_underscored_copy = dict(params_underscored or {})

    # Ensure the plain RPC param `insumo_nome` is always present (may be None).
    if "insumo_nome" not in params_plain_copy:
        params_plain_copy["insumo_nome"] = params_underscored_copy.get("_insumo_nome") if "_insumo_nome" in params_underscored_copy else None
    if "_insumo_nome" not in params_underscored_copy:
        params_underscored_copy["_insumo_nome"] = params_plain_copy.get("insumo_nome")

    underscored_payload = _strip_none_keep(params_underscored_copy, keep_keys={"_insumo_nome"})
    plain_payload = _strip_none_keep(params_plain_copy, keep_keys={"insumo_nome"})

    if client is not None:
        try:
            resp = client.rpc(previsao_rpc, underscored_payload if underscored_payload else None).execute()
        except Exception:
            try:
                resp = client.rpc(previsao_rpc, plain_payload if plain_payload else None).execute()
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
        status, parsed = await http_rpc_call(rpc_url, headers, plain_payload)
        if status in (200, 201) and isinstance(parsed, list):
            previsao_rpc_raw = parsed
            for item in parsed:
                nr = normalize_row(item)
                if nr and nr.get("ano") == year:
                    proj_value = nr.get("quantidade")
                    break
        else:
            status2, parsed2 = await http_rpc_call(rpc_url, headers, underscored_payload)
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


async def rpc_median_projection_totals(client, supabase_url: str, service_key: str, params_plain_base: Dict[str, Any], params_underscored_base: Dict[str, Any], years=None) -> Tuple[Optional[float], Any]:
    """Compute median projection for totals by fetching annual sums for given years.

    Uses rpc_obter_soma_por_ano_value to obtain the total per year (falls back to
    table query if RPC missing). Returns (median_value, raw_list) where raw_list is
    a list of per-year rpc raw responses for debugging.
    """
    if years is None:
        years = [2020, 2021, 2022, 2023, 2024]

    values = []
    raw_list = []

    for y in years:
        # copy base params and set the target year
        pp = dict(params_plain_base or {})
        pu = dict(params_underscored_base or {})
        pp["ano"] = y
        pu["_ano"] = y

        try:
            soma_value, soma_raw = await rpc_obter_soma_por_ano_value(client, supabase_url, service_key, pp, pu)
        except Exception:
            soma_value, soma_raw = None, {"error": "exception"}

        raw_list.append({"ano": y, "raw": soma_raw})
        if soma_value is not None:
            try:
                values.append(float(soma_value))
            except Exception:
                continue

    if not values:
        return None, raw_list

    # compute median
    values.sort()
    n = len(values)
    if n % 2 == 1:
        median = values[n // 2]
    else:
        median = (values[n // 2 - 1] + values[n // 2]) / 2.0

    return median, raw_list


async def rpc_timeseries_aggregated(
    client,
    supabase_url: str,
    service_key: str,
    params_plain: Dict[str, Any],
    params_underscored: Optional[Dict[str, Any]] = None,
) -> Tuple[Optional[list], Any]:
    """Return aggregated timeseries rows already grouped in DB.

    Expected RPC signature in Supabase:
      public.obter_serie_temporal_agrupada(_ano, _mes, _uf, _fabricante)
    and rows shaped as {ano, mes, doses}.
    """
    rpc_name = "obter_serie_temporal_agrupada"

    def _strip_none(d: Dict[str, Any]) -> Dict[str, Any]:
        return {k: v for k, v in (d or {}).items() if v is not None}

    plain_payload = _strip_none(params_plain or {})
    underscored_payload = _strip_none(params_underscored or {
        "_ano": params_plain.get("ano") if params_plain else None,
        "_mes": params_plain.get("mes") if params_plain else None,
        "_uf": params_plain.get("uf") if params_plain else None,
        "_fabricante": params_plain.get("fabricante") if params_plain else None,
    })

    rows = None

    if client is not None:
        try:
            resp = client.rpc(rpc_name, underscored_payload if underscored_payload else None).execute()
        except Exception:
            try:
                resp = client.rpc(rpc_name, plain_payload if plain_payload else None).execute()
            except Exception:
                resp = None

        if resp is not None:
            if hasattr(resp, "data"):
                rows = getattr(resp, "data")
            elif isinstance(resp, dict):
                rows = resp.get("data") or resp.get("result") or resp.get("body")
            else:
                rows = resp

    if rows is None:
        rpc_url = f"{supabase_url.rstrip('/')}/rest/v1/rpc/{rpc_name}"
        headers = {
            "apikey": service_key,
            "Authorization": f"Bearer {service_key}",
            "Accept": "application/json",
            "Content-Type": "application/json",
        }

        status, parsed = await http_rpc_call(rpc_url, headers, underscored_payload)
        if status not in (200, 201):
            status2, parsed2 = await http_rpc_call(rpc_url, headers, plain_payload)
            if status2 not in (200, 201):
                return None, {"error": "rpc_failed", "status": status2, "details": parsed2}
            rows = parsed2
        else:
            rows = parsed

    if not isinstance(rows, list):
        return None, {"error": "rpc_invalid_shape", "details": rows}

    normalized = []
    for item in rows:
        if not isinstance(item, dict):
            continue
        d = {str(k).lower(): v for k, v in item.items()}
        try:
            ano_val = int(d.get("ano") or 0)
            mes_val = int(d.get("mes") or 0)
            doses_val = int(float(d.get("doses") or 0))
        except Exception:
            continue
        normalized.append({"ano": ano_val, "mes": mes_val, "doses": doses_val})

    normalized.sort(key=lambda x: (x.get("ano", 0), x.get("mes", 0)))
    return normalized, rows


async def rpc_overview_aggregated(
    client,
    supabase_url: str,
    service_key: str,
    params_plain: Dict[str, Any],
    params_underscored: Optional[Dict[str, Any]] = None,
) -> Tuple[Optional[dict], Any]:
    """Return aggregated overview (total doses) already grouped in DB.

    Expected RPC signature in Supabase:
      public.obter_overview_agrupado(_ano, _mes, _uf, _fabricante)
    and rows shaped as {total_doses}.
    """
    rpc_name = "obter_overview_agrupado"

    def _strip_none(d: Dict[str, Any]) -> Dict[str, Any]:
        return {k: v for k, v in (d or {}).items() if v is not None}

    plain_payload = _strip_none(params_plain or {})
    underscored_payload = _strip_none(params_underscored or {
        "_ano": params_plain.get("ano") if params_plain else None,
        "_mes": params_plain.get("mes") if params_plain else None,
        "_uf": params_plain.get("uf") if params_plain else None,
        "_fabricante": params_plain.get("fabricante") if params_plain else None,
    })

    rows = None

    if client is not None:
        try:
            resp = client.rpc(rpc_name, underscored_payload if underscored_payload else None).execute()
        except Exception:
            try:
                resp = client.rpc(rpc_name, plain_payload if plain_payload else None).execute()
            except Exception:
                resp = None

        if resp is not None:
            if hasattr(resp, "data"):
                rows = getattr(resp, "data")
            elif isinstance(resp, dict):
                rows = resp.get("data") or resp.get("result") or resp.get("body")
            else:
                rows = resp

    if rows is None:
        rpc_url = f"{supabase_url.rstrip('/')}/rest/v1/rpc/{rpc_name}"
        headers = {
            "apikey": service_key,
            "Authorization": f"Bearer {service_key}",
            "Accept": "application/json",
            "Content-Type": "application/json",
        }

        status, parsed = await http_rpc_call(rpc_url, headers, underscored_payload)
        if status not in (200, 201):
            status2, parsed2 = await http_rpc_call(rpc_url, headers, plain_payload)
            if status2 not in (200, 201):
                return None, {"error": "rpc_failed", "status": status2, "details": parsed2}
            rows = parsed2
        else:
            rows = parsed

    if not isinstance(rows, list):
        return None, {"error": "rpc_invalid_shape", "details": rows}

    # Extract first result or return None
    if not rows:
        return {"total_doses": 0}, rows

    item = rows[0]
    if not isinstance(item, dict):
        return None, {"error": "rpc_invalid_row", "details": rows}

    d = {str(k).lower(): v for k, v in item.items()}
    try:
        total_doses = int(d.get("total_doses") or 0)
    except Exception:
        total_doses = 0

    return {"total_doses": total_doses}, rows


async def rpc_ranking_ufs_aggregated(
    client,
    supabase_url: str,
    service_key: str,
    params_plain: Dict[str, Any],
    params_underscored: Optional[Dict[str, Any]] = None,
) -> Tuple[Optional[list], Any]:
    """Return aggregated UF ranking (doses per state) already grouped in DB.

    Expected RPC signature in Supabase:
      public.obter_ranking_ufs_agrupado(_ano, _mes, _uf, _fabricante)
    and rows shaped as {uf, doses}.
    """
    rpc_name = "obter_ranking_ufs_agrupado"

    def _strip_none(d: Dict[str, Any]) -> Dict[str, Any]:
        return {k: v for k, v in (d or {}).items() if v is not None}

    plain_payload = _strip_none(params_plain or {})
    underscored_payload = _strip_none(params_underscored or {
        "_ano": params_plain.get("ano") if params_plain else None,
        "_mes": params_plain.get("mes") if params_plain else None,
        "_uf": params_plain.get("uf") if params_plain else None,
        "_fabricante": params_plain.get("fabricante") if params_plain else None,
    })

    rows = None

    if client is not None:
        try:
            resp = client.rpc(rpc_name, underscored_payload if underscored_payload else None).execute()
        except Exception:
            try:
                resp = client.rpc(rpc_name, plain_payload if plain_payload else None).execute()
            except Exception:
                resp = None

        if resp is not None:
            if hasattr(resp, "data"):
                rows = getattr(resp, "data")
            elif isinstance(resp, dict):
                rows = resp.get("data") or resp.get("result") or resp.get("body")
            else:
                rows = resp

    if rows is None:
        rpc_url = f"{supabase_url.rstrip('/')}/rest/v1/rpc/{rpc_name}"
        headers = {
            "apikey": service_key,
            "Authorization": f"Bearer {service_key}",
            "Accept": "application/json",
            "Content-Type": "application/json",
        }

        status, parsed = await http_rpc_call(rpc_url, headers, underscored_payload)
        if status not in (200, 201):
            status2, parsed2 = await http_rpc_call(rpc_url, headers, plain_payload)
            if status2 not in (200, 201):
                return None, {"error": "rpc_failed", "status": status2, "details": parsed2}
            rows = parsed2
        else:
            rows = parsed

    if not isinstance(rows, list):
        return None, {"error": "rpc_invalid_shape", "details": rows}

    normalized = []
    for item in rows:
        if not isinstance(item, dict):
            continue
        d = {str(k).lower(): v for k, v in item.items()}
        try:
            uf_val = str(d.get("uf") or "UNK")
            doses_val = int(float(d.get("doses") or 0))
        except Exception:
            continue
        normalized.append({"uf": uf_val, "doses": doses_val})
        try:
            uf_val = str(d.get("uf") or "UNK")
            # Extract 2-letter UF code after hyphen (e.g., "SES-SP" -> "SP")
            if "-" in uf_val:
                uf_val = uf_val.split("-")[-1]
            doses_val = int(float(d.get("doses") or 0))
        except Exception:
            continue
        normalized.append({"uf": uf_val, "doses": doses_val})

    return normalized, rows


async def rpc_top_vacinas_aggregated(
    client,
    supabase_url: str,
    service_key: str,
    params_plain: Dict[str, Any],
    params_underscored: Optional[Dict[str, Any]] = None,
) -> Tuple[Optional[list], Any]:
    """Return top 5 vaccines by summed quantity.

    Expected RPC signature in Supabase:
      public.obter_top_vacinas_agrupadas(_ano, _mes, _uf, _fabricante)
    and rows shaped as {tx_insumo, qtde}.
    """
    rpc_name = "obter_top_vacinas_agrupadas"

    def _strip_none(d: Dict[str, Any]) -> Dict[str, Any]:
        return {k: v for k, v in (d or {}).items() if v is not None}

    plain_payload = _strip_none(params_plain or {})
    underscored_payload = _strip_none(params_underscored or {
        "_ano": params_plain.get("ano") if params_plain else None,
        "_mes": params_plain.get("mes") if params_plain else None,
        "_uf": params_plain.get("uf") if params_plain else None,
        "_fabricante": params_plain.get("fabricante") if params_plain else None,
    })

    rows = None

    if client is not None:
        try:
            resp = client.rpc(rpc_name, underscored_payload if underscored_payload else None).execute()
        except Exception:
            try:
                resp = client.rpc(rpc_name, plain_payload if plain_payload else None).execute()
            except Exception:
                resp = None

        if resp is not None:
            if hasattr(resp, "data"):
                rows = getattr(resp, "data")
            elif isinstance(resp, dict):
                rows = resp.get("data") or resp.get("result") or resp.get("body")
            else:
                rows = resp

    if rows is None:
        rpc_url = f"{supabase_url.rstrip('/')}/rest/v1/rpc/{rpc_name}"
        headers = {
            "apikey": service_key,
            "Authorization": f"Bearer {service_key}",
            "Accept": "application/json",
            "Content-Type": "application/json",
        }

        status, parsed = await http_rpc_call(rpc_url, headers, underscored_payload)
        if status not in (200, 201):
            status2, parsed2 = await http_rpc_call(rpc_url, headers, plain_payload)
            if status2 not in (200, 201):
                return None, {"error": "rpc_failed", "status": status2, "details": parsed2}
            rows = parsed2
        else:
            rows = parsed

    if not isinstance(rows, list):
        return None, {"error": "rpc_invalid_shape", "details": rows}

    normalized = []
    for item in rows:
        if not isinstance(item, dict):
            continue
        d = {str(k).lower(): v for k, v in item.items()}
        tx_insumo = d.get("tx_insumo") or d.get("insumo") or d.get("vacina")
        qtde = d.get("qtde") or d.get("quantidade") or d.get("doses")
        if tx_insumo is None:
            continue
        try:
            qtde_val = int(float(qtde or 0))
        except Exception:
            qtde_val = 0
        normalized.append({"tx_insumo": str(tx_insumo), "qtde": qtde_val})

    normalized.sort(key=lambda x: x.get("qtde", 0), reverse=True)
    return normalized[:5], rows


async def rpc_sazonalidade_agrupada(
    client,
    supabase_url: str,
    service_key: str,
    params_plain: Dict[str, Any],
    params_underscored: Optional[Dict[str, Any]] = None,
) -> Tuple[Optional[list], Any]:
    """Return monthly seasonality grouped by month.

    Expected RPC signature in Supabase:
      public.obter_sazonalidade_agrupada(_ano, _uf, _fabricante)
    and rows shaped as {mes, qtde}.
    """
    rpc_name = "obter_sazonalidade_agrupada"

    def _strip_none(d: Dict[str, Any]) -> Dict[str, Any]:
        return {k: v for k, v in (d or {}).items() if v is not None}

    plain_payload = _strip_none({
        "ano": (params_plain or {}).get("ano"),
        "uf": (params_plain or {}).get("uf"),
        "fabricante": (params_plain or {}).get("fabricante"),
    })
    underscored_payload = _strip_none(params_underscored or {
        "_ano": plain_payload.get("ano"),
        "_uf": plain_payload.get("uf"),
        "_fabricante": plain_payload.get("fabricante"),
    })

    rows = None

    if client is not None:
        try:
            resp = client.rpc(rpc_name, underscored_payload if underscored_payload else None).execute()
        except Exception:
            try:
                resp = client.rpc(rpc_name, plain_payload if plain_payload else None).execute()
            except Exception:
                resp = None

        if resp is not None:
            if hasattr(resp, "data"):
                rows = getattr(resp, "data")
            elif isinstance(resp, dict):
                rows = resp.get("data") or resp.get("result") or resp.get("body")
            else:
                rows = resp

    if rows is None:
        rpc_url = f"{supabase_url.rstrip('/')}/rest/v1/rpc/{rpc_name}"
        headers = {
            "apikey": service_key,
            "Authorization": f"Bearer {service_key}",
            "Accept": "application/json",
            "Content-Type": "application/json",
        }

        status, parsed = await http_rpc_call(rpc_url, headers, underscored_payload)
        if status not in (200, 201):
            status2, parsed2 = await http_rpc_call(rpc_url, headers, plain_payload)
            if status2 not in (200, 201):
                return None, {"error": "rpc_failed", "status": status2, "details": parsed2}
            rows = parsed2
        else:
            rows = parsed

    if not isinstance(rows, list):
        return None, {"error": "rpc_invalid_shape", "details": rows}

    normalized = []
    for item in rows:
        if not isinstance(item, dict):
            continue
        d = {str(k).lower(): v for k, v in item.items()}
        try:
            mes_val = int(d.get("mes") or 0)
            qtde_val = int(float(d.get("qtde") or d.get("quantidade") or d.get("doses") or 0))
        except Exception:
            continue
        if mes_val <= 0:
            continue
        normalized.append({"mes": mes_val, "qtde": qtde_val})

    normalized.sort(key=lambda x: x.get("mes", 0))
    return normalized, rows


async def rpc_detalhes_geograficos_agrupados(
    client,
    supabase_url: str,
    service_key: str,
    params_plain: Dict[str, Any],
    params_underscored: Optional[Dict[str, Any]] = None,
) -> Tuple[Optional[list], Any]:
    """Return, for each UF, the most distributed vaccine and summed quantity.

    Expected RPC signature in Supabase:
      public.obter_detalhes_geograficos_agrupados(_ano, _mes, _fabricante)
    and rows shaped as {tx_sigla, tx_insumo, qtde}.
    """
    rpc_name = "obter_detalhes_geograficos_agrupados"

    def _strip_none(d: Dict[str, Any]) -> Dict[str, Any]:
        return {k: v for k, v in (d or {}).items() if v is not None}

    plain_payload = _strip_none({
        "ano": (params_plain or {}).get("ano"),
        "mes": (params_plain or {}).get("mes"),
        "fabricante": (params_plain or {}).get("fabricante"),
    })
    underscored_payload = _strip_none(params_underscored or {
        "_ano": plain_payload.get("ano"),
        "_mes": plain_payload.get("mes"),
        "_fabricante": plain_payload.get("fabricante"),
    })

    rows = None

    if client is not None:
        try:
            resp = client.rpc(rpc_name, underscored_payload if underscored_payload else None).execute()
        except Exception:
            try:
                resp = client.rpc(rpc_name, plain_payload if plain_payload else None).execute()
            except Exception:
                resp = None

        if resp is not None:
            if hasattr(resp, "data"):
                rows = getattr(resp, "data")
            elif isinstance(resp, dict):
                rows = resp.get("data") or resp.get("result") or resp.get("body")
            else:
                rows = resp

    if rows is None:
        rpc_url = f"{supabase_url.rstrip('/')}/rest/v1/rpc/{rpc_name}"
        headers = {
            "apikey": service_key,
            "Authorization": f"Bearer {service_key}",
            "Accept": "application/json",
            "Content-Type": "application/json",
        }

        status, parsed = await http_rpc_call(rpc_url, headers, underscored_payload)
        if status not in (200, 201):
            status2, parsed2 = await http_rpc_call(rpc_url, headers, plain_payload)
            if status2 not in (200, 201):
                return None, {"error": "rpc_failed", "status": status2, "details": parsed2}
            rows = parsed2
        else:
            rows = parsed

    if not isinstance(rows, list):
        return None, {"error": "rpc_invalid_shape", "details": rows}

    normalized = []
    for item in rows:
        if not isinstance(item, dict):
            continue
        d = {str(k).lower(): v for k, v in item.items()}
        uf = d.get("tx_sigla") or d.get("uf")
        insumo = d.get("tx_insumo") or d.get("insumo") or d.get("vacina")
        if uf is None or insumo is None:
            continue
        try:
            qtde_val = int(float(d.get("qtde") or d.get("quantidade") or d.get("doses") or 0))
        except Exception:
            qtde_val = 0
        normalized.append({"tx_sigla": str(uf), "tx_insumo": str(insumo), "qtde": qtde_val})

    normalized.sort(key=lambda x: str(x.get("tx_sigla", "")))
    return normalized, rows
