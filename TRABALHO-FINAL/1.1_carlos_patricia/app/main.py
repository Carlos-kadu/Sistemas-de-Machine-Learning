from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv
from fastapi import Body, FastAPI
from fastapi.exceptions import RequestValidationError
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from app.agent import ChurnAgent, GeminiClient
from app.model_service import ModelService
from app.monitoring import MonitoringStore
from app.schemas import HealthResponse, MetricsResponse, PredictionResponse


BASE_DIR = Path(__file__).resolve().parents[1]
load_dotenv(BASE_DIR / ".env")

MODEL_PATH = Path(os.getenv("MODEL_PATH", BASE_DIR / "model" / "model.joblib"))
METADATA_PATH = Path(os.getenv("METADATA_PATH", BASE_DIR / "model" / "metadata.json"))
LOG_PATH = Path(os.getenv("LOG_PATH", BASE_DIR / "logs" / "predictions.jsonl"))
DATASET_REPORT_PATH = BASE_DIR / "model" / "dataset_report.json"
EVALUATION_REPORT_PATH = BASE_DIR / "model" / "evaluation_report.json"
GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-2.5-flash-lite")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")

app = FastAPI(title="Agente de Previsão de Churn", version="1.0.0")
app.mount("/static", StaticFiles(directory=BASE_DIR / "static"), name="static")

model_service = None
agent = None
monitoring_store = MonitoringStore(LOG_PATH)


def get_agent():
    if agent is None:
        raise RuntimeError("Agente indisponível.")
    return agent


@app.on_event("startup")
def startup_event():
    global model_service, agent
    try:
        model_service = ModelService(MODEL_PATH, METADATA_PATH)
        gemini_client = GeminiClient(GEMINI_API_KEY, GEMINI_MODEL)
        agent = ChurnAgent(model_service, gemini_client)
    except Exception:
        model_service = None
        agent = None


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(_, exc):
    messages = [f"{'.'.join(str(i) for i in error['loc'])}: {error['msg']}" for error in exc.errors()]
    return JSONResponse(
        status_code=422,
        content={
            "detail": "Dados inválidos. Verifique os campos enviados.",
            "errors": messages,
        },
    )


@app.exception_handler(ValueError)
async def value_error_handler(_, exc):
    return JSONResponse(status_code=400, content={"detail": str(exc)})


@app.exception_handler(Exception)
async def generic_exception_handler(_, __):
    return JSONResponse(
        status_code=500,
        content={"detail": "Ocorreu um erro inesperado. Tente novamente em instantes."},
    )


@app.get("/", response_class=HTMLResponse)
def root():
    html_path = BASE_DIR / "templates" / "index.html"
    return HTMLResponse(
        html_path.read_text(encoding="utf-8"),
        headers={"Cache-Control": "no-store, max-age=0"},
    )


@app.post("/predict", response_model=PredictionResponse)
def predict(payload: dict = Body(...)):
    if agent is None:
        return JSONResponse(
            status_code=503,
            content={
                "detail": "O modelo ainda não foi carregado. Execute training.py para gerar model/model.joblib."
            },
        )

    result = get_agent().handle(payload)
    monitoring_store.append(
        {
            "latency_ms": result.total_latency_ms,
            "model_latency_ms": result.model_latency_ms,
            "llm_latency_ms": result.llm_latency_ms,
            "probability": result.response.probability,
            "classification": result.response.risk_class,
            "fallback_used": result.response.fallback_used,
            "response_time_ms": result.total_latency_ms,
        }
    )
    return result.response


@app.get("/health", response_model=HealthResponse)
def health():
    return HealthResponse(
        status="ok",
        model_loaded=model_service is not None,
        gemini_configured=bool(GEMINI_API_KEY),
    )


@app.get("/metrics", response_model=MetricsResponse)
def metrics():
    snapshot = monitoring_store.snapshot()
    return MetricsResponse(
        predictions=snapshot.predictions,
        average_latency_ms=snapshot.average_latency_ms,
        fallbacks=snapshot.fallbacks,
        fallback_rate=snapshot.fallback_rate,
        risk_counts=snapshot.risk_counts,
    )


@app.get("/dataset-report")
def dataset_report():
    if not DATASET_REPORT_PATH.exists():
        return JSONResponse(status_code=404, content={"detail": "Relatório do dataset não encontrado."})
    return JSONResponse(content=_read_json(DATASET_REPORT_PATH))


@app.get("/model-card")
def model_card():
    if not EVALUATION_REPORT_PATH.exists():
        return JSONResponse(status_code=404, content={"detail": "Relatório de avaliação não encontrado."})
    return JSONResponse(content=_read_json(EVALUATION_REPORT_PATH))


def _read_json(path):
    import json

    with path.open("r", encoding="utf-8") as handle:
        return json.load(handle)
