import json
import os
import re
import subprocess
import time
import tempfile
import base64
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

SEMANTIC_SCHEMA_VERSION = "1.0"

METRIC_SPEC = [
    {"name": "receita_operacional_liquida", "label": "Receita Operacional Líquida", "kind": "absoluta"},
    {"name": "lucro_liquido", "label": "Lucro Líquido", "kind": "absoluta"},
    {"name": "ebitda", "label": "EBITDA", "kind": "absoluta"},
    {"name": "margem_bruta", "label": "Margem Bruta", "kind": "percentual"},
    {"name": "vendas_liquidas", "label": "Vendas Líquidas", "kind": "absoluta"},
    {"name": "lancamentos", "label": "Lançamentos", "kind": "absoluta"},
    {"name": "unidades_produzidas", "label": "Unidades Produzidas", "kind": "absoluta"},
    {"name": "repasses", "label": "Repasses", "kind": "absoluta"},
    {"name": "estoque", "label": "Estoque", "kind": "absoluta"},
    {"name": "vso", "label": "VSO", "kind": "percentual"},
    {"name": "distratos", "label": "Distratos", "kind": "absoluta"},
    {"name": "geracao_caixa", "label": "Geração de Caixa", "kind": "absoluta"},
]

METRIC_ALIASES = {
    "receita_operacional_liquida": ["receita operacional líquida", "receita operacional liquida", "rol"],
    "lucro_liquido": ["lucro líquido", "lucro liquido"],
    "ebitda": ["ebitda"],
    "margem_bruta": ["margem bruta"],
    "vendas_liquidas": ["vendas líquidas", "vendas liquidas", "vendas líquidas contratadas", "vendas liquidas contratadas"],
    "lancamentos": ["lançamentos", "lancamentos"],
    "unidades_produzidas": ["unidades produzidas", "unidades produzidas"],
    "repasses": ["repasses", "unidades repassadas", "unidades repassadas"],
    "estoque": ["estoque", "estoques"],
    "vso": ["vso"],
    "distratos": ["distratos"],
    "geracao_caixa": ["geração de caixa", "geracao de caixa", "caixa"],
}

METRIC_GROUPS = [
    ["receita_operacional_liquida", "margem_bruta", "ebitda"],
    ["lucro_liquido", "geracao_caixa"],
    ["vendas_liquidas", "lancamentos", "unidades_produzidas"],
    ["repasses", "vso", "estoque", "distratos"],
]

ANNEX_KEYWORDS = [
    "anexo",
    "demonstração do resultado",
    "demonstracao do resultado",
    "demonstrações financeiras",
    "demonstracoes financeiras",
    "fluxo de caixa",
    "balanço patrimonial",
    "balanco patrimonial",
    "resultado consolidado",
]


def _load_env_file():
    env_path = Path(__file__).resolve().parent / ".env"
    if not env_path.exists():
        return

    for raw_line in env_path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        if key and key not in os.environ:
            os.environ[key] = value


_load_env_file()


def _run_command(args):
    return subprocess.run(args, capture_output=True, text=True, check=True)


def _pdf_text(pdf_path):
    result = _run_command(["pdftotext", "-layout", str(pdf_path), "-"])
    return result.stdout


def _pdf_page_count(pdf_path):
    result = _run_command(["pdfinfo", str(pdf_path)])
    match = re.search(r"^Pages:\s+(\d+)", result.stdout, re.MULTILINE)
    if not match:
        return None
    return int(match.group(1))


def _split_pages(text):
    pages = []
    for raw_page in text.split("\f"):
        cleaned = re.sub(r"\s+", " ", raw_page).strip()
        if cleaned:
            pages.append(cleaned)
    return pages


def _pick_chunks(pages, metric_names=None):
    chunks = []
    seen_pages = set()

    keywords = [
        "destaques financeiros",
        "destaques operacionais",
        "indicadores financeiros",
        "evento subsequente",
        "mensagem da administração",
    ]
    if metric_names:
        for metric_name in metric_names:
            keywords.extend(METRIC_ALIASES.get(metric_name, []))

    for page_number, page_text in enumerate(pages, start=1):
        lowered = page_text.lower()
        matches_metric_context = any(keyword in lowered for keyword in keywords)
        matches_annex_context = any(keyword in lowered for keyword in ANNEX_KEYWORDS)
        if not matches_metric_context and not matches_annex_context:
            continue

        for candidate_page in (page_number - 1, page_number, page_number + 1):
            if candidate_page < 1 or candidate_page > len(pages) or candidate_page in seen_pages:
                continue
            seen_pages.add(candidate_page)
            chunks.append(
                {
                    "pagina": candidate_page,
                    "trecho": pages[candidate_page - 1][:2200],
                }
            )

    if not chunks:
        fallback_pages = list(range(1, min(len(pages), 6) + 1))
        tail_start = max(1, len(pages) - 7)
        fallback_pages.extend(range(tail_start, len(pages) + 1))
        for page_number in dict.fromkeys(fallback_pages):
            chunks.append(
                {
                    "pagina": page_number,
                    "trecho": pages[page_number - 1][:2200],
                }
            )
    return chunks


def _pick_visual_pages(pages, metric_names=None):
    metric_names = metric_names or [spec["name"] for spec in METRIC_SPEC]
    aliases = []
    for metric_name in metric_names:
        aliases.extend(METRIC_ALIASES.get(metric_name, []))

    page_scores = {}
    metric_group_is_operational = any(
        metric_name in {
            "vendas_liquidas",
            "lancamentos",
            "unidades_produzidas",
            "repasses",
            "estoque",
            "vso",
            "distratos",
        }
        for metric_name in metric_names
    )
    metric_group_is_financial = any(
        metric_name in {
            "receita_operacional_liquida",
            "lucro_liquido",
            "ebitda",
            "margem_bruta",
            "geracao_caixa",
        }
        for metric_name in metric_names
    )

    def add_score(page_number, score):
        if 1 <= page_number <= len(pages):
            page_scores[page_number] = page_scores.get(page_number, 0) + score

    operational_keywords = [
        "destaques operacionais",
        "indicadores operacionais",
        "vendas líquidas",
        "vendas liquidas",
        "lançamentos",
        "lancamentos",
        "unidades produzidas",
        "unidades repassadas",
        "vso",
        "distrato",
        "distratos",
        "venda x distrato",
    ]
    financial_keywords = [
        "destaques financeiros",
        "indicadores financeiros",
        "receita operacional líquida",
        "receita operacional liquida",
        "rol",
        "ebitda",
        "lucro líquido",
        "lucro liquido",
        "geração de caixa",
        "geracao de caixa",
        "margem bruta",
    ]

    for page_number, page_text in enumerate(pages, start=1):
        lowered = page_text.lower()
        text_length = len(page_text.strip())
        alias_hits = sum(1 for alias in aliases if alias in lowered)
        if alias_hits:
            add_score(page_number, 20 + alias_hits * 3)
            add_score(page_number - 1, 5)
            add_score(page_number + 1, 8)
            add_score(page_number + 2, 4)
            if page_number <= max(12, len(pages) // 3):
                add_score(page_number, 10)

        if metric_group_is_operational:
            keyword_hits = sum(1 for keyword in operational_keywords if keyword in lowered)
            if keyword_hits:
                add_score(page_number, 32 + keyword_hits * 4)
                add_score(page_number + 1, 10)
                add_score(page_number + 2, 7)
                add_score(page_number + 3, 4)
                if page_number <= max(12, len(pages) // 3):
                    add_score(page_number, 18)
        if metric_group_is_financial:
            keyword_hits = sum(1 for keyword in financial_keywords if keyword in lowered)
            if keyword_hits:
                add_score(page_number, 32 + keyword_hits * 4)
                add_score(page_number + 1, 10)
                add_score(page_number + 2, 7)
                add_score(page_number + 3, 4)
                if page_number <= max(12, len(pages) // 3):
                    add_score(page_number, 18)

        if text_length <= 500:
            add_score(page_number, 9)
            add_score(page_number - 1, 4)
            add_score(page_number + 1, 8)
            add_score(page_number + 2, 6)
            add_score(page_number + 3, 3)

        if page_number <= max(16, len(pages) // 2):
            add_score(page_number, 5)
        if page_number <= max(10, len(pages) // 3):
            add_score(page_number, 4)

    if metric_group_is_operational:
        for page_number, page_text in enumerate(pages, start=1):
            lowered = page_text.lower()
            if "destaques operacionais" in lowered or "indicadores operacionais" in lowered:
                for offset, score in enumerate((30, 24, 20, 16, 12, 8, 5)):
                    add_score(page_number + offset, score)
    if metric_group_is_financial:
        for page_number, page_text in enumerate(pages, start=1):
            lowered = page_text.lower()
            if "destaques financeiros" in lowered or "indicadores financeiros" in lowered:
                for offset, score in enumerate((30, 24, 20, 16, 12, 8, 5)):
                    add_score(page_number + offset, score)

    if not page_scores:
        fallback_seeds = [3, 4, 7, 8, 10, 12, 13]
        for page_number in fallback_seeds:
            add_score(page_number, 10)

    ranked_pages = [
        page_number
        for page_number, _score in sorted(page_scores.items(), key=lambda item: (-item[1], item[0]))
    ]

    selected = []
    seen = set()
    for page_number in ranked_pages:
        if page_number in seen:
            continue
        seen.add(page_number)
        selected.append(page_number)
        if len(selected) >= 18:
            break

    if len(selected) < 12:
        anchors = list(selected) or [1]
        for anchor in anchors:
            for neighbor in (anchor - 1, anchor + 1, anchor + 2, anchor - 2, anchor + 3):
                if 1 <= neighbor <= len(pages) and neighbor not in seen:
                    seen.add(neighbor)
                    selected.append(neighbor)
                if len(selected) >= min(12, len(pages)):
                    break
            if len(selected) >= min(12, len(pages)):
                break

    return sorted(selected)


def _group_visual_pages(page_numbers, max_batch_size=4, overlap_size=1):
    if not page_numbers:
        return []

    ordered_pages = sorted(dict.fromkeys(page_numbers))
    contiguous_runs = []
    current_run = [ordered_pages[0]]

    for page_number in ordered_pages[1:]:
        if page_number == current_run[-1] + 1:
            current_run.append(page_number)
        else:
            contiguous_runs.append(current_run)
            current_run = [page_number]
    contiguous_runs.append(current_run)

    batches = []
    for run in contiguous_runs:
        if len(run) <= max_batch_size:
            batches.append(run)
            continue

        step = max(1, max_batch_size - max(0, overlap_size))
        for start in range(0, len(run), step):
            batch = run[start : start + max_batch_size]
            if not batch:
                continue
            if batches and batch == batches[-1]:
                continue
            batches.append(batch)
            if batch[-1] == run[-1]:
                break

    return batches


def _aggressive_visual_pages(pages, selected_pages):
    expanded = set(selected_pages)
    total_pages = len(pages)
    late_page_floor = max(1, total_pages - 14)

    for page_number, page_text in enumerate(pages, start=1):
        lowered = page_text.lower()
        text_length = len(page_text.strip())
        is_annex_like = any(keyword in lowered for keyword in ANNEX_KEYWORDS) or "anexo" in lowered
        is_financial_statement = any(
            keyword in lowered
            for keyword in (
                "demonstração do resultado",
                "demonstracao do resultado",
                "fluxo de caixa",
                "balanço patrimonial",
                "balanco patrimonial",
                "resultado consolidado",
            )
        )
        is_sparse_late_page = page_number >= late_page_floor and text_length <= 1200
        if not (is_annex_like or is_financial_statement or is_sparse_late_page):
            continue

        for candidate_page in (page_number - 1, page_number, page_number + 1):
            if 1 <= candidate_page <= total_pages:
                expanded.add(candidate_page)

    return sorted(expanded)


def _metric_schema(metric_names):
    schema = {}
    for metric_name in metric_names:
        schema[metric_name] = {
            "valor_textual": "string|null",
            "valor_numerico": "number|null",
            "unidade": "string|null",
            "pagina": "integer|null",
            "trecho_evidencia": "string|null",
            "encontrado": "boolean",
        }
    return schema


def _prompt_user_payload(document, metric_names, chunks=None):
    schema = {
        "schema_version": SEMANTIC_SCHEMA_VERSION,
        "empresa": "string",
        "ano": "integer",
        "trimestre": "integer",
        "titulo_documento": "string",
        "source_url": "string",
        "sha256": "string",
        "metricas": _metric_schema(metric_names),
        "observacoes": ["string"],
    }
    payload = {
        "documento": {
            "empresa": document.get("company", "MRV"),
            "ano": document.get("year"),
            "trimestre": document.get("quarter"),
            "titulo_documento": document.get("title"),
            "source_url": document.get("source_url"),
            "sha256": document.get("sha256"),
        },
        "schema": schema,
        "metricas_alvo": metric_names,
    }
    if chunks is not None:
        payload["chunks"] = chunks
    return payload


def build_semantic_prompt(document, pages, metric_names=None):
    metric_names = metric_names or [spec["name"] for spec in METRIC_SPEC]
    prompt = {
        "system": (
            "Você é um extrator semântico de relatórios trimestrais de RI. "
            "Extraia apenas dados explícitos no documento. Nunca invente valores. "
            "Se o valor não estiver claro, use null e `encontrado=false`. "
            "Priorize valores absolutos e ignore percentuais de variação quando a métrica for absoluta. "
            "Nunca reutilize um número vizinho de outra métrica ou de outro contexto da mesma página. "
            "Cada valor deve estar explicitamente associado ao rótulo da métrica pedida. "
            "Considere também tabelas e anexos no fim do relatório, inclusive demonstrações financeiras e fluxo de caixa. "
            "Retorne exatamente um objeto JSON, não uma lista."
        ),
        "user": _prompt_user_payload(document, metric_names, chunks=_pick_chunks(pages, metric_names)),
    }
    return prompt


def _append_diagnostic(diagnostics, payload):
    if diagnostics is None:
        return
    diagnostics.setdefault("attempts", []).append(payload)


def _visual_batch_delay():
    try:
        return float(os.environ.get("GEMINI_VISUAL_BATCH_DELAY_SECONDS", "1"))
    except ValueError:
        return 1.0


def _empty_metric(metric_name):
    return {
        "valor_textual": None,
        "valor_numerico": None,
        "unidade": None,
        "pagina": None,
        "trecho_evidencia": None,
        "encontrado": False,
    }


def _empty_semantic_record(document):
    return {
        "schema_version": SEMANTIC_SCHEMA_VERSION,
        "empresa": document.get("company", "MRV"),
        "ano": document.get("year"),
        "trimestre": document.get("quarter"),
        "titulo_documento": document.get("title"),
        "source_url": document.get("source_url"),
        "sha256": document.get("sha256"),
        "metricas": {spec["name"]: _empty_metric(spec["name"]) for spec in METRIC_SPEC},
        "observacoes": [],
    }


def validate_semantic_payload(payload, metric_names=None):
    if isinstance(payload, list):
        if not payload:
            raise ValueError("payload_semantico_invalido")
        payload = payload[0]

    if not isinstance(payload, dict):
        raise ValueError("payload_semantico_invalido")

    required = ["empresa", "ano", "trimestre", "titulo_documento", "source_url", "sha256", "metricas"]
    for key in required:
        if key not in payload:
            raise ValueError(f"campo_obrigatorio_ausente:{key}")

    payload["schema_version"] = str(payload.get("schema_version") or SEMANTIC_SCHEMA_VERSION)
    payload["observacoes"] = payload.get("observacoes") or []

    metricas = payload.get("metricas") or {}
    wanted = metric_names or [spec["name"] for spec in METRIC_SPEC]
    for metric_name in wanted:
        metric = metricas.get(metric_name) or {}
        metricas[metric_name] = {
            "valor_textual": metric.get("valor_textual"),
            "valor_numerico": metric.get("valor_numerico"),
            "unidade": metric.get("unidade"),
            "pagina": metric.get("pagina"),
            "trecho_evidencia": metric.get("trecho_evidencia"),
            "encontrado": bool(metric.get("encontrado")),
        }
    payload["metricas"] = metricas
    return payload


def _normalize_semantic_payload(payload, document):
    if isinstance(payload, list) and payload:
        payload = payload[0]

    if not isinstance(payload, dict):
        return None

    if not payload.get("metricas"):
        for wrapper_key in ("data", "result", "response", "payload", "schema"):
            nested = payload.get(wrapper_key)
            if isinstance(nested, dict) and nested.get("metricas"):
                payload = nested
                break

    payload.setdefault("schema_version", SEMANTIC_SCHEMA_VERSION)
    payload["empresa"] = payload.get("empresa") or document.get("company", "MRV")
    payload["ano"] = payload.get("ano") if payload.get("ano") is not None else document.get("year")
    payload["trimestre"] = payload.get("trimestre") if payload.get("trimestre") is not None else document.get("quarter")
    payload["titulo_documento"] = payload.get("titulo_documento") or document.get("title")
    payload["source_url"] = payload.get("source_url") or document.get("source_url")
    payload["sha256"] = payload.get("sha256") or document.get("sha256")
    payload["metricas"] = payload.get("metricas") or {}
    payload["observacoes"] = payload.get("observacoes") or []
    return payload


def _merge_semantic_records(base, partial):
    if not partial:
        return base

    for key in ("schema_version", "empresa", "ano", "trimestre", "titulo_documento", "source_url", "sha256"):
        if partial.get(key) is not None:
            base[key] = partial.get(key)

    base["observacoes"] = list(dict.fromkeys((base.get("observacoes") or []) + (partial.get("observacoes") or [])))

    partial_metrics = partial.get("metricas") or {}
    for metric_name, metric in partial_metrics.items():
        if metric.get("encontrado"):
            base["metricas"][metric_name] = metric
        elif metric_name not in base["metricas"]:
            base["metricas"][metric_name] = metric

    return base


def _full_pdf_allowed(pdf_path):
    max_mb = float(os.environ.get("GEMINI_FULL_PDF_MAX_MB", "8"))
    max_pages = int(os.environ.get("GEMINI_FULL_PDF_MAX_PAGES", "80"))
    file_size_mb = Path(pdf_path).stat().st_size / (1024 * 1024)
    page_count = _pdf_page_count(pdf_path)
    if page_count is None:
        return False, {"file_size_mb": file_size_mb, "page_count": None}
    return file_size_mb <= max_mb and page_count <= max_pages, {
        "file_size_mb": file_size_mb,
        "page_count": page_count,
        "max_mb": max_mb,
        "max_pages": max_pages,
    }


def _extract_pdf_bundle(document, pdf_path, metric_names, diagnostics=None):
    allowed, limits = _full_pdf_allowed(pdf_path)
    if not allowed:
        _append_diagnostic(
            diagnostics,
            {
                "kind": "pdf",
                "metric_names": list(metric_names),
                "status": "skipped_by_size",
                **limits,
            },
        )
        return None

    user_payload = _prompt_user_payload(document, metric_names)
    prompt_text = (
        "Você é um extrator semântico de relatórios trimestrais de RI. "
        "O PDF completo está anexado como application/pdf. Leia o documento inteiro, incluindo destaques, tabelas, gráficos e anexos. "
        "Extraia apenas dados explícitos no documento. Nunca invente valores. "
        "Se o valor não estiver claro, use null e `encontrado=false`. "
        "Priorize valores absolutos e ignore percentuais de variação quando a métrica for absoluta. "
        "Cada valor deve estar explicitamente associado ao rótulo da métrica pedida.\n\n"
        f"DOCUMENTO_JSON:\n{json.dumps(user_payload, ensure_ascii=False)}\n\n"
        "Retorne apenas JSON válido no formato solicitado."
    )
    encoded_pdf = base64.b64encode(Path(pdf_path).read_bytes()).decode("ascii")
    body = json.dumps(
        {
            "contents": [
                {
                    "parts": [
                        {"text": prompt_text},
                        {
                            "inline_data": {
                                "mime_type": "application/pdf",
                                "data": encoded_pdf,
                            }
                        },
                    ]
                }
            ],
            "generationConfig": {
                "temperature": 0,
                "responseMimeType": "application/json",
            },
        }
    ).encode("utf-8")

    _append_diagnostic(
        diagnostics,
        {
            "kind": "pdf",
            "metric_names": list(metric_names),
            "prompt": prompt_text,
            "status": "request",
            **limits,
        },
    )

    request = Request(
        f"https://generativelanguage.googleapis.com/v1beta/models/{os.environ.get('GEMINI_MODEL', 'gemma-4-26b-a4b-it')}:generateContent",
        data=body,
        headers={
            "content-type": "application/json",
            "x-goog-api-key": os.environ.get("GEMINI_API_KEY", ""),
        },
        method="POST",
    )

    max_attempts = 3
    base_delay = float(os.environ.get("GEMINI_RETRY_DELAY_SECONDS", "20"))
    for attempt in range(1, max_attempts + 1):
        try:
            with urlopen(request, timeout=180) as response:
                result = json.loads(response.read().decode("utf-8"))
            content = _gemini_response_text(result)
            if not content:
                _append_diagnostic(
                    diagnostics,
                    {"kind": "pdf", "metric_names": list(metric_names), "status": "empty_response"},
                )
                return None
            parsed_snapshot = json.loads(content)
            parsed = _normalize_semantic_payload(parsed_snapshot, document)
            if not parsed:
                _append_diagnostic(
                    diagnostics,
                    {
                        "kind": "pdf",
                        "metric_names": list(metric_names),
                        "raw_response": content,
                        "parsed": parsed_snapshot,
                        "status": "normalize_failed",
                    },
                )
                return None
            validated = validate_semantic_payload(parsed, metric_names=metric_names)
            _append_diagnostic(
                diagnostics,
                {
                    "kind": "pdf",
                    "metric_names": list(metric_names),
                    "raw_response": content,
                    "parsed": parsed_snapshot,
                    "validated": validated,
                    "status": "ok",
                },
            )
            return validated
        except (ValueError, json.JSONDecodeError):
            _append_diagnostic(
                diagnostics,
                {"kind": "pdf", "metric_names": list(metric_names), "status": "json_error"},
            )
            return None
        except HTTPError as exc:
            if exc.code in {400, 413, 415}:
                _append_diagnostic(
                    diagnostics,
                    {
                        "kind": "pdf",
                        "metric_names": list(metric_names),
                        "status": f"unsupported_or_too_large:{exc.code}",
                    },
                )
                return None
            if exc.code not in {429, 500, 502, 503, 504}:
                raise
            _append_diagnostic(
                diagnostics,
                {
                    "kind": "pdf",
                    "metric_names": list(metric_names),
                    "status": f"retryable_http_error:{exc.code}",
                    "attempt": attempt,
                },
            )
            if attempt == max_attempts:
                return None
            time.sleep(base_delay * attempt)
        except URLError:
            _append_diagnostic(
                diagnostics,
                {
                    "kind": "pdf",
                    "metric_names": list(metric_names),
                    "status": "retryable_url_error",
                    "attempt": attempt,
                },
            )
            if attempt == max_attempts:
                return None
            time.sleep(base_delay * attempt)


def _extract_bundle(document, pdf_path, metric_names, diagnostics=None):
    text = _pdf_text(pdf_path)
    pages = _split_pages(text)
    prompt = build_semantic_prompt(document, pages, metric_names=metric_names)
    prompt_text = (
        f"{prompt['system']}\n\n"
        f"DOCUMENTO_JSON:\n{json.dumps(prompt['user'], ensure_ascii=False)}\n\n"
        "Retorne apenas JSON válido no formato solicitado."
    )

    body = json.dumps(
        {
            "contents": [
                {
                    "parts": [
                        {
                            "text": prompt_text
                        }
                    ]
                }
            ],
            "generationConfig": {
                "temperature": 0,
                "responseMimeType": "application/json",
            },
            }
        ).encode("utf-8")

    _append_diagnostic(
        diagnostics,
        {
            "kind": "text",
            "metric_names": list(metric_names),
            "chunks": prompt["user"]["chunks"],
            "prompt": prompt_text,
        },
    )

    request = Request(
        f"https://generativelanguage.googleapis.com/v1beta/models/{os.environ.get('GEMINI_MODEL', 'gemma-4-26b-a4b-it')}:generateContent",
        data=body,
        headers={
            "content-type": "application/json",
            "x-goog-api-key": os.environ.get("GEMINI_API_KEY", ""),
        },
        method="POST",
    )

    max_attempts = 4
    base_delay = float(os.environ.get("GEMINI_RETRY_DELAY_SECONDS", "20"))

    for attempt in range(1, max_attempts + 1):
        try:
            with urlopen(request, timeout=180) as response:
                result = json.loads(response.read().decode("utf-8"))
            content = _gemini_response_text(result)
            if not content:
                _append_diagnostic(
                    diagnostics,
                    {
                        "kind": "text",
                        "metric_names": list(metric_names),
                        "raw_response": None,
                        "status": "empty_response",
                    },
                )
                return None
            parsed = json.loads(content)
            parsed_snapshot = parsed
            parsed = _normalize_semantic_payload(parsed, document)
            if not parsed:
                _append_diagnostic(
                    diagnostics,
                    {
                        "kind": "text",
                        "metric_names": list(metric_names),
                        "raw_response": content,
                        "parsed": parsed_snapshot,
                        "status": "normalize_failed",
                    },
                )
                return None
            validated = validate_semantic_payload(parsed, metric_names=metric_names)
            _append_diagnostic(
                diagnostics,
                {
                    "kind": "text",
                    "metric_names": list(metric_names),
                    "raw_response": content,
                    "parsed": parsed_snapshot,
                    "validated": validated,
                    "status": "ok",
                },
            )
            return validated
        except (ValueError, json.JSONDecodeError):
            _append_diagnostic(
                diagnostics,
                {
                    "kind": "text",
                    "metric_names": list(metric_names),
                    "status": "json_error",
                },
            )
            return None
        except HTTPError as exc:
            if exc.code not in {429, 500, 502, 503, 504} or attempt == max_attempts:
                raise
            retry_after = exc.headers.get("Retry-After")
            wait_seconds = base_delay * attempt
            if retry_after:
                try:
                    wait_seconds = max(wait_seconds, float(retry_after))
                except ValueError:
                    pass
            time.sleep(wait_seconds)
        except URLError:
            if attempt == max_attempts:
                raise
            time.sleep(base_delay * attempt)


def _render_page_png_base64(pdf_path, page_number):
    with tempfile.TemporaryDirectory() as temp_dir:
        prefix = Path(temp_dir) / f"page-{page_number}"
        _run_command(
            [
                "pdftoppm",
                "-f",
                str(page_number),
                "-l",
                str(page_number),
                "-png",
                str(pdf_path),
                str(prefix),
            ]
        )
        image_path = Path(f"{prefix}-{page_number}.png")
        if not image_path.exists():
            return None
        return base64.b64encode(image_path.read_bytes()).decode("ascii")


def _extract_visual_bundle(document, pdf_path, metric_names, diagnostics=None, aggressive=False):
    vision_model = os.environ.get("GEMINI_VISION_MODEL") or os.environ.get("GEMINI_MODEL", "gemma-4-26b-a4b-it")
    text = _pdf_text(pdf_path)
    pages = _split_pages(text)
    selected_pages = _pick_visual_pages(
        pages,
        metric_names=metric_names,
    )
    if aggressive:
        selected_pages = _aggressive_visual_pages(pages, selected_pages)
    if not selected_pages:
        return None

    prompt = build_semantic_prompt(document, pages, metric_names=metric_names)
    merged = _empty_semantic_record(document)
    extracted_any = False
    recovery_note = (
        "MODO_RECUPERACAO_AGRESSIVO: este lote é um segundo passe de recuperação. "
        "Concentre-se nas páginas com anexos, demonstrações financeiras, gráficos ou blocos visuais pouco textuais, incluindo vizinhas imediatas. "
        "Se a métrica pedida não estiver confirmada, retorne null.\n\n"
        if aggressive
        else ""
    )

    for page_batch in _group_visual_pages(selected_pages):
        batch_diagnostic = {
            "kind": "visual",
            "metric_names": list(metric_names),
            "selected_pages": list(page_batch),
            "aggressive": aggressive,
        }
        parts = [
                {
                    "text": (
                        "Você está recebendo páginas renderizadas do release trimestral. "
                        "Leia os cards, tabelas e gráficos visuais e extraia APENAS as métricas explícitas listadas em metricas_alvo. "
                        "Se uma métrica não estiver visível com segurança, mantenha null. "
                        "Ignore comparativos e percentuais de variação quando a métrica pedida for absoluta.\n\n"
                        "Nunca associe um número de outra métrica ou de um gráfico vizinho ao campo solicitado. "
                        "Cada valor deve estar explicitamente legível ao lado do rótulo correspondente.\n\n"
                        f"{recovery_note}"
                        f"PAGINAS_DESTE_LOTE: {page_batch}\n\n"
                        f"DOCUMENTO_JSON:\n{json.dumps(prompt['user'], ensure_ascii=False)}\n\n"
                        "Retorne apenas JSON válido no formato solicitado."
                    )
                }
        ]

        for page_number in page_batch:
            encoded = _render_page_png_base64(pdf_path, page_number)
            if not encoded:
                continue
            parts.append(
                {
                    "inline_data": {
                        "mime_type": "image/png",
                        "data": encoded,
                    }
                }
            )

        if len(parts) == 1:
            continue

        body = json.dumps(
            {
                "contents": [{"parts": parts}],
                "generationConfig": {
                    "temperature": 0,
                    "responseMimeType": "application/json",
                },
            }
        ).encode("utf-8")

        request = Request(
            f"https://generativelanguage.googleapis.com/v1beta/models/{vision_model}:generateContent",
            data=body,
            headers={
                "content-type": "application/json",
                "x-goog-api-key": os.environ.get("GEMINI_API_KEY", ""),
            },
            method="POST",
        )

        try:
            with urlopen(request, timeout=180) as response:
                result = json.loads(response.read().decode("utf-8"))
            content = _gemini_response_text(result)
            if not content:
                batch_diagnostic["status"] = "empty_response"
                _append_diagnostic(diagnostics, batch_diagnostic)
                continue
            parsed = json.loads(content)
            parsed_snapshot = parsed
            parsed = _normalize_semantic_payload(parsed, document)
            if not parsed:
                batch_diagnostic.update(
                    {
                        "raw_response": content,
                        "parsed": parsed_snapshot,
                        "status": "normalize_failed",
                    }
                )
                _append_diagnostic(diagnostics, batch_diagnostic)
                continue
            parsed = validate_semantic_payload(parsed, metric_names=metric_names)
            merged = _merge_semantic_records(merged, parsed)
            batch_diagnostic.update(
                {
                    "raw_response": content,
                    "parsed": parsed_snapshot,
                    "validated": parsed,
                    "status": "ok",
                }
            )
            _append_diagnostic(diagnostics, batch_diagnostic)
            if any(
                (merged.get("metricas") or {}).get(metric_name, {}).get("encontrado")
                for metric_name in metric_names
            ):
                extracted_any = True
        except (ValueError, json.JSONDecodeError, HTTPError, URLError):
            batch_diagnostic["status"] = "exception"
            _append_diagnostic(diagnostics, batch_diagnostic)
            continue
        finally:
            delay_seconds = _visual_batch_delay()
            if delay_seconds > 0:
                time.sleep(delay_seconds)

    if not extracted_any:
        return None
    return validate_semantic_payload(merged, metric_names=metric_names)


def try_llm_extract(document, pdf_path, diagnostics=None):
    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key:
        return None

    base_record = _empty_semantic_record(document)
    extracted_any = False
    all_metric_names = [spec["name"] for spec in METRIC_SPEC]

    pdf_partial = _extract_pdf_bundle(document, pdf_path, all_metric_names, diagnostics=diagnostics)
    if pdf_partial:
        base_record = _merge_semantic_records(base_record, pdf_partial)
        extracted_any = any(
            metric.get("encontrado")
            for metric in (base_record.get("metricas") or {}).values()
        )

    for metric_group in METRIC_GROUPS:
        missing_group_metrics = [
            metric_name
            for metric_name in metric_group
            if not (base_record.get("metricas") or {}).get(metric_name, {}).get("encontrado")
        ]
        if not missing_group_metrics:
            continue

        partial = _extract_bundle(document, pdf_path, missing_group_metrics, diagnostics=diagnostics)
        if not partial:
            partial = _extract_visual_bundle(document, pdf_path, missing_group_metrics, diagnostics=diagnostics)
        if not partial:
            continue
        base_record = _merge_semantic_records(base_record, partial)
        if any((base_record.get("metricas") or {}).get(metric, {}).get("encontrado") for metric in missing_group_metrics):
            extracted_any = True

    missing_metrics = [
        metric_name
        for metric_name, metric in (base_record.get("metricas") or {}).items()
        if not metric.get("encontrado")
    ]
    if missing_metrics:
        partial = _extract_visual_bundle(
            document,
            pdf_path,
            missing_metrics,
            diagnostics=diagnostics,
            aggressive=True,
        )
        if partial:
            base_record = _merge_semantic_records(base_record, partial)
            extracted_any = True

    if not extracted_any:
        return None

    return base_record


def _gemini_response_text(result):
    candidates = result.get("candidates") or []
    if not candidates:
        return None

    parts = (candidates[0].get("content") or {}).get("parts") or []
    texts = []
    for part in parts:
        if part.get("text"):
            texts.append(part["text"])

    if not texts:
        return None

    return texts[-1].strip()


def _gemini_schema():
    metric_schema = {
        "type": ["object", "null"],
        "properties": {
            "valor_textual": {"type": ["string", "null"]},
            "valor_numerico": {"type": ["number", "null"]},
            "unidade": {"type": ["string", "null"]},
            "pagina": {"type": ["integer", "null"]},
            "trecho_evidencia": {"type": ["string", "null"]},
            "encontrado": {"type": "boolean"},
        },
        "required": [
            "valor_textual",
            "valor_numerico",
            "unidade",
            "pagina",
            "trecho_evidencia",
            "encontrado",
        ],
    }

    properties = {
        "schema_version": {"type": "string"},
        "empresa": {"type": "string"},
        "ano": {"type": "integer"},
        "trimestre": {"type": "integer"},
        "titulo_documento": {"type": "string"},
        "source_url": {"type": "string"},
        "sha256": {"type": "string"},
        "metricas": {
            "type": "object",
            "properties": {
                spec["name"]: metric_schema for spec in METRIC_SPEC
            },
            "required": [spec["name"] for spec in METRIC_SPEC],
        },
        "observacoes": {
            "type": "array",
            "items": {"type": "string"},
        },
    }

    return {
        "type": "object",
        "properties": properties,
        "required": list(properties.keys()),
    }


def _quarter_sort_key(record):
    return (
        int(record.get("ano") or 0),
        int(record.get("trimestre") or 0),
        str(record.get("empresa") or ""),
    )


def _normalize_records(records):
    normalized = []
    for record in records:
        normalized.append(record)
    return sorted(normalized, key=_quarter_sort_key)


def _company_records(records):
    grouped = {}
    for record in records:
        company = record.get("empresa") or "desconhecida"
        grouped.setdefault(company, []).append(record)
    for company in grouped:
        grouped[company] = sorted(grouped[company], key=_quarter_sort_key)
    return grouped


def _metric_value(record, metric_name):
    metric = (record.get("metricas") or {}).get(metric_name) or {}
    value = metric.get("valor_numerico")
    if value is None:
        return None
    return value


def _metric_unit(record, metric_name):
    metric = (record.get("metricas") or {}).get(metric_name) or {}
    unit = metric.get("unidade")
    return unit if unit is not None else None


def _normalize_metric_unit(unit):
    if unit is None:
        return None
    text = str(unit).strip().lower()
    if not text:
        return None
    if "bilh" in text or text == "bi":
        return "bilhões"
    if "milh" in text or text == "mi":
        return "milhões"
    if "mil" in text:
        return "mil"
    return str(unit).strip()


def _comparison_value(record, metric_name):
    value = _metric_value(record, metric_name)
    if value is None:
        return None

    unit = _normalize_metric_unit(_metric_unit(record, metric_name))
    if unit == "milhões":
        return value / 1000
    if unit == "mil":
        return value / 1000000
    return value


def _current_record(company_records, ano, trimestre):
    for record in company_records:
        if int(record.get("ano") or 0) == int(ano) and int(record.get("trimestre") or 0) == int(trimestre):
            return record
    return None


def _previous_quarter(ano, trimestre):
    ano = int(ano)
    trimestre = int(trimestre)
    if trimestre > 1:
        return ano, trimestre - 1
    return ano - 1, 4


def _same_quarter_previous_year(ano, trimestre):
    return int(ano) - 1, int(trimestre)


def _percent_change(current, previous):
    if current is None or previous is None:
        return None
    if previous == 0:
        return None
    return round(((current - previous) / previous) * 100, 1)


def _sum_metric(records, metric_name, ano, trimestres):
    total = 0
    found = False
    for record in records:
        if int(record.get("ano") or 0) != int(ano):
            continue
        if int(record.get("trimestre") or 0) not in trimestres:
            continue
        value = _comparison_value(record, metric_name)
        if value is None:
            continue
        total += value
        found = True
    return total if found else None


def _sum_company_values(companies, section_name):
    total = 0
    found = False
    for item in companies:
        value = item.get(section_name, {}).get("valor_atual")
        if value is None:
            continue
        total += value
        found = True
    return total if found else None


def _first_company_unit(companies, section_name):
    for item in companies:
        unit = item.get(section_name, {}).get("unidade")
        if unit is not None:
            return unit
    return None


def _summarize_metric(company_records, metric_name, ano, trimestre):
    current = _current_record(company_records, ano, trimestre)
    if not current:
        return {
            "valor_atual": None,
            "variacao_trimestre_anterior": None,
            "variacao_mesmo_trimestre_ano_anterior": None,
            "acumulado_9m_atual": None,
            "acumulado_9m_ano_anterior": None,
            "variacao_9m": None,
            "fonte": None,
        }

    current_value = _comparison_value(current, metric_name)
    prev_ano, prev_trim = _previous_quarter(ano, trimestre)
    prev_record = _current_record(company_records, prev_ano, prev_trim)
    prev_value = _comparison_value(prev_record, metric_name) if prev_record else None

    yoy_ano, yoy_trim = _same_quarter_previous_year(ano, trimestre)
    yoy_record = _current_record(company_records, yoy_ano, yoy_trim)
    yoy_value = _comparison_value(yoy_record, metric_name) if yoy_record else None

    accum_current = _sum_metric(company_records, metric_name, ano, range(1, int(trimestre) + 1))
    accum_prev = _sum_metric(company_records, metric_name, yoy_ano, range(1, int(trimestre) + 1))

    return {
        "valor_atual": current_value,
        "variacao_trimestre_anterior": _percent_change(current_value, prev_value),
        "variacao_mesmo_trimestre_ano_anterior": _percent_change(current_value, yoy_value),
        "acumulado_9m_atual": accum_current,
        "acumulado_9m_ano_anterior": accum_prev,
        "variacao_9m": _percent_change(accum_current, accum_prev),
        "unidade": _metric_unit(current, metric_name),
        "fonte": current.get("source_url"),
    }


def build_dashboard_contract(records, ano=None, trimestre=None, empresa=None):
    records = _normalize_records(records or [])
    if not records:
        return {
            "schema_version": "dashboard-1.0",
            "titulo": "Conjuntura do Setor Habitacional",
            "periodo_referencia": {"ano": ano, "trimestre": trimestre},
            "filtros": {"empresa": empresa},
            "balanco_das_empresas": [],
            "cards_totais": {},
            "fontes": [],
        }

    if ano is None:
        ano = max(int(record.get("ano") or 0) for record in records)
    if trimestre is None:
        trimestre = max(
            int(record.get("trimestre") or 0)
            for record in records
            if int(record.get("ano") or 0) == int(ano)
        )

    grouped = _company_records(records)
    if empresa:
        grouped = {
            name: items
            for name, items in grouped.items()
            if name.lower() == str(empresa).lower()
        }

    companies = []
    all_sources = set()
    for company_name, company_records in grouped.items():
        lancamentos = _summarize_metric(company_records, "lancamentos", ano, trimestre)
        vendas = _summarize_metric(company_records, "vendas_liquidas", ano, trimestre)
        for record in company_records:
            if int(record.get("ano") or 0) == int(ano) and int(record.get("trimestre") or 0) == int(trimestre):
                all_sources.add(record.get("source_url"))

        companies.append(
            {
                "empresa": company_name,
                "lancamentos": lancamentos,
                "vendas": vendas,
                "linha_fonte": {
                    "source_url": lancamentos.get("fonte") or vendas.get("fonte"),
                },
            }
        )

    totals = {
        "lancamentos": {
            "valor_atual": _sum_company_values(companies, "lancamentos"),
            "unidade": _first_company_unit(companies, "lancamentos"),
            "variacao_trimestre_anterior": None,
            "variacao_mesmo_trimestre_ano_anterior": None,
            "acumulado_9m_atual": None,
            "acumulado_9m_ano_anterior": None,
            "variacao_9m": None,
        },
        "vendas": {
            "valor_atual": _sum_company_values(companies, "vendas"),
            "unidade": _first_company_unit(companies, "vendas"),
            "variacao_trimestre_anterior": None,
            "variacao_mesmo_trimestre_ano_anterior": None,
            "acumulado_9m_atual": None,
            "acumulado_9m_ano_anterior": None,
            "variacao_9m": None,
        },
    }

    return {
        "schema_version": "dashboard-1.0",
        "titulo": "Conjuntura do Setor Habitacional",
        "periodo_referencia": {"ano": int(ano), "trimestre": int(trimestre)},
        "filtros": {"empresa": empresa},
        "balanco_das_empresas": companies,
        "cards_totais": totals,
        "fontes": sorted(src for src in all_sources if src),
    }
