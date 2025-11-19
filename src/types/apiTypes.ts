// Shared TypeScript types for API data

export interface OverviewData {
  total_doses: number;
  periodo?: string;
}

export interface TimeseriesDataPoint {
  data: string;
  doses_distribuidas: number;
}

export interface RankingUF {
  uf: string;
  sigla: string;
  doses_distribuidas: number;
}

export interface ForecastDataPoint {
  data: string;
  doses_previstas: number;
  doses_historico?: number | null;
  doses_projecao?: number | null;
  intervalo_inferior?: number;
  intervalo_superior?: number;
}

export interface PrevisaoResponse {
  status: "success" | string;
  purpose?: string;
  ano_previsao?: number;
  filtros_aplicados?: Record<string, unknown>;
  previsao_doses?: number | null;
}

export interface FilterParams {
  ano?: string;
  mes?: string;
  uf?: string;
  fabricante?: string;
}
