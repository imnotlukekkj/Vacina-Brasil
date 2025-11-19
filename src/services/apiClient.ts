import { FilterParams, OverviewData, TimeseriesDataPoint, RankingUF, ForecastDataPoint, PrevisaoResponse } from "@/types/apiTypes";

// API Client para comunicação com backend FastAPI

// Use a variável de ambiente do Vite em produção. Em ambientes de build (ex: Vercel/Render)
// a URL da API deve ser fornecida por `VITE_API_BASE_URL`. Não utilizar fallback para
// localhost em produção: isso causava NetworkError em deploys que não expõem o backend.
const BASE_API_URL = import.meta.env.VITE_API_BASE_URL;

if (!BASE_API_URL) {
  // Fail fast with a clear message to catch misconfigured deploys early
  throw new Error("VITE_API_BASE_URL não configurada no ambiente!");
}

class APIClient {
  private baseURL: string;

  constructor(baseURL: string) {
    this.baseURL = baseURL;
  }

  private buildURL(endpoint: string, params?: FilterParams): string {
    const url = new URL(endpoint, this.baseURL);
    if (params) {
      Object.entries(params).forEach(([key, value]) => {
        if (value !== undefined && value !== null && String(value).length > 0) url.searchParams.append(key, String(value));
      });
    }
    return url.toString();
  }

  async getOverview(params?: FilterParams): Promise<OverviewData> {
  const url = this.buildURL("/api/overview", params);
    const response = await fetch(url);
    if (!response.ok) {
      const txt = await response.text();
      const err = new Error(`Erro ao buscar overview: ${response.status} ${txt}`) as Error & { status?: number; body?: unknown };
      err.status = response.status;
      err.body = txt;
      throw err;
    }
    const payload = await response.json();
    // Backend returns { total_doses: number, periodo: string|null }
    // but some proxies or wrappers may nest the payload; normalize defensively.
    if (payload && typeof payload === "object") {
      if (Array.isArray(payload)) {
        // unexpected array -> return empty overview
        return { total_doses: 0, periodo: undefined };
      }
      const obj = payload as Record<string, unknown>;
      if (obj["total_doses"] !== undefined) {
        return { total_doses: Number(obj["total_doses"] ?? 0), periodo: obj["periodo"] as string | undefined };
      }
      // common wrapper shapes: { data: { ... } } or { result: { ... } }
      if (obj["data"] && typeof obj["data"] === "object") {
        const inner = obj["data"] as Record<string, unknown>;
        if (inner["total_doses"] !== undefined) return { total_doses: Number(inner["total_doses"] ?? 0), periodo: inner["periodo"] as string | undefined };
      }
      if (obj["result"] && typeof obj["result"] === "object") {
        const inner = obj["result"] as Record<string, unknown>;
        if (inner["total_doses"] !== undefined) return { total_doses: Number(inner["total_doses"] ?? 0), periodo: inner["periodo"] as string | undefined };
      }
    }
    // fallback: empty overview
    return { total_doses: 0, periodo: undefined };
  }

  async getTimeseries(params?: FilterParams): Promise<TimeseriesDataPoint[]> {
  const url = this.buildURL("/api/timeseries", params);
    const response = await fetch(url);
    if (!response.ok) {
      const txt = await response.text();
      const err = new Error(`Erro ao buscar série temporal: ${response.status} ${txt}`) as Error & { status?: number; body?: unknown };
      err.status = response.status;
      err.body = txt;
      throw err;
    }
    const payload = await response.json();
    // Backend returns an array of { data: string, doses_distribuidas: number }
    // Normalize common wrapper shapes defensively.
    if (Array.isArray(payload)) {
      return payload.map((p: unknown) => {
        const obj = p as Record<string, unknown>;
        return { data: String(obj["data"] ?? ""), doses_distribuidas: Number(obj["doses_distribuidas"] ?? 0) } as TimeseriesDataPoint;
      });
    }
    if (payload && typeof payload === "object") {
      const obj = payload as Record<string, unknown>;
      if (Array.isArray(obj["data"])) {
        return (obj["data"] as Array<unknown>).map((p) => {
          const item = p as Record<string, unknown>;
          return { data: String(item["data"] ?? ""), doses_distribuidas: Number(item["doses_distribuidas"] ?? 0) } as TimeseriesDataPoint;
        });
      }
      if (Array.isArray(obj["result"])) {
        return (obj["result"] as Array<unknown>).map((p) => {
          const item = p as Record<string, unknown>;
          return { data: String(item["data"] ?? ""), doses_distribuidas: Number(item["doses_distribuidas"] ?? 0) } as TimeseriesDataPoint;
        });
      }
    }
    // fallback: empty array
    return [];
  }

  async getRankingUFs(params?: FilterParams): Promise<RankingUF[]> {
  const url = this.buildURL("/api/ranking/ufs", params);
    const response = await fetch(url);
    if (!response.ok) {
      const txt = await response.text();
      const err = new Error(`Erro ao buscar ranking: ${response.status} ${txt}`) as Error & { status?: number; body?: unknown };
      err.status = response.status;
      err.body = txt;
      throw err;
    }
    const payload = await response.json();
    // Backend returns an array of { uf, sigla, doses_distribuidas }
    if (Array.isArray(payload)) {
      return payload.map((p: unknown) => {
        const obj = p as Record<string, unknown>;
        return { uf: String(obj["uf"] ?? ""), sigla: String(obj["sigla"] ?? ""), doses_distribuidas: Number(obj["doses_distribuidas"] ?? 0) } as RankingUF;
      });
    }
    // wrapper shapes
    if (payload && typeof payload === "object") {
      const obj = payload as Record<string, unknown>;
      if (Array.isArray(obj["data"])) {
        return (obj["data"] as Array<unknown>).map((p) => {
          const it = p as Record<string, unknown>;
          return { uf: String(it["uf"] ?? ""), sigla: String(it["sigla"] ?? ""), doses_distribuidas: Number(it["doses_distribuidas"] ?? 0) } as RankingUF;
        });
      }
      if (Array.isArray(obj["result"])) {
        return (obj["result"] as Array<unknown>).map((p) => {
          const it = p as Record<string, unknown>;
          return { uf: String(it["uf"] ?? ""), sigla: String(it["sigla"] ?? ""), doses_distribuidas: Number(it["doses_distribuidas"] ?? 0) } as RankingUF;
        });
      }
    }
    return [];
  }

  async getForecast(params?: FilterParams): Promise<ForecastDataPoint[]> {
  const url = this.buildURL("/api/forecast", params);
    const response = await fetch(url);
    if (!response.ok) {
      throw new Error(`Erro ao buscar previsão: ${response.statusText}`);
    }
    return response.json() as Promise<ForecastDataPoint[]>;
  }

  async getPrevisao(params: { insumo_nome: string; uf?: string; mes?: number | string }): Promise<PrevisaoResponse> {
    const url = new URL("/api/previsao", this.baseURL);
    url.searchParams.append("insumo_nome", params.insumo_nome);
    if (params.uf) url.searchParams.append("uf", String(params.uf));
    if (params.mes !== undefined && params.mes !== null) url.searchParams.append("mes", String(params.mes));

    const response = await fetch(url.toString());
    if (!response.ok) {
      const txt = await response.text();
      const err = new Error(`Erro ao buscar /api/previsao: ${response.status} ${txt}`) as Error & { status?: number; body?: unknown };
      err.status = response.status;
      err.body = txt;
      throw err;
    }
    return response.json() as Promise<PrevisaoResponse>;
  }

  async getComparacao(params: { insumo_nome?: string; ano?: number | string; uf?: string; mes?: number | string }) {
    const url = new URL("/api/previsao/comparacao", this.baseURL);
    if (params.insumo_nome !== undefined && params.insumo_nome !== null && String(params.insumo_nome).trim() !== "") {
      url.searchParams.append("insumo_nome", String(params.insumo_nome).trim());
    }
    if (params.ano !== undefined && params.ano !== null) url.searchParams.append("ano", String(params.ano));
    if (params.uf) url.searchParams.append("uf", String(params.uf));
    if (params.mes !== undefined && params.mes !== null) url.searchParams.append("mes", String(params.mes));

    const response = await fetch(url.toString());
    if (!response.ok) {
      const txt = await response.text();
      const err = new Error(`Erro ao buscar /api/previsao/comparacao: ${response.status} ${txt}`) as Error & { status?: number; body?: unknown };
      err.status = response.status;
      err.body = txt;
      throw err;
    }
    return response.json() as Promise<unknown>;
  }

  // Retorna lista de vacinas disponíveis com total de doses, com shape
  // [{ vacina: string, total_doses: number, ano_base?: number }, ...]
  async getVacinas(): Promise<Array<{ vacina: string; total_doses: number }>> {
    const url = new URL("/api/mappings/available", this.baseURL).toString();
    const response = await fetch(url);
    if (!response.ok) {
      throw new Error(`Erro ao buscar vacinas: ${response.statusText}`);
    }
    const payload = await response.json();
    // Expecting an array of objects. Handle common wrapper shapes defensively.
    let items: Array<unknown> = [];
    if (Array.isArray(payload)) items = payload as Array<unknown>;
    else if (payload && Array.isArray((payload as Record<string, unknown>)["data"])) items = (payload as Record<string, unknown>)["data"] as Array<unknown>;
    else if (payload && Array.isArray((payload as Record<string, unknown>)["result"])) items = (payload as Record<string, unknown>)["result"] as Array<unknown>;

    return items.map((p) => {
      const obj = p as Record<string, unknown>;
      return { vacina: String(obj["vacina"] ?? obj["nome"] ?? ""), total_doses: Number(obj["total_doses"] ?? obj["qtde"] ?? 0) };
    });
  }
}

export const apiClient = new APIClient(BASE_API_URL);
