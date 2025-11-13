from fastapi import FastAPI, Query
from fastapi.middleware.cors import CORSMiddleware
from dotenv import load_dotenv
from typing import Optional, List, Dict, Any
from pathlib import Path
import json
import os
import asyncio
try:
    import asyncpg
except Exception:  # pragma: no cover - optional dependency
    asyncpg = None
import httpx
from .normalizer import get_default_normalizer
from .routers.previsao_router import router as previsao_router
from .env_utils import ensure_loaded_backend_env

# load backend/.env if present (prefer the file inside the backend folder)
# force override so the reloader/worker processes pick up values from the file
load_dotenv(dotenv_path=Path(__file__).parent / ".env", override=True)
# best-effort: also copy any missing keys from backend/.env into os.environ
ensure_loaded_backend_env()

DATABASE_URL = os.getenv("DATABASE_URL")
DATA_TABLE = os.getenv("DATA_TABLE", "distribuicao")
_default_origins = "http://localhost:5173,http://127.0.0.1:5173,http://localhost:8080,http://127.0.0.1:8080,http://localhost:8081,http://127.0.0.1:8081"
CORS_ORIGINS = os.getenv("CORS_ORIGINS", _default_origins).split(",")

app = FastAPI(title="Vacina Normalizer API")
normalizer = get_default_normalizer()

# include previsao router (exposes /api/previsao)
app.include_router(previsao_router, prefix="/api")

# Async DB pool (optional)
from typing import Any
db_pool: Optional[Any] = None

# Seu dominio publico do Vercel (deve ser definido como variavel de ambiente no Render)
FRONTEND_ORIGIN = os.getenv("FRONTEND_URL", "https://vacina-data-visor.vercel.app") 

# Lista de origens permitidas
origins = [
    # Domínios de desenvolvimento (URLs literais apenas)
    "http://localhost:8080",
    "http://127.0.0.1:8000",
    "http://localhost:3000",
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    # Regex para aceitar qualquer subdomínio do vercel.app (deploys temporários)
    allow_origin_regex=r"https://.*\.vercel\.app$",
    allow_credentials=True,
    allow_methods=["GET"],
    allow_headers=["*"],
)

@app.on_event("startup")
async def startup_event():
    global db_pool
    # Ensure backend/.env is loaded at startup in case it was added after import
    # and override any existing env values so the worker process sees them.
    load_dotenv(dotenv_path=Path(__file__).parent / ".env", override=True)
    # Ensure any remaining missing keys from backend/.env are loaded into os.environ
    ensure_loaded_backend_env()

    if os.getenv("DATABASE_URL"):
        if asyncpg is None:
            print("DATABASE_URL is set but asyncpg is not installed; skipping DB pool creation")
        else:
            try:
                db_pool = await asyncpg.create_pool(os.getenv("DATABASE_URL"), min_size=1, max_size=5)
                print("Connected to database")
            except Exception as e:
                print("Failed to connect to database:", e)
    else:
        # not connected via DATABASE_URL; log Supabase REST availability
        supabase_url = os.getenv("SUPABASE_URL")
        supabase_key = os.getenv("SUPABASE_SERVICE_ROLE_KEY")
        if supabase_url and supabase_key:
            # print a short confirmation (don't reveal the key)
            print(f"Supabase REST configured (host={supabase_url.split('://')[-1]})")
        else:
            print("No DATABASE_URL or SUPABASE_* configured: using local JSON fallback")


@app.on_event("shutdown")
async def shutdown_event():
    global db_pool
    if db_pool:
        await db_pool.close()


def _load_local_data() -> List[Dict[str, Any]]:
    # prefer rerun2, then rerun; older filenames were removed to avoid confusion
    base = Path("backend")
    candidates = ["normalized_vacinas_rerun2.json", "normalized_vacinas_rerun.json"]
    for c in candidates:
        p = base / c
        if p.exists():
            with p.open("r", encoding="utf-8") as f:
                return json.load(f)
    return []


async def _fetch_rows_from_db(table: str, filters: Dict[str, Optional[str]]) -> List[Dict[str, Any]]:
    """Busca linhas do banco (postgrest) e retorna lista de dicts com colunas comuns.
    Faz seleção básica sem normalização; a normalização é aplicada em memória depois."""
    global db_pool
    if not db_pool:
        return []
    # Construir WHERE com parâmetros para reduzir volume
    clauses = []
    args = []
    if filters.get("ano"):
        val = filters.get("ano")
        if val:
            clauses.append(f"ANO = ${len(args)+1}")
            args.append(int(val))
    if filters.get("mes"):
        val = filters.get("mes")
        if val:
            clauses.append(f"MES = ${len(args)+1}")
            args.append(int(val))
    if filters.get("uf"):
        # TX_SIGLA pode ser 'SES-PR' — filtramos por ILIKE '%PR%'
        clauses.append(f"TX_SIGLA ILIKE ${len(args)+1}")
        args.append(f"%{filters.get('uf')}%")
    if filters.get("fabricante"):
        # fallback: filtrar por substring em TX_INSUMO
        clauses.append(f"TX_INSUMO ILIKE ${len(args)+1}")
        args.append(f"%{filters.get('fabricante')}%")

    query = f"SELECT TX_SIGLA, TX_INSUMO, ANO, MES, QTDE FROM {table}"
    if clauses:
        query += " WHERE " + " AND ".join(clauses)

    async with db_pool.acquire() as conn:
        rows = await conn.fetch(query, *args)
    result = []
    for r in rows:
        result.append({
            "TX_SIGLA": r.get("tx_sigla") if r.get("tx_sigla") is not None else r.get("TX_SIGLA"),
            "TX_INSUMO": r.get("tx_insumo") if r.get("tx_insumo") is not None else r.get("TX_INSUMO"),
            "ANO": r.get("ano") if r.get("ano") is not None else r.get("ANO"),
            "MES": r.get("mes") if r.get("mes") is not None else r.get("MES"),
            "QTDE": r.get("qtde") if r.get("qtde") is not None else r.get("QTDE"),
        })
    return result


async def _fetch_rows_from_supabase(table: str, filters: Dict[str, Optional[str]]) -> List[Dict[str, Any]]:
    """Busca linhas usando o endpoint PostgREST do Supabase via HTTPS.
    Requer SUPABASE_URL e SUPABASE_SERVICE_ROLE_KEY no ambiente.
    Retorna lista de dicts com colunas: TX_SIGLA, TX_INSUMO, ANO, MES, QTDE"""
    SUPABASE_URL = os.getenv("SUPABASE_URL")
    SUPABASE_SERVICE_ROLE_KEY = os.getenv("SUPABASE_SERVICE_ROLE_KEY")
    if not SUPABASE_URL or not SUPABASE_SERVICE_ROLE_KEY:
        return []

    base = SUPABASE_URL.rstrip("/")
    url = f"{base}/rest/v1/{table}"
    # montar params
    params = {}
    # selecionar colunas explicitamente
    params["select"] = "TX_SIGLA,TX_INSUMO,ANO,MES,QTDE"
    if filters.get("ano"):
        params["ANO"] = f"eq.{filters.get('ano')}"
    if filters.get("mes"):
        params["MES"] = f"eq.{filters.get('mes')}"
    if filters.get("uf"):
        # usar ilike para pegar SES-PR etc. sintaxe: TX_SIGLA=ilike.*PR*
        params["TX_SIGLA"] = f"ilike.*{filters.get('uf')}*"
    if filters.get("fabricante"):
        # filtrar por substring em TX_INSUMO
        params["TX_INSUMO"] = f"ilike.*{filters.get('fabricante')}*"

    headers = {
        "apikey": SUPABASE_SERVICE_ROLE_KEY,
        "Authorization": f"Bearer {SUPABASE_SERVICE_ROLE_KEY}",
        "Accept": "application/json",
    }

    async with httpx.AsyncClient(timeout=30.0) as client:
        resp = await client.get(url, params=params, headers=headers)
        if resp.status_code != 200:
            # log minimalmente e retornar vazio
            print(f"Supabase request failed: {resp.status_code} {resp.text}")
            return []
        data = resp.json()

    result = []
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
    """Wrapper que tenta, nesta ordem:
    1) conexão direta ao DB (asyncpg pool) se disponível
    2) Supabase PostgREST via HTTPS se configurado
    3) fallback para arquivos locais
    """
    # 1) DB pool
    if db_pool:
        return await _fetch_rows_from_db(table, filters)
    # 2) Supabase REST
    rows = await _fetch_rows_from_supabase(table, filters)
    if rows:
        return rows
    # 3) local fallback
    return _load_local_data()


@app.get("/source")
def source():
    """Return the currently available data source: 'db', 'supabase-rest' or 'local'"""
    if db_pool:
        return {"source": "db"}
    # Check environment at call time so dynamic .env loading works
    supabase_url = os.getenv("SUPABASE_URL")
    supabase_key = os.getenv("SUPABASE_SERVICE_ROLE_KEY")
    if supabase_url and supabase_key:
        return {"source": "supabase-rest"}
    return {"source": "local"}


@app.get("/normalize")
def normalize_endpoint(tx_insumo: Optional[str] = Query(None), tx_sigla: Optional[str] = Query(None)):
    return {
        "tx_insumo": tx_insumo,
        "tx_insumo_norm": normalizer.normalize_insumo(tx_insumo),
        "tx_sigla": tx_sigla,
        "tx_sigla_norm": normalizer.normalize_sigla(tx_sigla),
    }


@app.get("/mappings")
def get_mappings():
    # retorna lista de vacina_normalizada disponível nos mappings
    items = [m.get("vacina_normalizada") for m in normalizer.mappings]
    # filtrar None e duplicatas mantendo ordem
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
    return {"vacinas": uniq}


@app.get("/overview")
async def overview(ano: Optional[str] = None, mes: Optional[str] = None, uf: Optional[str] = None, fabricante: Optional[str] = None):
    rows = await _fetch_rows(DATA_TABLE, {"ano": ano, "mes": mes, "uf": uf, "fabricante": fabricante})
    # apply normalization (ensure fields exist)
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
    return {"total_doses": total, "periodo": periodo}


@app.get("/timeseries")
async def timeseries(ano: Optional[str] = None, mes: Optional[str] = None, uf: Optional[str] = None, fabricante: Optional[str] = None):
    rows = await _fetch_rows(DATA_TABLE, {"ano": ano, "mes": mes, "uf": uf, "fabricante": fabricante})
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
    # group by ANO-MES
    buckets = {}
    for r in matched:
        ano_val = int(r.get('ANO') or 0)
        mes_val = int(r.get('MES') or 0)
        key = f"{ano_val:04d}-{mes_val:02d}"
        buckets.setdefault(key, 0)
        buckets[key] += int(r.get("QTDE") or 0)

    result = [{"data": k, "doses_distribuidas": v} for k, v in sorted(buckets.items())]
    return result


@app.get("/ranking/ufs")
async def ranking_ufs(ano: Optional[str] = None, mes: Optional[str] = None, fabricante: Optional[str] = None):
    rows = await _fetch_rows(DATA_TABLE, {"ano": ano, "mes": mes, "fabricante": fabricante})
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
    buckets = {}
    for r in matched:
        uf = r.get("tx_sigla_norm") or r.get("TX_SIGLA")
        buckets.setdefault(uf, 0)
        buckets[uf] += int(r.get("QTDE") or 0)

    res = [{"uf": k, "sigla": k, "doses_distribuidas": v} for k, v in sorted(buckets.items(), key=lambda x: -x[1])]
    return res


@app.get("/forecast")
async def forecast(ano: Optional[str] = None, mes: Optional[str] = None, uf: Optional[str] = None, fabricante: Optional[str] = None):
    """
    Forecast endpoint behaviour:
    - If no filters provided (ano, mes, uf, fabricante all falsy) the frontend should prompt the user to select a filter. We return an empty list here.
    - If `mes` is provided: compute forecast for 2025 for that month based on the average value of that month across available years (e.g., 2020-2024).
    - Otherwise (ano provided or other filters): compute forecast for 2025 as the average of annual totals across available years (respecting uf/fabricante filters but ignoring ano param so we can use multiple years).
    Returns a list of points (usually a single point for 2025) with keys: data, doses_previstas, intervalo_inferior, intervalo_superior
    """
    # If no filters are provided, return empty so frontend can prompt user
    if not any([ano, mes, uf, fabricante]):
        return []

    # For month-based forecast, we only need rows for that month across years
    fetch_filters = {}
    if mes:
        fetch_filters["mes"] = mes
    if uf:
        fetch_filters["uf"] = uf
    if fabricante:
        fetch_filters["fabricante"] = fabricante

    # For ano-based (or other) forecast we want multi-year data, so do not include ano in fetch_filters
    rows = await _fetch_rows(DATA_TABLE, fetch_filters)
    # apply normalization keys (used by some filters)
    for r in rows:
        r.setdefault("tx_insumo_norm", normalizer.normalize_insumo(r.get("TX_INSUMO")))
        r.setdefault("tx_sigla_norm", normalizer.normalize_sigla(r.get("TX_SIGLA")))

    # normalize incoming filter values for robust comparison against normalized rows
    uf_norm = normalizer.normalize_sigla(uf) if uf else None
    fabricante_norm = normalizer.normalize_insumo(fabricante) if fabricante else None

    # apply matching filters that should be respected (uf and fabricante already used in fetch; ano intentionally ignored for averaging)
    def row_matches(r):
        # compare normalized UF when possible
        if uf:
            if uf_norm:
                if (r.get("tx_sigla_norm") != uf_norm):
                    return False
            else:
                # fallback: compare raw TX_SIGLA substring
                if not r.get("TX_SIGLA") or uf.lower() not in r.get("TX_SIGLA", "").lower():
                    return False

        # compare normalized fabricante when possible
        if fabricante:
            if fabricante_norm:
                if (r.get("tx_insumo_norm") != fabricante_norm):
                    return False
            else:
                # fallback: substring match on raw TX_INSUMO
                if not r.get("TX_INSUMO") or fabricante.lower() not in r.get("TX_INSUMO", "").lower():
                    return False

        return True

    matched = [r for r in rows if row_matches(r)]
    if not matched:
        return []

    # group by year
    buckets = {}
    for r in matched:
        ano_val = int(r.get('ANO') or 0)
        buckets.setdefault(ano_val, 0)
        buckets[ano_val] += int(r.get('QTDE') or 0)

    years = sorted(k for k in buckets.keys() if k > 0)
    if not years:
        return []

    vals = [buckets[y] for y in years]
    import statistics

    avg = statistics.mean(vals)
    if len(vals) > 1:
        sd = statistics.pstdev(vals)
    else:
        sd = 0

    lower = max(0, avg - sd)
    upper = avg + sd

    if mes:
        # return single point for the requested month in 2025
        m = int(mes)
        label = f"2025-{m:02d}"
    else:
        label = "2025"

    return [{
        "data": label,
        "doses_previstas": int(round(avg)),
        "intervalo_inferior": int(round(lower)),
        "intervalo_superior": int(round(upper)),
    }]
