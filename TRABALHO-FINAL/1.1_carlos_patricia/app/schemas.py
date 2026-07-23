from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator


TENURE_MAX = 1000


class ChurnInput(BaseModel):
    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    gender: Literal["Female", "Male"]
    senior_citizen: int = Field(ge=0, le=1, alias="SeniorCitizen")
    partner: Literal["Yes", "No"] = Field(alias="Partner")
    dependents: Literal["Yes", "No"] = Field(alias="Dependents")
    tenure: int = Field(ge=0, le=TENURE_MAX)
    phone_service: Literal["Yes", "No"] = Field(alias="PhoneService")
    multiple_lines: Literal["Yes", "No", "No phone service"] = Field(alias="MultipleLines")
    internet_service: Literal["DSL", "Fiber optic", "No"] = Field(alias="InternetService")
    online_security: Literal["Yes", "No", "No internet service"] = Field(alias="OnlineSecurity")
    online_backup: Literal["Yes", "No", "No internet service"] = Field(alias="OnlineBackup")
    device_protection: Literal["Yes", "No", "No internet service"] = Field(alias="DeviceProtection")
    tech_support: Literal["Yes", "No", "No internet service"] = Field(alias="TechSupport")
    streaming_tv: Literal["Yes", "No", "No internet service"] = Field(alias="StreamingTV")
    streaming_movies: Literal["Yes", "No", "No internet service"] = Field(alias="StreamingMovies")
    contract: Literal["Month-to-month", "One year", "Two year"] = Field(alias="Contract")
    paperless_billing: Literal["Yes", "No"] = Field(alias="PaperlessBilling")
    payment_method: Literal[
        "Electronic check",
        "Mailed check",
        "Bank transfer (automatic)",
        "Credit card (automatic)",
    ] = Field(alias="PaymentMethod")
    monthly_charges: float = Field(ge=0, alias="MonthlyCharges")
    total_charges: float = Field(ge=0, alias="TotalCharges")

    @field_validator("total_charges", mode="before")
    @classmethod
    def normalize_total_charges(cls, value):
        if value in {"", None}:
            return 0
        return value

    def to_model_input(self):
        return self.model_dump(by_alias=True)


class PredictionResponse(BaseModel):
    probability: float
    risk_class: Literal["LOW", "MEDIUM", "HIGH"]
    explanation: str
    recommendations: list[str]
    fallback_used: bool
    factors: list[dict[str, Any]]


class MetricsResponse(BaseModel):
    predictions: int
    average_latency_ms: float
    fallbacks: int
    fallback_rate: float
    risk_counts: dict[str, int]


class HealthResponse(BaseModel):
    status: str
    model_loaded: bool
    gemini_configured: bool
