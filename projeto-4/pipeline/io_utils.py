import hashlib
import json
import re
import subprocess
from datetime import datetime, timezone


def load_json(path, default):
    if not path.exists():
        return default
    return json.loads(path.read_text(encoding="utf-8"))


def save_json(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")


def sha256_file(path):
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(8192), b""):
            digest.update(chunk)
    return digest.hexdigest()


def now_utc():
    return datetime.now(timezone.utc).isoformat()


def run_command(args):
    return subprocess.run(
        args,
        capture_output=True,
        text=True,
        check=True,
    )


def pdf_page_count(pdf_path):
    result = run_command(["pdfinfo", str(pdf_path)])
    match = re.search(r"^Pages:\s+(\d+)", result.stdout, re.MULTILINE)
    if not match:
        return None
    return int(match.group(1))


def pdf_text(pdf_path):
    result = run_command(["pdftotext", "-layout", str(pdf_path), "-"])
    return result.stdout
