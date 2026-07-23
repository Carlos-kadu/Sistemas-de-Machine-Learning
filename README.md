# Sistemas de Machine Learning

Repositório com os trabalhos desenvolvidos para a disciplina de **Sistemas de Machine Learning**. A coleção reúne projetos individuais e em dupla sobre agentes de IA, pipelines de ML, rastreamento de experimentos, automações com n8n, extração estruturada de documentos e deploy de aplicações com API.

## Visão geral

| Pasta | Tema | Principais tecnologias | Entregáveis |
| --- | --- | --- | --- |
| `projeto-1/` | Agente para detecção de anomalias em textos de licitações públicas | Python, Gemini API, regras heurísticas | Código, dados de exemplo e relatório |
| `projeto-2/` | Pipeline de classificação de spam em comentários do YouTube | Python, Hugging Face, MLflow, FastAPI | Fine-tuning, tracking, API e relatório |
| `projeto-3/` | Curadoria automática de artigos científicos | n8n, Gemini, Telegram Bot, Node.js | Workflows, documentação e evidências |
| `projeto-4/` | Pipeline UDA para Relações com Investidores da MRV | Python, Gemini, extração de PDF, API local, dashboard HTML | Coleta, estruturação, API, painel e relatório |
| `TRABALHO-FINAL/` | Agente de previsão de churn com explicação por IA | Python, FastAPI, Docker, Random Forest, Gemini | Aplicação web, API, modelo treinado e relatório |

## Estrutura do repositório

```text
.
├── projeto-1/
│   ├── data/
│   ├── docs/
│   ├── src/
│   └── requirements.txt
├── projeto-2/
│   ├── data/
│   ├── docs/
│   ├── scripts/
│   ├── src/
│   └── README.md
├── projeto-3/
│   ├── docs/
│   ├── solutions/
│   ├── src/
│   └── README.md
├── projeto-4/
│   ├── docs/
│   ├── pipeline/
│   ├── scripts/
│   └── README.md
└── TRABALHO-FINAL/
    ├── 1.1_carlos_patricia/
    ├── readme.md
    └── trilhas.md
```

## Projetos

### Projeto 1 - Anomalias em licitações públicas

Implementa um agente em Python para analisar textos de licitações públicas e sinalizar possíveis inconsistências. O pipeline combina pré-processamento, extração de características, regras determinísticas e chamada à API do Gemini para gerar uma saída estruturada com risco, categoria, justificativa e confiança.

Documentação principal:

- [`projeto-1/docs/documento-engenharia.md`](projeto-1/docs/documento-engenharia.md)
- [`projeto-1/docs/relatorio-entrega.md`](projeto-1/docs/relatorio-entrega.md)

Execução básica:

```bash
cd projeto-1
pip install -r requirements.txt
cp .env.example .env
python src/main.py
```

### Projeto 2 - Classificação de spam com MLflow

Pipeline para classificação de spam em comentários do YouTube. O projeto utiliza um modelo pré-treinado do Hugging Face, realiza adaptação ao domínio dos comentários, registra experimentos no MLflow e expõe inferência por FastAPI.

Documentação principal:

- [`projeto-2/README.md`](projeto-2/README.md)
- [`projeto-2/docs/relatorio-entrega.md`](projeto-2/docs/relatorio-entrega.md)

Execução básica:

```bash
cd projeto-2
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python scripts/finetune.py
python scripts/serve.py
```

### Projeto 3 - Curadoria automática de artigos científicos

Sistema de automação em n8n para triagem de artigos científicos. Foram desenvolvidas três abordagens de solução, incluindo fluxo simples, fluxo com apoio de recuperação de contexto e fluxo mais robusto com validações, confiança e encaminhamento para revisão humana.

Documentação principal:

- [`projeto-3/README.md`](projeto-3/README.md)
- [`projeto-3/docs/relatorio-entrega.md`](projeto-3/docs/relatorio-entrega.md)
- [`projeto-3/docs/adr/001-escolha-da-solucao.md`](projeto-3/docs/adr/001-escolha-da-solucao.md)

Execução básica:

```bash
cd projeto-3
n8n start
node src/solution-b-retriever.js
```

Os workflows ficam em `projeto-3/solutions/`.

### Projeto 4 - Pipeline UDA para RI da MRV

Pipeline para coleta, extração e estruturação de relatórios de resultados da MRV. O sistema baixa PDFs, mantém catálogos de linhagem, extrai métricas com apoio de IA, valida os registros e disponibiliza os dados por API e painel HTML.

Documentação principal:

- [`projeto-4/README.md`](projeto-4/README.md)
- [`projeto-4/docs/documento-engenharia.md`](projeto-4/docs/documento-engenharia.md)
- [`projeto-4/docs/relatorio-entrega.md`](projeto-4/docs/relatorio-entrega.md)

Execução básica:

```bash
cd projeto-4
pip install -r requirements.txt
cp .env.example .env
python3 scripts/download_mrv_reports.py --start-year 2020 --end-year 2026
python3 scripts/extract_mrv_reports.py
python3 scripts/serve_conjuntura_api.py
```

Depois, acesse `http://127.0.0.1:8000/dashboard`.

### Trabalho final - Previsão de churn com explicação por IA

Aplicação de ponta a ponta para previsão de churn em telecomunicações. O sistema treina um modelo tabular, expõe previsões por FastAPI, gera explicações em português com IA generativa e inclui fallback determinístico, guardrails, logs e interface web.

Documentação principal:

- [`TRABALHO-FINAL/readme.md`](TRABALHO-FINAL/readme.md)
- [`TRABALHO-FINAL/trilhas.md`](TRABALHO-FINAL/trilhas.md)
- [`TRABALHO-FINAL/1.1_carlos_patricia/docs/relatorio.md`](TRABALHO-FINAL/1.1_carlos_patricia/docs/relatorio.md)

Execução básica:

```bash
cd TRABALHO-FINAL/1.1_carlos_patricia
docker compose up --build
```

Depois, acesse `http://localhost:8000`.


## Autores

- Carlos Eduardo Rodrigues - 221031265
- Patrícia Helena Macedo da Silva - 221037993, nos projetos desenvolvidos em dupla