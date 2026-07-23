import argparse
import json
import os
import sys
import time
import re
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from pipeline_core import (
    CATALOG_PATH,
    PROCESSED_RECORDS_PATH,
    build_semantic_record,
    build_data_lineage,
    extract_metric_from_line,
    find_raw_pdf,
    load_catalog,
    iter_catalog_documents,
    load_processed_records,
    save_processed_records,
    save_json,
    upsert_lineage_record,
    sha256_file,
)
from semantic_contract import METRIC_SPEC, try_llm_extract

METRIC_KIND = {spec["name"]: spec["kind"] for spec in METRIC_SPEC}
METRIC_REQUIRED_TERMS = {
    "receita_operacional_liquida": ["receita operacional líquida", "receita operacional liquida", "rol"],
    "lucro_liquido": ["lucro líquido", "lucro liquido"],
    "ebitda": ["ebitda"],
    "margem_bruta": ["margem bruta"],
    "vendas_liquidas": ["vendas líquidas", "vendas liquidas", "vendas"],
    "lancamentos": ["lançamentos", "lancamentos"],
    "unidades_produzidas": ["unidades produzidas", "produção", "producao"],
    "repasses": ["repasses", "repassadas", "unidades repassadas"],
    "estoque": ["estoque"],
    "vso": ["vso"],
    "distratos": ["distratos", "distrato", "unidades distratadas"],
    "geracao_caixa": ["geração de caixa", "geracao de caixa"],
}


def parse_args():
    parser = argparse.ArgumentParser(
        description="Extrai métricas dos PDFs da MRV com seleção explícita de documentos"
    )
    parser.add_argument("--year", type=int, help="Processa somente documentos deste ano")
    parser.add_argument("--quarter", type=int, choices=[1, 2, 3, 4], help="Processa somente este trimestre")
    parser.add_argument("--file", type=str, help="Processa diretamente um PDF local")
    parser.add_argument("--document-id", type=str, help="Seleciona um documento pelo sha256, título, URL ou caminho")
    parser.add_argument("--limit", type=int, help="Limita a quantidade de documentos processados")
    parser.add_argument("--one-per-year", action="store_true", help="Seleciona um PDF por ano, de forma determinística")
    parser.add_argument("--recent-only", action="store_true", help="Ordena os candidatos mais recentes primeiro")
    parser.add_argument("--force", action="store_true", help="Força reprocessamento mesmo se já existir registro")
    parser.add_argument("--validate-only", action="store_true", help="Valida registros já persistidos sem chamar o LLM")
    parser.add_argument("--diagnostics-dir", type=str, help="Salva artefatos temporários de diagnóstico para os documentos selecionados")
    parser.add_argument("--ingestion-trigger", type=str, default="batch", help="Etiqueta de origem da ingestão: batch, watcher ou manual")
    return parser.parse_args()


def _int_or_none(value):
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _normalize_path(path_value):
    if not path_value:
        return None
    path = Path(path_value)
    if path.is_absolute():
        return path
    return (PROJECT_ROOT / path).resolve()


def _document_sort_key(document):
    return (
        _int_or_none(document.get("year")) or 0,
        _int_or_none(document.get("quarter")) or 0,
        str(document.get("title") or ""),
        str(document.get("sha256") or ""),
    )


def _document_matches_id(document, document_id):
    if not document_id:
        return True

    needle = str(document_id).strip().lower()
    haystacks = [
        str(document.get("sha256") or "").lower(),
        str(document.get("title") or "").lower(),
        str(document.get("source_url") or "").lower(),
        str(document.get("stored_path") or "").lower(),
    ]
    return any(needle == value or needle in value for value in haystacks)


def _build_document_from_file(file_path, year=None, quarter=None):
    path = _normalize_path(file_path)
    if not path or not path.exists():
        raise FileNotFoundError(f"arquivo_pdf_nao_encontrado:{file_path}")

    digest = sha256_file(path)
    catalog = load_catalog()
    for candidate in catalog.get("documents", []):
        stored_path = candidate.get("stored_path")
        if candidate.get("sha256") == digest:
            return dict(candidate), path
        if stored_path and _normalize_path(stored_path) == path:
            return dict(candidate), path

    inferred = re.search(r"(20\d{2}).*?[qQ]([1-4])", path.stem)
    inferred_year = int(inferred.group(1)) if inferred else None
    inferred_quarter = int(inferred.group(2)) if inferred else None
    year = _int_or_none(year) or inferred_year
    quarter = _int_or_none(quarter) or inferred_quarter
    if year is None or quarter is None:
        raise ValueError("nao_foi_possivel_inferir_ano_trimestre_do_arquivo")

    document = {
        "company": "MRV",
        "year": year,
        "quarter": quarter,
        "title": path.stem,
        "source_url": path.resolve().as_uri(),
        "sha256": digest,
        "stored_path": str(path.relative_to(PROJECT_ROOT)) if path.is_relative_to(PROJECT_ROOT) else str(path),
        "downloaded_at": None,
    }
    return document, path


def _select_catalog_documents(args):
    documents = list(iter_catalog_documents())

    if args.year is not None:
        documents = [doc for doc in documents if _int_or_none(doc.get("year")) == args.year]

    if args.quarter is not None:
        documents = [doc for doc in documents if _int_or_none(doc.get("quarter")) == args.quarter]

    if args.document_id:
        documents = [doc for doc in documents if _document_matches_id(doc, args.document_id)]

    documents = sorted(documents, key=_document_sort_key, reverse=bool(args.recent_only))

    if args.one_per_year:
        by_year = {}
        ordered_years = sorted(
            {_int_or_none(doc.get("year")) for doc in documents if _int_or_none(doc.get("year")) is not None},
            reverse=bool(args.recent_only),
        )
        for year in ordered_years:
            year_docs = [doc for doc in documents if _int_or_none(doc.get("year")) == year]
            if not year_docs:
                continue
            by_year[year] = max(year_docs, key=_document_sort_key)
        documents = [by_year[year] for year in ordered_years if year in by_year]

    if args.limit is not None:
        documents = documents[: max(args.limit, 0)]

    return documents


def _load_existing_index():
    records_bundle = load_processed_records()
    existing_records = records_bundle.get("records", [])
    existing_index = {
        item.get("sha256"): item
        for item in existing_records
        if item.get("sha256")
    }
    return records_bundle, existing_index


def _validate_existing_record(record):
    validated = dict(record)
    validated["metricas"] = sanitize_metrics(validated.get("metricas") or {})
    validated["modo_extracao"] = validated.get("modo_extracao") or "validacao_existente"
    return validated


def _print_selection(documents, reason):
    print(f"[INFO] Documentos selecionados: {len(documents)}")
    print(f"[INFO] Motivo da seleção: {reason}")
    for document in documents:
        print(
            f"[INFO] Empresa: {document.get('company') or 'MRV'} "
            f"Ano: {document.get('year')} "
            f"Trimestre: {document.get('quarter')} "
            f"Arquivo: {document.get('stored_path') or document.get('source_url') or document.get('title')}"
        )


def process_document(document, pdf_path=None, diagnostics=None):
    pdf_path = pdf_path or find_raw_pdf(document)
    if not pdf_path:
        return None, "arquivo_pdf_nao_encontrado"

    llm_record = None
    for attempt in range(2):
        llm_record = try_llm_extract(document, pdf_path, diagnostics=diagnostics)
        if llm_record:
            break
        if attempt == 0:
            time.sleep(2)

    if not llm_record:
        heuristic_record = build_semantic_record(document, pdf_path)
        heuristic_record["stored_path"] = document.get("stored_path")
        heuristic_record["modo_extracao"] = "pdftotext+heuristicas"
        if diagnostics is not None:
            diagnostics["status"] = "heuristic_fallback"
            diagnostics["record"] = heuristic_record
        return heuristic_record, None

    llm_record["stored_path"] = document.get("stored_path")
    llm_record["modo_extracao"] = "llm_json_schema_primary"
    llm_record["schema_version"] = llm_record.get("schema_version") or "1.0"
    llm_record["metricas"] = sanitize_metrics(llm_record.get("metricas") or {})

    missing_metrics = [
        metric_name
        for metric_name, metric in (llm_record.get("metricas") or {}).items()
        if not metric.get("encontrado")
    ]

    heuristic_record = None
    if missing_metrics:
        heuristic_record = build_semantic_record(document, pdf_path)
        heuristic_metrics = heuristic_record.get("metricas") or {}
        llm_metrics = llm_record.get("metricas") or {}
        rescued_metrics = 0
        for metric_name in missing_metrics:
            current_metric = llm_metrics.get(metric_name) or {}
            heuristic_metric = heuristic_metrics.get(metric_name) or {}
            if (
                not current_metric.get("encontrado")
                and heuristic_metric.get("encontrado")
            ):
                llm_metrics[metric_name] = heuristic_metric
                rescued_metrics += 1
        llm_record["metricas"] = llm_metrics
        if rescued_metrics:
            llm_record["modo_extracao"] = "llm_json_schema_primary+heuristic_recovery"
            llm_record.setdefault("observacoes", []).append(
                f"heuristicas_aplicadas_em_metricas_ausentes={rescued_metrics}"
            )

    if heuristic_record and heuristic_record.get("observacoes"):
        llm_record["observacoes"] = list(
            dict.fromkeys((llm_record.get("observacoes") or []) + heuristic_record.get("observacoes", []))
        )

    llm_record["metricas"] = sanitize_metrics(llm_record.get("metricas") or {})
    if diagnostics is not None:
        diagnostics["status"] = "ok"
        diagnostics["record"] = llm_record

    return llm_record, None


def sanitize_metrics(metricas):
    suspicious_patterns = [
        r"\bimpactad\w*\b",
        r"\bimpacto\b",
        r"\bequivalente\w*\b",
        r"\bdesreconhecimento\b",
        r"\bestorno\b",
    ]
    positive_patterns = [
        r"\balcançou\b",
        r"\balcançando\b",
        r"\batingiu\b",
        r"\batingindo\b",
        r"\btotalizou\b",
        r"\btotalizando\b",
        r"\bregistrou\b",
        r"\bfoi de\b",
        r"\bmarca de\b",
        r"\bchegou a\b",
    ]
    quantity_metrics = {"unidades_produzidas", "repasses"}
    percent_metrics = {"margem_bruta", "vso"}
    monetary_metrics = {
        "receita_operacional_liquida",
        "lucro_liquido",
        "ebitda",
        "vendas_liquidas",
        "lancamentos",
        "estoque",
        "geracao_caixa",
    }
    flexible_metrics = {"distratos"}
    quantity_units = {"unidades", "unidade", "k", "mil unidades", "mil"}
    percent_units = {"%", "percentual", "porcentagem"}
    monetary_units = {
        "r$",
        "brl",
        "milhões",
        "milhoes",
        "bilhões",
        "bilhoes",
        "r$ milhões",
        "r$ milhoes",
        "r$ bilhões",
        "r$ bilhoes",
        "milhões de reais",
        "milhoes de reais",
        "bilhões de reais",
        "bilhoes de reais",
        "mil",
    }

    def _tokenize_evidence(text):
        return re.findall(r"R\$|US\$|[-+]?\d[\d\.\,]*%?|[A-Za-zÀ-ÿ]+", text or "")

    def _evidence_confirms_metric(metric_name, evidence, page_number):
        if not evidence:
            return False
        aliases = METRIC_REQUIRED_TERMS.get(metric_name, [])
        tokens = _tokenize_evidence(evidence)
        if not tokens:
            return False

        aliases_tokens = [_tokenize_evidence(alias) for alias in aliases if alias]
        for alias_tokens in aliases_tokens:
            if not alias_tokens:
                continue
            alias_len = len(alias_tokens)
            for start_index in range(0, max(len(tokens) - alias_len + 1, 0)):
                if tokens[start_index : start_index + alias_len] != alias_tokens:
                    continue
                window_start = max(0, start_index - 4)
                window_end = min(len(tokens), start_index + alias_len + 12)
                window = tokens[window_start:window_end]
                numeric_seen = False
                for token in window:
                    if re.search(r"\d", token):
                        numeric_seen = True
                        break
                if numeric_seen:
                    return True
        return False

    for metric_name, metric in metricas.items():
        evidence = " ".join(
            str(metric.get(key) or "")
            for key in ("valor_textual", "trecho_evidencia", "trecho")
        ).lower()
        if not evidence:
            continue

        expected_terms = METRIC_REQUIRED_TERMS.get(metric_name, [])
        if expected_terms and not any(term in evidence for term in expected_terms):
            metricas[metric_name] = {
                "valor_textual": None,
                "valor_numerico": None,
                "unidade": None,
                "pagina": None,
                "trecho_evidencia": None,
                "encontrado": False,
            }
            continue

        kind = METRIC_KIND.get(metric_name)
        unit = str(metric.get("unidade") or "").lower()
        value_text = str(metric.get("valor_textual") or "").lower()
        is_flexible_metric = metric_name in flexible_metrics
        if kind == "percentual":
            if unit not in percent_units and "%" not in value_text:
                metricas[metric_name] = {
                    "valor_textual": None,
                    "valor_numerico": None,
                    "unidade": None,
                    "pagina": None,
                    "trecho_evidencia": None,
                    "encontrado": False,
                }
                continue
        elif kind == "absoluta":
            if not is_flexible_metric and (unit in percent_units or "%" in value_text):
                metricas[metric_name] = {
                    "valor_textual": None,
                    "valor_numerico": None,
                    "unidade": None,
                    "pagina": None,
                    "trecho_evidencia": None,
                    "encontrado": False,
                }
                continue

            if metric_name in quantity_metrics:
                if unit and unit not in quantity_units:
                    metricas[metric_name] = {
                        "valor_textual": None,
                        "valor_numerico": None,
                        "unidade": None,
                        "pagina": None,
                        "trecho_evidencia": None,
                        "encontrado": False,
                    }
                    continue
                if unit == "k" and metric.get("valor_numerico") is not None:
                    metric["valor_numerico"] = float(metric.get("valor_numerico")) * 1000
                    metric["unidade"] = "unidades"
            elif metric_name in monetary_metrics:
                if unit and unit in quantity_units:
                    metricas[metric_name] = {
                        "valor_textual": None,
                        "valor_numerico": None,
                        "unidade": None,
                        "pagina": None,
                        "trecho_evidencia": None,
                        "encontrado": False,
                    }
                    continue
            elif metric_name in flexible_metrics:
                if unit and unit in quantity_units:
                    metricas[metric_name] = {
                        "valor_textual": None,
                        "valor_numerico": None,
                        "unidade": None,
                        "pagina": None,
                        "trecho_evidencia": None,
                        "encontrado": False,
                    }
                    continue

        if metric.get("encontrado") and metric_name in METRIC_REQUIRED_TERMS and not _evidence_confirms_metric(
            metric_name,
            evidence,
            metric.get("pagina"),
        ):
            metricas[metric_name] = {
                "valor_textual": None,
                "valor_numerico": None,
                "unidade": None,
                "pagina": None,
                "trecho_evidencia": None,
                "encontrado": False,
            }
            continue

        suspicious = any(re.search(pattern, evidence) for pattern in suspicious_patterns)
        positive = any(re.search(pattern, evidence) for pattern in positive_patterns)
        tabular_profit_evidence = (
            metric_name == "lucro_liquido"
            and any(term in evidence for term in METRIC_REQUIRED_TERMS.get(metric_name, []))
            and re.search(r"[-+]?\d[\d\.\,]*", evidence)
        )
        if metric_name == "lucro_liquido" and not positive and not tabular_profit_evidence:
            metricas[metric_name] = {
                "valor_textual": None,
                "valor_numerico": None,
                "unidade": None,
                "pagina": None,
                "trecho_evidencia": None,
                "encontrado": False,
            }
            continue
        if suspicious and not positive:
            metricas[metric_name] = {
                "valor_textual": None,
                "valor_numerico": None,
                "unidade": None,
                "pagina": None,
                "trecho_evidencia": None,
                "encontrado": False,
            }
    return metricas


def main():
    args = parse_args()
    records_bundle, existing_index = _load_existing_index()
    diagnostics_dir = Path(args.diagnostics_dir) if args.diagnostics_dir else None
    if diagnostics_dir:
        diagnostics_dir.mkdir(parents=True, exist_ok=True)

    if args.file:
        selected_documents = []
        document, pdf_path = _build_document_from_file(args.file, args.year, args.quarter)
        document["_pdf_path"] = str(pdf_path)
        selected_documents.append(document)
        selection_reason = "arquivo explícito"
    else:
        selected_documents = _select_catalog_documents(args)
        selection_reason = "filtros explícitos" if any(
            [
                args.year is not None,
                args.quarter is not None,
                args.document_id,
                args.limit is not None,
                args.one_per_year,
                args.recent_only,
            ]
        ) else "catálogo completo"

    if not selected_documents:
        print("[AVISO] Nenhum documento selecionado", file=sys.stderr)
        return 1

    _print_selection(selected_documents, selection_reason)

    processed = 0
    atualizados = 0
    skipped = 0
    failures = 0

    print(f"[INFO] Lendo catálogo em: {CATALOG_PATH}")
    pause_seconds = float(
        os.environ.get("GEMINI_REQUEST_DELAY_SECONDS", "12")
    )

    for document in selected_documents:
        sha256 = document.get("sha256")
        try:
            diagnostics = None
            if diagnostics_dir:
                diagnostics = {
                    "document": {
                        "empresa": document.get("company") or document.get("empresa"),
                        "ano": document.get("year"),
                        "trimestre": document.get("quarter"),
                        "titulo_documento": document.get("title") or document.get("titulo_documento"),
                        "source_url": document.get("source_url"),
                        "sha256": sha256,
                        "stored_path": document.get("stored_path"),
                    },
                    "attempts": [],
                }

            if args.validate_only:
                existing = existing_index.get(sha256)
                if not existing:
                    print(
                        f"[AVISO] Ignorando {document.get('title')}: registro_nao_encontrado_para_validacao",
                        file=sys.stderr,
                    )
                    failures += 1
                    continue
                record = _validate_existing_record(existing)
                error = None
                if diagnostics is not None:
                    diagnostics["status"] = "validated_existing"
                    diagnostics["record"] = record
            else:
                if not args.force and sha256 in existing_index:
                    skipped += 1
                    print(
                        f"[INFO] Ignorando já processado: empresa={document.get('company', 'MRV')} "
                        f"ano={document.get('year')} trimestre={document.get('quarter')} "
                        f"titulo={document.get('title')}"
                    )
                    continue

                record, error = process_document(
                    document,
                    pdf_path=document.get("_pdf_path"),
                    diagnostics=diagnostics,
                )

            if error:
                print(
                    f"[AVISO] Ignorando {document.get('title')}: {error}",
                    file=sys.stderr,
                )
                failures += 1
                continue

            lineage_pdf_path = document.get("_pdf_path") or find_raw_pdf(document)
            record["data_lineage"] = build_data_lineage(
                document,
                lineage_pdf_path,
                trigger=args.ingestion_trigger,
                record_path=str(PROCESSED_RECORDS_PATH.relative_to(PROJECT_ROOT)),
            )

            if sha256 in existing_index:
                atualizados += 1

            records_bundle["records"] = [
                item
                for item in records_bundle.get("records", [])
                if item.get("sha256") != sha256
            ]
            records_bundle.setdefault("records", []).append(record)
            existing_index[sha256] = record
            upsert_lineage_record(record["data_lineage"])
            processed += 1

            records_bundle["records"] = sorted(
                records_bundle.get("records", []),
                key=lambda item: (
                    item.get("ano") or 0,
                    item.get("trimestre") or 0,
                    item.get("titulo_documento") or "",
                ),
            )
            save_json(PROCESSED_RECORDS_PATH, records_bundle)

            print(
                f"[INFO] Extraído: empresa={record.get('empresa')} "
                f"ano={record.get('ano')} trimestre={record.get('trimestre')} "
                f"titulo={record.get('titulo_documento')}"
            )

            if diagnostics_dir and diagnostics is not None:
                diag_name = f"{record.get('ano')}_Q{record.get('trimestre')}_{sha256[:12]}.json"
                diag_path = diagnostics_dir / diag_name
                diag_path.write_text(
                    json.dumps(diagnostics, indent=2, ensure_ascii=False),
                    encoding="utf-8",
                )
        except Exception as exc:  # noqa: BLE001
            failures += 1
            print(
                f"[ERRO] Falha ao extrair {document.get('title')}: {exc}",
                file=sys.stderr,
            )

        if not args.validate_only and pause_seconds > 0:
            time.sleep(pause_seconds)

    records_bundle["records"] = sorted(
        records_bundle.get("records", []),
        key=lambda item: (
            item.get("ano") or 0,
            item.get("trimestre") or 0,
            item.get("titulo_documento") or "",
        ),
    )
    save_json(PROCESSED_RECORDS_PATH, records_bundle)

    print(
        f"[INFO] Processamento concluído: novos={processed} "
        f"atualizados={atualizados} ignorados={skipped} falhas={failures}"
    )
    print(f"[INFO] Base estruturada salva em: {PROCESSED_RECORDS_PATH}")
    return 0 if failures == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
