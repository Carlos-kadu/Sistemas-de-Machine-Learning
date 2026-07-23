from __future__ import annotations

import os
import re
import time
from dataclasses import dataclass

import requests
from pydantic import ValidationError

from app.model_service import ModelService
from app.schemas import ChurnInput, PredictionResponse


DEFAULT_RECOMMENDATIONS = {
    "LOW": [
        "Manter o acompanhamento do cliente e revisar a jornada periodicamente.",
        "Oferecer benefícios leves para fortalecer o relacionamento.",
    ],
    "MEDIUM": [
        "Entrar em contato para entender sinais de insatisfação.",
        "Avaliar oferta de retenção alinhada ao perfil do cliente.",
        "Verificar qualidade do serviço e histórico de atendimento.",
    ],
    "HIGH": [
        "Priorizar contato ativo com proposta de retenção.",
        "Revisar plano, preço e pontos de atrito com urgência.",
        "Acionar time de retenção para abordagem personalizada.",
    ],
}


@dataclass
class AgentResult:
    response: PredictionResponse
    model_latency_ms: float
    llm_latency_ms: float
    total_latency_ms: float


class GeminiClient:
    def __init__(self, api_key, model_name):
        self.api_key = api_key or ""
        self.model_name = model_name
        self.enabled = os.getenv("GEMINI_ENABLED", "true").lower() not in {"0", "false", "no"}

    @property
    def configured(self):
        return bool(self.api_key) and self.enabled

    def explain(self, prompt, timeout=12.0):
        if not self.configured:
            raise RuntimeError("Gemini não configurado.")

        url = (
            "https://generativelanguage.googleapis.com/v1beta/models/"
            f"{self.model_name}:generateContent?key={self.api_key}"
        )
        payload = {
            "contents": [
                {
                    "role": "user",
                    "parts": [{"text": prompt}],
                }
            ],
            "generationConfig": {
                "temperature": 0.2,
                "maxOutputTokens": 250,
            },
        }
        response = requests.post(url, json=payload, timeout=(3, timeout))
        response.raise_for_status()
        data = response.json()
        candidates = data.get("candidates", [])
        if not candidates:
            raise RuntimeError("Gemini retornou resposta vazia.")
        parts = candidates[0].get("content", {}).get("parts", [])
        text = "".join(part.get("text", "") for part in parts).strip()
        if not text:
            raise RuntimeError("Gemini retornou resposta vazia.")
        return text


class ChurnAgent:
    def __init__(self, model_service, gemini_client):
        self.model_service = model_service
        self.gemini_client = gemini_client

    def handle(self, payload):
        started_at = time.perf_counter()
        try:
            item = ChurnInput.model_validate(payload)
        except ValidationError as exc:
            raise ValueError(self._friendly_validation_error(exc)) from exc

        model_started = time.perf_counter()
        prediction = self.model_service.predict(item)
        model_latency_ms = (time.perf_counter() - model_started) * 1000

        prompt = self._build_prompt(item, prediction)
        llm_started = time.perf_counter()
        fallback_used = False

        try:
            explanation = self.gemini_client.explain(prompt)
            llm_latency_ms = (time.perf_counter() - llm_started) * 1000
            explanation = self._validate_llm_response(explanation, prediction)
        except Exception:
            fallback_used = True
            llm_latency_ms = (time.perf_counter() - llm_started) * 1000
            explanation = self._fallback_explanation(prediction["risk_class"])

        response = PredictionResponse(
            probability=round(prediction["probability"], 4),
            risk_class=prediction["risk_class"],
            explanation=explanation,
            recommendations=DEFAULT_RECOMMENDATIONS[prediction["risk_class"]][:3],
            fallback_used=fallback_used,
            factors=prediction["factors"],
        )

        total_latency_ms = (time.perf_counter() - started_at) * 1000
        return AgentResult(
            response=response,
            model_latency_ms=round(model_latency_ms, 2),
            llm_latency_ms=round(llm_latency_ms, 2),
            total_latency_ms=round(total_latency_ms, 2),
        )

    def _build_prompt(self, item, prediction):
        context = {
            "probabilidade": round(prediction["probability"] * 100, 2),
            "classificacao": prediction["risk_class"],
            "fatores_principais": prediction["factors"],
            "cliente": item.to_model_input(),
        }
        return (
            "Você é um assistente de retenção de clientes.\n"
            "Explique o resultado da previsão de churn em português, de forma objetiva.\n"
            "Use no máximo 3 recomendações práticas.\n"
            "Não invente probabilidades nem números novos.\n"
            "Não use linguagem técnica desnecessária.\n"
            "Contexto:\n"
            f"{context}\n"
            "Resposta:"
        )

    def _validate_llm_response(self, text, prediction):
        cleaned = text.strip()
        if not cleaned:
            raise ValueError("Resposta vazia.")
        if len(cleaned) > 1200:
            raise ValueError("Resposta muito longa.")

        expected = round(prediction["probability"] * 100)
        numbers = re.findall(r"(\d+(?:[.,]\d+)?)\s*%", cleaned)
        if numbers:
            parsed = [float(value.replace(",", ".")) for value in numbers]
            if all(abs(value - expected) > 5 for value in parsed):
                raise ValueError("Resposta fora do contexto numérico esperado.")

        keywords = ("churn", "risco", "retenção", "cliente", "probabilidade")
        if not any(keyword in cleaned.lower() for keyword in keywords):
            raise ValueError("Resposta fora do contexto.")

        return cleaned

    def _fallback_explanation(self, risk_class):
        return (
            "O serviço de IA está indisponível no momento. "
            f"O cliente foi classificado com risco {risk_class.lower()} de churn."
        )

    def _friendly_validation_error(self, exc):
        errors = []
        for error in exc.errors():
            field = ".".join(str(part) for part in error.get("loc", []))
            message = error.get("msg", "valor inválido")
            errors.append(f"{field}: {message}")
        return "Dados inválidos. Verifique os campos enviados. " + "; ".join(errors)
