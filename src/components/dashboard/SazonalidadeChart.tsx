import { useEffect, useMemo, useState } from "react";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { apiClient } from "@/services/apiClient";
import { useFilterStore } from "@/stores/filterStore";
import { SazonalidadeDataPoint } from "@/types/apiTypes";
import { motion } from "framer-motion";
import { Area, AreaChart, CartesianGrid, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";

const numberFmt = new Intl.NumberFormat("pt-BR");

const MONTH_LABELS = ["Jan", "Fev", "Mar", "Abr", "Mai", "Jun", "Jul", "Ago", "Set", "Out", "Nov", "Dez"];

interface ChartRow {
  mes: number;
  mesLabel: string;
  qtde: number;
}

const SazonalidadeChart = (): JSX.Element => {
  const { ano, uf, vacina } = useFilterStore();
  const [data, setData] = useState<SazonalidadeDataPoint[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;

    const fetchSazonalidade = async () => {
      setLoading(true);
      setError(null);
      try {
        const resp = await apiClient.getSazonalidade({
          ano: ano || undefined,
          uf: uf || undefined,
          fabricante: vacina || undefined,
        });
        if (cancelled) return;

        const normalized = (resp || [])
          .map((item) => ({ mes: Number(item.mes || 0), qtde: Number(item.qtde || 0) }))
          .filter((item) => item.mes >= 1 && item.mes <= 12)
          .sort((a, b) => a.mes - b.mes);

        setData(normalized);
      } catch (err) {
        if (cancelled) return;
        console.error(err);
        setError("Não foi possível carregar a sazonalidade.");
        setData([]);
      } finally {
        if (!cancelled) setLoading(false);
      }
    };

    fetchSazonalidade();

    return () => {
      cancelled = true;
    };
  }, [ano, uf, vacina]);

  const chartData = useMemo<ChartRow[]>(() => {
    const byMonth = new Map<number, number>();
    data.forEach((d) => byMonth.set(d.mes, d.qtde));

    return Array.from({ length: 12 }, (_, i) => {
      const mes = i + 1;
      return {
        mes,
        mesLabel: MONTH_LABELS[i],
        qtde: byMonth.get(mes) ?? 0,
      };
    });
  }, [data]);

  if (loading) {
    return (
      <Card>
        <CardHeader>
          <CardTitle>Sazonalidade da Distribuição</CardTitle>
          <CardDescription>Distribuição mensal de doses ao longo do ano</CardDescription>
        </CardHeader>
        <CardContent>
          <div className="h-80 flex items-center justify-center">
            <div className="animate-pulse text-muted-foreground">Carregando sazonalidade...</div>
          </div>
        </CardContent>
      </Card>
    );
  }

  if (error) {
    return (
      <Card>
        <CardHeader>
          <CardTitle>Sazonalidade da Distribuição</CardTitle>
          <CardDescription>Distribuição mensal de doses ao longo do ano</CardDescription>
        </CardHeader>
        <CardContent>
          <div className="h-80 flex items-center justify-center text-sm text-muted-foreground">{error}</div>
        </CardContent>
      </Card>
    );
  }

  const hasAnyValue = chartData.some((d) => d.qtde > 0);
  if (!hasAnyValue) {
    return (
      <Card>
        <CardHeader>
          <CardTitle>Sazonalidade da Distribuição</CardTitle>
          <CardDescription>Distribuição mensal de doses ao longo do ano</CardDescription>
        </CardHeader>
        <CardContent>
          <div className="h-80 flex items-center justify-center text-sm text-muted-foreground">
            Nenhum dado disponível para os filtros selecionados.
          </div>
        </CardContent>
      </Card>
    );
  }

  return (
    <motion.div initial={{ opacity: 0, y: 18 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: 0.2 }}>
      <Card>
        <CardHeader>
          <CardTitle>Sazonalidade da Distribuição</CardTitle>
          <CardDescription>Distribuição mensal de doses ao longo do ano</CardDescription>
        </CardHeader>
        <CardContent>
          <ResponsiveContainer width="100%" height={360}>
            <AreaChart data={chartData} margin={{ top: 12, right: 18, left: 18, bottom: 8 }}>
              <defs>
                <linearGradient id="sazonalidadeFill" x1="0" y1="0" x2="0" y2="1">
                  <stop offset="0%" stopColor="hsl(var(--primary))" stopOpacity={0.38} />
                  <stop offset="100%" stopColor="hsl(var(--primary))" stopOpacity={0.04} />
                </linearGradient>
              </defs>

              <CartesianGrid strokeDasharray="3 3" className="stroke-muted" />
              <XAxis
                dataKey="mesLabel"
                tick={{ fill: "hsl(var(--muted-foreground))", fontSize: 12 }}
                axisLine={{ stroke: "hsl(var(--border))" }}
                tickLine={{ stroke: "hsl(var(--border))" }}
              />
              <YAxis
                tick={{ fill: "hsl(var(--muted-foreground))", fontSize: 12 }}
                tickFormatter={(v) => numberFmt.format(Number(v))}
                axisLine={{ stroke: "hsl(var(--border))" }}
                tickLine={{ stroke: "hsl(var(--border))" }}
              />
              <Tooltip
                contentStyle={{
                  backgroundColor: "hsl(var(--card))",
                  border: "1px solid hsl(var(--border))",
                  borderRadius: 10,
                  color: "hsl(var(--foreground))",
                }}
                labelStyle={{ color: "hsl(var(--foreground))" }}
                itemStyle={{ color: "hsl(var(--foreground))" }}
                formatter={(value: number) => [numberFmt.format(Number(value)), "Doses"]}
                labelFormatter={(label) => `Mês: ${label}`}
              />
              <Area
                type="monotone"
                dataKey="qtde"
                stroke="hsl(var(--primary))"
                strokeWidth={3}
                fill="url(#sazonalidadeFill)"
                name="Doses por mês"
                dot={{ fill: "hsl(var(--primary))", r: 3 }}
                activeDot={{ r: 5, fill: "hsl(var(--primary))" }}
              />
            </AreaChart>
          </ResponsiveContainer>
        </CardContent>
      </Card>
    </motion.div>
  );
};

export default SazonalidadeChart;
