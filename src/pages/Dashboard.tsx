import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { Activity, AlertCircle, Info } from "lucide-react";
import { useFilterStore } from "@/stores/filterStore";
import { apiClient } from "@/services/apiClient";
import { OverviewData, TimeseriesDataPoint, RankingUF, ForecastDataPoint } from "@/types/apiTypes";
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
  const filtersSelected = Boolean(ano || mes || uf || vacina);

  const [overviewData, setOverviewData] = useState<OverviewData | null>(null);
  const [timeseriesData, setTimeseriesData] = useState<TimeseriesDataPoint[]>([]);
  const [rankingData, setRankingData] = useState<RankingUF[]>([]);
  const [forecastData, setForecastData] = useState<any>([]);

  const [loadingOverview, setLoadingOverview] = useState(false);
  const [loadingTimeseries, setLoadingTimeseries] = useState(false);
  const [loadingRanking, setLoadingRanking] = useState(false);
  const [loadingForecast, setLoadingForecast] = useState(false);

  const [error, setError] = useState<string | null>(null);
  const [forecastInsufficient, setForecastInsufficient] = useState(false);

  useEffect(() => {
    const fetchData = async () => {
      const params = getAPIParams();
      setError(null);

      // Overview
      setLoadingOverview(true);
      let overview: OverviewData | null = null;
      try {
        overview = await apiClient.getOverview(params);
        setOverviewData(overview);
      } catch (err) {
        setError("Erro ao carregar dados. Verifique se o backend está rodando.");
        console.error(err);
      } finally {
        setLoadingOverview(false);
      }

      // Timeseries
      setLoadingTimeseries(true);
      try {
        const timeseries = await apiClient.getTimeseries(params);
        setTimeseriesData(timeseries);
      } catch (err) {
        console.error(err);
      } finally {
        setLoadingTimeseries(false);
      }

      // Ranking
      setLoadingRanking(true);
      try {
        const ranking = await apiClient.getRankingUFs(params);
        setRankingData(ranking);
      } catch (err) {
        console.error(err);
      } finally {
        setLoadingRanking(false);
      }

      // Forecast
      setForecastInsufficient(false);
      if (!filtersSelected) {
        setForecastData([]);
        setLoadingForecast(false);
        return;
      }

      setLoadingForecast(true);
      try {
  const forecast = await apiClient.getForecast(params);
  // keep existing forecast series from the legacy /forecast endpoint
  let merged = forecast || [];

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
              const resp: any = await apiClient.getComparacao({ insumo_nome: vacinaTrim, ano: 2024, uf: uf || undefined, mes: mes || undefined });

            // resp.dados_comparacao is expected to be an array like [{ ano: 2024, quantidade: number|null, tipo: 'historico' }, { ano: 2025, quantidade: number|null, tipo: 'projeção' }]
            if (resp && Array.isArray(resp.dados_comparacao)) {
              const dados = resp.dados_comparacao;

              // mark insufficient if both quantities are null (backend uses null when no usable data)
              const q2024 = dados.find((d: any) => Number(d.ano) === 2024)?.quantidade ?? null;
              const q2025 = dados.find((d: any) => Number(d.ano) === 2025)?.quantidade ?? null;
              if ((q2024 === null || q2024 === 0) && (q2025 === null || q2025 === 0)) {
                setForecastData([]);
                setForecastInsufficient(true);
              } else {
                // pass the comparison payload (may include projecao_unidade) to the chart component
                // store the full response so the chart can annualize when appropriate
                setForecastData(resp as any);
                setForecastInsufficient(false);
              }
            } else {
              // fallback: no usable comparison data
              setForecastData([]);
              setForecastInsufficient(true);
            }
            }
          } catch (err: any) {
            // bubble up specific statuses if needed
            if (err && err.status === 400) {
              // validation error from backend (e.g. ano must be 2024) – surface to user
              setError(err.body || String(err));
            } else {
              console.warn("Falha ao chamar /api/previsao/comparacao:", err);
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
              const resp: any = await apiClient.getComparacao({ ano: Number(ano), uf: uf || undefined, mes: mes || undefined });

              if (resp && Array.isArray(resp.dados_comparacao)) {
                const q2024 = resp.dados_comparacao.find((d: any) => Number(d.ano) === Number(ano))?.quantidade ?? null;
                const q2025 = resp.dados_comparacao.find((d: any) => Number(d.ano) === 2025)?.quantidade ?? null;
                if ((q2024 === null || q2024 === 0) && (q2025 === null || q2025 === 0)) {
                  setForecastData([]);
                  setForecastInsufficient(true);
                } else {
                  setForecastData(resp);
                  setForecastInsufficient(false);
                }
              } else {
                setForecastData([]);
                setForecastInsufficient(true);
              }
            } catch (err) {
              console.error(err);
              setForecastData([]);
              setForecastInsufficient(true);
            }
          } else {
            setForecastData(merged);
          }
        }
      } catch (err) {
        console.error(err);
      } finally {
        setLoadingForecast(false);
      }
    };

    fetchData();
  }, [ano, mes, uf, vacina]);

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
