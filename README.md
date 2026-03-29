#  Vacina Brasil  Dashboard Nacional de Distribuição de Vacinas

Aplicação para visualização e análise de dados públicos sobre distribuição de vacinas no Brasil. O repositório contém o frontend (React + TypeScript) e um backend protótipo em FastAPI usado como fonte de dados e para normalização.

## Visão rápida
- Interface com KPIs, séries temporais e mapa do Brasil por UF.
- Filtros dinâmicos: ano, mês, UF e vacina/insumo.
- Previsões simples (heurísticas) para 2025 quando aplicável.

## Stack e bibliotecas principais
- Frontend: React 18 + TypeScript (Vite)
- UI: TailwindCSS + shadcn/ui
- Estado: Zustand
- Visualização: Recharts (gráficos) + react-simple-maps (mapa)
- Backend: FastAPI (Python)

## Como as previsões funcionam (resumo)
- Fonte de dados: o backend lê dados brutos (via Supabase REST/RPC quando configurado) ou usa arquivos JSON locais como fallback no desenvolvimento.
- `GET /api/timeseries`: retorna séries agregadas por `ano`+`mes` no formato `{ data: "YYYY-MM", doses_distribuidas: number }`.
- `GET /api/forecast`:
  - Se o filtro incluir `mes`, a projeção é calculada como a média histórica simples daquele mês (por exemplo, média dos meses `MM` entre os anos disponíveis) e é retornada para `2025-MM`.
  - Se não houver `mes`, a projeção anual é a média aritmética dos totais anuais disponíveis e usada como estimativa para 2025.
  - Endpoints como `/previsao` e `/previsao/comparacao` podem delegar a funções RPC no banco; o backend valida e aplica fallbacks (mediana, média recente) quando necessário.

## Executando localmente

### Windows (PowerShell)
```powershell
cd backend
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
uvicorn app:app --reload --port 8000

# em outro terminal, no diretório raiz:
cd ..
npm install
npm run dev
```

### Linux / macOS
```bash
python -m venv .venv
source .venv/bin/activate
pip install -r backend/requirements.txt
python -m uvicorn backend.app:app --reload --port 8000

# em outro terminal
npm install
npm run dev
```

## Script helper
- Há um `run_dev.ps1` para facilitar o desenvolvimento em Windows (inicia frontend + backend). Verifique a política de execução do PowerShell antes de rodar.

## Endpoints úteis (resumo)
- `GET /api/overview`  `{ total_doses: number, periodo?: string }`
- `GET /api/timeseries`  `[{ data: "YYYY-MM", doses_distribuidas: number }, ...]`
- `GET /api/ranking/ufs`  lista `{ uf, sigla, doses_distribuidas }` ordenada
- `GET /api/forecast`  previsão simplificada (ver seção acima)
- `GET /previsao` e `/previsao/comparacao`  endpoints que podem exigir parâmetros e delegam a RPCs no banco

## Notas operacionais e recomendações
- Não versionar ambientes virtuais (`.venv`)  adicione-os ao `.gitignore`.
- Recomenda-se Python 3.11 para compatibilidade com dependências.
- A `SUPABASE_SERVICE_ROLE_KEY` é sensível  nunca a exponha no frontend.
- Para produção, recomenda-se persistir `tx_insumo_norm` no banco e indexar as colunas de busca para melhor desempenho.

## Desenvolvimento e qualidade
- Rode `npm run lint` e `npm run build` antes de abrir PRs.
- Tests: ainda não há uma suíte de testes automatizada; posso ajudar a adicionar testes unitários para o normalizador e para rotas do backend.

## Mais detalhes do backend
- Veja `backend/README.md` para explicações técnicas adicionais, exemplos de RPC e comportamento de fallback.
