import re


def parse_numeric_value(raw):
    if not raw:
        return None, None

    cleaned = raw.replace("R$", "").replace("US$", "").strip()
    unit = None
    lowered = cleaned.lower()

    if "bilhão" in lowered or "bilhao" in lowered or "bilhões" in lowered or "bilhoes" in lowered or re.search(r"\bbi\b", lowered):
        unit = "bilhões"
    elif "milhões" in lowered or "milhoes" in lowered or "mm" in lowered:
        unit = "milhões"
    elif "mil" in lowered:
        unit = "mil"
    elif "p.p." in lowered:
        unit = "p.p."
    elif "%" in cleaned:
        unit = "%"
    elif "unidades" in lowered:
        unit = "unidades"
    elif "k" in cleaned.lower():
        unit = "K"

    match = re.search(r"[-+]?\d[\d\.\,]*", cleaned)
    if not match:
        return None, unit

    is_parenthesized_negative = cleaned.strip().startswith("(")
    number = match.group(0).replace(".", "").replace(",", ".")
    try:
        value = float(number)
    except ValueError:
        return None, unit
    if is_parenthesized_negative:
        value = -value

    return value, unit


def infer_unit_from_text(text):
    lowered = text.lower()
    if "r$ bilhões" in lowered or "r$ bilh" in lowered or "(r$ bilhões)" in lowered:
        return "bilhões"
    if " bilhões" in lowered or " bilhoes" in lowered or re.search(r"\bbi\b", lowered):
        return "bilhões"
    if "r$ milhões" in lowered or "r$ milhoes" in lowered or " milhões" in lowered or " milhoes" in lowered:
        return "milhões"
    if "r$ mil" in lowered or " mil)" in lowered or " mil " in lowered:
        return "mil"
    if "unidades" in lowered:
        return "unidades"
    if "%" in lowered:
        return "%"
    return None


def extract_primary_token(text, expect_percent=False):
    if not text:
        return None

    if expect_percent:
        match = re.search(r"[-+]?\d[\d\.\,]*\s*%", text)
        if match:
            return re.sub(r"\s+", "", match.group(0))
        return None

    patterns = [
        r"R\$\s*\(?[-+]?\d[\d\.\,]*\)?\s*(?:bilhão|bilhao|bilhões|bilhoes|milhões|milhoes|mil|bi|MM|K)?",
        r"US\$\s*\(?[-+]?\d[\d\.\,]*\)?\s*(?:bilhão|bilhao|bilhões|bilhoes|milhões|milhoes|mil|bi|MM|K)?",
        r"\(?[-+]?\d[\d\.\,]*\)?\s*(?:bilhão|bilhao|bilhões|bilhoes|milhões|milhoes|mil|bi|MM|K)",
        r"\(?[-+]?\d[\d\.\,]*\)?",
    ]
    for pattern in patterns:
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            token = re.sub(r"\s+", " ", match.group(0)).strip()
            if token.lower().endswith("x"):
                continue
            return token
    return None


def extract_value_from_window(window):
    if not window:
        return None, None

    patterns = [
        r"R\$\s*[-+]?\d[\d\.\,]*(?:\s*(?:milhões|milhoes|mil|bi|bilhão|bilhao|bilhoes|bilhões|MM|K))?",
        r"US\$\s*[-+]?\d[\d\.\,]*(?:\s*(?:milhões|milhoes|mil|bi|bilhão|bilhao|bilhoes|bilhões|MM|K))?",
        r"[-+]?\d[\d\.\,]*\s*(?:bilhão|bilhao|bilhões|bilhoes|milhões|milhoes|mil|K|%)",
        r"[-+]?\d[\d\.\,]*\s*p\.p\.",
    ]

    for pattern in patterns:
        match = re.search(pattern, window, re.IGNORECASE)
        if match:
            raw = re.sub(r"\s+", " ", match.group(0)).strip()
            value, unit = parse_numeric_value(raw)
            return raw, {
                "valor_numerico": value,
                "unidade": unit,
            }

    return None, None
