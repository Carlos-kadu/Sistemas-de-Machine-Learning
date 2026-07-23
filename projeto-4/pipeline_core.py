import re
from pathlib import Path

from pipeline.io_utils import (
    load_json,
    now_utc,
    pdf_page_count,
    pdf_text,
    run_command,
    save_json,
    sha256_file,
)
from pipeline.metric_payload import build_metric_payload, empty_metric
from pipeline.numeric import (
    extract_primary_token,
    extract_value_from_window,
    infer_unit_from_text,
    parse_numeric_value,
)
from pipeline.text_utils import (
    classify_section,
    normalize_line,
    normalize_text,
    page_excerpt,
    split_pages,
    split_raw_pages,
)

ROOT_DIR = Path(__file__).resolve().parent
DATA_DIR = ROOT_DIR / "data"
RAW_DIR = DATA_DIR / "raw" / "mrv" / "releases"
CATALOG_PATH = DATA_DIR / "catalog" / "mrv_release_catalog.json"
LINEAGE_CATALOG_PATH = DATA_DIR / "catalog" / "mrv_lineage_catalog.json"
PROCESSED_DIR = DATA_DIR / "processed"
PROCESSED_RECORDS_PATH = PROCESSED_DIR / "conjuntura_records.json"

METRIC_SPECS = [
    ("receita_operacional_liquida", ["receita operacional líquida", "receita operacional liquida", "rol"]),
    ("lucro_liquido", ["lucro líquido", "lucro liquido"]),
    ("ebitda", ["ebitda"]),
    ("margem_bruta", ["margem bruta"]),
    ("vendas_liquidas", ["vendas líquidas", "vendas liquidas"]),
    ("lancamentos", ["lançamentos", "lancamentos"]),
    ("unidades_produzidas", ["unidades produzidas", "unidades produzidas"]),
    ("repasses", ["repasses"]),
    ("estoque", ["estoque"]),
    ("vso", ["vso"]),
    ("distratos", ["distratos"]),
    ("geracao_caixa", ["geração de caixa", "geracao de caixa"]),
]

def load_catalog():
    return load_json(CATALOG_PATH, {"documents": []})


def load_processed_records():
    return load_json(PROCESSED_RECORDS_PATH, {"records": []})


def save_processed_records(data):
    save_json(PROCESSED_RECORDS_PATH, data)


def load_lineage_catalog():
    return load_json(LINEAGE_CATALOG_PATH, {"records": []})


def save_lineage_catalog(data):
    save_json(LINEAGE_CATALOG_PATH, data)


def iter_catalog_documents():
    catalog = load_catalog()
    for document in catalog.get("documents", []):
        yield document


def build_data_lineage(document, pdf_path, *, trigger="batch", record_path=None):
    pdf_path = Path(pdf_path) if pdf_path else None
    return {
        "schema_version": "lineage-1.0",
        "source_system": "central_de_resultados_mrv",
        "trigger": trigger,
        "empresa": document.get("company", "MRV"),
        "ano": document.get("year"),
        "trimestre": document.get("quarter"),
        "titulo_documento": document.get("title"),
        "source_url": document.get("source_url"),
        "stored_path": document.get("stored_path"),
        "sha256": document.get("sha256") or sha256_file(pdf_path),
        "catalog_path": str(CATALOG_PATH.relative_to(ROOT_DIR)),
        "lineage_catalog_path": str(LINEAGE_CATALOG_PATH.relative_to(ROOT_DIR)),
        "processed_records_path": str(PROCESSED_RECORDS_PATH.relative_to(ROOT_DIR)),
        "record_path": record_path,
        "captured_at": now_utc(),
    }


def upsert_lineage_record(lineage_record):
    catalog = load_lineage_catalog()
    records = [
        record
        for record in catalog.get("records", [])
        if record.get("sha256") != lineage_record.get("sha256")
    ]
    records.append(lineage_record)
    catalog["records"] = sorted(
        records,
        key=lambda item: (
            item.get("ano") or 0,
            item.get("trimestre") or 0,
            item.get("titulo_documento") or "",
        ),
    )
    save_lineage_catalog(catalog)


def find_raw_pdf(document):
    stored_path = document.get("stored_path")
    if stored_path:
        path = ROOT_DIR / stored_path
        if path.exists():
            return path

    year = document.get("year")
    title = document.get("title") or "document"
    if year:
        guess_dir = RAW_DIR / str(year)
        if guess_dir.exists():
            for candidate in guess_dir.glob("*.pdf"):
                if slugify(title) in candidate.stem:
                    return candidate
    return None


def slugify(value):
    value = str(value).strip().lower()
    value = re.sub(r"[^a-z0-9]+", "-", value)
    return value.strip("-") or "document"


def find_value_window(text, aliases):
    lowered = text.lower()
    best_index = None

    for alias in aliases:
        index = lowered.find(alias)
        if index >= 0 and (best_index is None or index < best_index):
            best_index = index

    if best_index is None:
        return None, None

    start = max(0, best_index - 140)
    end = min(len(text), best_index + 460)
    window = text[start:end]
    return window, best_index


def extract_distratos_from_page(page_text, page_number):
    normalized = normalize_line(page_text)
    lowered = normalized.lower()
    if "distrato" not in lowered:
        return None

    percent_graph_match = re.search(
        r"%\s*distrato\s*-\s*mrv\s+incorpora[çc][ãa]o(?P<body>.*?)(?:\b[1-4]t\d{2}\b)",
        normalized,
        re.IGNORECASE,
    )
    if percent_graph_match:
        graph_text = percent_graph_match.group(0)
        percentages = re.findall(r"[-+]?\d[\d\.,]*\s*%", graph_text)
        if percentages:
            return build_metric_payload(
                "distratos",
                percentages[-1],
                page_number,
                graph_text,
                "%",
            )

    narrative_patterns = [
        r"distratos registrados.{0,180}?totalizando(?: apenas)?\s+R\$\s*(\(?[-+]?\d[\d\.,]*\)?)(?:\s*(milhões|milhoes|bilhões|bilhoes|bi))?",
        r"distratos?.{0,80}?R\$\s*(\(?[-+]?\d[\d\.,]*\)?)(?:\s*(milhões|milhoes|bilhões|bilhoes|bi))?",
    ]
    for pattern in narrative_patterns:
        match = re.search(pattern, normalized, re.IGNORECASE)
        if not match:
            continue
        unit_hint = "milhões"
        if len(match.groups()) > 1 and match.group(2):
            unit_hint = match.group(2)
        return build_metric_payload(
            "distratos",
            match.group(1).strip(),
            page_number,
            match.group(0),
            unit_hint,
        )

    graph_match = re.search(
        r"venda\s+(?:x|vs)\s+distrato.*?(?=\b[1-4]t\d{2}\b)",
        normalized,
        re.IGNORECASE,
    )
    if graph_match:
        graph_text = graph_match.group(0)
        numbers = re.findall(r"(?<![\w%])\(?[-+]?\d[\d\.,]*\)?(?![\w%])", graph_text)
        if len(numbers) >= 2:
            return build_metric_payload(
                "distratos",
                numbers[-1],
                page_number,
                graph_text,
                "milhões",
            )
    return None


def extract_lancamentos_graph_from_page(page_text, page_number):
    normalized_lines = [normalize_line(line) for line in page_text.splitlines()]
    for index, line in enumerate(normalized_lines):
        lowered = line.lower()
        if "lançamentos ltm" not in lowered and "lancamentos ltm" not in lowered:
            continue

        lookahead_lines = [candidate for candidate in normalized_lines[index : index + 5] if candidate]
        lookahead = " ".join(lookahead_lines)

        monetary_match = re.search(
            r"R\$\s*\(?[-+]?\d[\d\.,]*\)?\s*(?:bilhão|bilhao|bilhões|bilhoes|milhões|milhoes|mil|bi)",
            lookahead,
            re.IGNORECASE,
        )
        if monetary_match:
            return build_metric_payload(
                "lancamentos",
                monetary_match.group(0).strip(),
                page_number,
                lookahead,
                infer_unit_from_text(lookahead) or "milhões",
            )

        for candidate_line in lookahead_lines[1:]:
            if re.search(r"\b[1-4]t\d{2}\b", candidate_line, re.IGNORECASE):
                break
            if not re.search(r"\d", candidate_line):
                continue
            numbers = [
                token
                for token in re.findall(r"(?<![\w%])\(?[-+]?\d[\d\.,]*\)?(?!\s*%|\w)", candidate_line)
                if not token.lower().endswith("x")
            ]
            if numbers:
                return build_metric_payload(
                    "lancamentos",
                    numbers[-1],
                    page_number,
                    f"{line} {candidate_line}",
                    infer_unit_from_text(line) or "milhões",
                )

    return None


def extract_compact_operational_metric_from_page(metric_name, page_text, page_number):
    normalized = normalize_line(page_text)
    patterns = {
        "vendas_liquidas": [
            (r"vendas\s+l[íi]quidas\s+vgv\s*-\s*%mrv\s+(\(?[-+]?\d[\d\.,]*\)?)", "milhões"),
            (r"\bvendas\b(?:(?!\b(?:repasses|produ[çc][ãa]o|propriedades|land\s+bank|lan[çc]amentos)\b).){0,240}?vgv\s*\(r\$\s*milh[õo]es\)\s+(\(?[-+]?\d[\d\.,]*\)?)", "milhões"),
        ],
        "lancamentos": [
            (r"lan[çc]amentos\s+vgv\s*-\s*%mrv\s+(\(?[-+]?\d[\d\.,]*\)?)", "milhões"),
            (r"lan[çc]amentos(?:(?!\b(?:vendas|repasses|produ[çc][ãa]o|propriedades|land\s+bank)\b).){0,240}?vgv\s*\(r\$\s*milh[õo]es\)\s+(\(?[-+]?\d[\d\.,]*\)?)", "milhões"),
        ],
        "unidades_produzidas": (
            r"\bprodu[çc][ãa]o\s+unidades\s+(\(?[-+]?\d[\d\.,]*\)?)",
            "unidades",
        ),
        "repasses": (
            r"\brepasses\s+unidades\s+(\(?[-+]?\d[\d\.,]*\)?)",
            "unidades",
        ),
    }
    metric_patterns = patterns.get(metric_name)
    if not metric_patterns:
        return None

    if isinstance(metric_patterns, tuple):
        metric_patterns = [metric_patterns]

    match = None
    unit_hint = None
    for pattern, candidate_unit_hint in metric_patterns:
        match = re.search(pattern, normalized, re.IGNORECASE)
        if match:
            unit_hint = candidate_unit_hint
            break
    if not match or not unit_hint:
        return None

    return build_metric_payload(
        metric_name,
        match.group(1).strip(),
        page_number,
        match.group(0),
        unit_hint,
    )


def extract_stock_total_from_page(page_text, page_number):
    normalized = normalize_line(page_text)
    if "estoques (imóveis a comercializar)" not in normalized.lower() and "estoques (imoveis a comercializar)" not in normalized.lower():
        return None

    match = re.search(
        r"estoques\s*\(im[óo]veis\s+a\s+comercializar\)\s*\(r\$\s*milh[õo]es\).*?\btotal\s+(\(?[-+]?\d[\d\.,]*\)?)",
        normalized,
        re.IGNORECASE,
    )
    if not match:
        return None

    return build_metric_payload(
        "estoque",
        match.group(1).strip(),
        page_number,
        match.group(0),
        "milhões",
    )


def extract_operational_narrative_from_page(metric_name, page_text, page_number):
    normalized = normalize_line(page_text)
    lowered = normalized.lower()

    if metric_name == "lancamentos":
        if "lançamentos" not in lowered and "lancamentos" not in lowered:
            return None
        patterns = [
            r"(?:maior\s+volume\s+de\s+)?lan[çc]amentos?.{0,180}?(?:totalizando|totalizaram|somaram|atingiram|alcan[çc]aram)\s+(R\$\s*\(?[-+]?\d[\d\.,]*\)?\s*(?:bilhão|bilhao|bilhões|bilhoes|milhões|milhoes|mil|bi)?)",
            r"lan[çc]amentos?.{0,120}?(R\$\s*\(?[-+]?\d[\d\.,]*\)?\s*(?:bilhão|bilhao|bilhões|bilhoes|milhões|milhoes|mil|bi)?)",
        ]
    elif metric_name == "vendas_liquidas":
        if "vendas líquidas" not in lowered and "vendas liquidas" not in lowered:
            return None
        patterns = [
            r"vendas\s+l[íi]quidas(?:\s+contratadas)?\s*\(\s*(R\$\s*\(?[-+]?\d[\d\.,]*\)?\s*(?:bilhão|bilhao|bilhões|bilhoes|milhões|milhoes|mil|bi)?)\s*\)",
            r"vendas\s+l[íi]quidas(?:\s+contratadas)?.{0,80}?(?:de|totalizando|totalizaram|somaram|atingiram|alcan[çc]aram)\s+(R\$\s*\(?[-+]?\d[\d\.,]*\)?\s*(?:bilhão|bilhao|bilhões|bilhoes|milhões|milhoes|mil|bi)?)",
            r"vendas\s+l[íi]quidas(?:\s+contratadas)?.{0,80}?(R\$\s*\(?[-+]?\d[\d\.,]*\)?\s*(?:bilhão|bilhao|bilhões|bilhoes|milhões|milhoes|mil|bi)?)",
        ]
    else:
        return None

    for pattern in patterns:
        match = re.search(pattern, normalized, re.IGNORECASE)
        if not match:
            continue
        evidence = match.group(0)
        if metric_name == "lancamentos" and re.search(r"\b(?:luggo|urba|ahs)\b", evidence, re.IGNORECASE) and not re.search(r"mrv\s*&?\s*co", evidence, re.IGNORECASE):
            continue
        return build_metric_payload(
            metric_name,
            match.group(1).strip(),
            page_number,
            evidence,
            infer_unit_from_text(evidence),
        )

    return None


def extract_metric_from_line(metric_name, line, page_number, unit_hint=None):
    normalized = normalize_line(line)
    lowered = normalized.lower()
    if not normalized:
        return None

    if metric_name == "estoque":
        stock_match = re.search(
            r"estoque\s+a\s+valor\s+de\s+mercado\s*\(r\$\s*(bilh[õo]es|milh[õo]es|mil|bi)\)\*?\s+(\(?[-+]?\d[\d\.,]*\)?)",
            normalized,
            re.IGNORECASE,
        )
        if stock_match:
            return build_metric_payload(
                metric_name,
                stock_match.group(2).strip(),
                page_number,
                normalized,
                stock_match.group(1).strip(),
            )

    if metric_name == "geracao_caixa":
        cash_match = re.search(
            r"gera[çc][ãa]o\s+de\s+caixa(?:\s*-\s*r\$\s*milh[õo]es)?\s+(\(?[-+]?\d[\d\.,]*\)?)",
            normalized,
            re.IGNORECASE,
        )
        if cash_match:
            return build_metric_payload(
                metric_name,
                cash_match.group(1).strip(),
                page_number,
                normalized,
                "milhões",
            )

    patterns = {
        "receita_operacional_liquida": r"receita operacional l[íi]quida(?: total)?\s+(\(?[-+]?\d[\d\.,]*\)?(?:\s*(?:bilhões|bilhoes|milhões|milhoes|mil|bi))?\b)",
        "lucro_liquido": r"lucro l[íi]quido(?! ajustado)\s+(\(?[-+]?\d[\d\.,]*\)?(?:\s*(?:bilhões|bilhoes|milhões|milhoes|mil|bi))?\b)",
        "ebitda": r"\bebitda\b(?!\s*12)\s+(\(?[-+]?\d[\d\.,]*\)?(?:\s*(?:bilhões|bilhoes|milhões|milhoes|mil|bi))?\b)",
        "margem_bruta": r"margem bruta(?: \(%\))?\s+([-+]?\d[\d\.,]*\s*%)",
        "vso": r"\bvso\b[^\d%]*([-+]?\d[\d\.,]*\s*%)",
        "estoque": r"estoques? \(im[óo]veis a comercializar\)[^\d]*(\(?[-+]?\d[\d\.,]*\)?)",
        "geracao_caixa": r"gera[çc][ãa]o de caixa[^\d\(+-]*(\(?[-+]?\d[\d\.,]*\)?(?:\s*(?:bilhões|bilhoes|milhões|milhoes|mil|bi))?\b)",
    }

    pattern = patterns.get(metric_name)
    if not pattern:
        return None
    if metric_name == "ebitda" and "12 meses" in lowered:
        return None

    match = re.search(pattern, normalized, re.IGNORECASE)
    if not match:
        return None
    inferred_unit = unit_hint
    if metric_name in {"margem_bruta", "vso"}:
        inferred_unit = "%"
    elif metric_name in {"estoque", "geracao_caixa"}:
        inferred_unit = infer_unit_from_text(normalized)
    return build_metric_payload(metric_name, match.group(1).strip(), page_number, normalized, inferred_unit)


def extract_table_metrics_from_raw_pages(raw_pages):
    metrics = {
        metric_name: empty_metric(metric_name)
        for metric_name, _ in METRIC_SPECS
    }

    for page_number, raw_page in enumerate(raw_pages, start=1):
        normalized_lines = [normalize_line(line) for line in raw_page.splitlines() if normalize_line(line)]
        current_section = None
        if not metrics["distratos"].get("encontrado"):
            distratos_candidate = extract_distratos_from_page(raw_page, page_number)
            if distratos_candidate and distratos_candidate.get("encontrado"):
                metrics["distratos"] = distratos_candidate
        if not metrics["lancamentos"].get("encontrado"):
            lancamentos_graph_candidate = extract_lancamentos_graph_from_page(raw_page, page_number)
            if lancamentos_graph_candidate and lancamentos_graph_candidate.get("encontrado"):
                metrics["lancamentos"] = lancamentos_graph_candidate
        if not metrics["estoque"].get("encontrado"):
            stock_total_candidate = extract_stock_total_from_page(raw_page, page_number)
            if stock_total_candidate and stock_total_candidate.get("encontrado"):
                metrics["estoque"] = stock_total_candidate
        for metric_name in ("vendas_liquidas", "lancamentos", "unidades_produzidas", "repasses"):
            if metrics[metric_name].get("encontrado"):
                continue
            compact_candidate = extract_compact_operational_metric_from_page(metric_name, raw_page, page_number)
            if compact_candidate and compact_candidate.get("encontrado"):
                metrics[metric_name] = compact_candidate
        for metric_name in ("lancamentos", "vendas_liquidas"):
            if metrics[metric_name].get("encontrado"):
                continue
            narrative_candidate = extract_operational_narrative_from_page(metric_name, raw_page, page_number)
            if narrative_candidate and narrative_candidate.get("encontrado"):
                metrics[metric_name] = narrative_candidate

        for line in normalized_lines:
            lowered = line.lower()
            if "vendas líquidas contratadas" in lowered or "vendas - mrv" in lowered or "vendas - mrv&co" in lowered:
                current_section = "vendas_liquidas"
            elif lowered == "produção" or lowered == "producao" or lowered.startswith("produção ") or lowered.startswith("producao "):
                current_section = "unidades_produzidas"
            elif "crédito imobiliário" in lowered or "credito imobiliario" in lowered or lowered.startswith("repasses"):
                current_section = "repasses"
            elif "lançamentos" in lowered or "lancamentos" in lowered:
                current_section = "lancamentos"
            elif "estoque a valor de mercado" in lowered or lowered.startswith("estoque"):
                current_section = "estoque"

            for metric_name in (
                "receita_operacional_liquida",
                "lucro_liquido",
                "ebitda",
                "margem_bruta",
                "vso",
                "estoque",
                "distratos",
                "geracao_caixa",
            ):
                if metrics[metric_name].get("encontrado"):
                    continue
                candidate = extract_metric_from_line(metric_name, line, page_number)
                if candidate and candidate.get("encontrado"):
                    metrics[metric_name] = candidate

            if not metrics["vendas_liquidas"].get("encontrado"):
                if current_section == "vendas_liquidas" and (
                    lowered.startswith("vendas (")
                    or lowered.startswith("vendas vgv ")
                    or lowered.startswith("vgv (")
                    or lowered.startswith("mrv vgv ")
                ):
                    token = extract_primary_token(line, expect_percent=False)
                    if token:
                        metrics["vendas_liquidas"] = build_metric_payload(
                            "vendas_liquidas",
                            token,
                            page_number,
                            line,
                            infer_unit_from_text(line) or "milhões",
                        )

            if not metrics["lancamentos"].get("encontrado"):
                if current_section == "lancamentos" and (
                    lowered.startswith("vgv (")
                    or lowered.startswith("mrv vgv ")
                    or lowered.startswith("lançamentos vgv ")
                    or lowered.startswith("lancamentos vgv ")
                ):
                    token = extract_primary_token(line, expect_percent=False)
                    if token:
                        metrics["lancamentos"] = build_metric_payload(
                            "lancamentos",
                            token,
                            page_number,
                            line,
                            infer_unit_from_text(line) or "milhões",
                        )

            if not metrics["unidades_produzidas"].get("encontrado") and lowered.startswith("unidades produzidas"):
                token = extract_primary_token(line, expect_percent=False)
                if token:
                    metrics["unidades_produzidas"] = build_metric_payload(
                        "unidades_produzidas",
                        token,
                        page_number,
                        line,
                        "unidades",
                    )

            if not metrics["repasses"].get("encontrado") and lowered.startswith("unidades repassadas"):
                token = extract_primary_token(line, expect_percent=False)
                if token:
                    metrics["repasses"] = build_metric_payload(
                        "repasses",
                        token,
                        page_number,
                        line,
                        "unidades",
                    )
    return metrics


def extract_metrics_from_pages(pages):
    metrics = {}

    for metric_name, aliases in METRIC_SPECS:
        metrics[metric_name] = empty_metric(metric_name)

        for page_number, page_text in enumerate(pages, start=1):
            lowered = page_text.lower()
            alias_index = None

            for alias in aliases:
                index = lowered.find(alias)
                if index >= 0 and (alias_index is None or index < alias_index):
                    alias_index = index

            if alias_index is None:
                continue

            windows = [
                page_text[alias_index : alias_index + 420],
                page_text[max(0, alias_index - 80) : alias_index + 420],
            ]

            value_text = None
            payload = None
            for window in windows:
                value_text, payload = extract_value_from_window(window)
                if value_text:
                    break

            if not value_text:
                continue

            metrics[metric_name] = {
                "nome": metric_name,
                "valor_textual": value_text,
                "valor_numerico": payload.get("valor_numerico"),
                "unidade": payload.get("unidade"),
                "pagina": page_number,
                "trecho": page_excerpt(window),
                "encontrado": True,
            }
            break

    return metrics


def build_semantic_record(document, pdf_path):
    text = pdf_text(pdf_path)
    pages = split_pages(text)
    raw_pages = split_raw_pages(text)
    page_payloads = []

    for page_number, page_text in enumerate(pages, start=1):
        page_payloads.append(
            {
                "pagina": page_number,
                "secao": classify_section(page_text),
                "texto": page_text,
                "trecho": page_excerpt(page_text),
                "caracteres": len(page_text),
            }
        )

    return {
        "empresa": document.get("company", "MRV"),
        "ano": document.get("year"),
        "trimestre": document.get("quarter"),
        "titulo_documento": document.get("title"),
        "tipo_documento": document.get("internal_name"),
        "data_publicacao": document.get("published_date"),
        "source_url": document.get("source_url"),
        "stored_path": document.get("stored_path"),
        "sha256": document.get("sha256") or sha256_file(pdf_path),
        "data_lineage": build_data_lineage(document, pdf_path),
        "extraido_em": now_utc(),
        "modo_extracao": "pdftotext+heuristicas",
        "schema_version": "fallback-heuristic-1.0",
        "pagina_total": len(page_payloads),
        "paginas": page_payloads,
        "metricas": merge_metric_sources(
            extract_table_metrics_from_raw_pages(raw_pages),
            extract_metrics_from_pages(pages),
        ),
    }


def merge_metric_sources(primary, secondary):
    merged = {}
    for metric_name, _ in METRIC_SPECS:
        primary_metric = (primary or {}).get(metric_name) or empty_metric(metric_name)
        secondary_metric = (secondary or {}).get(metric_name) or empty_metric(metric_name)
        merged[metric_name] = primary_metric if primary_metric.get("encontrado") else secondary_metric
    return merged
