import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card";
import { ComposableMap, Geographies, Geography } from "react-simple-maps";
import { motion } from "framer-motion";
import React, { useState } from "react";
import { scaleLinear } from "d3-scale";

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

const BrazilMap = ({ data, loading, selectedUF = null }: BrazilMapProps) => {
  const [hover, setHover] = useState<{ name: string; x: number; y: number; visible: boolean }>({
    name: "",
    x: 0,
    y: 0,
    visible: false,
  });
  // reflect externally selected UF first (from filters). Local clicks still override.
  const [selected, setSelected] = useState<string | null>(selectedUF || null);

  // keep selected in sync if parent filter changes
  React.useEffect(() => {
    setSelected(selectedUF || null);
  }, [selectedUF]);
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
      d.sigla === stateName || d.uf.toLowerCase() === stateName.toLowerCase()
    );
    // If an external filter selected a UF, only highlight that state; others should be muted
    if (selectedUF) {
      const matches = stateData && (stateData.sigla === selectedUF || stateData.uf.toLowerCase() === String(selectedUF).toLowerCase());
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
            <div className="w-full h-96 relative">
              <ComposableMap
                projection="geoMercator"
                projectionConfig={{
                  scale: 600,
                  center: [-55, -15],
                }}
              >
                <Geographies geography={geoUrl}>
                  {({ geographies }) =>
                    geographies.map((geo) => {
                      const stateName = geo.properties.sigla || geo.properties.name;
                      const isSelected = selected === stateName;
                      return (
                        <Geography
                          key={geo.rsmKey}
                          geography={geo}
                          fill={getColorForState(stateName)}
                          stroke={isSelected ? "hsl(var(--primary))" : "hsl(var(--border))"}
                          strokeWidth={isSelected ? 1.5 : 0.5}
                          onMouseEnter={(evt) => {
                            const name = stateName;
                            setHover({ name, x: evt.clientX + 12, y: evt.clientY + 12, visible: true });
                          }}
                          onMouseMove={(evt) => {
                            setHover(h => (h.visible ? { ...h, x: evt.clientX + 12, y: evt.clientY + 12 } : h));
                          }}
                          onMouseLeave={() => setHover(h => ({ ...h, visible: false }))}
                          onClick={() => setSelected(stateName)}
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

              {hover.visible && (
                <div
                  className="pointer-events-none fixed z-50 rounded-md px-2 py-1 bg-white/90 text-sm shadow"
                  style={{ left: hover.x, top: hover.y }}
                >
                  {hover.name}
                </div>
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
