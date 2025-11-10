# Welcome to your Lovable project

## Project info

**URL**: https://lovable.dev/projects/84027fd2-5b7f-4527-90f2-3bee09608788

## How can I edit this code?

There are several ways of editing your application.

**Use Lovable**

Simply visit the [Lovable Project](https://lovable.dev/projects/84027fd2-5b7f-4527-90f2-3bee09608788) and start prompting.

Changes made via Lovable will be committed automatically to this repo.

**Use your preferred IDE**

If you want to work locally using your own IDE, you can clone this repo and push changes. Pushed changes will also be reflected in Lovable.

The only requirement is having Node.js & npm installed - [install with nvm](https://github.com/nvm-sh/nvm#installing-and-updating)

Follow these steps:

```sh
# Step 1: Clone the repository using the project's Git URL.
git clone <YOUR_GIT_URL>

# Step 2: Navigate to the project directory.
cd <YOUR_PROJECT_NAME>

# Step 3: Install the necessary dependencies.
npm i

# Step 4: Start the development server with auto-reloading and an instant preview.
npm run dev
```

**Edit a file directly in GitHub**

- Navigate to the desired file(s).
- Click the "Edit" button (pencil icon) at the top right of the file view.
- Make your changes and commit the changes.

**Use GitHub Codespaces**

- Navigate to the main page of your repository.
- Click on the "Code" button (green button) near the top right.
- Select the "Codespaces" tab.
- Click on "New codespace" to launch a new Codespace environment.
- Edit files directly within the Codespace and commit and push your changes once you're done.

## What technologies are used for this project?

This project is built with:

- Vite
- TypeScript
- React
- shadcn-ui
- Tailwind CSS

## How can I deploy this project?

Simply open [Lovable](https://lovable.dev/projects/84027fd2-5b7f-4527-90f2-3bee09608788) and click on Share -> Publish.

## Can I connect a custom domain to my Lovable project?

Yes, you can!

To connect a domain, navigate to Project > Settings > Domains and click Connect Domain.

Read more here: [Setting up a custom domain](https://docs.lovable.dev/features/custom-domain#custom-domain)

## Backend (normalização on-the-fly)

Este repositório também inclui um backend Python/FastAPI simples para normalizar dinamicamente os campos recebidos do dataset (por exemplo, `TX_INSUMO` e `TX_SIGLA`). Ele é usado apenas como protótipo para que o frontend possa consumir dados já normalizados sem necessidade de migrar/atualizar o banco imediatamente.

- Localização: `backend/`
- Arquivos principais:
	- `backend/app.py` — servidor FastAPI mínimo com endpoints de exemplo (`/normalize`, `/overview`, `/timeseries`, `/ranking/ufs`, `/forecast`).
	- `backend/normalizer.py` — módulo que carrega `backend/mappings.json` e aplica regex para mapear `TX_INSUMO` → `tx_insumo_norm` e `TX_SIGLA` → `tx_sigla_norm`.
	- `backend/mappings.json` — patterns usados para normalização (padrões regex e prioridades).
	- `backend/etl_normalize.py` — script utilitário para rodar o ETL offline e gerar JSONs normalizados (útil para backfill).

Como executar localmente:

```bash
# criar/ativar venv e instalar dependências
python -m venv .venv
source .venv/bin/activate
pip install fastapi uvicorn

# iniciar servidor (porta 8000)
python -m uvicorn backend.app:app --reload --port 8000
```

Endpoints úteis:
- `GET /normalize?tx_insumo=...&tx_sigla=...` — retorna os campos normalizados (útil para testar um único registro).
- `GET /overview` — versão de exemplo que usa os JSONs locais quando não há DB; aceita filtros `ano`, `mes`, `uf`, `fabricante`.

Se for integrar com Supabase em produção, a recomendação é persistir `tx_insumo_norm` e `tx_sigla_norm` no banco e migrar os patterns para uma tabela (`insumo_mappings`) para facilitar atualizações sem deploy.

