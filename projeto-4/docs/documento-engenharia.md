# Documento de Engenharia - Projeto 4

> **Aluno(a):** Carlos Eduardo Rodrigues e Patrícia Helena Macedo da Silva
> **Matrícula:** 221031265; 221037993
> **Projeto:** Projeto Individual 4  
> **Domínio:** Relatórios de relações com investidores da MRV

---

## 1. Contexto e Problema

O objetivo deste projeto é transformar relatórios trimestrais em PDF da MRV em dados estruturados para alimentar um boletim de conjuntura do setor habitacional.

Os documentos publicados pela empresa variam bastante de layout ao longo do tempo. Há releases em formato de texto, tabelas, apresentações em slides e páginas com gráficos ou cards que não são copiáveis como texto. Isso torna a extração puramente textual insuficiente.

O problema central é preservar cobertura sem sacrificar consistência semântica: o pipeline precisa encontrar os valores absolutos corretos, ignorar percentuais de marketing e manter rastreabilidade documental.

Desde a primeira versão da documentação, a implementação passou a:

- tentar o PDF completo quando o arquivo cabe nos limites configurados;
- cair para chunks textuais e páginas visuais quando o PDF é maior;
- usar heurísticas específicas para gráficos, tabelas e cards;
- normalizar a apresentação de valores monetários na interface;
- simplificar o painel de comparação para exibir somente a variação trimestral mais útil na entrega.

---

## 2. Objetivo da Solução

Construir uma pipeline de UDA capaz de:

- descobrir e baixar PDFs da Central de Resultados da MRV;
- evitar duplicidade por meio de `sha256`;
- acionar automaticamente a ingestão quando novos PDFs aparecem no diretório monitorado;
- extrair métricas com apoio de LLM e contrato semântico;
- normalizar valores monetários, percentuais e quantidades;
- persistir registros com linhagem;
- expor consulta via API e painel simples.

---

## 3. Requisitos Atendidos

| ID | Requisito | Situação |
|----|-----------|----------|
| RF01 | Coleta automatizada dos PDFs | Atendido |
| RF02 | Idempotência por hash | Atendido |
| RF03 | Extração semântica com LLM | Atendido |
| RF04 | Estruturação em JSON com contrato | Atendido |
| RF05 | Persistência com linhagem | Atendido |
| RF06 | API para consulta por empresa e período | Atendido |
| RF07 | Validação da base persistida | Atendido |

---

## 4. Arquitetura

O fluxo do projeto é composto por quatro camadas:

1. **Descoberta e download**  
   Busca releases na Central de Resultados e salva os PDFs localmente.

2. **Gatilho de ingestão**  
   Monitora o diretório dos PDFs por alterações locais e dispara a extração sempre que um arquivo novo ou alterado é detectado.

3. **Extração semântica**  
   Usa texto extraído do PDF, páginas visuais e chamadas à LLM para recuperar métricas relevantes.

4. **Contrato semântico e validação**  
   Normaliza campos, rejeita inconsistências e mantém `null` quando a métrica não é confirmada.

5. **Serviço de consulta**  
   Expõe os registros em JSON via API e um painel HTML leve.

Fluxo resumido:

```text
Descoberta -> Download -> Hash/Idempotência -> Parsing -> LLM -> Validação
-> Persistência -> API
```

O gatilho de ingestão entra entre download e parsing, observando o sistema de arquivos e acionando a extração sem depender de execução manual contínua.

---

## 5. Estratégia de Extração

A extração não depende de coordenadas fixas.

O projeto combina:

- leitura textual com `pdftotext -layout`;
- seleção dinâmica de páginas candidatas;
- tentativa de envio do PDF inteiro quando ele cabe no limite configurado;
- agrupamento de páginas em lotes visuais;
- recuperação agressiva apenas quando faltam métricas;
- validação por unidade, contexto e evidência.

Na prática, a estratégia é híbrida: PDFs pequenos podem seguir um caminho mais próximo de full-scan, enquanto documentos maiores passam por chunking textual, páginas visuais e recuperação orientada por evidência.

Os PDFs mais recentes exigem mais atenção porque:

- muitas métricas aparecem em gráficos ou cards;
- algumas tabelas viram imagem;
- os releases passam a misturar anexos e demonstrativos no fim do documento;
- o valor absoluto pode estar distante da métrica textual no layout.

Por isso, a LLM não é usada como adivinha, e sim como verificador semântico da evidência.

---

## 6. Contrato Semântico

Cada métrica segue a estrutura:

- `valor_textual`
- `valor_numerico`
- `unidade`
- `pagina`
- `trecho_evidencia`
- `encontrado`

Quando a métrica não pode ser confirmada:

```json
{
  "valor_textual": null,
  "valor_numerico": null,
  "unidade": null,
  "pagina": null,
  "trecho_evidencia": null,
  "encontrado": false
}
```

Regras centrais:

- não inventar dados ausentes;
- preservar sinais negativos entre parênteses;
- manter percentuais como percentuais;
- normalizar a exibição monetária na interface para evitar rótulos inconsistentes;
- tratar quantidades como unidades;
- diferenciar trimestre, acumulado anual e comparativos;
- rejeitar métricas sem evidência coerente.

---

## 7. Persistência e Linhagem

Cada registro persistido guarda:

- empresa;
- ano;
- trimestre;
- título do documento;
- URL original;
- caminho local;
- `sha256`;
- modo de extração;
- métricas estruturadas;
- observações de qualidade.

Isso permite auditar de onde veio cada valor e repetir a extração quando necessário.

---

## 8. Limitações Conhecidas

- a cobertura ainda depende da qualidade do layout do PDF;
- releases mais novos podem conter trechos rasterizados;
- algumas métricas podem permanecer `null` quando o documento não expõe o valor absoluto com clareza;
- a extração continua dependente da API do Gemini para os casos mais difíceis;
- quando a rede externa falha, a etapa de LLM não conclui.

---

## 09. Conclusão

A solução entrega uma pipeline funcional de UDA para os relatórios da MRV, com catálogo, idempotência, contrato semântico, persistência estruturada e API de consulta.

O principal avanço do projeto foi tornar a extração mais robusta para layouts híbridos sem amarrar a solução a posições fixas de página.
