import re


SECTION_RULES = [
    ("destaques_financeiros", ["destaques financeiros", "financial highlights"]),
    ("destaques_operacionais", ["destaques operacionais", "operational highlights"]),
    ("destaques_resia", ["destaques resia"]),
    ("indicadores_financeiros", ["indicadores financeiros", "financial indicators"]),
    ("evento_subsequente", ["evento subsequente", "subsequent event"]),
    ("mensagem_da_administracao", ["mensagem da administração", "mensagem da administracao"]),
    ("demonstracoes", ["demonstrações financeiras", "demonstracoes financeiras"]),
    ("capa", ["divulgação de resultados", "divulgacao de resultados"]),
]


def normalize_text(text):
    text = text.replace("\r", "\n")
    lines = []
    for line in text.split("\n"):
        line = re.sub(r"\s+", " ", line).strip()
        if line:
            lines.append(line)
    return "\n".join(lines).strip()


def split_pages(text):
    pages = []
    for raw_page in text.split("\f"):
        cleaned = normalize_text(raw_page)
        if cleaned:
            pages.append(cleaned)
    return pages


def split_raw_pages(text):
    pages = []
    for raw_page in text.split("\f"):
        if raw_page.strip():
            pages.append(raw_page)
    return pages


def normalize_line(line):
    return re.sub(r"\s+", " ", line).strip()


def classify_section(page_text):
    lowered = page_text.lower()
    for section, keywords in SECTION_RULES:
        for keyword in keywords:
            if keyword in lowered:
                return section
    return "conteudo_geral"


def page_excerpt(page_text, size=420):
    compact = re.sub(r"\s+", " ", page_text).strip()
    if len(compact) <= size:
        return compact
    return compact[: size - 3] + "..."
