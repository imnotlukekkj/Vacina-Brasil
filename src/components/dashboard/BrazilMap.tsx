import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card";
import { ComposableMap, Geographies, Geography } from "react-simple-maps";
import { motion } from "framer-motion";
import { useEffect, useMemo, useState } from "react";
import { scaleLinear } from "d3-scale";
import { Sparkles } from "lucide-react";
import { apiClient } from "@/services/apiClient";
import { useFilterStore } from "@/stores/filterStore";
import { DetalhesGeograficosDataPoint } from "@/types/apiTypes";

interface BrazilMapProps {
  data: Array<{
    uf: string;
    sigla: string;
    doses_distribuidas: number;
  }>;
  loading: boolean;
  selectedUF?: string | null;
}

// GeoJSON simplificado do Brasil (você pode usar um TopoJSON mais detalhado)
const geoUrl = "https://raw.githubusercontent.com/codeforamerica/click_that_hood/master/public/data/brazil-states.geojson";

const numberFmt = new Intl.NumberFormat("pt-BR");

const normalizeUfSigla = (value: string | null | undefined): string => {
  const raw = String(value || "").trim().toUpperCase();
  if (!raw) return "";
  if (raw.includes("-")) {
    const parts = raw.split("-");
    return String(parts[parts.length - 1] || "").trim();
  }
  return raw;
};

interface HoverState {
  sigla: string;
  name: string;
  x: number;
  y: number;
  visible: boolean;
}

interface DetalhesPorUf {
  tx_insumo: string;
  qtde: number;
}

const BrazilMap = ({ data, loading, selectedUF = null }: BrazilMapProps) => {
  const { ano, mes, vacina } = useFilterStore();
  const [hover, setHover] = useState<HoverState>({ sigla: "", name: "", x: 0, y: 0, visible: false });
  const [detalhesRows, setDetalhesRows] = useState<DetalhesGeograficosDataPoint[]>([]);
  const [loadingDetalhes, setLoadingDetalhes] = useState(false);
  // reflect externally selected UF first (from filters). Local clicks still override.
  const [selected, setSelected] = useState<string | null>(selectedUF || null);

  // keep selected in sync if parent filter changes
  useEffect(() => {
    setSelected(selectedUF || null);
  }, [selectedUF]);

  useEffect(() => {
    let cancelled = false;

    const fetchDetalhesGeograficos = async () => {
      setLoadingDetalhes(true);
      try {
        const rows = await apiClient.getDetalhesGeograficos({
          ano: ano || undefined,
          mes: mes || undefined,
          fabricante: vacina || undefined,
        });
        if (cancelled) return;
        setDetalhesRows(rows || []);
      } catch (err) {
        if (cancelled) return;
        console.error(err);
        setDetalhesRows([]);
      } finally {
        if (!cancelled) setLoadingDetalhes(false);
      }
    };

    fetchDetalhesGeograficos();

    return () => {
      cancelled = true;
    };
  }, [ano, mes, vacina]);

  const detalhesPorUf = useMemo<Record<string, DetalhesPorUf>>(() => {
    const map: Record<string, DetalhesPorUf> = {};
    for (const row of detalhesRows) {
      const sigla = normalizeUfSigla(row.tx_sigla);
      if (!sigla) continue;
      map[sigla] = {
        tx_insumo: String(row.tx_insumo || ""),
        qtde: Number(row.qtde || 0),
      };
    }
    return map;
  }, [detalhesRows]);

  if (loading) {
    return (
      <Card>
        <CardHeader>
          <CardTitle>Mapa do Brasil</CardTitle>
          <CardDescription>Distribuição por UF</CardDescription>
        </CardHeader>
        <CardContent>
          <div className="h-96 flex items-center justify-center">
            <div className="animate-pulse text-muted-foreground">Carregando mapa...</div>
          </div>
        </CardContent>
      </Card>
    );
  }

  // Cria um mapa de cores baseado nas doses distribuídas
  const colorScale = scaleLinear<string>()
    .domain([
      0,
      Math.max(...data.map(d => d.doses_distribuidas)) / 2,
      Math.max(...data.map(d => d.doses_distribuidas))
    ])
    .range(["hsl(var(--muted))", "hsl(var(--primary) / 0.5)", "hsl(var(--primary))"]);

  const getColorForState = (stateName: string) => {
    const stateData = data.find(d =>
      normalizeUfSigla(d.sigla) === normalizeUfSigla(stateName) ||
      normalizeUfSigla(d.uf) === normalizeUfSigla(stateName)
    );
    // If an external filter selected a UF, only highlight that state; others should be muted
    if (selectedUF) {
      const matches = stateData && (
        normalizeUfSigla(stateData.sigla) === normalizeUfSigla(selectedUF) ||
        normalizeUfSigla(stateData.uf) === normalizeUfSigla(selectedUF)
      );
      return matches ? colorScale(stateData!.doses_distribuidas) : "hsl(var(--muted))";
    }
    return stateData ? colorScale(stateData.doses_distribuidas) : "hsl(var(--muted))";
  };

  return (
    <motion.div
      initial={{ opacity: 0, y: 20 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ delay: 0.3 }}
    >
      <Card>
        <CardHeader>
          <CardTitle>Mapa do Brasil</CardTitle>
          <CardDescription>Distribuição de doses por Unidade Federativa</CardDescription>
        </CardHeader>
        <CardContent>
          {data.length === 0 ? (
            <div className="h-96 flex items-center justify-center">
              <p className="text-muted-foreground">Nenhum dado disponível para o mapa</p>
            </div>
          ) : (
            <div className="w-full h-96 relative flex items-center justify-center">
              <div className="w-full h-full max-w-[760px]">
                <ComposableMap
                  className="w-full h-full"
                  projection="geoMercator"
                  projectionConfig={{
                    scale: 600,
                    center: [-55, -15],
                  }}
                >
                <Geographies geography={geoUrl}>
                  {({ geographies }) =>
                    geographies.map((geo) => {
                      const stateName = String(geo.properties.name || geo.properties.sigla || "");
                      const stateSigla = normalizeUfSigla(String(geo.properties.sigla || geo.properties.name || ""));
                      const isSelected = normalizeUfSigla(String(selected || "")) === stateSigla;
                      return (
                        <Geography
                          key={geo.rsmKey}
                          geography={geo}
                          fill={getColorForState(stateSigla || stateName)}
                          stroke={isSelected ? "hsl(var(--primary))" : "hsl(var(--border))"}
                          strokeWidth={isSelected ? 1.5 : 0.5}
                          onMouseEnter={(evt) => {
                            setHover({ sigla: stateSigla, name: stateName, x: evt.clientX + 12, y: evt.clientY + 12, visible: true });
                          }}
                          onMouseMove={(evt) => {
                            setHover(h => (h.visible ? { ...h, x: evt.clientX + 12, y: evt.clientY + 12 } : h));
                          }}
                          onMouseLeave={() => setHover(h => ({ ...h, visible: false }))}
                          onClick={() => setSelected(stateSigla || stateName)}
                          style={{
                            default: { outline: "none" },
                            hover: {
                              fill: "hsl(var(--secondary))",
                              outline: "none",
                              cursor: "pointer",
                            },
                            pressed: { outline: "none" },
                          }}
                        />
                      );
                    })
                  }
                </Geographies>
                </ComposableMap>
              </div>

              {hover.visible && (
                (() => {
                  const detalhe = detalhesPorUf[normalizeUfSigla(hover.sigla || hover.name)];
                  return (
                    <div
                      className="pointer-events-none fixed z-50 min-w-[260px] max-w-[320px] rounded-xl border border-border/60 bg-card/95 p-3 shadow-xl backdrop-blur"
                      style={{ left: hover.x, top: hover.y }}
                    >
                      <div className="text-xs uppercase tracking-wide text-muted-foreground">Estado</div>
                      <div className="text-sm font-bold text-foreground">{hover.sigla || hover.name}</div>

                      {loadingDetalhes ? (
                        <div className="mt-2 text-xs text-muted-foreground">Carregando detalhes...</div>
                      ) : detalhe ? (
                        <>
                          <div className="mt-2 text-xs uppercase tracking-wide text-muted-foreground">Doses</div>
                          <div className="text-sm font-semibold text-foreground">{numberFmt.format(detalhe.qtde)}</div>

                          <div className="mt-2 flex items-start gap-2">
                            <Sparkles className="mt-0.5 h-3.5 w-3.5 text-primary" />
                            <div>
                              <div className="text-xs uppercase tracking-wide text-muted-foreground">Vacina Principal</div>
                              <div className="text-sm font-medium text-primary">{detalhe.tx_insumo}</div>
                            </div>
                          </div>
                        </>
                      ) : (
                        <div className="mt-2 text-sm font-medium text-muted-foreground">Sem distribuição no período</div>
                      )}
                    </div>
                  );
                })()
              )}

              {selected && (
                <div className="absolute left-2 top-2 z-40 rounded-md bg-white/90 px-3 py-1 text-sm shadow">
                  {selected}
                </div>
              )}
            </div>
          )}
          <div className="mt-4 flex items-center justify-center gap-4 text-sm">
            <div className="flex items-center gap-2">
              <div className="w-4 h-4 rounded" style={{ backgroundColor: "hsl(var(--muted))" }}></div>
              <span className="text-muted-foreground">Menor</span>
            </div>
            <div className="flex items-center gap-2">
              <div className="w-4 h-4 rounded" style={{ backgroundColor: "hsl(var(--primary))" }}></div>
              <span className="text-muted-foreground">Maior</span>
            </div>
          </div>
        </CardContent>
      </Card>
    </motion.div>
  );
};

export default BrazilMap;
