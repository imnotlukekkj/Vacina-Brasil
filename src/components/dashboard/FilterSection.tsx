import { useEffect, useState } from "react";
import { useSearchParams } from "react-router-dom";
import { Button } from "@/components/ui/button";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Label } from "@/components/ui/label";
import { Card, CardContent } from "@/components/ui/card";
import { X } from "lucide-react";
import { useFilterStore } from "@/stores/filterStore";
import { apiClient } from "@/lib/api";

const ANOS = ["2020", "2021", "2022", "2023", "2024"];
const MESES = [
  { value: "01", label: "Janeiro" },
  { value: "02", label: "Fevereiro" },
  { value: "03", label: "Março" },
  { value: "04", label: "Abril" },
  { value: "05", label: "Maio" },
  { value: "06", label: "Junho" },
  { value: "07", label: "Julho" },
  { value: "08", label: "Agosto" },
  { value: "09", label: "Setembro" },
  { value: "10", label: "Outubro" },
  { value: "11", label: "Novembro" },
  { value: "12", label: "Dezembro" },
];
const UFS = [
  "AC", "AL", "AP", "AM", "BA", "CE", "DF", "ES", "GO", "MA", "MT", "MS", 
  "MG", "PA", "PB", "PR", "PE", "PI", "RJ", "RN", "RS", "RO", "RR", "SC", 
  "SP", "SE", "TO"
];
// VACINAS agora carregadas dinamicamente do backend via API

const FilterSection = () => {
  const [searchParams, setSearchParams] = useSearchParams();
  const { ano, mes, uf, vacina, setAno, setMes, setUF, setVacina, clearFilters } = useFilterStore();
  const [vacinasList, setVacinasList] = useState<string[]>([]);
  const [loadingVacinas, setLoadingVacinas] = useState(false);

  // Sincroniza URL com store
  useEffect(() => {
    const anoParam = searchParams.get("ano");
    const mesParam = searchParams.get("mes");
    const ufParam = searchParams.get("uf");
    const vacinaParam = searchParams.get("vacina");

    if (anoParam) setAno(anoParam);
    if (mesParam) setMes(mesParam);
    if (ufParam) setUF(ufParam);
    if (vacinaParam) setVacina(vacinaParam);
  }, []);

  // buscar lista de vacinas do backend
  useEffect(() => {
    let mounted = true;
    setLoadingVacinas(true);
    apiClient
      .getVacinas()
      .then((list) => {
        if (!mounted) return;
        setVacinasList(list);
      })
      .catch((err) => {
        console.error("Erro ao carregar vacinas:", err);
      })
      .finally(() => setLoadingVacinas(false));

    return () => {
      mounted = false;
    };
  }, []);

  // Atualiza URL quando filtros mudam
  useEffect(() => {
    const params = new URLSearchParams();
    if (ano) params.set("ano", ano);
    if (mes) params.set("mes", mes);
    if (uf) params.set("uf", uf);
    if (vacina) params.set("vacina", vacina);
    setSearchParams(params);
  }, [ano, mes, uf, vacina, setSearchParams]);

  const handleClearFilters = () => {
    clearFilters();
    setSearchParams(new URLSearchParams());
  };

  const hasFilters = ano || mes || uf || vacina;

  return (
    <Card>
      <CardContent className="pt-6">
        <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
          <div className="space-y-2">
            <Label htmlFor="ano">Ano</Label>
            <Select value={ano || "all"} onValueChange={(v) => setAno(v === "all" ? "" : v)}>
              <SelectTrigger id="ano">
                <SelectValue placeholder="Todos" />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="all">Todos</SelectItem>
                {ANOS.map((a) => (
                  <SelectItem key={a} value={a}>{a}</SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>

          <div className="space-y-2">
            <Label htmlFor="mes">Mês</Label>
            <Select value={mes || "all"} onValueChange={(v) => setMes(v === "all" ? "" : v)}>
              <SelectTrigger id="mes">
                <SelectValue placeholder="Todos" />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="all">Todos</SelectItem>
                {MESES.map((m) => (
                  <SelectItem key={m.value} value={m.value}>{m.label}</SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>

          <div className="space-y-2">
            <Label htmlFor="uf">UF</Label>
            <Select value={uf || "all"} onValueChange={(v) => setUF(v === "all" ? "" : v)}>
              <SelectTrigger id="uf">
                <SelectValue placeholder="Todas" />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="all">Todas</SelectItem>
                {UFS.map((u) => (
                  <SelectItem key={u} value={u}>{u}</SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>

          <div className="space-y-2">
            <Label htmlFor="vacina">Vacina</Label>
            <Select value={vacina || "all"} onValueChange={(v) => setVacina(v === "all" ? "" : v)}>
              <SelectTrigger id="vacina">
                <SelectValue placeholder="Todas" />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="all">Todas</SelectItem>
                {loadingVacinas ? (
                  <SelectItem value="all">Carregando...</SelectItem>
                ) : (
                  vacinasList.map((i) => (
                    <SelectItem key={i} value={i}>{i}</SelectItem>
                  ))
                )}
              </SelectContent>
            </Select>
          </div>
        </div>

        {hasFilters && (
          <div className="mt-4 flex justify-end">
            <Button variant="outline" size="sm" onClick={handleClearFilters}>
              <X className="mr-2 h-4 w-4" />
              Limpar Filtros
            </Button>
          </div>
        )}
      </CardContent>
    </Card>
  );
};

export default FilterSection;
