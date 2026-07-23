import json
import sys
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from pipeline_core import PROCESSED_RECORDS_PATH, load_processed_records
from semantic_contract import build_dashboard_contract


def to_int(value):
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def load_records():
    bundle = load_processed_records()
    return bundle.get("records", [])


def dashboard_html():
    return """<!doctype html>
<html lang="pt-BR">
<head>
    <meta charset="utf-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1" />
    <title>Conjuntura MRV | Dashboard</title>
    <style>
        :root {
            color-scheme: light;
            --bg: #f6f4ef;
            --surface: #ffffff;
            --surface-soft: #f7f6f2;
            --line: #ded7c9;
            --line-strong: #c6bca7;
            --text: #122018;
            --muted: #66746b;
            --accent: #0f6d46;
            --accent-2: #e66d18;
            --good: #0f6d46;
            --bad: #ad2f44;
            --shadow: 0 16px 48px rgba(17, 32, 24, 0.08);
        }

        * { box-sizing: border-box; }
        html, body { min-height: 100%; }
        body {
            margin: 0;
            font-family: "Arial", "Helvetica Neue", Helvetica, sans-serif;
            background: var(--bg);
            color: var(--text);
        }

        .wrap {
            max-width: 1700px;
            margin: 0 auto;
            padding: 12px 14px 16px;
        }

        .hero {
            display: grid;
            grid-template-columns: 1fr;
            gap: 12px;
            margin-bottom: 12px;
        }

        .brand, .panel, .stat, .metric-card, .source-item {
            background: var(--surface);
            border: 1px solid var(--line);
            box-shadow: var(--shadow);
        }

        .controls {
            background: transparent;
            box-shadow: none;
        }

        .brand, .controls, .panel {
            border-radius: 12px;
        }

        .brand {
            padding: 18px 18px 16px;
            position: relative;
            overflow: hidden;
        }

        .brand::after {
            content: none;
        }

        .brand-top {
            display: flex;
            flex-wrap: wrap;
            gap: 10px;
            align-items: center;
        }

        .kicker {
            display: inline-flex;
            align-items: center;
            gap: 8px;
            color: var(--accent);
            font-size: 12px;
            text-transform: uppercase;
            letter-spacing: 0.12em;
            font-weight: 700;
        }

        .kicker::before {
            content: "";
            width: 10px;
            height: 10px;
            border-radius: 2px;
            background: var(--accent);
            display: inline-block;
        }

        h1 {
            margin: 12px 0 10px;
            font-size: clamp(1.8rem, 3vw, 3rem);
            line-height: 0.92;
            letter-spacing: -0.05em;
            max-width: 14ch;
            font-family: inherit;
        }

        .subtitle {
            margin: 0;
            max-width: 74ch;
            font-size: 15px;
            line-height: 1.6;
            color: var(--muted);
        }

        .meta-row {
            margin-top: 18px;
            display: flex;
            flex-wrap: wrap;
            gap: 8px;
        }

        .chip {
            display: inline-flex;
            align-items: center;
            gap: 8px;
            padding: 8px 12px;
            border-radius: 999px;
            border: 1px solid var(--line);
            background: var(--surface-soft);
            color: var(--text);
            font-size: 13px;
        }

        .chip .muted { color: var(--muted); }

        .control-grid {
            display: grid;
            grid-template-columns: repeat(3, minmax(0, 1fr));
            gap: 8px;
        }

        .field label {
            display: block;
            margin-bottom: 6px;
            color: var(--muted);
            font-size: 12px;
            text-transform: uppercase;
            letter-spacing: 0.08em;
            font-weight: 700;
        }

        select, button {
            width: 100%;
            border-radius: 12px;
            border: 1px solid var(--line-strong);
            background: var(--surface);
            color: var(--text);
            padding: 12px 14px;
            font-size: 14px;
            outline: none;
        }

        select:focus, button:focus {
            border-color: var(--accent);
            box-shadow: 0 0 0 3px rgba(15, 109, 70, 0.14);
        }

        button {
            cursor: pointer;
            font-weight: 700;
            background: linear-gradient(180deg, #fff8db, #f3ead0);
        }

        button:hover {
            border-color: #9a7c28;
        }

        .status-line {
            display: flex;
            gap: 12px;
            align-items: center;
            justify-content: space-between;
            flex-wrap: wrap;
            color: var(--muted);
            font-size: 14px;
        }

        .content {
            display: grid;
            grid-template-columns: 1fr;
            gap: 10px;
            margin-top: 10px;
        }

        .stack {
            display: grid;
            gap: 10px;
        }

        .panel {
            padding: 14px;
        }

        .panel h2 {
            margin: 0;
            font-size: 18px;
            letter-spacing: -0.03em;
            font-family: inherit;
        }

        .panel-header {
            display: flex;
            justify-content: space-between;
            gap: 10px;
            align-items: baseline;
            margin-bottom: 14px;
            padding-bottom: 10px;
            border-bottom: 1px solid var(--line);
        }

        .panel-header small {
            color: var(--muted);
        }

        .report-stack {
            display: grid;
            gap: 14px;
        }

        .report-block {
            display: block;
        }

        .report-table-shell {
            background: var(--surface);
            border: 1px solid var(--line);
            box-shadow: var(--shadow);
        }

        .report-table-shell {
            overflow: hidden;
        }

        .report-head {
            background: #ffc20f;
            padding: 14px 16px;
            display: flex;
            justify-content: space-between;
            gap: 12px;
            align-items: baseline;
            border-bottom: 1px solid rgba(0, 0, 0, 0.12);
        }

        .report-head h2 {
            margin: 0;
            font-size: clamp(18px, 2vw, 24px);
            font-family: inherit;
            letter-spacing: -0.03em;
        }

        .report-head small {
            font-weight: 700;
            color: rgba(18, 32, 24, 0.84);
        }

        .report-table-wrap {
            overflow: auto;
            background: #f3f3f1;
        }

        .report-table {
            width: 100%;
            border-collapse: collapse;
            font-size: 14px;
        }

        .report-table th,
        .report-table td {
            border: 1px solid #ffffff;
            padding: 12px 14px;
            text-align: center;
            vertical-align: middle;
        }

        .report-table th {
            background: #ffc20f;
            color: #101010;
            font-size: 15px;
            font-weight: 800;
            letter-spacing: -0.02em;
            white-space: nowrap;
        }

        .report-table td {
            background: #efefee;
            color: #111;
            font-weight: 700;
        }

        .report-table td:first-child {
            text-align: left;
            font-size: 16px;
            font-weight: 800;
        }

        .report-table tbody tr:nth-child(odd) td {
            background: #f5f5f4;
        }

        .report-table .pos {
            color: #00a651;
        }

        .report-table .neg {
            color: #d60000;
        }

        .report-table .neutral {
            color: #66746b;
        }

        .report-foot {
            padding: 8px 14px 14px;
            font-size: 12px;
            color: var(--muted);
        }

        table {
            width: 100%;
            border-collapse: collapse;
            border-spacing: 0;
            font-size: 14px;
        }

        th, td {
            padding: 12px 10px;
            border-bottom: 1px solid var(--line);
            vertical-align: top;
            text-align: left;
        }

        th {
            color: var(--muted);
            font-size: 12px;
            text-transform: uppercase;
            letter-spacing: 0.08em;
        }

        tbody tr:hover {
            background: rgba(15, 109, 70, 0.03);
        }

        .pill {
            display: inline-flex;
            align-items: center;
            gap: 6px;
            padding: 6px 10px;
            border-radius: 999px;
            font-size: 12px;
            border: 1px solid var(--line);
            background: #fff;
            white-space: nowrap;
        }

        .ok { color: var(--good); }
        .missing { color: var(--bad); }
        .muted { color: var(--muted); }

        .sources {
            display: grid;
            gap: 10px;
        }

        .source-item {
            padding: 12px 14px;
            border-radius: 14px;
            background: var(--surface-soft);
        }

        .loading, .empty {
            padding: 20px 10px;
            color: var(--muted);
            text-align: center;
        }

        .error {
            color: var(--bad);
            background: rgba(173, 47, 68, 0.08);
            border: 1px solid rgba(173, 47, 68, 0.18);
            padding: 10px 12px;
            border-radius: 12px;
        }

        .table-wrap {
            overflow: auto;
            border: 1px solid var(--line);
            border-radius: 14px;
        }

        .table-wrap table thead th {
            position: sticky;
            top: 0;
            background: #fafcf9;
            z-index: 1;
        }

        .section-full {
            margin-top: 14px;
        }

        @media (max-width: 1100px) {
            .hero, .content {
                grid-template-columns: 1fr;
            }
            .control-grid {
                grid-template-columns: 1fr;
            }
        }

        @media (max-width: 720px) {
            .wrap {
                padding: 10px;
            }
            h1 {
                max-width: none;
                font-size: 2.2rem;
            }
        }
    </style>
</head>
<body>
    <main class="wrap">
        <section class="hero">
            <div class="brand">
                <div class="brand-top">
                    <div class="kicker">Conjuntura MRV</div>
                </div>
                <h1>Painel</h1>
                <div class="controls" style="margin-top: 14px;">
                    <div class="control-grid">
                        <div class="field">
                            <label for="empresa">Empresa</label>
                            <select id="empresa"></select>
                        </div>
                        <div class="field">
                            <label for="ano">Ano</label>
                            <select id="ano"></select>
                        </div>
                        <div class="field">
                            <label for="trimestre">Trimestre</label>
                            <select id="trimestre"></select>
                        </div>
                    </div>
                    <div class="status-line">
                        <span id="status">Carregando dados...</span>
                        <button id="reload" type="button">Atualizar</button>
                    </div>
                </div>
            </div>
        </section>

        <section class="content">
            <div class="stack">
                <div id="reportsArea" class="report-stack" aria-label="Relatórios executivos">
                    <div class="loading">Carregando relatório comparativo...</div>
                </div>
            </div>
        </section>
    </main>

    <script>
        const apiBase = window.location.origin;
        const state = {
            records: [],
            latest: { empresa: "MRV", ano: null, trimestre: null },
        };

        const metricLabels = {
            receita_operacional_liquida: "Receita Operacional Líquida",
            lucro_liquido: "Lucro Líquido",
            ebitda: "EBITDA",
            margem_bruta: "Margem Bruta",
            vendas_liquidas: "Vendas Líquidas",
            lancamentos: "Lançamentos",
            unidades_produzidas: "Unidades Produzidas",
            repasses: "Repasses",
            estoque: "Estoque",
            vso: "VSO",
            distratos: "Distratos",
            geracao_caixa: "Geração de Caixa",
        };

        const metricOrder = [
            "receita_operacional_liquida",
            "lucro_liquido",
            "ebitda",
            "margem_bruta",
            "vendas_liquidas",
            "lancamentos",
            "unidades_produzidas",
            "repasses",
            "estoque",
            "vso",
            "distratos",
            "geracao_caixa",
        ];

        const formatNumber = (value) => {
            if (value === null || value === undefined || Number.isNaN(value)) return "-";
            return new Intl.NumberFormat("pt-BR", { maximumFractionDigits: 2 }).format(value);
        };

        const normalizeUnitLabel = (unit) => {
            if (unit === null || unit === undefined) return null;
            const text = String(unit).trim().toLowerCase();
            if (!text) return null;
            if (text.includes("%")) return "%";
            if (text.includes("p.p")) return "p.p.";
            if (text.includes("unidade")) return "unidades";
            if (text.includes("bilh") || text === "bi") return "bilhões";
            if (text.includes("milh") || text === "mi") return "milhões";
            if (text.includes("mil")) return "mil";
            return String(unit).trim();
        };

        const normalizeRawMetricText = (text) => String(text)
            .replace(/\b(bilh(?:ão|ao|ões|oes)?|bi)\b/gi, "bi")
            .replace(/\b(milh(?:ão|ao|ões|oes)?|mi)\b/gi, "mi");

        const formatMonetaryValue = (value, unit) => {
            const numeric = Number(value);
            if (!Number.isFinite(numeric)) return "-";

            const normalizedUnit = normalizeUnitLabel(unit);
            if (normalizedUnit === "bilhões") {
                return `R$ ${formatNumber(numeric)} bi`;
            }
            if (normalizedUnit === "milhões") {
                if (Math.abs(numeric) >= 1000) {
                    return `R$ ${formatNumber(numeric / 1000)} bi`;
                }
                return `R$ ${formatNumber(numeric)} mi`;
            }
            if (normalizedUnit === "mil") {
                return `R$ ${formatNumber(numeric)} mil`;
            }
            return `R$ ${formatNumber(numeric)}`;
        };

        const comparisonValue = (metric) => {
            if (!metric || !metric.encontrado) return null;
            const value = Number(metric.valor_numerico);
            if (!Number.isFinite(value)) return null;
            const unit = normalizeUnitLabel(metric.unidade);
            if (unit === "milhões") return value / 1000;
            if (unit === "mil") return value / 1000000;
            return value;
        };

        const metricDisplay = (metric) => {
            if (!metric || !metric.encontrado) return "-";
            const value = Number(metric.valor_numerico);
            const unit = normalizeUnitLabel(metric.unidade);

            if (Number.isFinite(value) && unit) {
                if (unit === "%") return `${formatNumber(value)}%`;
                if (unit === "p.p.") return `${formatNumber(value)} p.p.`;
                if (unit === "bilhões" || unit === "milhões" || unit === "mil") {
                    return formatMonetaryValue(value, unit);
                }
                if (unit === "unidades") return `${formatNumber(value)} unidades`;
            }

            if (metric.valor_textual !== null && metric.valor_textual !== undefined) {
                return normalizeRawMetricText(metric.valor_textual);
            }

            return Number.isFinite(value) ? formatNumber(value) : "-";
        };

        const periodKey = (record) => `${Number(record?.ano) || 0}-${Number(record?.trimestre) || 0}`;

        const previousQuarter = (year, quarter) => {
            const yearValue = Number(year) || 0;
            const quarterValue = Number(quarter) || 0;
            if (quarterValue <= 1) return { ano: yearValue - 1, trimestre: 4 };
            return { ano: yearValue, trimestre: quarterValue - 1 };
        };

        const sameQuarterLastYear = (year, quarter) => ({
            ano: (Number(year) || 0) - 1,
            trimestre: Number(quarter) || 0,
        });

        const periodRank = (record) => (Number(record?.ano) || 0) * 10 + (Number(record?.trimestre) || 0);

        const periodLabel = (record) => {
            if (!record) return "-";
            return `${Number(record.trimestre) || "-"}T${String(record.ano || "").slice(-2)}`;
        };

        const percentChange = (current, previous) => {
            const currentValue = Number(current);
            const previousValue = Number(previous);
            if (!Number.isFinite(currentValue) || !Number.isFinite(previousValue) || previousValue === 0) return null;
            return ((currentValue - previousValue) / Math.abs(previousValue)) * 100;
        };

        const formatPercentChange = (value) => {
            if (value === null || value === undefined || Number.isNaN(value)) return "-";
            const rounded = Math.round(value * 10) / 10;
            const sign = rounded > 0 ? "+" : "";
            return `${sign}${formatNumber(rounded)}%`;
        };

        const deltaClass = (value) => {
            if (value === null || value === undefined || Number.isNaN(value)) return "neutral";
            if (value > 0) return "pos";
            if (value < 0) return "neg";
            return "neutral";
        };

        const lookupRecords = (records) => {
            const map = new Map();
            records.forEach((record) => {
                map.set(periodKey(record), record);
            });
            return map;
        };

        const isPeriodAtOrBefore = (candidate, anchor) => {
            if (!candidate || !anchor) return false;
            return periodRank(candidate) <= periodRank(anchor);
        };

        const isPeriodAtOrAfter = (candidate, anchor) => {
            if (!candidate || !anchor) return false;
            return periodRank(candidate) >= periodRank(anchor);
        };

        const shortSource = (record, metric) => {
            if (!metric || !metric.encontrado) return "-";
            const parts = [];
            if (metric.pagina !== null && metric.pagina !== undefined) parts.push(`p. ${metric.pagina}`);
            if (record?.titulo_documento) parts.push(record.titulo_documento);
            return parts.length ? parts.join(" • ") : "-";
        };

        function buildComparisonRows(records, metricName) {
            const map = lookupRecords(records);
            return records.map((record) => {
                const metric = record.metricas?.[metricName];
                const current = comparisonValue(metric);
                const prevRecord = map.get(periodKey(previousQuarter(record.ano, record.trimestre)));
                const prevMetric = prevRecord?.metricas?.[metricName];
                return {
                    record,
                    metric,
                    current,
                    prevDelta: percentChange(current, comparisonValue(prevMetric)),
                };
            });
        }

        function renderReportBlock(records, currentRecord, metricName, title) {
            const companyRecords = records
                .filter((record) => record.empresa === currentRecord.empresa)
                .sort(byLatest);
            const lowerBound = sameQuarterLastYear(currentRecord.ano, currentRecord.trimestre);
            const visibleRecords = companyRecords
                .filter((record) => isPeriodAtOrBefore(record, currentRecord) && isPeriodAtOrAfter(record, lowerBound))
                .sort(byLatest)
                .slice(0, 5);
            const rows = buildComparisonRows(visibleRecords, metricName);

            return `
                <article class="report-block">
                    <div class="report-table-shell">
                        <div class="report-head">
                            <h2>${title} ${periodLabel(currentRecord)}</h2>
                            <small>${currentRecord.empresa || ""} • ${currentRecord.titulo_documento || ""}</small>
                        </div>
                        <div class="report-table-wrap">
                            <table class="report-table">
                                <thead>
                                    <tr>
                                        <th>Período</th>
                                        <th>Valor</th>
                                        <th>Variação vs tri. ant.</th>
                                    </tr>
                                </thead>
                                <tbody>
                                    ${rows.map(({ record, metric, prevDelta }) => `
                                        <tr>
                                            <td>${periodLabel(record)}</td>
                                            <td>${metricDisplay(metric)}</td>
                                            <td class="${deltaClass(prevDelta)}">${formatPercentChange(prevDelta)}</td>
                                        </tr>
                                    `).join("")}
                                </tbody>
                            </table>
                        </div>
                        <div class="report-foot">Fonte: relatórios trimestrais processados da MRV.</div>
                    </div>
                </article>`;
        }

        const percentFromRatio = (value, maxValue) => {
            if (!Number.isFinite(value) || !Number.isFinite(maxValue) || maxValue <= 0) return 0;
            return Math.max(6, Math.min(100, (value / maxValue) * 100));
        };

        const byLatest = (a, b) => (b.ano - a.ano) || (b.trimestre - a.trimestre);

        function setOptions(select, values, currentValue) {
            select.innerHTML = "";
            values.forEach((value) => {
                const option = document.createElement("option");
                option.value = value;
                option.textContent = value;
                if (String(value) === String(currentValue)) option.selected = true;
                select.appendChild(option);
            });
        }

        function populateFilters(records) {
            const empresas = [...new Set(records.map((record) => record.empresa).filter(Boolean))].sort();
            const currentEmpresa = state.latest.empresa || empresas[0] || "MRV";
            const companyRecords = records.filter((record) => record.empresa === currentEmpresa);
            const anos = [...new Set(companyRecords.map((record) => record.ano))].sort((a, b) => a - b);
            const currentAno = state.latest.ano || anos[anos.length - 1];
            const quarters = companyRecords.filter((record) => record.ano === currentAno).map((record) => record.trimestre).sort((a, b) => a - b);
            const currentQuarter = state.latest.trimestre || quarters[quarters.length - 1];

            setOptions(document.getElementById("empresa"), empresas, currentEmpresa);
            setOptions(document.getElementById("ano"), anos, currentAno);
            setOptions(document.getElementById("trimestre"), quarters, currentQuarter);

            if (!state.latest.ano) state.latest.ano = currentAno;
            if (!state.latest.trimestre) state.latest.trimestre = currentQuarter;
            state.latest.empresa = currentEmpresa;
        }

        function refreshQuarterOptions(records, empresa, ano, selectedQuarter) {
            const empresaRecords = records.filter((record) => record.empresa === empresa);
            const anos = [...new Set(empresaRecords.map((record) => record.ano))].sort((a, b) => a - b);
            const anoValue = anos.includes(Number(ano)) ? Number(ano) : anos[anos.length - 1];
            const quarters = empresaRecords.filter((record) => record.ano === anoValue).map((record) => record.trimestre).sort((a, b) => a - b);
            const trimestreValue = quarters.includes(Number(selectedQuarter)) ? Number(selectedQuarter) : quarters[quarters.length - 1];

            setOptions(document.getElementById("ano"), anos, anoValue);
            setOptions(document.getElementById("trimestre"), quarters, trimestreValue);

            state.latest.ano = anoValue;
            state.latest.trimestre = trimestreValue;
        }

        function renderMetrics(record) {
            const area = document.getElementById("metricsArea");
            if (!area) return;
            const entries = metricOrder
                .map((name) => [name, record.metricas?.[name]])
                .filter(([, metric]) => metric);

            const maxValue = Math.max(...entries.map(([, metric]) => Math.abs(comparisonValue(metric) || 0)), 1);
            area.innerHTML = entries.map(([name, metric]) => {
                const value = comparisonValue(metric);
                const width = metric.encontrado ? percentFromRatio(Math.abs(value || 0), maxValue) : 0;
                const statusClass = metric.encontrado ? "ok" : "missing";
                return `
                    <article class="metric-card">
                        <div class="metric-title">
                            <span>${metricLabels[name] || name}</span>
                            <span class="pill ${statusClass}">${metric.encontrado ? "Encontrado" : "Ausente"}</span>
                        </div>
                        <div class="metric-value">${metricDisplay(metric)}</div>
                        <div class="bar"><span style="width:${width}%"></span></div>
                        <div class="metric-foot">Página ${metric.pagina ?? "-"}${metric.trecho_evidencia ? ` • ${metric.trecho_evidencia}` : ""}</div>
                    </article>`;
            }).join("") || '<div class="empty">Nenhuma métrica disponível para o filtro atual.</div>';
        }

        function renderReports(records, currentRecord) {
            const area = document.getElementById("reportsArea");
            area.innerHTML = [
                renderReportBlock(records, currentRecord, "lancamentos", "Lançamentos"),
                renderReportBlock(records, currentRecord, "vendas_liquidas", "Vendas Líquidas"),
            ].join("");
        }

        function renderBalance(contract) {
            const area = document.getElementById("balanceArea");
            if (!area) return;
            const cards = Object.entries(contract.cards_totais || {});
            area.innerHTML = cards.map(([name, card]) => {
                const current = card?.valor_atual;
                const unit = card?.unidade;
                const label = name === "lancamentos" ? "Lançamentos totais" : "Vendas totais";
                return `
                    <div class="summary-item">
                        <strong>${label}</strong>
                        <div class="value">${formatMonetaryValue(current, unit)}</div>
                        <div class="detail">Valor consolidado do contrato para o recorte selecionado.</div>
                    </div>`;
            }).join("") || '<div class="empty">Sem dados consolidados para o recorte atual.</div>';
        }

        function renderSources(contract) {
            const area = document.getElementById("sourcesArea");
            if (!area) return;
            const fontes = contract.fontes || [];
            area.innerHTML = fontes.length
                ? fontes.map((source, index) => `
                        <div class="source-item">
                            <div class="pill">Fonte ${index + 1}</div>
                            <div style="margin-top:8px; word-break: break-word;">${source}</div>
                        </div>`).join("")
                : '<div class="empty">Nenhuma fonte retornada pelo contrato.</div>';
        }

        function renderTable(record) {
            const body = document.getElementById("metricsTable");
            if (!body) return;
            const rows = metricOrder
                .map((name) => [name, record.metricas?.[name]])
                .filter(([, metric]) => metric);

            body.innerHTML = rows.map(([name, metric]) => `
                <tr>
                    <td>${metricLabels[name] || name}</td>
                    <td>${metricDisplay(metric)}</td>
                    <td>${metric.pagina ?? "-"}</td>
                    <td><span class="pill ${metric.encontrado ? "ok" : "missing"}">${metric.encontrado ? "Encontrado" : "Ausente"}</span></td>
                    <td class="muted">${metric.trecho_evidencia || metric.trecho || "-"}</td>
                </tr>
            `).join("");
        }

        function updateHeader(record, contract, records) {
            document.getElementById("status").textContent = `Exibindo ${record.empresa || ""} ${record.ano || ""} T${record.trimestre || ""}`;
        }

        async function loadDashboard() {
            const empresa = document.getElementById("empresa").value;
            const ano = document.getElementById("ano").value;
            const trimestre = document.getElementById("trimestre").value;

            document.getElementById("status").textContent = "Atualizando painel...";

            const params = new URLSearchParams();
            if (empresa) params.set("empresa", empresa);
            if (ano) params.set("ano", ano);
            if (trimestre) params.set("trimestre", trimestre);

            const [recordsResponse, dashboardResponse, dataResponse] = await Promise.all([
                fetch(`${apiBase}/api/conjuntura?${params.toString()}`),
                fetch(`${apiBase}/api/dashboard/conjuntura?${params.toString()}`),
                fetch(`${apiBase}/api/conjuntura?empresa=${encodeURIComponent(empresa || "")}`),
            ]);

            const recordsPayload = await recordsResponse.json();
            const dashboardPayload = await dashboardResponse.json();
            const allRecordsPayload = await dataResponse.json();

            const records = allRecordsPayload.data || [];
            state.records = records;

            if (!records.length) {
                document.getElementById("status").innerHTML = '<span class="error">Nenhum registro encontrado para o filtro selecionado.</span>';
                return;
            }

            const currentRecord = (recordsPayload.data || [])[0] || records.sort(byLatest)[0];
            const currentEmpresa = currentRecord.empresa || empresa || state.latest.empresa || "MRV";
            state.latest.empresa = currentEmpresa;
            state.latest.ano = Number(currentRecord.ano || ano || state.latest.ano);
            state.latest.trimestre = Number(currentRecord.trimestre || trimestre || state.latest.trimestre);

            populateFilters(records);
            refreshQuarterOptions(records, currentEmpresa, state.latest.ano, state.latest.trimestre);
            updateHeader(currentRecord, dashboardPayload.data || {}, records);
            renderReports(records, currentRecord);
            document.getElementById("status").textContent = `Pronto: ${currentRecord.empresa} ${currentRecord.ano} T${currentRecord.trimestre}`;
        }

        document.getElementById("empresa").addEventListener("change", () => {
            const empresa = document.getElementById("empresa").value;
            const records = state.records.filter((record) => record.empresa === empresa);
            const anos = [...new Set(records.map((record) => record.ano))].sort((a, b) => a - b);
            const ano = anos[anos.length - 1];
            const quarters = records.filter((record) => record.ano === ano).map((record) => record.trimestre).sort((a, b) => a - b);
            const trimestre = quarters[quarters.length - 1];
            setOptions(document.getElementById("ano"), anos, ano);
            setOptions(document.getElementById("trimestre"), quarters, trimestre);
            state.latest.empresa = empresa;
            state.latest.ano = ano;
            state.latest.trimestre = trimestre;
        });

        document.getElementById("ano").addEventListener("change", () => {
            const empresa = document.getElementById("empresa").value;
            const ano = Number(document.getElementById("ano").value);
            const quarters = state.records.filter((record) => record.empresa === empresa && Number(record.ano) === ano).map((record) => record.trimestre).sort((a, b) => a - b);
            const trimestre = quarters[quarters.length - 1];
            setOptions(document.getElementById("trimestre"), quarters, trimestre);
            state.latest.ano = ano;
            state.latest.trimestre = trimestre;
        });

        document.getElementById("reload").addEventListener("click", loadDashboard);

        (async () => {
            try {
                const response = await fetch(`${apiBase}/api/conjuntura`);
                const payload = await response.json();
                state.records = (payload.data || []).sort(byLatest);

                if (!state.records.length) {
                    document.getElementById("status").innerHTML = '<span class="error">A API respondeu sem registros.</span>';
                    return;
                }

                const latest = state.records[0];
                state.latest.empresa = latest.empresa || "MRV";
                state.latest.ano = Number(latest.ano);
                state.latest.trimestre = Number(latest.trimestre);
                populateFilters(state.records);
                await loadDashboard();
            } catch (error) {
                document.getElementById("status").innerHTML = `<span class="error">Falha ao carregar o painel: ${error.message}</span>`;
            }
        })();
    </script>
</body>
</html>"""


def filter_records(records, params):
    empresa = params.get("empresa", [None])[0]
    ano = to_int(params.get("ano", [None])[0])
    trimestre = to_int(params.get("trimestre", [None])[0])

    filtered = []
    for record in records:
        if empresa and str(record.get("empresa", "")).lower() != empresa.lower():
            continue
        if ano is not None and to_int(record.get("ano")) != ano:
            continue
        if trimestre is not None and to_int(record.get("trimestre")) != trimestre:
            continue
        filtered.append(record)
    return filtered


class ConjunturaHandler(BaseHTTPRequestHandler):
    def send_json(self, status, payload):
        body = json.dumps(payload, ensure_ascii=False, indent=2).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def send_html(self, status, body):
        payload = body.encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(payload)))
        self.end_headers()
        self.wfile.write(payload)

    def do_GET(self):
        parsed = urlparse(self.path)

        if parsed.path in ("/", "/dashboard"):
            return self.send_html(200, dashboard_html())

        if parsed.path == "/health":
            return self.send_json(
                200,
                {
                    "success": True,
                    "status": "ok",
                    "arquivo": str(PROCESSED_RECORDS_PATH),
                },
            )

        if parsed.path == "/api/conjuntura":
            params = parse_qs(parsed.query)
            records = load_records()
            filtered = filter_records(records, params)
            return self.send_json(
                200,
                {
                    "success": True,
                    "count": len(filtered),
                    "data": filtered,
                },
            )

        if parsed.path == "/api/documentos":
            params = parse_qs(parsed.query)
            records = load_records()
            filtered = filter_records(records, params)
            documentos = [
                {
                    "empresa": record.get("empresa"),
                    "ano": record.get("ano"),
                    "trimestre": record.get("trimestre"),
                    "titulo_documento": record.get("titulo_documento"),
                    "source_url": record.get("source_url"),
                    "stored_path": record.get("stored_path"),
                    "sha256": record.get("sha256"),
                    "data_publicacao": record.get("data_publicacao"),
                }
                for record in filtered
            ]
            return self.send_json(
                200,
                {
                    "success": True,
                    "count": len(documentos),
                    "data": documentos,
                },
            )

        if parsed.path == "/api/dashboard/conjuntura":
            params = parse_qs(parsed.query)
            records = load_records()
            filtered = filter_records(records, params)
            return self.send_json(
                200,
                {
                    "success": True,
                    "data": build_dashboard_contract(
                        filtered,
                        ano=to_int(params.get("ano", [None])[0]),
                        trimestre=to_int(params.get("trimestre", [None])[0]),
                        empresa=params.get("empresa", [None])[0],
                    ),
                },
            )

        return self.send_json(
            404,
            {
                "success": False,
                "error": "endpoint_nao_encontrado",
            },
        )


def main():
    host = "127.0.0.1"
    port = 8000
    server = HTTPServer((host, port), ConjunturaHandler)
    print(f"[INFO] API rodando em http://{host}:{port}")
    print(f"[INFO] Lendo dados de {PROCESSED_RECORDS_PATH}")
    server.serve_forever()


if __name__ == "__main__":
    raise SystemExit(main())
