Endpoint /api/previsao (RPC)

Adicionalmente, existe um endpoint específico usado pelo frontend para obter a série histórica e a previsão de 2025 para um insumo (vacina).

- Rota: `GET /api/previsao`
- Parâmetros de query:
  - `insumo_nome` (obrigatório): nome normalizado da vacina (ex.: `Covid-19`).
  - `uf` (opcional): código/identificador da unidade (ex.: `PR`).
  - `mes` (opcional): número do mês (1-12) para filtrar por mês across years.
  - `debug` (opcional): `true` para incluir o payload RPC bruto (`rpc_raw`) na resposta.

Este endpoint chama a função Postgres `public.obter_historico_e_previsao_vacinacao` que deve devolver uma lista JSON com objetos no formato:

```json
{ "ano": 2020, "quantidade": 12345, "tipo_dado": "historico" }
```

Em particular, a função deve:
- Agregar o histórico por `ANO` (SUM de `QTDE`) para 2020–2024 e retornar linhas com `tipo_dado = 'historico'`.
- Calcular a previsão para 2025 como a média (`AVG`) dos anos disponíveis (2020–2024) e retornar uma linha `tipo_dado = 'previsao'` apenas quando a média for maior que zero.

Observações práticas
- Caso a sua tabela já possua uma coluna normalizada (por exemplo `tx_insumo_norm`) a função deve preferir usá-la para matching; caso contrário pode casar por `TX_INSUMO` com `ILIKE` ou usar os padrões em `vacina_mappings`.
- Se quiser correspondência mais tolerante a acentos, adicione a extensão `unaccent` no Postgres: `CREATE EXTENSION IF NOT EXISTS unaccent;` e use `unaccent(lower(...))` nas comparações.

Exemplo de teste (RPC direto via PostgREST):

```bash
export $(grep -v '^#' backend/.env | xargs)
curl -s -X POST "$SUPABASE_URL/rest/v1/rpc/obter_historico_e_previsao_vacinacao" \
  -H "apikey: $SUPABASE_SERVICE_ROLE_KEY" \
  -H "Authorization: Bearer $SUPABASE_SERVICE_ROLE_KEY" \
  -H "Content-Type: application/json" \
  -d '{"_insumo_nome":"Covid-19","_uf":"PR","_mes":10}' | jq
```

Depois de aplicar a função no banco, o frontend (`src/pages/Dashboard.tsx`) já está preparado para consumir o array retornado e mesclar os pontos históricos + previsão no gráfico de previsão (`ForecastChart.tsx`).
