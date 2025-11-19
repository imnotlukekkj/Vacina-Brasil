import { create } from "zustand";

export interface FilterState {
  ano: string;
  mes: string;
  uf: string;
  vacina: string; // No backend usamos 'fabricante'; no frontend este filtro é exibido como 'Vacina'
  
  setAno: (ano: string) => void;
  setMes: (mes: string) => void;
  setUF: (uf: string) => void;
  setVacina: (vacina: string) => void;
  clearFilters: () => void;
  
  // Converte o valor selecionado (UI: 'Vacina') para o parâmetro esperado pela API ('fabricante')
  getAPIParams: () => {
    ano?: string;
    mes?: string;
    uf?: string;
    fabricante?: string;
  };
}

export const useFilterStore = create<FilterState>((set, get) => ({
  ano: "",
  mes: "",
  uf: "",
  vacina: "",
  
  setAno: (ano) => set({ ano }),
  setMes: (mes) => set({ mes }),
  setUF: (uf) => set({ uf }),
  setVacina: (vacina) => set({ vacina }),
  
  clearFilters: () => set({ ano: "", mes: "", uf: "", vacina: "" }),
  
  getAPIParams: () => {
    const state = get();
    const params: Partial<{ ano: string; mes: string; uf: string; fabricante: string }> = {};
    if (state.ano) params.ano = state.ano;
    if (state.mes) params.mes = state.mes;
    if (state.uf) params.uf = state.uf;
    if (state.vacina) params.fabricante = state.vacina; // Conversão (UI Vacina) → fabricante
    return params;
  },
}));
