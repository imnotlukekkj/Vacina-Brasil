# Backend - Vacina Brasil

Este diretório contém a API que fornece os dados usados pelo frontend. O backend processa dados públicos, normaliza e expõe endpoints REST para consumo.

O que faz o backend
- Carrega e normaliza dados de distribuição de vacinas.
- Expõe endpoints para: overview (KPIs), séries temporais, ranking por UF, previsões/projeções e comparações.
- Calcula projeções (2025) usando séries históricas e retorna intervalos de confiança quando disponíveis.

Como rodar localmente (Windows - PowerShell)
```powershell
cd backend
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
uvicorn services.main:app --reload --port 8000
```

Variáveis de ambiente
- O backend pode depender de variáveis (ex.: chaves de API, URL de banco). Confira `backend/env_utils.py` e configure conforme necessário.

## Backend - visão precisa

O backend fornece endpoints REST usados pelo frontend e implementa lógica de normalização e alguns cálculos de previsão. Abaixo estão os detalhes corretos e atualizados sobre comportamento e opções de execução.

Comportamento real dos endpoints (resumo)
- `GET /api/overview`: retorna um objeto simples com `total_doses` e `periodo` (não expõe, por padrão, métricas derivadas como doses aplicadas ou estoque).
- `GET /api/timeseries`: agrega as linhas por `ANO`+`MES` e retorna `[{ data: "YYYY-MM", doses_distribuidas: number }, ...]`.
- `GET /api/ranking/ufs`: agrega por UF e retorna `{ uf, sigla, doses_distribuidas }` ordenado por total.
- `GET /api/forecast`: faz previsões simples com base em médias históricas (média mensal quando `mes` informado; média anual quando não há `mes`).
- `/previsao` e `/previsao/comparacao` (e `/api/previsao/comparacao`): chamam RPCs no banco (Supabase) para obter histórico + projeção quando disponíveis; o backend aplica heurísticas e fallbacks caso a RPC retorne dados inconsistentes.

Fontes de dados e normalização
- O backend tenta obter dados via Supabase REST/RPC quando as variáveis `SUPABASE_URL` e `SUPABASE_SERVICE_ROLE_KEY` estão configuradas.
- Em ausência do Supabase, há fallback para arquivos JSON locais (fixtures) para permitir desenvolvimento offline.
- O `normalizer` (arquivo `backend/normalizer.py` e `mappings.json`) mapeia nomes brutos de insumos (`TX_INSUMO`) para nomes normalizados, ajudando a reconciliar variações de texto.

Como rodar (exemplos)
PowerShell (Windows):
```powershell
cd backend
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
uvicorn app:app --reload --port 8000
```

Bash / macOS / Linux:
```bash
python -m venv .venv
source .venv/bin/activate
pip install -r backend/requirements.txt
python -m uvicorn backend.app:app --reload --port 8000
```

Variáveis de ambiente importantes
- `SUPABASE_URL` e `SUPABASE_SERVICE_ROLE_KEY` — habilitam uso do Supabase (REST e RPC).
- `DATA_TABLE` / `RAW_DATA_TABLE` — nomes de tabela usados na leitura.

Notas operacionais
- Evite versionar `.venv` no repositório; adicione-o ao `.gitignore` se necessário.
- A `SERVICE_ROLE` do Supabase tem privilégios elevados: mantenha-a apenas no servidor/back-end e nunca no frontend ou em repositórios públicos.

Sobre previsões e comparações (detalhe técnico)
- `GET /api/forecast` usa médias simples:
  - com `mes`: média simples dos valores daquele mês ao longo dos anos disponíveis (retorna um ponto para `2025-MM`).
  - sem `mes`: média aritmética dos totais anuais para projeção de `2025`.
- `/previsao` e `/previsao/comparacao` chamam RPCs no banco e podem retornar estruturas mais ricas (histórico + previsão). O backend valida e aplica heurísticas:
  - se o RPC retornar somente um ponto isolado (por exemplo apenas uma previsão com quantidade zero), o backend trata como "sem dados" e retorna 404/erro apropriado para evitar gráficos enganosos;
  - se a projeção recebida for muito divergente do histórico, o backend tenta um fallback (ex.: média dos últimos anos ou mediana de totais) antes de responder.

Se quiser que eu adicione exemplos `curl` para testar cada rota ou um diagrama simples do fluxo de dados (Supabase → normalizer → endpoints → frontend), eu atualizo esse README com os exemplos.
