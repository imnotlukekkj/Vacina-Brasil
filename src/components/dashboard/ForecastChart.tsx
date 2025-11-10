import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card";
import React, { useMemo } from "react";
import { LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, Legend, ResponsiveContainer, Area, ComposedChart, ReferenceLine } from "recharts";
import { motion } from "framer-motion";
import { TrendingUp } from "lucide-react";

interface ForecastChartProps {
  data: Array<{
    data: string;
    doses_previstas: number;
    doses_historico?: number | null;
    doses_projecao?: number | null;
    intervalo_inferior?: number;
    intervalo_superior?: number;
  }>;
  loading: boolean;
  filtersSelected?: boolean;
}

const ForecastChart = ({ data, loading, filtersSelected = false }: ForecastChartProps) => {
  const numberFmt = useMemo(() => new Intl.NumberFormat("pt-BR"), []);

  const chartData = useMemo(() => {
    if (!data) return [];
    const base = data.map((d) => ({
      ...d,
      ci_range:
        d.intervalo_superior !== undefined && d.intervalo_inferior !== undefined
          ? Math.max(0, d.intervalo_superior - d.intervalo_inferior)
          : undefined,
    }));

    // if there's only one meaningful point, add a small synthetic previous point
    const meaningful = base.filter(
      (d) => d.doses_previstas !== undefined || (d.intervalo_superior !== undefined && d.intervalo_inferior !== undefined) || (d.doses_historico !== undefined && d.doses_historico !== null) || (d.doses_projecao !== undefined && d.doses_projecao !== null)
    );
    if (meaningful.length === 1) {
      const p = meaningful[0];
      // try to derive a previous-year label if possible (e.g. '2025-05' -> '2024-05')
      const match = String(p.data).match(/(\d{4})(.*)/);
      let prevLabel = "prev";
      if (match) {
        const year = Number(match[1]);
        const rest = match[2] || "";
        prevLabel = `${year - 1}${rest}`;
      }
      const synthetic = { ...p, data: prevLabel, synthetic: true };
      // insert synthetic before the real point so line goes from synthetic -> real
      return [synthetic, ...base];
    }

    return base;
  }, [data]);

  // derive some metrics for axis/domain handling
  const { yDomain, hasSinglePoint } = useMemo(() => {
    const vals: number[] = [];
    chartData.forEach((d) => {
      if (d.doses_previstas !== undefined) vals.push(Number(d.doses_previstas));
      if (d.doses_historico !== undefined && d.doses_historico !== null) vals.push(Number(d.doses_historico));
      if (d.doses_projecao !== undefined && d.doses_projecao !== null) vals.push(Number(d.doses_projecao));
      if (d.intervalo_inferior !== undefined) vals.push(Number(d.intervalo_inferior));
      if (d.intervalo_superior !== undefined) vals.push(Number(d.intervalo_superior));
    });

    const max = vals.length ? Math.max(...vals) : 0;
    const min = vals.length ? Math.min(...vals) : 0;

    let domainMin = Math.min(0, min);
    let domainMax = max;

    // If there's only one meaningful value, provide a nicer domain so the point doesn't sit on a flat axis
    const meaningfulPoints = chartData.filter((d) => (d.doses_previstas !== undefined) || (d.doses_historico !== undefined && d.doses_historico !== null) || (d.doses_projecao !== undefined && d.doses_projecao !== null) || (d.intervalo_superior !== undefined && d.intervalo_inferior !== undefined));
    const single = meaningfulPoints.length === 1;
    if (single) {
      // give some headroom (moderate)
      domainMax = Math.max(1, domainMax * 1.15);
      // ensure min is zero for clarity
      domainMin = 0;
    }

    return { yDomain: [domainMin, domainMax], hasSinglePoint: single };
  }, [chartData]);

  const CustomTooltip = ({ active, payload, label }: any) => {
  if (!active || !payload || payload.length === 0) return null;
    // payload[0].payload is the data object for the hovered point
    const payloadPoint = payload[0] && payload[0].payload ? payload[0].payload : null;
    // if the hovered point is synthetic, show the next real point's values (so tooltip displays 2025 instead of the synthetic prev label)
    let displayPoint = payloadPoint;
    if (payloadPoint && (payloadPoint as any).synthetic) {
      const nextReal = chartData.find((d: any) => !d.synthetic && (d.doses_previstas !== undefined || d.doses_historico !== undefined || d.doses_projecao !== undefined));
      if (nextReal) displayPoint = nextReal;
    }

    const p = payload.reduce((acc: any, cur: any) => {
      acc[cur.dataKey] = cur.value;
      return acc;
    }, {} as any);

    return (
      <div
        style={{
          backgroundColor: "hsl(var(--card))",
          border: "1px solid hsl(var(--border))",
          borderRadius: 8,
          padding: 12,
          color: "hsl(var(--foreground))",
          minWidth: 160,
        }}
      >
  <div className="font-medium mb-2">{displayPoint?.data ?? label}</div>
  <div className="text-sm text-muted-foreground">Histórico: <span className="font-semibold">{displayPoint?.doses_historico !== undefined && displayPoint?.doses_historico !== null ? numberFmt.format(displayPoint.doses_historico) : '—'}</span></div>
  <div className="text-sm text-muted-foreground">Projeção: <span className="font-semibold text-primary">{displayPoint?.doses_projecao !== undefined && displayPoint?.doses_projecao !== null ? numberFmt.format(displayPoint.doses_projecao) : (displayPoint?.doses_previstas !== undefined ? numberFmt.format(displayPoint.doses_previstas) : '—')}</span></div>
        {p.intervalo_inferior !== undefined && p.intervalo_superior !== undefined && (
          <div className="text-sm text-muted-foreground mt-1">
            Intervalo de Confiança: <span className="font-medium">{numberFmt.format(p.intervalo_inferior)} — {numberFmt.format(p.intervalo_superior)}</span>
          </div>
        )}
        {/* note: synthetic point info moved to chart caption/legend */}
      </div>
    );
  };
  if (loading) {
    return (
      <Card>
        <CardHeader>
          <div className="flex items-center gap-2">
            <TrendingUp className="h-5 w-5 text-primary" />
            <CardTitle>Previsão de Distribuição</CardTitle>
          </div>
          <CardDescription>Projeção baseada em dados históricos</CardDescription>
        </CardHeader>
        <CardContent>
          <div className="h-80 flex items-center justify-center">
            <div className="animate-pulse text-muted-foreground">Calculando previsão...</div>
          </div>
        </CardContent>
      </Card>
    );
  }

  // If no filters are selected, prompt the user to choose one. This keeps the UX clear
  // (the backend returns an empty list in that case).
  if (!filtersSelected && !loading) {
    return (
      <Card>
        <CardHeader>
          <div className="flex items-center gap-2">
            <TrendingUp className="h-5 w-5 text-primary" />
            <CardTitle>Previsão de Distribuição</CardTitle>
          </div>
          <CardDescription>Projeção de doses distribuídas baseada em dados históricos</CardDescription>
        </CardHeader>
        <CardContent>
          <div className="h-80 flex flex-col items-center justify-center text-center gap-2">
            <p className="text-muted-foreground">Selecione um filtro para gerar a previsão.</p>
            <p className="text-sm text-muted-foreground">Por exemplo, selecione um ano para estimar o total de 2025 com base na média histórica, ou selecione um mês para prever aquele mês em 2025 com base nos mesmos meses anteriores.</p>
          </div>
        </CardContent>
      </Card>
    );
  }

  if (!data || data.length === 0) {
    return (
      <Card>
        <CardHeader>
          <div className="flex items-center gap-2">
            <TrendingUp className="h-5 w-5 text-primary" />
            <CardTitle>Previsão de Distribuição</CardTitle>
          </div>
          <CardDescription>Projeção baseada em dados históricos</CardDescription>
        </CardHeader>
        <CardContent>
          <div className="h-80 flex items-center justify-center">
            <p className="text-muted-foreground">Dados insuficientes para gerar previsão</p>
          </div>
        </CardContent>
      </Card>
    );
  }

  return (
    <motion.div
      initial={{ opacity: 0, y: 20 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ delay: 0.4 }}
    >
      <Card>
        <CardHeader>
          <div className="flex items-center gap-2">
            <TrendingUp className="h-5 w-5 text-primary" />
            <CardTitle>Previsão de Distribuição</CardTitle>
          </div>
          <CardDescription>Projeção de doses distribuídas baseada em dados históricos</CardDescription>
        </CardHeader>
        <CardContent>
          {/* Provide a persistent caption/legend area (includes synthetic note when applicable) */}
          <div className="mb-3 flex flex-col gap-2">
            {data && data.length === 1 && String(data[0].data).includes("2025") && (
              <div className="text-sm text-muted-foreground">Apenas previsão para 2025 disponível — sem histórico suficiente para desenhar série completa</div>
            )}
            <div className="flex items-center gap-4 text-sm">
              <div className="flex items-center gap-2">
                <span className="inline-block w-4 h-0.5 bg-[color:var(--primary)] rounded" />
                <span className="text-muted-foreground">Distribuição Histórica</span>
              </div>
              <div className="flex items-center gap-2">
                <span className="inline-block w-4 h-0.5 rounded" style={{ background: 'linear-gradient(90deg, transparent 0%, var(--primary) 100%)' }} />
                <span className="text-muted-foreground">Projeção</span>
              </div>
              <div className="flex items-center gap-2">
                <span className="w-3 h-3 rounded-full bg-[color:var(--primary)] border border-white" />
                <span className="text-muted-foreground">Ponto projetado 2025</span>
              </div>
            </div>
            {chartData.some((d) => (d as any).synthetic) && (
              <div className="text-xs text-muted-foreground">Nota: um ponto sintético é adicionado apenas para desenhar a linha quando não há séries históricas suficientes.</div>
            )}
          </div>
          <ResponsiveContainer width="100%" height={400}>
            <ComposedChart data={chartData}>
              <CartesianGrid strokeDasharray="3 3" className="stroke-muted" />
              <XAxis 
                dataKey="data" 
                className="text-xs"
                tick={{ fill: "hsl(var(--muted-foreground))" }}
              />
              <YAxis 
                className="text-xs"
                tick={{ fill: "hsl(var(--muted-foreground))" }}
                tickFormatter={(v) => numberFmt.format(Number(v))}
                domain={yDomain}
                allowDecimals={false}
              />
              <Tooltip content={<CustomTooltip />} />
              <Legend />
              {/* show a baseline at zero when there's only a single point so chart feels less empty */}
              {hasSinglePoint && (
                <ReferenceLine y={0} stroke="hsl(var(--muted))" strokeDasharray="3 3" />
              )}
              {chartData[0]?.intervalo_inferior !== undefined && (
                <>
                  {/* base invisible area to serve as stack base */}
                  <Area
                    type="monotone"
                    dataKey="intervalo_inferior"
                    fill="transparent"
                    stroke="none"
                    stackId="ci"
                  />
                  {/* stacked area representing (upper - lower) to create band */}
                  <Area
                    type="monotone"
                    dataKey="ci_range"
                    fill="hsl(var(--primary) / 0.12)"
                    stroke="none"
                    stackId="ci"
                    name="Intervalo de Confiança"
                  />
                </>
              )}
              {/* Linha histórica: sólida */}
              <Line
                type="monotone"
                dataKey="doses_historico"
                stroke="hsl(var(--primary))"
                strokeWidth={3}
                name="Distribuição Histórica"
                dot={false}
                isAnimationActive={false}
              />

              {/* Linha projeção: tracejada */}
              <Line
                type="monotone"
                dataKey="doses_projecao"
                stroke="hsl(var(--primary))"
                strokeWidth={3}
                strokeDasharray={"5 5"}
                name="Projeção"
                dot={(dotProps: any) => {
                  const p = dotProps && dotProps.payload;
                  const is2025 = p && String(p.data).includes("2025");
                  const isSynthetic = p && p.synthetic;
                  const cx = dotProps.cx;
                  const cy = dotProps.cy;
                  if (is2025) {
                    return (
                      <g>
                        <circle cx={cx} cy={cy} r={6} fill="hsl(var(--primary))" stroke="#fff" strokeWidth={2} />
                        <text x={cx} y={cy - 12} textAnchor="middle" fill="hsl(var(--foreground))" fontSize={12} fontWeight={600}>
                          {numberFmt.format(p.doses_projecao ?? p.doses_previstas)}
                        </text>
                      </g>
                    );
                  }
                  if (isSynthetic) return <circle cx={cx} cy={cy} r={3} fill="hsl(var(--primary))" opacity={0.45} />;
                  return <circle cx={cx} cy={cy} r={4} fill="hsl(var(--primary))" />;
                }}
              />
              {/* message handled above the chart so it doesn't overlap SVG axes */}
            </ComposedChart>
          </ResponsiveContainer>
        </CardContent>
      </Card>
    </motion.div>
  );
};

export default ForecastChart;
