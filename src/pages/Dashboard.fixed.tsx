import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { Activity, AlertCircle, Info } from "lucide-react";
import { useFilterStore } from "@/stores/filterStore";
import { apiClient, OverviewData, TimeseriesDataPoint, RankingUF, ForecastDataPoint } from "@/lib/api";
import FilterSection from "@/components/dashboard/FilterSection";
import KPICards from "@/components/dashboard/KPICards";
import TimeseriesChart from "@/components/dashboard/TimeseriesChart";
import BrazilMap from "@/components/dashboard/BrazilMap";
import ForecastChart from "@/components/dashboard/ForecastChart";
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
import { motion } from "framer-motion";

const Dashboard = (): JSX.Element => {
  const { ano, mes, uf, vacina, getAPIParams } = useFilterStore();
  const filtersSelected = Boolean(ano || mes || uf || vacina);

  const [overviewData, setOverviewData] = useState<OverviewData | null>(null);
  const [timeseriesData, setTimeseriesData] = useState<TimeseriesDataPoint[]>([]);
  const [rankingData, setRankingData] = useState<RankingUF[]>([]);
  const [forecastData, setForecastData] = useState<ForecastDataPoint[]>([]);

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

      setLoadingOverview(true);
      try {
        const overview = await apiClient.getOverview(params);
        setOverviewData(overview);
      } catch (err) {
        setError("Erro ao carregar dados. Verifique se o backend está rodando.");
        console.error(err);
      } finally {
        setLoadingOverview(false);
      }

      setLoadingTimeseries(true);
      try {
        const timeseries = await apiClient.getTimeseries(params);
        setTimeseriesData(timeseries);
      } catch (err) {
        console.error(err);
      } finally {
        setLoadingTimeseries(false);
      }

      setLoadingRanking(true);
      try {
        const ranking = await apiClient.getRankingUFs(params);
        setRankingData(ranking);
      } catch (err) {
        console.error(err);
      } finally {
        setLoadingRanking(false);
      }

      setForecastInsufficient(false);
      if (!filtersSelected) {
        setForecastData([]);
        setLoadingForecast(false);
        return;
      }

      setLoadingForecast(true);
      try {
        const forecast = await apiClient.getForecast(params);
        let merged = forecast || [];
        let insufficient = false;

        if (vacina) {
          try {
            const resp: any = await apiClient.getPrevisao({ insumo_nome: vacina, uf: uf || undefined, mes: mes || undefined });

            if (Array.isArray(resp)) {
              const rpcPoints = resp
                .map((r: any) => {
                  const ano = r.ano ?? r.year ?? null;
                  const qtd = r.quantidade ?? r.qtd ?? null;
                  if (ano == null || qtd == null) return null;
                  const tipo = (r.tipo_dado ?? r._tipo ?? null) as string | null;
                  return {
                    data: String(ano),
                    doses_historico: tipo === "historico" ? Number(qtd) : null,
                    doses_projecao: tipo === "previsao" ? Number(qtd) : null,
                    doses_previstas: Number(qtd),
                    intervalo_inferior: undefined,
                    intervalo_superior: undefined,
                    _tipo: tipo,
                  };
                })
                .filter(Boolean) as any[];

              const byData: Record<string, any> = {};
              merged.forEach((m) => (byData[String(m.data)] = m));
              rpcPoints.forEach((p) => (byData[String(p.data)] = p));
              merged = Object.values(byData).sort((a: any, b: any) => (String(a.data) > String(b.data) ? 1 : -1));
            } else if (resp && (resp.previsao_doses != null || resp.ano_previsao)) {
              const label = resp.ano_previsao ? String(resp.ano_previsao) : (mes ? `2025-${String(mes).padStart(2, "0")}` : "2025");
              const qtd = Number(resp.previsao_doses || 0);
              merged = [
                ...merged,
                {
                  data: label,
                  doses_historico: null,
                  doses_projecao: qtd,
                  doses_previstas: qtd,
                  intervalo_inferior: undefined,
                  intervalo_superior: undefined,
                },
              ];
            }
          } catch (err: any) {
            if (err && err.status === 404) {
              insufficient = true;
              setForecastData([]);
              setForecastInsufficient(true);
            } else {
              console.warn("Falha ao chamar /api/previsao:", err);
            }
          }
        }

        if (!insufficient) setForecastData(merged);
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

        <Alert>
          <Info className="h-4 w-4" />
          <AlertTitle>Configuração do Backend</AlertTitle>
          <AlertDescription>
            Este dashboard consome dados de uma API FastAPI. Configure a variável de ambiente{' '}
            <code className="bg-muted px-1 py-0.5 rounded">VITE_BASE_API_URL</code> para apontar para seu backend.
          </AlertDescription>
        </Alert>

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

        <ForecastChart data={forecastData} loading={loadingForecast} filtersSelected={filtersSelected} />
      </main>
    </div>
  );
};

export default Dashboard;
