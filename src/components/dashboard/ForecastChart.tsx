import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card";
import React, { useMemo } from "react";
import { LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, Legend, ResponsiveContainer, Area, ComposedChart, ReferenceLine, BarChart, Bar } from "recharts";
import { motion } from "framer-motion";
import { TrendingUp } from "lucide-react";
import ComparisonChart from "./ComparisonChart";
import ExplainForecastButton from "./ExplainForecastButton";

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
type RawPoint = {
  data: string;
  doses_previstas?: number | null;
  doses_historico?: number | null;
  doses_projecao?: number | null;
  intervalo_inferior?: number | null;
  intervalo_superior?: number | null;
  synthetic?: boolean;
  [k: string]: unknown;
};

type ChartPoint = RawPoint & { doses_projecao?: number | undefined; ci_range?: number };

const ForecastChart = ({ data, loading, filtersSelected = false }: ForecastChartProps) => {
  const numberFmt = useMemo(() => new Intl.NumberFormat("pt-BR"), []);


  const chartData = useMemo<ChartPoint[]>(() => {
    if (!data || !Array.isArray(data)) return [];
    const base = (data as RawPoint[]).map((d) => {
      const raw = d;
      const doses_projecao = raw.doses_projecao ?? raw.doses_previstas ?? undefined;
      const intervalo_superior = raw.intervalo_superior ?? undefined;
      const intervalo_inferior = raw.intervalo_inferior ?? undefined;
      const ci_range = intervalo_superior !== undefined && intervalo_inferior !== undefined ? Math.max(0, Number(intervalo_superior) - Number(intervalo_inferior)) : undefined;
      return { ...raw, doses_projecao, ci_range } as ChartPoint;
    });

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

  // DEBUG: show processed chart data in dev to help diagnose empty charts
  const meta = (import.meta as unknown) as { env?: Record<string, unknown> };
  const showDebug = typeof import.meta !== "undefined" && !!meta.env && !!meta.env.DEV;

  // derive some metrics for axis/domain handling
  const { yDomain, hasSinglePoint } = useMemo(() => {
    const vals: number[] = [];
    chartData.forEach((d) => {
      if (d.doses_previstas !== undefined && d.doses_previstas !== null) vals.push(Number(d.doses_previstas));
      if (d.doses_historico !== undefined && d.doses_historico !== null) vals.push(Number(d.doses_historico));
      if (d.doses_projecao !== undefined && d.doses_projecao !== null) vals.push(Number(d.doses_projecao));
      if (d.intervalo_inferior !== undefined && d.intervalo_inferior !== null) vals.push(Number(d.intervalo_inferior));
      if (d.intervalo_superior !== undefined && d.intervalo_superior !== null) vals.push(Number(d.intervalo_superior));
    });

    const max = vals.length ? Math.max(...vals) : 0;
    const min = vals.length ? Math.min(...vals) : 0;

    let domainMin = Math.min(0, min);
    let domainMax = max;

    // If there's only one meaningful value, provide a nicer domain so the point doesn't sit on a flat axis
    const meaningfulPoints = chartData.filter((d) => d.doses_previstas !== undefined || (d.doses_historico !== undefined && d.doses_historico !== null) || (d.doses_projecao !== undefined && d.doses_projecao !== null) || (d.intervalo_superior !== undefined && d.intervalo_inferior !== undefined));
    const single = meaningfulPoints.length === 1;
    if (single) {
      // give some headroom (moderate)
      domainMax = Math.max(1, domainMax * 1.15);
      // ensure min is zero for clarity
      domainMin = 0;
    }

    return { yDomain: [domainMin, domainMax], hasSinglePoint: single };
  }, [chartData]);

  // detect simple comparison pair: one historical point and one projection for the same month
  const isComparisonPair = useMemo(() => {
    if (!chartData || chartData.length !== 2) return false;
    const a = chartData[0];
    const b = chartData[1];
    const hasHist = (a.doses_historico !== undefined && a.doses_historico !== null) || (b.doses_historico !== undefined && b.doses_historico !== null);
    const hasProj = (a.doses_projecao !== undefined && a.doses_projecao !== null) || (b.doses_projecao !== undefined && b.doses_projecao !== null);
    if (!hasHist || !hasProj) return false;
    // ensure both points refer to the same month pattern (e.g. '2024-06' and '2025-06') when a month was selected
    const months = chartData.map((d) => {
      const s = String(d.data);
      return s.includes("-") ? s.slice(-3) : s.slice(-2);
    });
    return months[0] === months[1];
  }, [chartData]);

  // (no early return here) when there's a month-pair we'll render the
  // ComparisonChart inside the main return to keep hook order stable.

  const barData = useMemo(() => {
    if (!isComparisonPair) return [] as { name: string; hist: number; proj: number }[];
    const histPoint = chartData.find((d) => d.doses_historico !== undefined && d.doses_historico !== null);
    const projPoint = chartData.find((d) => d.doses_projecao !== undefined && d.doses_projecao !== null);
    const labelSuffix = String(histPoint?.data || projPoint?.data || "");
    // single-row data with two keys so Bars render side-by-side
    return [{ name: labelSuffix, hist: Number(histPoint?.doses_historico ?? 0), proj: Number(projPoint?.doses_projecao ?? 0) }];
  }, [isComparisonPair, chartData]);

  const CustomTooltip = ({ active, payload, label }: { active?: boolean; payload?: unknown[]; label?: string | number }) => {
  if (!active || !payload || payload.length === 0) return null;
    // payload[0].payload is the data object for the hovered point
    const first = payload[0] as Record<string, unknown> | undefined;
    const payloadPoint = first && first.payload ? (first.payload as ChartPoint) : null;
    // if the hovered point is synthetic, show the next real point's values (so tooltip displays 2025 instead of the synthetic prev label)
    let displayPoint: ChartPoint | null = payloadPoint;
    if (payloadPoint && payloadPoint.synthetic) {
      const nextReal = chartData.find((d) => !d.synthetic && (d.doses_previstas !== undefined || d.doses_historico !== undefined || d.doses_projecao !== undefined));
      if (nextReal) displayPoint = nextReal;
    }

    const p = (payload as Record<string, unknown>[]).reduce<Record<string, unknown>>((acc, cur) => {
      const c = cur as Record<string, unknown>;
      const key = String(c.dataKey ?? c.name ?? "value");
      acc[key] = c.value as unknown;
      return acc;
    }, {});

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
            Intervalo de Confiança: <span className="font-medium">{numberFmt.format(Number(p.intervalo_inferior))} — {numberFmt.format(Number(p.intervalo_superior))}</span>
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

  // detect if incoming `data` is actually a comparison payload (from /api/previsao/comparacao)
  const isComparisonPayload = (() => {
    if (!data) return false;
    // backend may send an object with `dados_comparacao` or the frontend may pass the raw array
    const asUnknown = data as unknown;
    if (asUnknown && typeof asUnknown === "object" && "dados_comparacao" in (asUnknown as Record<string, unknown>)) return true;
    if (Array.isArray(asUnknown) && (asUnknown as unknown[]).length) {
      const first = (asUnknown as unknown[])[0] as Record<string, unknown> | undefined;
      if (first && ("ano" in first || "quantidade" in first)) return true;
    }
    return false;
  })();

  // We will check `isComparisonPayload` during rendering to decide whether to
  // show the `ComparisonChart` layout; avoid returning early to preserve hooks.

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
    // show the same 'dados insuficientes' UI for empty/absent data
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
          {/* Caption area (kept minimal) */}
          <div className="mb-3 flex flex-col gap-2">
            {data && data.length === 1 && String((data as RawPoint[])[0].data).includes("2025") && (
              <div className="text-sm text-muted-foreground">Apenas previsão para 2025 disponível — sem histórico suficiente para desenhar série completa</div>
            )}
          </div>
          <ResponsiveContainer width="100%" height={400}>
            {isComparisonPair ? (
              // Render ComparisonChart inside main JSX to preserve consistent hook order
              (() => {
                const hist = chartData.find((d) => d.doses_historico !== undefined && d.doses_historico !== null)?.doses_historico ?? null;
                const proj = chartData.find((d) => d.doses_projecao !== undefined && d.doses_projecao !== null)?.doses_projecao ?? null;
                const yearA = Number(String((chartData[0] || {}).data).slice(0,4)) || 2024;
                const yearB = Number(String((chartData[1] || {}).data).slice(0,4)) || yearA + 1 || 2025;
                const histPoint = chartData.find((d) => d.doses_historico !== undefined && d.doses_historico !== null);
                const projPoint = chartData.find((d) => d.doses_projecao !== undefined && d.doses_projecao !== null);
                const labelSuffix = String(histPoint?.data || projPoint?.data || "");
                // Determine whether we should annualize the projection when comparing.
                // If the labelSuffix contains a month (e.g. '2024-06') we are comparing
                // monthly values and should NOT multiply the projection by 12.
                const shouldAnnualize = !labelSuffix.includes("-");
                const compPayload = {
                  projecao_unidade: "mensal",
                  dados_comparacao: [ { ano: yearA, quantidade: hist, tipo: 'historico' }, { ano: yearB, quantidade: proj, tipo: 'projeção' } ],
                  annualize_projection: shouldAnnualize,
                };
                return <ComparisonChart data={compPayload} loading={loading} embedded />;
              })()
            ) : (
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
                    key="ci-base-area"
                  />
                  {/* stacked area representing (upper - lower) to create band */}
                  <Area
                    type="monotone"
                    dataKey="ci_range"
                    fill="hsl(var(--primary) / 0.12)"
                    stroke="none"
                    stackId="ci"
                    key="ci-range-area"
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
                key="line-historico"
              />

              {/* Linha projeção: tracejada */}
              <Line
                type="monotone"
                dataKey="doses_projecao"
                stroke="hsl(var(--primary))"
                strokeWidth={3}
                strokeDasharray={"5 5"}
                name="Projeção"
                  dot={(dotProps?: { payload?: ChartPoint; cx?: number; cy?: number }) => {
                  const p = dotProps?.payload;
                  const is2025 = !!(p && String(p.data).includes("2025"));
                  const isSynthetic = !!(p && p.synthetic);
                  const cx = dotProps?.cx ?? 0;
                  const cy = dotProps?.cy ?? 0;
                  const keyId = p ? `dot-${String(p.data)}` : `dot-${cx}-${cy}`;
                  if (is2025 && p) {
                    return (
                      <g key={`${keyId}-g`}>
                        <circle key={`${keyId}-circle`} cx={cx} cy={cy} r={6} fill="hsl(var(--primary))" stroke="#fff" strokeWidth={2} />
                        <text key={`${keyId}-text`} x={cx} y={cy - 12} textAnchor="middle" fill="hsl(var(--foreground))" fontSize={12} fontWeight={600}>
                          {numberFmt.format((p.doses_projecao ?? p.doses_previstas) as number)}
                        </text>
                      </g>
                    );
                  }
                  if (isSynthetic) return <circle key={`${keyId}-synthetic`} cx={cx} cy={cy} r={3} fill="hsl(var(--primary))" opacity={0.45} />;
                  return <circle key={`${keyId}-normal`} cx={cx} cy={cy} r={4} fill="hsl(var(--primary))" />;
                }}
                key="line-projecao"
              />
              {/* message handled above the chart so it doesn't overlap SVG axes */}
              </ComposedChart>
              )}
            </ResponsiveContainer>
          {/* debug information removed for production clarity */}
          {isComparisonPair && (
            <div className="mt-3">
              <ExplainForecastButton />
            </div>
          )}
        </CardContent>
      </Card>
    </motion.div>
  );
};

export default ForecastChart;
