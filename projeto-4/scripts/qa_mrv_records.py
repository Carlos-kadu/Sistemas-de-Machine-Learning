import json
import sys
from collections import Counter
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from pipeline_core import load_processed_records


ABSOLUTE_METRICS = {
    "receita_operacional_liquida",
    "lucro_liquido",
    "ebitda",
    "vendas_liquidas",
    "lancamentos",
    "unidades_produzidas",
    "repasses",
    "estoque",
    "geracao_caixa",
}

PERCENTAGE_METRICS = {"margem_bruta", "vso"}
FLEXIBLE_METRICS = {"distratos"}


def metric_is_suspicious(metric_name, metric):
    value = metric.get("valor_textual")
    unit = metric.get("unidade")
    if not metric.get("encontrado"):
        return False
    if metric_name in ABSOLUTE_METRICS and unit == "%":
        return True
    if metric_name in PERCENTAGE_METRICS and unit not in {"%", "percentual", "porcentagem", None}:
        return True
    if metric_name in ABSOLUTE_METRICS and value and "%" in str(value):
        return True
    if metric_name in FLEXIBLE_METRICS and unit in {"unidades", "unidade"}:
        return True
    return False


def main():
    bundle = load_processed_records()
    records = bundle.get("records", [])

    coverage = Counter()
    suspicious = []
    low_signal = []

    for record in records:
        found_count = 0
        for metric_name, metric in record.get("metricas", {}).items():
            if metric.get("encontrado"):
                coverage[metric_name] += 1
                found_count += 1
                if metric_is_suspicious(metric_name, metric):
                    suspicious.append(
                        {
                            "ano": record.get("ano"),
                            "trimestre": record.get("trimestre"),
                            "titulo_documento": record.get("titulo_documento"),
                            "metric_name": metric_name,
                            "valor_textual": metric.get("valor_textual"),
                            "unidade": metric.get("unidade"),
                            "pagina": metric.get("pagina"),
                        }
                    )
        if found_count < 8:
            low_signal.append(
                {
                    "ano": record.get("ano"),
                    "trimestre": record.get("trimestre"),
                    "titulo_documento": record.get("titulo_documento"),
                    "metricas_encontradas": found_count,
                }
            )

    report = {
        "total_documentos": len(records),
        "cobertura_metricas": dict(coverage),
        "registros_com_pouca_sinalizacao": low_signal,
        "sinais_suspeitos": suspicious,
    }

    out_path = Path("data/processed/qa_report.json")
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")

    print(f"total_documentos={len(records)}")
    print("cobertura_metricas:")
    for metric_name, count in sorted(coverage.items()):
        print(f"  {metric_name}: {count}")
    print(f"registros_com_pouca_sinalizacao={len(low_signal)}")
    print(f"sinais_suspeitos={len(suspicious)}")
    print(f"relatorio={out_path}")


if __name__ == "__main__":
    raise SystemExit(main())
