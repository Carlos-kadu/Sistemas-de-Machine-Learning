# Projeto 4 - Pipeline UDA para RI da MRV

> **Aluno(a):** Carlos Eduardo Rodrigues e Patrícia Helena Macedo da Silva
> **Matrícula:** 221031265; 221037993

Este projeto implementa uma pipeline em etapas para coletar PDFs da Central de Resultados da MRV, estruturar o conteúdo com um contrato semântico e servir os dados por API.

## O que foi feito

1. Coleta automatizada dos PDFs de `Earnings Release` por ano.
2. Catálogo local com linhagem e `sha256` para evitar duplicidade.
3. Gatilho local de ingestão que monitora novos PDFs e dispara a extração automaticamente.
4. Extração textual dos PDFs usando `pdftotext`, com fallback para o PDF completo quando o arquivo cabe no limite configurado.
5. Chunking semântico por página, páginas visuais e classificação por seção.
6. Contrato semântico em JSON com métricas, evidência e valores ausentes como `null`.
7. API JSON para consulta por empresa, período e dashboard estruturado.
8. Painel HTML com janela histórica até o mesmo trimestre do ano anterior e formatação monetária padronizada.

![Painel do projeto](docs/painel.png)

## Requisitos do ambiente

- `python3`
- `pdftotext`
- `pdfinfo`
- `requirements.txt` com as dependências do projeto

## Variáveis de ambiente

Copie `.env.example` para `.env` e configure:

```bash
GEMINI_API_KEY=...
GEMINI_MODEL=gemma-4-26b-a4b-it
```

## Etapa 1: baixar os PDFs

```bash
python3 scripts/download_mrv_reports.py --start-year 2020 --end-year 2026
```

Saída:
- PDFs em `data/raw/mrv/releases/<ano>/`
- Catálogo em `data/catalog/mrv_release_catalog.json`

## Etapa 2: estruturar os PDFs

```bash
python3 scripts/extract_mrv_reports.py
```

Saída:
- Base estruturada em `data/processed/conjuntura_records.json`
- Catálogo de linhagem em `data/catalog/mrv_lineage_catalog.json`
- Reprocessamento seletivo por `--year`, `--quarter`, `--file` e `--force`
- Validação local com `--validate-only`

## Etapa 3: subir a API

```bash
python3 scripts/serve_conjuntura_api.py
```

Depois abra no navegador:

- `http://127.0.0.1:8000/` ou `http://127.0.0.1:8000/dashboard` para o painel visual
- `http://127.0.0.1:8000/health` para checagem de saúde da API

Exemplos de consulta:

```bash
curl "http://127.0.0.1:8000/api/conjuntura?empresa=MRV&ano=2026&trimestre=1"
curl "http://127.0.0.1:8000/api/documentos?empresa=MRV&ano=2026"
curl "http://127.0.0.1:8000/api/dashboard/conjuntura?empresa=MRV&ano=2025&trimestre=3"
```

O painel visual consome essas mesmas rotas JSON para montar cartões, tabela e resumo consolidado do período.

## Estrutura dos dados

Cada registro estruturado contém:

- empresa
- ano
- trimestre
- título do documento
- URL de origem
- caminho local do PDF
- hash `sha256`
- páginas extraídas
- métricas semânticas

## Observação técnica

A extração atual tenta primeiro a chamada à API do Gemini com saída estruturada em JSON Schema. Quando o PDF é pequeno o suficiente, o fluxo pode enviar o documento inteiro; quando não é, ele recorre a chunks textuais, páginas visuais e heurísticas de recuperação local.

O painel passa a padronizar a exibição monetária para `bi` quando o valor é grande o suficiente, evitando misturas como `mi`, `bi` e `bilhões`.

Para ingestão contínua, use:

```bash
python3 scripts/watch_mrv_ingestion.py --bootstrap-existing
```

O watcher observa `data/raw/mrv/releases/` e dispara a extração quando um PDF novo ou alterado aparece.


## Controle de qualidade

```bash
python3 scripts/qa_mrv_records.py
```
