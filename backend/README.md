# Backend helpers — mapeamento TX_INSUMO → vacina_normalizada

Arquivos criados:


Como usar (PowerShell):

```powershell
# Normalizar um arquivo data.json e gravar em um arquivo de saída escolhido
python backend/etl_normalize.py --input data.json --output <output.json>

# Para aplicar no banco (Supabase/Postgres):
# 1) Rode `insumo_mappings_seed.sql` contra seu banco (psql ou via Supabase SQL Editor).
# 2) Use o script ETL para popular a coluna `tx_insumo_norm` ou executar atualizações via SQL
#    (ex.: UPDATE distribuicao SET tx_insumo_norm = '...' WHERE tx_insumo ILIKE '%...%')
```

Observações:
  você provavelmente precisará ajustar `mappings.json` (novos padrões ou prioridades).
# Backend — visão geral e referência

Este diretório contém o protótipo do backend em Python (FastAPI) usado pelo projeto. O foco principal é
fornecer normalização on-the-fly para os campos `TX_INSUMO` e `TX_SIGLA` usando regras em `backend/mappings.json`.

Conteúdo e arquivos principais

- `app.py` — servidor FastAPI com endpoints públicos e lógica de fallback (DB → Supabase REST → JSON local).
- `normalizer.py` — carrega `backend/mappings.json` e expõe métodos para normalizar insumo e sigla.
- `mappings.json` — padrões (regex) usados para mapear `TX_INSUMO` → `vacina_normalizada`.
- `etl_normalize.py` — script utilitário para normalização em lote (ETL offline).
- `repositories/`, `routers/`, `schemas/`, `utils/` — organização por camadas (dados, rotas, schemas, utilitários).

Principais endpoints (resumo)

- `GET /normalize?tx_insumo=...&tx_sigla=...` — normaliza um único registro e retorna `tx_insumo_norm` / `tx_sigla_norm`.
- `GET /overview` — agregações (usa DB ou fallback local).
- `GET /timeseries` — série temporal (DB ou fallback local).
- `GET /ranking/ufs` — ranking por UF (DB ou fallback local).
- `GET /api/previsao` — rota específica que retorna histórico + previsão (veja seção "Previsão / RPC" abaixo).

Como rodar localmente

PowerShell (Windows):

```powershell
# criar e ativar venv (opcional)
python -m venv .venv
.\\.venv\\Scripts\\Activate.ps1

# instalar dependências
pip install -r backend/requirements.txt

# rodar o servidor (exemplo)
python -m uvicorn backend.app:app --reload --port 8000
```

Recomendação de runtime
-----------------------

Para evitar incompatibilidades com bibliotecas (por exemplo `httpx`/`httpcore`) e garantir comportamento consistente entre ambientes, recomendamos usar Python 3.11 para o backend. Você pode criar um virtualenv específico nomeado `.venv311` como no exemplo abaixo:

```powershell
py -3.11 -m venv backend\.venv311
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
.\backend\.venv311\Scripts\Activate.ps1
python -m pip install --upgrade pip
pip install -r backend\requirements.txt
python -m uvicorn backend.app:app --reload --port 8000
```

No deploy (Render/Heroku/Outros), assegure que o runtime esteja configurado para Python 3.11 (veja `runtime.txt` na raiz do repositório).

Bash / macOS / Linux:

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r backend/requirements.txt
python -m uvicorn backend.app:app --reload --port 8000
```

Configuração e fallback de dados

O backend tenta, nesta ordem, obter dados reais:
1. Conexão direta ao Postgres via `DATABASE_URL` (asyncpg)
2. PostgREST do Supabase via `SUPABASE_URL` + `SUPABASE_SERVICE_ROLE_KEY` (HTTP)
3. Arquivos JSON locais dentro de `backend/` (fallback)

Para usar o modo Supabase REST, exporte (NUNCA compartilhe a service role key publicamente):

```bash
export SUPABASE_URL="https://<your-project>.supabase.co"
export SUPABASE_SERVICE_ROLE_KEY="<service_role_key>"
export DATA_TABLE=distribuicao
```

Observações de segurança: a `SERVICE_ROLE` tem privilégios elevados — guarde-a apenas no servidor.

ETL (normalização offline)

Use `backend/etl_normalize.py` para aplicar os mapeamentos a um arquivo JSON local e gerar um arquivo de saída qualquer:

```powershell
python backend/etl_normalize.py --input data.json --output out_normalized.json
```

Documentação sobre previsão / RPC (resumo)

O endpoint `/api/previsao` chama a função Postgres `public.obter_historico_e_previsao_vacinacao` e espera receber uma
lista de objetos JSON com elementos no formato:

```json
{ "ano": 2020, "quantidade": 12345, "tipo_dado": "historico" }
```

Regras esperadas da função RPC:
- Retornar linhas agregadas por `ANO` (2020–2024) com `tipo_dado = 'historico'`.
- Retornar uma linha `tipo_dado = 'previsao'` para 2025 (por exemplo, média dos anos anteriores) quando aplicável.

Exemplo de chamada RPC via PostgREST (teste):

```bash
export $(grep -v '^#' backend/.env | xargs)
curl -s -X POST "$SUPABASE_URL/rest/v1/rpc/obter_historico_e_previsao_vacinacao" \
  -H "apikey: $SUPABASE_SERVICE_ROLE_KEY" \
  -H "Authorization: Bearer $SUPABASE_SERVICE_ROLE_KEY" \
  -H "Content-Type: application/json" \
  -d '{"_insumo_nome":"Covid-19","_uf":"PR","_mes":10}' | jq
```

Notas sobre arquivos `normalized.json` e `normalized_vacinas.json`

Estes arquivos antigos foram removidos do fluxo ativo para evitar confusão: o `app.py` agora prefere arquivos mais explícitos
(`normalized_vacinas_rerun2.json`, `normalized_vacinas_rerun.json`) como candidates locais. Caso precise de backups dos arquivos
anteriores, crie uma pasta `backend/archive/` e armazene-os lá.

Práticas recomendadas para produção

- Persistir `tx_insumo_norm` e `tx_sigla_norm` no banco e indexar as colunas para consultas rápidas.
- Mover `mappings.json` para uma tabela `insumo_mappings` e expor um endpoint administrativo para atualizar padrões sem deploy.
- Evitar exposição da `SUPABASE_SERVICE_ROLE_KEY` no frontend; sempre encapsular chamadas sensíveis no backend.

Próximos passos sugeridos

- Implementar endpoint de backfill que aplica a normalização em massa e grava no banco.
- Adicionar testes unitários para `normalize_row` e para os wrappers do Supabase.
- Remover artefatos ETL redundantes e manter um procedimento claro de backfill/seed.

-----

Se quiser, posso:
- aplicar o backfill (script) — preciso das credenciais e da confirmação;
- adicionar testes unitários e CI;
- mover os arquivos antigos para `backend/archive/` e confirmar a remoção do repo.
