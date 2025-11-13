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
        if (value) url.searchParams.append(key, value);
      });
    }
    return url.toString();
  }

  async getOverview(params?: FilterParams): Promise<OverviewData> {
  const url = this.buildURL("/api/overview", params);
    const response = await fetch(url);
    if (!response.ok) {
      const txt = await response.text();
      const err: any = new Error(`Erro ao buscar overview: ${response.status} ${txt}`);
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
      if (payload.total_doses !== undefined) {
        return { total_doses: Number(payload.total_doses || 0), periodo: payload.periodo };
      }
      // common wrapper shapes: { data: { ... } } or { result: { ... } }
      if (payload.data && payload.data.total_doses !== undefined) {
        return { total_doses: Number(payload.data.total_doses || 0), periodo: payload.data.periodo };
      }
      if (payload.result && payload.result.total_doses !== undefined) {
        return { total_doses: Number(payload.result.total_doses || 0), periodo: payload.result.periodo };
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
      const err: any = new Error(`Erro ao buscar série temporal: ${response.status} ${txt}`);
      err.status = response.status;
      err.body = txt;
      throw err;
    }
    const payload = await response.json();
    // Backend returns an array of { data: string, doses_distribuidas: number }
    // Normalize common wrapper shapes defensively.
    if (Array.isArray(payload)) {
      return payload.map((p: any) => ({ data: String(p.data), doses_distribuidas: Number(p.doses_distribuidas || 0) }));
    }
    if (payload && payload.data && Array.isArray(payload.data)) {
      return payload.data.map((p: any) => ({ data: String(p.data), doses_distribuidas: Number(p.doses_distribuidas || 0) }));
    }
    if (payload && payload.result && Array.isArray(payload.result)) {
      return payload.result.map((p: any) => ({ data: String(p.data), doses_distribuidas: Number(p.doses_distribuidas || 0) }));
    }
    // fallback: empty array
    return [];
  }

  async getRankingUFs(params?: FilterParams): Promise<RankingUF[]> {
  const url = this.buildURL("/api/ranking/ufs", params);
    const response = await fetch(url);
    if (!response.ok) {
      const txt = await response.text();
      const err: any = new Error(`Erro ao buscar ranking: ${response.status} ${txt}`);
      err.status = response.status;
      err.body = txt;
      throw err;
    }
    const payload = await response.json();
    // Backend returns an array of { uf, sigla, doses_distribuidas }
    if (Array.isArray(payload)) {
      return payload.map((p: any) => ({ uf: String(p.uf), sigla: String(p.sigla), doses_distribuidas: Number(p.doses_distribuidas || 0) }));
    }
    // wrapper shapes
    if (payload && Array.isArray(payload.data)) {
      return payload.data.map((p: any) => ({ uf: String(p.uf), sigla: String(p.sigla), doses_distribuidas: Number(p.doses_distribuidas || 0) }));
    }
    if (payload && Array.isArray(payload.result)) {
      return payload.result.map((p: any) => ({ uf: String(p.uf), sigla: String(p.sigla), doses_distribuidas: Number(p.doses_distribuidas || 0) }));
    }
    return [];
  }

  async getForecast(params?: FilterParams): Promise<ForecastDataPoint[]> {
  const url = this.buildURL("/api/forecast", params);
    const response = await fetch(url);
    if (!response.ok) {
      throw new Error(`Erro ao buscar previsão: ${response.statusText}`);
    }
    return response.json();
  }

  async getPrevisao(params: { insumo_nome: string; uf?: string; mes?: number | string }): Promise<PrevisaoResponse> {
    const url = new URL("/api/previsao", this.baseURL);
    url.searchParams.append("insumo_nome", params.insumo_nome);
    if (params.uf) url.searchParams.append("uf", String(params.uf));
    if (params.mes !== undefined && params.mes !== null) url.searchParams.append("mes", String(params.mes));

    const response = await fetch(url.toString());
    if (!response.ok) {
      const txt = await response.text();
      const err: any = new Error(`Erro ao buscar /api/previsao: ${response.status} ${txt}`);
      err.status = response.status;
      err.body = txt;
      throw err;
    }
    return response.json();
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
      const err: any = new Error(`Erro ao buscar /api/previsao/comparacao: ${response.status} ${txt}`);
      err.status = response.status;
      err.body = txt;
      throw err;
    }
    return response.json();
  }

  async getVacinas(): Promise<string[]> {
  const url = new URL("/api/mappings", this.baseURL).toString();
    const response = await fetch(url);
    if (!response.ok) {
      throw new Error(`Erro ao buscar vacinas: ${response.statusText}`);
    }
    const data = await response.json();
    return data.vacinas || [];
  }
}

export const apiClient = new APIClient(BASE_API_URL);
