from pipeline.numeric import parse_numeric_value
from pipeline.text_utils import page_excerpt


def empty_metric(name):
    return {
        "nome": name,
        "valor_textual": None,
        "valor_numerico": None,
        "unidade": None,
        "pagina": None,
        "trecho": None,
        "encontrado": False,
    }


def build_metric_payload(metric_name, raw_value, page_number, evidence, unit_hint=None):
    metric = empty_metric(metric_name)
    if not raw_value:
        return metric

    numeric_value, parsed_unit = parse_numeric_value(raw_value)
    if parsed_unit == "K" and metric_name in {"unidades_produzidas", "repasses"} and numeric_value is not None:
        numeric_value = numeric_value * 1000
        parsed_unit = "unidades"
    metric["valor_textual"] = raw_value
    metric["valor_numerico"] = numeric_value
    metric["unidade"] = parsed_unit or unit_hint
    metric["pagina"] = page_number
    excerpt = page_excerpt(evidence)
    metric["trecho"] = excerpt
    metric["trecho_evidencia"] = excerpt
    metric["encontrado"] = numeric_value is not None
    return metric
