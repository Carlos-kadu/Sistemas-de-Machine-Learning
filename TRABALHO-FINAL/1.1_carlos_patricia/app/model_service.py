from __future__ import annotations

import json
from dataclasses import dataclass

import joblib
@dataclass
class ModelArtifacts:
    pipeline: object
    metadata: dict


class ModelService:
    def __init__(self, model_path, metadata_path):
        self.model_path = model_path
        self.metadata_path = metadata_path
        self.artifacts = self._load_artifacts()

    def _load_artifacts(self):
        if not self.model_path.exists():
            raise FileNotFoundError(
                f"Modelo não encontrado em {self.model_path}. Execute training.py primeiro."
            )
        if not self.metadata_path.exists():
            raise FileNotFoundError(
                f"Metadata não encontrada em {self.metadata_path}. Execute training.py primeiro."
            )

        pipeline = joblib.load(self.model_path)
        with self.metadata_path.open("r", encoding="utf-8") as handle:
            metadata = json.load(handle)

        return ModelArtifacts(pipeline=pipeline, metadata=metadata)

    def reload(self):
        self.artifacts = self._load_artifacts()

    @property
    def metadata(self):
        return self.artifacts.metadata

    def validate_categories(self, item):
        allowed = self.metadata.get("allowed_values", {})
        payload = item.to_model_input()
        for field_name, choices in allowed.items():
            value = payload.get(field_name)
            if choices and value not in choices:
                raise ValueError(f"Valor inválido em {field_name}: {value}")

    def predict(self, item):
        self.validate_categories(item)
        features = item.to_model_input()
        pipeline = self.artifacts.pipeline
        probability = float(pipeline.predict_proba([features])[0][1])
        risk_class = self._classify(probability)
        factors = self._top_factors(features)

        return {
            "probability": probability,
            "risk_class": risk_class,
            "factors": factors,
        }

    def _classify(self, probability):
        threshold = float(self.metadata.get("decision_threshold", 0.5))
        low_cutoff = max(0.15, round(threshold * 0.7, 4))
        medium_cutoff = threshold

        if probability < low_cutoff:
            return "LOW"
        if probability < medium_cutoff:
            return "MEDIUM"
        return "HIGH"

    def _top_factors(self, features, limit=3):
        pipeline = self.artifacts.pipeline
        vectorizer = pipeline.named_steps["vectorizer"]
        model = pipeline.named_steps["model"]
        feature_names = vectorizer.get_feature_names_out()
        transformed = vectorizer.transform([features])[0]
        importances = getattr(model, "feature_importances_", [])

        candidates = []
        for idx, value in enumerate(transformed):
            if value <= 0:
                continue
            feature_name = feature_names[idx]
            importance = float(importances[idx]) if idx < len(importances) else 0.0
            candidates.append(
                {
                    "feature": feature_name,
                    "importance": round(importance, 4),
                    "value": self._friendly_value(feature_name, features),
                }
            )

        candidates.sort(key=lambda item: item["importance"], reverse=True)
        return candidates[:limit]

    def _friendly_value(self, feature_name, features):
        if "=" in feature_name:
            field, raw_value = feature_name.split("=", 1)
            return f"{field}={raw_value}"

        value = features.get(feature_name)
        if isinstance(value, float):
            return f"{value:.2f}"
        return str(value)
