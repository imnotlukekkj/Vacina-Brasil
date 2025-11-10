Backend — Documentação rápida

Visão geral

Este diretório contém um protótipo de backend em Python (FastAPI) que normaliza dinamicamente os campos `TX_INSUMO` e `TX_SIGLA` usando padrões em `backend/mappings.json`.

O objetivo é fornecer um serviço on-the-fly que o frontend possa consultar para obter valores normalizados (por exemplo, `tx_insumo_norm` e `tx_sigla_norm`) sem exigir migração imediata do banco.

Arquivos relevantes

- backend/app.py
  - Servidor FastAPI com endpoints:
    - GET /normalize?tx_insumo=...&tx_sigla=...  — retorna normalização de um único registro
    - GET /overview — agregação de doses (usa arquivos locais como fallback)
    - GET /timeseries — série temporal (usa arquivos locais como fallback)
    - GET /ranking/ufs — ranking por UF (usa arquivos locais como fallback)
    - GET /forecast — previsão simples (exemplo)

- backend/normalizer.py
  - Carrega `backend/mappings.json` e expõe:
    - normalize_insumo(tx_insumo) -> vacina_normalizada | None
    - normalize_sigla(tx_sigla) -> UF (ex.: 'PR') | None

- backend/mappings.json
  - JSON com objetos: {"vacina_normalizada", "pattern", "pattern_type", "priority"}
  - Edite este arquivo para adicionar/ajustar padrões. Menor `priority` = maior precedência.

- backend/etl_normalize.py
  - Script utilitário para rodar a normalização em lote sobre arquivos JSON (ETL offline).

Como rodar localmente

1. (Recomendado) criar e ativar um virtualenv

```bash
python -m venv .venv
source .venv/bin/activate
```

2. Instalar dependências necessárias

```bash
# instalar a partir do requirements.txt (recomendado)
pip install -r backend/requirements.txt
```

3. Iniciar o servidor

```bash
# opcional: defina DATABASE_URL e DATA_TABLE para conectar ao Supabase/Postgres
export DATABASE_URL=postgres://user:password@dbhost:5432/dbname
export DATA_TABLE=distribuicao

python -m uvicorn backend.app:app --reload --port 8000
```

Fallback via Supabase (PostgREST / HTTPS)

Se você não puder usar conexão direta ao banco (por exemplo, quando o projeto Supabase exige add-on IPv4 pago para conexões diretas), o backend agora suporta um fallback que consulta o endpoint REST do Supabase (PostgREST) via HTTPS. Para usar esse modo, exporte as seguintes variáveis de ambiente no seu terminal (NUNCA publique a service_role key em chat público):

```bash
export SUPABASE_URL="https://<your-project>.supabase.co"
export SUPABASE_SERVICE_ROLE_KEY="<service_role_key>"
export DATA_TABLE=distribuicao

# então rode o servidor normalmente
python -m uvicorn backend.app:app --reload --port 8000
```

O backend tentará, nesta ordem:
1) usar `DATABASE_URL` + asyncpg (conexão direta ao Postgres)
2) usar `SUPABASE_URL` + `SUPABASE_SERVICE_ROLE_KEY` (PostgREST HTTPS)
3) fallback para arquivos JSON locais em `backend/`

Observações de segurança: a `SERVICE_ROLE` tem privilégios de escrita/leitura totais — mantenha-a apenas no servidor (variáveis de ambiente) e não a inclua no frontend. Para produção, prefere-se um endpoint de backend que encapsule essas credenciais e aplique regras de autorização.

Testes rápidos

- Normalizar um insumo:
  - GET http://localhost:8000/normalize?tx_insumo=VACINA%20ORAL%20CONTRA%20POLIOMIELITE&tx_sigla=SES-PR

- Overview (usa arquivos locais caso não haja DB):
  - GET http://localhost:8000/overview?ano=2021&uf=PR&fabricante=Poliomielite

Notas importantes

- O backend atual NÃO grava nada no banco. Ele aplica normalização on-the-fly e retorna resultados para o frontend.
- Para produção, recomenda-se:
  1) Persistir `tx_insumo_norm` e `tx_sigla_norm` no banco (Supabase/Postgres) e indexar essas colunas.
  2) Mover os patterns para uma tabela `insumo_mappings` no banco para permitir updates sem deploy.

Próximos passos que posso executar

- Limpar o repositório (remover artefatos ETL redundantes) e manter apenas o backend on-the-fly.
- Implementar conexão direta com Supabase para que os endpoints consultem dados reais.
- Implementar endpoint administrativo que execute um backfill (aplica normalização e grava no banco).

Diga qual dessas opções prefere e eu implemento em seguida.
