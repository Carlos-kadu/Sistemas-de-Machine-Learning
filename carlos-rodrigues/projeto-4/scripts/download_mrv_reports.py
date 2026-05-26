import argparse
import hashlib
import json
import re
import sys
from datetime import datetime, timezone
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import urlparse
from urllib.request import Request, urlopen

API_URL = (
    "https://apicatalog.mziq.com/filemanager/company/"
    "4b56353d-d5d9-435f-bf63-dcbf0a6c25d5/filter/categories/year/meta"
)

DEFAULT_CATEGORIES = [
    "central_de_resultados_release",
    "central_de_resultados_previa",
    "central_de_resultados_itr",
    "central_de_resultados_planilha_interativa",
    "central_de_resultados_audio",
    "central_de_resultados_transcricao",
]

RELEASE_INTERNAL_NAMES = {
    "central_de_resultados_release",
}


def build_headers():
    return {
        "accept": "application/json, text/javascript, */*; q=0.01",
        "content-type": "application/json",
        "origin": "https://ri.mrv.com.br",
        "referer": "https://ri.mrv.com.br/",
        "user-agent": (
            "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
            "(KHTML, like Gecko) Chrome/147.0.0.0 Safari/537.36"
        ),
    }


def post_json(url, payload, timeout=30):
    request = Request(
        url=url,
        method="POST",
        headers=build_headers(),
        data=json.dumps(payload).encode("utf-8"),
    )
    with urlopen(request, timeout=timeout) as response:
        body = response.read().decode("utf-8")
    return json.loads(body)


def get_document_metas(year, language, categories):
    payload = {
        "year": str(year),
        "categories": categories,
        "language": language,
        "published": True,
    }
    data = post_json(API_URL, payload)
    if not data.get("success"):
        raise RuntimeError(f"API returned success=false for year={year}: {data}")
    return data.get("data", {}).get("document_metas", [])


def is_release_pdf(meta):
    internal_name = str(meta.get("internal_name") or "")
    file_url = str(meta.get("file_url") or "")
    permalink = str(meta.get("permalink") or "")
    link_url = str(meta.get("link_url") or "")
    title = str(meta.get("file_title") or "")

    if internal_name not in RELEASE_INTERNAL_NAMES:
        return False

    combined_url = f"{file_url} {permalink} {link_url}".lower()
    if ".pdf" in combined_url:
        return True

    return "release" in title.lower()


def choose_download_url(meta):
    for key in ("file_url", "permalink", "link_url"):
        value = meta.get(key)
        if value:
            return str(value)
    return None


def slugify(value):
    value = value.strip().lower()
    value = re.sub(r"[^a-z0-9]+", "-", value)
    return value.strip("-") or "document"


def infer_ext(url, content_type):
    if content_type and "pdf" in content_type.lower():
        return ".pdf"
    path = urlparse(url).path.lower()
    if path.endswith(".pdf"):
        return ".pdf"
    return ".bin"


def sha256_bytes(data):
    return hashlib.sha256(data).hexdigest()


def load_catalog(path):
    if not path.exists():
        return {"documents": []}
    return json.loads(path.read_text(encoding="utf-8"))


def save_catalog(path, catalog):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(catalog, indent=2, ensure_ascii=False), encoding="utf-8")


def already_seen(catalog, sha256, source_url):
    for doc in catalog.get("documents", []):
        if doc.get("sha256") == sha256 or doc.get("source_url") == source_url:
            return True
    return False


def download_file(url, timeout=60):
    request = Request(url=url, headers={"user-agent": build_headers()["user-agent"]})
    with urlopen(request, timeout=timeout) as response:
        data = response.read()
        content_type = response.headers.get("content-type")
    return data, content_type


def persist_doc(
    *,
    out_dir,
    year,
    quarter,
    title,
    ext,
    data,
):
    quarter_label = f"Q{quarter}" if quarter else "QX"
    filename = f"{year}_{quarter_label}_{slugify(title)}{ext}"
    year_dir = out_dir / str(year)
    year_dir.mkdir(parents=True, exist_ok=True)
    file_path = year_dir / filename
    file_path.write_bytes(data)
    return file_path


def process_year(
    year,
    out_dir,
    catalog,
    catalog_path,
    language,
    categories,
):
    metas = get_document_metas(year=year, language=language, categories=categories)
    release_metas = [m for m in metas if is_release_pdf(m)]

    baixados = 0
    ignorados = 0
    falhas = 0

    for meta in release_metas:
        source_url = choose_download_url(meta)
        if not source_url:
            falhas += 1
            continue

        try:
            raw, content_type = download_file(source_url)
        except (HTTPError, URLError) as exc:
            print(f"[AVISO] Falha ao baixar {source_url}: {exc}", file=sys.stderr)
            falhas += 1
            continue

        digest = sha256_bytes(raw)
        if already_seen(catalog, digest, source_url):
            ignorados += 1
            continue

        title = str(meta.get("file_title") or meta.get("file_name_original") or "release")
        quarter = meta.get("file_quarter")
        ext = infer_ext(source_url, content_type)
        file_path = persist_doc(
            out_dir=out_dir,
            year=year,
            quarter=int(quarter) if quarter else None,
            title=title,
            ext=ext,
            data=raw,
        )

        catalog.setdefault("documents", []).append(
            {
                "company": "MRV",
                "year": year,
                "quarter": quarter,
                "title": title,
                "internal_name": meta.get("internal_name"),
                "published_date": meta.get("file_published_date"),
                "source_url": source_url,
                "stored_path": str(file_path),
                "sha256": digest,
                "downloaded_at": datetime.now(timezone.utc).isoformat(),
            }
        )
        baixados += 1

    save_catalog(catalog_path, catalog)
    return len(metas), len(release_metas), baixados, ignorados, falhas


def parse_args():
    parser = argparse.ArgumentParser(
        description="Download MRV earnings release files by year with idempotency"
    )
    parser.add_argument("--start-year", type=int, required=True, help="First year")
    parser.add_argument("--end-year", type=int, required=True, help="Last year")
    parser.add_argument("--language", default="pt_BR", help="API language (default: pt_BR)")
    parser.add_argument(
        "--output-dir",
        default="data/raw/mrv/releases",
        help="Base output directory",
    )
    parser.add_argument(
        "--catalog",
        default="data/catalog/mrv_release_catalog.json",
        help="Catalog JSON path",
    )
    parser.add_argument(
        "--categories",
        nargs="+",
        default=DEFAULT_CATEGORIES,
        help="Categories sent to API request",
    )
    return parser.parse_args()


def main():
    args = parse_args()
    if args.start_year > args.end_year:
        print("[ERRO] --start-year deve ser <= --end-year", file=sys.stderr)
        return 2

    out_dir = Path(args.output_dir)
    catalog_path = Path(args.catalog)
    catalog = load_catalog(catalog_path)

    print(
        f"[INFO] Buscando anos {args.start_year}..{args.end_year} "
        f"(idioma={args.language})"
    )

    for year in range(args.start_year, args.end_year + 1):
        try:
            total, releases, baixados, ignorados, falhas = process_year(
                year=year,
                out_dir=out_dir,
                catalog=catalog,
                catalog_path=catalog_path,
                language=args.language,
                categories=args.categories,
            )
            print(
                f"[INFO] ano={year} total_docs={total} "
                f"candidatos_release={releases} baixados={baixados} "
                f"ignorados={ignorados} falhas={falhas}"
            )
        except Exception as exc:  # noqa: BLE001
            print(f"[ERRO] ano={year} falhou: {exc}", file=sys.stderr)

    print(f"[INFO] Catálogo atualizado em: {catalog_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
