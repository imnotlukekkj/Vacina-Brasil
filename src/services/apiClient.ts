import { FilterParams, OverviewData, TimeseriesDataPoint, RankingUF, ForecastDataPoint, PrevisaoResponse } from "@/types/apiTypes";

// API Client para comunicação com backend FastAPI

// Use a variável de ambiente do Vite em produção. Em builds locais defina em .env
const BASE_API_URL = import.meta.env.VITE_API_BASE_URL || "http://localhost:8000";

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
    const url = this.buildURL("/overview", params);
    const response = await fetch(url);
    if (!response.ok) {
      throw new Error(`Erro ao buscar overview: ${response.statusText}`);
    }
    return response.json();
  }

  async getTimeseries(params?: FilterParams): Promise<TimeseriesDataPoint[]> {
    const url = this.buildURL("/timeseries", params);
    const response = await fetch(url);
    if (!response.ok) {
      throw new Error(`Erro ao buscar série temporal: ${response.statusText}`);
    }
    return response.json();
  }

  async getRankingUFs(params?: FilterParams): Promise<RankingUF[]> {
    const url = this.buildURL("/ranking/ufs", params);
    const response = await fetch(url);
    if (!response.ok) {
      throw new Error(`Erro ao buscar ranking: ${response.statusText}`);
    }
    return response.json();
  }

  async getForecast(params?: FilterParams): Promise<ForecastDataPoint[]> {
    const url = this.buildURL("/forecast", params);
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
    const url = new URL("/mappings", this.baseURL).toString();
    const response = await fetch(url);
    if (!response.ok) {
      throw new Error(`Erro ao buscar vacinas: ${response.statusText}`);
    }
    const data = await response.json();
    return data.vacinas || [];
  }
}

export const apiClient = new APIClient(BASE_API_URL);
