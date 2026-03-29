import { useEffect, useMemo, useState } from "react";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { apiClient } from "@/services/apiClient";
import { useFilterStore } from "@/stores/filterStore";
import { TopVacinaDataPoint } from "@/types/apiTypes";
import { motion } from "framer-motion";
import { ResponsiveContainer, BarChart, Bar, CartesianGrid, XAxis, YAxis, Tooltip, Cell } from "recharts";

const numberFmt = new Intl.NumberFormat("pt-BR");

const truncateLabel = (label: string, max = 30) => {
  if (!label) return "";
  return label.length > max ? `${label.slice(0, max - 1)}…` : label;
};

const TopVacinasChart = (): JSX.Element => {
  const { ano, mes, uf, vacina } = useFilterStore();
  const [data, setData] = useState<TopVacinaDataPoint[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;

    const fetchTopVacinas = async () => {
      setLoading(true);
      setError(null);
      try {
        const params = {
          ano: ano || undefined,
          mes: mes || undefined,
          uf: uf || undefined,
          fabricante: vacina || undefined,
        };
        const resp = await apiClient.getTopVacinas(params);
        if (cancelled) return;
        const normalized = (resp || [])
          .filter((item) => item && item.tx_insumo)
          .map((item) => ({
            tx_insumo: item.tx_insumo,
            qtde: Number(item.qtde || 0),
          }))
          .sort((a, b) => b.qtde - a.qtde)
          .slice(0, 5);
        setData(normalized);
      } catch (err) {
        if (cancelled) return;
        console.error(err);
        setError("Não foi possível carregar o Top 5 vacinas.");
        setData([]);
      } finally {
        if (!cancelled) setLoading(false);
      }
    };

    fetchTopVacinas();

    return () => {
      cancelled = true;
    };
  }, [ano, mes, uf, vacina]);

  const chartData = useMemo(
    () => data.map((item) => ({ ...item, label: truncateLabel(item.tx_insumo) })),
    [data]
  );

  if (loading) {
    return (
      <Card>
        <CardHeader>
          <CardTitle>Top 5 Vacinas</CardTitle>
          <CardDescription>Vacinas com maior distribuição no período filtrado</CardDescription>
        </CardHeader>
        <CardContent>
          <div className="h-80 flex items-center justify-center">
            <div className="animate-pulse text-muted-foreground">Carregando Top 5 vacinas...</div>
          </div>
        </CardContent>
      </Card>
    );
  }

  if (error) {
    return (
      <Card>
        <CardHeader>
          <CardTitle>Top 5 Vacinas</CardTitle>
          <CardDescription>Vacinas com maior distribuição no período filtrado</CardDescription>
        </CardHeader>
        <CardContent>
          <div className="h-80 flex items-center justify-center text-center text-sm text-muted-foreground">
            {error}
          </div>
        </CardContent>
      </Card>
    );
  }

  if (!chartData.length) {
    return (
      <Card>
        <CardHeader>
          <CardTitle>Top 5 Vacinas</CardTitle>
          <CardDescription>Vacinas com maior distribuição no período filtrado</CardDescription>
        </CardHeader>
        <CardContent>
          <div className="h-80 flex items-center justify-center text-center text-sm text-muted-foreground">
            Nenhum dado disponível para os filtros selecionados.
          </div>
        </CardContent>
      </Card>
    );
  }

  return (
    <motion.div initial={{ opacity: 0, y: 16 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: 0.15 }}>
      <Card>
        <CardHeader>
          <CardTitle>Top 5 Vacinas</CardTitle>
          <CardDescription>Vacinas com maior distribuição no período filtrado</CardDescription>
        </CardHeader>
        <CardContent>
          <ResponsiveContainer width="100%" height={360}>
            <BarChart data={chartData} layout="vertical" margin={{ top: 8, right: 20, left: 4, bottom: 8 }}>
              <CartesianGrid strokeDasharray="3 3" className="stroke-muted" horizontal={false} />
              <XAxis
                type="number"
                tick={{ fill: "hsl(var(--muted-foreground))", fontSize: 12 }}
                axisLine={{ stroke: "hsl(var(--border))" }}
                tickLine={{ stroke: "hsl(var(--border))" }}
                tickFormatter={(v) => numberFmt.format(Number(v))}
              />
              <YAxis
                dataKey="label"
                type="category"
                width={200}
                tick={{ fill: "hsl(var(--muted-foreground))", fontSize: 12 }}
                axisLine={{ stroke: "hsl(var(--border))" }}
                tickLine={{ stroke: "hsl(var(--border))" }}
              />
              <Tooltip
                cursor={{ fill: "hsl(var(--muted) / 0.25)" }}
                contentStyle={{
                  backgroundColor: "hsl(var(--card))",
                  border: "1px solid hsl(var(--border))",
                  borderRadius: 10,
                  color: "hsl(var(--foreground))",
                }}
                labelStyle={{ color: "hsl(var(--foreground))" }}
                itemStyle={{ color: "hsl(var(--foreground))" }}
                formatter={(value: number, _name: string, payload: { payload?: TopVacinaDataPoint }) => {
                  const item = payload?.payload;
                  return [numberFmt.format(Number(value)), item?.tx_insumo || "Vacina"];
                }}
                labelFormatter={() => "Doses distribuídas"}
              />
              <Bar dataKey="qtde" radius={[0, 8, 8, 0]}>
                {chartData.map((entry, index) => (
                  <Cell
                    key={`${entry.tx_insumo}-${index}`}
                    fill={index === 0 ? "hsl(var(--primary))" : "hsl(var(--primary) / 0.8)"}
                  />
                ))}
              </Bar>
            </BarChart>
          </ResponsiveContainer>
        </CardContent>
      </Card>
    </motion.div>
  );
};

export default TopVacinasChart;
