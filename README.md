# 🩺 Vacina Brasil - Dashboard Nacional de Distribuição de Vacinas

Dashboard interativo e responsivo para visualização e análise de dados oficiais de distribuição e aplicação de vacinas em todo o território nacional.

## 📋 Sobre o Projeto

Este projeto acadêmico oferece uma interface moderna para acompanhamento em tempo real da campanha de vacinação nacional, com:

- **KPIs em tempo real**: Doses distribuídas, aplicadas, estoque e taxa de aplicação
- **Série temporal interativa**: Evolução das doses ao longo do tempo
- **Mapa do Brasil**: Visualização geográfica por UF
-- **Filtros dinâmicos**: Ano, mês, UF e fabricante/vacina
- **Design responsivo**: Funciona perfeitamente em desktop, tablet e mobile

## 🚀 Stack Tecnológica

- **Frontend**: React 18 + TypeScript + Vite
- **UI**: TailwindCSS + shadcn/ui
- **Gerenciamento de Estado**: Zustand
- **Visualização de Dados**: Recharts + react-simple-maps
- **Animações**: Framer Motion
- **Backend**: FastAPI (integração via REST API)

## 📦 Instalação

```bash
# Clone o repositório
git clone <seu-repositorio>
cd <nome-do-projeto>

# Instale as dependências
npm install

# Configure as variáveis de ambiente
cp .env.example .env
# Edite o arquivo .env e configure VITE_BASE_API_URL
```

## ⚙️ Configuração do Backend

O dashboard consome dados de uma API FastAPI. Configure a URL base no arquivo `.env`:

```env
VITE_BASE_API_URL=http://localhost:8000
```

### Endpoints Esperados

O backend deve expor os seguintes endpoints:

#### 1. GET `/overview`
Retorna KPIs agregados.

**Query Params**: `ano`, `mes`, `uf`, `fabricante` (todos opcionais)

**Resposta esperada**:
```json
{
	"total_doses": 1000000,
	"total_aplicadas": 850000,
	"total_estoque": 150000,
	"taxa_aplicacao": 85.0,
	"periodo": "2024-01"
}
```

#### 2. GET `/timeseries`
Retorna série temporal de distribuição.

**Query Params**: `ano`, `mes`, `uf`, `fabricante` (todos opcionais)

**Resposta esperada**:
```json
[
	{
		"data": "2024-01-01",
		"doses_distribuidas": 100000,
		"doses_aplicadas": 85000,
		"doses_estoque": 15000
	},
	...
]
```

#### 3. GET `/ranking/ufs`
Retorna dados agregados por UF.

**Query Params**: `ano`, `mes`, `uf`, `fabricante` (todos opcionais)

**Resposta esperada**:
```json
[
	{
		"uf": "São Paulo",
		"sigla": "SP",
		"doses_distribuidas": 500000,
		"doses_aplicadas": 450000,
		"doses_estoque": 50000,
		"taxa_aplicacao": 90.0
	},
	...
]
```

### Importante: Conversão de Parâmetros

O frontend exibe o filtro como **"Vacina"** (para facilitar a seleção do tipo de vacina), mas envia o valor como **"fabricante"** para a API. Esta conversão é feita automaticamente no cliente.

## 🏃 Executando o Projeto

```bash
# Modo desenvolvimento
npm run dev

# Build para produção
npm run build

# Preview da build
npm start
```

O aplicativo estará disponível em `http://localhost:8080`

### Windows (PowerShell)

Se você estiver em um ambiente Windows com PowerShell, há um script auxiliar `run_dev.ps1` que inicia o backend e o frontend juntos. Se a política de execução do PowerShell impedir a execução do script, pode temporariamente permitir com:

```powershell
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
.\run_dev.ps1
```

O script criará (se necessário) um virtualenv em `.venv`, instalará as dependências Python do backend, iniciará o servidor FastAPI (uvicorn) em background, criará um `.env.local` apontando para `http://localhost:8000` e executará `npm run dev`.

## Python runtime (backend)

O backend é um projeto Python (FastAPI) e deve ser executado com uma versão estável do Python 3.11.
Recomendamos criar um virtualenv com Python 3.11 (por exemplo `backend/.venv311`) e executar o servidor como módulo para garantir que os imports relativos funcionem corretamente:

```powershell
# criar venv com Python 3.11 (Windows PowerShell)
py -3.11 -m venv backend\.venv311
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
.\backend\.venv311\Scripts\Activate.ps1
python -m pip install --upgrade pip
pip install -r backend\requirements.txt
python -m uvicorn backend.app:app --reload --port 8000
```

Para deploy em plataformas como Render, adicione (ou garanta) que o runtime esteja definido como Python 3.11 (veja `runtime.txt` no repositório). Isso evita incompatibilidades com bibliotecas como `httpx`/`httpcore` em versões mais novas do Python.

## 📁 Estrutura do Projeto

```
src/
├── components/
│   └── dashboard/
│       ├── FilterSection.tsx    # Filtros do dashboard
│       ├── KPICards.tsx         # Cards de indicadores
│       ├── TimeseriesChart.tsx  # Gráfico de série temporal
│       └── BrazilMap.tsx        # Mapa interativo do Brasil
├── lib/
│   └── api.ts                   # Cliente da API
├── pages/
│   ├── Landing.tsx              # Página inicial
│   ├── Dashboard.tsx            # Dashboard principal
│   └── About.tsx                # Página sobre
├── stores/
│   └── filterStore.ts           # Store Zustand para filtros
└── index.css                    # Design system
```

## 🎨 Design System

O projeto utiliza um design system baseado em tokens semânticos:

- **Primário (Verde)**: `hsl(158 64% 52%)` - Representa saúde
- **Secundário (Azul)**: `hsl(217 91% 60%)` - Representa confiança institucional
- **Gradientes**: Definidos em CSS variables para consistência
- **Sombras**: Sistema de elevação com múltiplos níveis
- **Animações**: Transições suaves com Framer Motion

## 🔄 Sincronização de Filtros

Os filtros do dashboard são:
- Sincronizados com a URL via query params
- Persistidos no estado global com Zustand
- Atualizados em tempo real em todos os componentes

Exemplo de URL: `/dashboard?ano=2024&mes=01&uf=SP&vacina=Pfizer` (o frontend agora envia `vacina`; o backend ainda aceita `fabricante` como parâmetro para compatibilidade)

## 🧪 Desenvolvimento

### Lint
```bash
npm run lint
```

### Type Check
```bash
npm run type-check
```

## 📊 Funcionalidades Implementadas

- ✅ Landing page animada com CTA
- ✅ Dashboard com filtros dinâmicos
- ✅ KPIs em cards responsivos
- ✅ Série temporal com Recharts
- ✅ Mapa do Brasil com react-simple-maps
- ✅ Estados de loading, erro e vazio
- ✅ Sincronização URL ↔ Estado
- ✅ Design responsivo e acessível
- ✅ Página sobre o projeto
- ✅ SEO otimizado

## 🌐 Deploy

O projeto está pronto para deploy em plataformas como:
- Vercel
- Netlify
- GitHub Pages
- Lovable (recomendado)

Certifique-se de configurar a variável `VITE_BASE_API_URL` no ambiente de produção.

## 📝 Licença

Projeto acadêmico desenvolvido para fins educacionais.

## 👥 Autores

Desenvolvido como trabalho acadêmico.

## 🔗 Links Úteis

- [OpenDataSUS](https://opendatasus.saude.gov.br/)
- [Ministério da Saúde](https://www.gov.br/saude/pt-br)
- [React](https://react.dev/)
- [shadcn/ui](https://ui.shadcn.com/)
- [Recharts](https://recharts.org/)

## Nota sobre Projeção Nacional Total

Quando o usuário solicita a comparação no modo "Totais Nacionais" (sem especificar um
`insumo_nome`), o backend utiliza um fallback estatístico estável para calcular a
projeção do ano seguinte. Em caso de falha ou indisponibilidade da função RPC de
projeção, o sistema calcula a **Mediana Aritmética** dos totais anuais agregados
para os anos de 2020 a 2024 e usa esse valor como a quantidade projetada para 2025.

Essa abordagem foi escolhida por sua robustez contra outliers e instabilidades na
regressão linear quando aplicada aos totais agregados.

````

