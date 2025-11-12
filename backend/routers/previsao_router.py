from fastapi import APIRouter, Query
from fastapi.responses import JSONResponse
from fastapi import HTTPException
from typing import Optional, Any, Dict, List
import os
import re
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
)
from ..schemas.previsao_schemas import ComparisonResponse

router = APIRouter()


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

    # Resolve Supabase client and call RPC using repository helpers
    client = get_supabase_client()
    data, rpc_raw = await rpc_get_historico_e_previsao_raw(client, SUPABASE_URL, SUPABASE_SERVICE_ROLE_KEY, params_plain, params_underscored)
    if data is None:
        # rpc_raw is expected to contain error info when call failed
        return JSONResponse(status_code=502, content={"erro": "Falha ao chamar RPC via HTTP no Supabase.", "details": rpc_raw})

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
    - Chama `public.obter_historico_e_previsao_vacinacao` e extrai a linha com ano=2025 para obter a projeção.
    """
    # Validações iniciais
    if ano is None or int(ano) != 2024:
        return JSONResponse(status_code=400, content={"erro": "Para gerar a comparação de previsão, o ano base precisa ser 2024."})

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

    # Prepare params for obter_historico_e_previsao_vacinacao
    params_plain_prev: Dict[str, Any] = {}
    params_underscored_prev: Dict[str, Any] = {}
    if insumo_nome_trim:
        params_plain_prev["insumo_nome"] = insumo_nome_trim
        params_underscored_prev["_insumo_nome"] = insumo_pattern or (fabricante_norm or insumo_nome_trim)
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
    proj_value, previsao_rpc_raw = await rpc_obter_projecao_ano(client, SUPABASE_URL, SUPABASE_SERVICE_ROLE_KEY, params_plain_prev, params_underscored_prev, year=2025)
    if isinstance(previsao_rpc_raw, dict) and previsao_rpc_raw.get("error") == "rpc_failed":
        return JSONResponse(status_code=502, content={"erro": "Falha ao chamar RPC obter_historico_e_previsao_vacinacao no Supabase.", "details": previsao_rpc_raw})

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
