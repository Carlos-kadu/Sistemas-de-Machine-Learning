import argparse
import json
import subprocess
import sys
import time
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
RAW_DIR = PROJECT_ROOT / "data" / "raw" / "mrv" / "releases"
STATE_PATH = PROJECT_ROOT / "data" / "processed" / "mrv_ingestion_state.json"
EXTRACT_SCRIPT = PROJECT_ROOT / "scripts" / "extract_mrv_reports.py"


def parse_args():
    parser = argparse.ArgumentParser(
        description="Monitora PDFs da MRV e dispara a extração quando arquivos novos aparecem"
    )
    parser.add_argument("--raw-dir", type=str, default=str(RAW_DIR), help="Diretório raiz dos PDFs")
    parser.add_argument("--state-path", type=str, default=str(STATE_PATH), help="Arquivo local de estado do watcher")
    parser.add_argument("--interval", type=float, default=30.0, help="Intervalo de verificação em segundos")
    parser.add_argument("--trigger-label", type=str, default="watcher", help="Etiqueta gravada na linhagem")
    parser.add_argument("--bootstrap-existing", action="store_true", help="Processa PDFs já presentes ao iniciar")
    parser.add_argument("--once", action="store_true", help="Executa uma única checagem e encerra")
    return parser.parse_args()


def load_state(state_path):
    if not state_path.exists():
        return {"files": {}}
    try:
        data = json.loads(state_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {"files": {}}
    if not isinstance(data, dict):
        return {"files": {}}
    data.setdefault("files", {})
    return data


def save_state(state_path, state):
    state_path.parent.mkdir(parents=True, exist_ok=True)
    state_path.write_text(json.dumps(state, indent=2, ensure_ascii=False), encoding="utf-8")


def sha256_file(path):
    import hashlib

    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(8192), b""):
            digest.update(chunk)
    return digest.hexdigest()


def list_pdf_files(raw_dir):
    if not raw_dir.exists():
        return []
    return sorted(path for path in raw_dir.rglob("*.pdf") if path.is_file())


def run_extractor(pdf_path, trigger_label):
    command = [
        sys.executable,
        str(EXTRACT_SCRIPT),
        "--file",
        str(pdf_path),
        "--force",
        "--ingestion-trigger",
        trigger_label,
    ]
    return subprocess.run(command, check=False)


def bootstrap_state(state_path, raw_dir, state, bootstrap_existing):
    files = list_pdf_files(raw_dir)
    current_snapshot = {str(path): sha256_file(path) for path in files}
    if not state.get("files"):
        state["files"] = current_snapshot
        save_state(state_path, state)
        if bootstrap_existing:
            return files
        return []

    pending = []
    for path in files:
        digest = current_snapshot[str(path)]
        if state["files"].get(str(path)) != digest:
            pending.append(path)
    return pending


def poll_once(state_path, raw_dir, state, trigger_label):
    files = list_pdf_files(raw_dir)
    current_snapshot = {str(path): sha256_file(path) for path in files}
    pending = []
    for path in files:
        digest = current_snapshot[str(path)]
        if state["files"].get(str(path)) != digest:
            pending.append(path)
    if not pending:
        return 0

    processed = 0
    for pdf_path in pending:
        print(f"[INFO] Novo PDF detectado: {pdf_path}")
        result = run_extractor(pdf_path, trigger_label)
        if result.returncode == 0:
            state["files"][str(pdf_path)] = current_snapshot[str(pdf_path)]
            processed += 1
            print(f"[INFO] Ingestão concluída: {pdf_path}")
        else:
            print(f"[AVISO] Falha ao processar {pdf_path} (exit={result.returncode})")
    save_state(state_path, state)
    return processed


def main():
    args = parse_args()
    raw_dir = Path(args.raw_dir)
    state_path = Path(args.state_path)
    state = load_state(state_path)

    pending = bootstrap_state(state_path, raw_dir, state, args.bootstrap_existing)
    if pending:
        for pdf_path in pending:
            print(f"[INFO] PDF pronto para ingestão: {pdf_path}")
            result = run_extractor(pdf_path, args.trigger_label)
            if result.returncode == 0:
                state["files"][str(pdf_path)] = sha256_file(pdf_path)
                print(f"[INFO] Ingestão concluída: {pdf_path}")
            else:
                print(f"[AVISO] Falha ao processar {pdf_path} (exit={result.returncode})")
        save_state(state_path, state)

    if args.once:
        return 0

    print(f"[INFO] Monitorando {raw_dir} a cada {args.interval:.0f}s")
    while True:
        poll_once(state_path, raw_dir, state, args.trigger_label)
        time.sleep(args.interval)


if __name__ == "__main__":
    raise SystemExit(main())
