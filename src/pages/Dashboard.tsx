import { useEffect, useState, useRef } from "react";
import { Link } from "react-router-dom";
import { Activity, AlertCircle, Info } from "lucide-react";
import { useFilterStore } from "@/stores/filterStore";
import { apiClient } from "@/services/apiClient";
import { OverviewData, TimeseriesDataPoint, RankingUF, ForecastDataPoint, FilterParams } from "@/types/apiTypes";
import FilterSection from "@/components/dashboard/FilterSection";
import KPICards from "@/components/dashboard/KPICards";
import TimeseriesChart from "@/components/dashboard/TimeseriesChart";
import BrazilMap from "@/components/dashboard/BrazilMap";
import ForecastChart from "@/components/dashboard/ForecastChart";
import ComparisonChart from "@/components/dashboard/ComparisonChart";
import ErrorBoundary from "@/components/ui/error-boundary";
import ExplainForecastButton from "@/components/dashboard/ExplainForecastButton";
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
import { motion } from "framer-motion";

const Dashboard = (): JSX.Element => {
  const { ano, mes, uf, vacina, getAPIParams } = useFilterStore();

  // request counter to avoid race conditions when multiple rapid filter changes
  // incrementing this value cancels previous in-flight fetches (we check it
  // after each await and bail out early if it's changed).
  const requestCounter = useRef<number>(0);

  const [overviewData, setOverviewData] = useState<OverviewData | null>(null);
  const [timeseriesData, setTimeseriesData] = useState<TimeseriesDataPoint[]>([]);
  const [rankingData, setRankingData] = useState<RankingUF[]>([]);
  const [forecastData, setForecastData] = useState<unknown>([]);

  const [loadingOverview, setLoadingOverview] = useState(false);
  const [loadingTimeseries, setLoadingTimeseries] = useState(false);
  const [loadingRanking, setLoadingRanking] = useState(false);
  const [loadingForecast, setLoadingForecast] = useState(false);

  const [error, setError] = useState<string | null>(null);
  const [forecastInsufficient, setForecastInsufficient] = useState(false);

  useEffect(() => {
    type ComparacaoRow = { ano: number | string; quantidade: number | null; tipo?: string };
    type ComparacaoResponse = { projecao_unidade?: string; dados_comparacao?: ComparacaoRow[]; [k: string]: unknown };
    const fetchData = async () => {
      const thisRequest = ++requestCounter.current;
      const params = getAPIParams();
      setError(null);

      // Overview
      setLoadingOverview(true);
      let overview: OverviewData | null = null;
      try {
        overview = await apiClient.getOverview(params);
        // if a newer request started, stop processing this one
        if (requestCounter.current !== thisRequest) return;
        // ensure numeric shape: backend returns OverviewData but be defensive
        const normalizedOverview: OverviewData = {
          total_doses: Number(overview?.total_doses ?? 0),
          periodo: overview?.periodo,
        };
        setOverviewData(normalizedOverview);
      } catch (err) {
        setError("Erro ao carregar dados. Verifique se o backend está rodando.");
        console.error(err);
      } finally {
        setLoadingOverview(false);
      }

      // Timeseries
      setLoadingTimeseries(true);
      try {
        // If user selected both year and month, show the same month across other years.
        // To achieve this, request the timeseries without the `ano` filter so the
        // backend returns all years for the selected month (e.g. 2022-01, 2023-01, 2024-01).
        const timeseriesParams = { ...(params as FilterParams) } as FilterParams;
        if (params.ano && params.mes) {
          delete timeseriesParams.ano;
        }

        const timeseries = await apiClient.getTimeseries(timeseriesParams);
        if (requestCounter.current !== thisRequest) return;
        // API returns TimeseriesDataPoint[]; normalize defensively
        const normalized = (timeseries || []).map((p: TimeseriesDataPoint) => ({ data: String(p.data), doses_distribuidas: Number(p.doses_distribuidas || 0) }));
        setTimeseriesData(normalized);
      } catch (err) {
        setError("Erro ao carregar dados. Verifique se o backend está rodando.");
        console.error(err);
      } finally {
        setLoadingTimeseries(false);
      }

      // Ranking
      setLoadingRanking(true);
      try {
        const ranking = await apiClient.getRankingUFs(params);
        if (requestCounter.current !== thisRequest) return;
        setRankingData(ranking);
      } catch (err) {
        setError("Erro ao carregar dados. Verifique se o backend está rodando.");
        console.error(err);
      } finally {
        setLoadingRanking(false);
      }

      // Forecast
      setForecastInsufficient(false);
      if (!(ano || mes || uf || vacina)) {
        setForecastData([]);
        setLoadingForecast(false);
        return;
      }

  setLoadingForecast(true);
  try {
    const forecast = await apiClient.getForecast(params);
    if (requestCounter.current !== thisRequest) return;
    // keep existing forecast series from the legacy /forecast endpoint
    const merged = forecast || [];

  // if user selected a vacina, call the new comparison endpoint and render a simple bar chart
  if (vacina) {
          try {
            // ensure vacina is a non-empty trimmed string before calling
            const vacinaTrim = String(vacina || "").trim();
            if (!vacinaTrim) {
              // nothing meaningful selected, skip comparison call
              setForecastData([]);
              setForecastInsufficient(true);
            } else {
              // endpoint requires ano=2024 per backend validation
              type ComparacaoRow = { ano: number | string; quantidade: number | null; tipo?: string };
              type ComparacaoResponse = { projecao_unidade?: string; dados_comparacao?: ComparacaoRow[]; [k: string]: unknown };
              const respRaw = await apiClient.getComparacao({ insumo_nome: vacinaTrim, ano: 2024, uf: uf || undefined, mes: mes || undefined });
              const resp = respRaw as ComparacaoResponse;

            // resp.dados_comparacao is expected to be an array like [{ ano: 2024, quantidade: number|null, tipo: 'historico' }, { ano: 2025, quantidade: number|null, tipo: 'projeção' }]
            if (resp && Array.isArray(resp.dados_comparacao)) {
              const dados = resp.dados_comparacao;

              // mark insufficient if both quantities are null (backend uses null when no usable data)
              const q2024 = dados.find((d) => Number((d as ComparacaoRow).ano) === 2024)?.quantidade ?? null;
              const q2025 = dados.find((d) => Number((d as ComparacaoRow).ano) === 2025)?.quantidade ?? null;
              if ((q2024 === null || q2024 === 0) && (q2025 === null || q2025 === 0)) {
                setForecastData([]);
                setForecastInsufficient(true);
              } else {
                // pass the comparison payload (may include projecao_unidade) to the chart component
                // store the full response so the chart can annualize when appropriate
                if (requestCounter.current !== thisRequest) return;
                setForecastData(resp);
                setForecastInsufficient(false);
              }
            } else {
              // fallback: no usable comparison data
              if (requestCounter.current !== thisRequest) return;
              setForecastData([]);
              setForecastInsufficient(true);
            }
            }
            } catch (err) {
            // bubble up specific statuses if needed
            const apiErr = err as Error & { status?: number; body?: unknown };
            if (apiErr && apiErr.status === 400) {
              // validation error from backend (e.g. ano must be 2024) – surface to user
              setError(String(apiErr.body ?? apiErr.message));
            } else {
              setForecastData([]);
              setForecastInsufficient(true);
            }
          }
        } else {
          // If user selected a year (ano) but not a specific vacina, show a comparison-style
          // view comparing the total doses for the selected year vs the 2025 projection (annualized)
          if (ano) {
            try {
              // Use the same comparison logic as the vacina flow by calling the
              // backend /api/previsao/comparacao WITHOUT an insumo_nome so the
              // server computes totals/projecoes across all vacinas.
              const respRaw = await apiClient.getComparacao({ ano: Number(ano), uf: uf || undefined, mes: mes || undefined });
              const resp = respRaw as ComparacaoResponse;

                if (requestCounter.current !== thisRequest) return;

              if (resp && Array.isArray(resp.dados_comparacao)) {
                const q2024 = resp.dados_comparacao?.find((d) => Number((d as ComparacaoRow).ano) === Number(ano))?.quantidade ?? null;
                const q2025 = resp.dados_comparacao?.find((d) => Number((d as ComparacaoRow).ano) === 2025)?.quantidade ?? null;
                if ((q2024 === null || q2024 === 0) && (q2025 === null || q2025 === 0)) {
                  if (requestCounter.current !== thisRequest) return;
                  setForecastData([]);
                  setForecastInsufficient(true);
                } else {
                  if (requestCounter.current !== thisRequest) return;
                  // If a specific month is selected together with ano, the comparison
                  // endpoint returns two rows (historical vs projeção) for that month.
                  // Convert that shape into the ForecastChart-friendly timeseries
                  // array when `mes` is present so the line chart can render.
                  if (params.mes) {
                    const m = String(params.mes).padStart(2, "0");
                    const converted = (resp.dados_comparacao || []).map((d) => {
                      const row = d as { ano: number | string; quantidade: number | null; tipo?: string };
                      return {
                        data: `${row.ano}-${m}`,
                        doses_projecao: row.tipo === "projeção" ? (row.quantidade ?? null) : null,
                        doses_historico: row.tipo === "historico" ? (row.quantidade ?? null) : null,
                      } as ForecastDataPoint;
                    });
                    setForecastData(converted);
                  } else {
                    setForecastData(resp);
                  }
                  setForecastInsufficient(false);
                }
              } else {
                if (requestCounter.current !== thisRequest) return;
                setForecastData([]);
                setForecastInsufficient(true);
              }
            } catch (err) {
              if (requestCounter.current !== thisRequest) return;
              setForecastData([]);
              setForecastInsufficient(true);
            }
          } else {
            if (requestCounter.current !== thisRequest) return;
            setForecastData(merged);
          }
        }
      } catch (err) {
        setError("Erro ao carregar dados. Verifique se o backend está rodando.");
        console.error(err);
      } finally {
        if (requestCounter.current === thisRequest) setLoadingForecast(false);
      }
    };

    fetchData();
    // capture the counter value after starting the fetch so the cleanup
    // can reliably invalidate this specific run without reading a ref
    // value that may have changed later (avoids eslint hook warning).
    const effectSnapshot = requestCounter.current;
    // cancel/ignore previous in-flight fetches when any dependency changes
    return () => {
      // set the counter to snapshot+1 to invalidate this run
      requestCounter.current = effectSnapshot + 1;
    };
  }, [ano, mes, uf, vacina, getAPIParams]);

  return (
    <div className="min-h-screen bg-background">
      <header className="border-b bg-card sticky top-0 z-50 backdrop-blur-sm">
        <div className="container mx-auto px-4 py-4 flex justify-between items-center">
          <Link to="/" className="flex items-center gap-2">
            <Activity className="h-8 w-8 text-primary" />
            <h1 className="text-xl font-bold text-foreground">Vacina Brasil</h1>
          </Link>
          <nav className="flex gap-4 items-center">
            <Link to="/sobre" className="text-muted-foreground hover:text-foreground transition-colors">Sobre</Link>
          </nav>
        </div>
      </header>

      <main className="container mx-auto px-4 py-8 space-y-8">
        <motion.div initial={{ opacity: 0, y: -10 }} animate={{ opacity: 1, y: 0 }}>
          <h1 className="text-3xl font-bold text-foreground mb-2">Dashboard Nacional</h1>
          <p className="text-muted-foreground">Acompanhe os dados de distribuição e aplicação de vacinas em tempo real</p>
        </motion.div>

        

        {error && (
          <Alert variant="destructive">
            <AlertCircle className="h-4 w-4" />
            <AlertTitle>Erro</AlertTitle>
            <AlertDescription>{error}</AlertDescription>
          </Alert>
        )}

        <FilterSection />

        <KPICards data={overviewData} loading={loadingOverview} />

        <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
          <TimeseriesChart data={timeseriesData} loading={loadingTimeseries} />
          <BrazilMap data={rankingData} loading={loadingRanking} selectedUF={uf || null} />
        </div>

        {forecastInsufficient && (
          <Alert>
            <AlertTitle>Dados insuficientes</AlertTitle>
            <AlertDescription>Não há histórico suficiente para gerar previsão para os filtros selecionados.</AlertDescription>
          </Alert>
        )}

        { (vacina || (ano && !mes && !vacina)) ? (
          <ErrorBoundary>
            <ComparisonChart data={forecastData} loading={loadingForecast} />
            <div className="mt-3">
              {/* explanation button placed below the comparison chart */}
              <ExplainForecastButton />
            </div>
          </ErrorBoundary>
        ) : (
          <ErrorBoundary>
            <ForecastChart data={forecastData} loading={loadingForecast} filtersSelected={filtersSelected} />
          </ErrorBoundary>
        )}
      </main>
    </div>
  );
};

export default Dashboard;
