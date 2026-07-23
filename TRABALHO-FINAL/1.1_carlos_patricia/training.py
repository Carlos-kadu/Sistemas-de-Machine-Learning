from __future__ import annotations

import csv
import json
from collections import Counter, defaultdict
from pathlib import Path
from statistics import mean, median, pstdev

import joblib
from sklearn.ensemble import RandomForestClassifier
from sklearn.feature_extraction import DictVectorizer
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import accuracy_score, f1_score, precision_score, recall_score, roc_auc_score
from sklearn.model_selection import train_test_split
from sklearn.pipeline import Pipeline


BASE_DIR = Path(__file__).resolve().parent
DATA_DIR = BASE_DIR / "data"
MODEL_DIR = BASE_DIR / "model"
RAW_DATA_PATH = DATA_DIR / "WA_Fn-UseC_-Telco-Customer-Churn.csv"
MODEL_PATH = MODEL_DIR / "model.joblib"
METADATA_PATH = MODEL_DIR / "metadata.json"
REPORT_PATH = MODEL_DIR / "training_report.json"
DATASET_REPORT_PATH = MODEL_DIR / "dataset_report.json"
EVALUATION_REPORT_PATH = MODEL_DIR / "evaluation_report.json"
ENGINEERING_LOG_PATH = BASE_DIR / "ENGINEERING_LOG.md"

DATASET_SOURCE_URL = "https://www.kaggle.com/datasets/blastchar/telco-customer-churn"

NUMERIC_FIELDS = {"SeniorCitizen", "tenure", "MonthlyCharges", "TotalCharges"}
VALIDATION_NUMERIC_FIELDS = {"tenure", "MonthlyCharges", "TotalCharges"}
TARGET = "Churn"
IGNORE_FIELDS = {"customerID", TARGET}

EXPECTED_CATEGORIES = {
    "gender": {"Female", "Male"},
    "Partner": {"No", "Yes"},
    "Dependents": {"No", "Yes"},
    "PhoneService": {"No", "Yes"},
    "MultipleLines": {"No", "No phone service", "Yes"},
    "InternetService": {"DSL", "Fiber optic", "No"},
    "OnlineSecurity": {"No", "No internet service", "Yes"},
    "OnlineBackup": {"No", "No internet service", "Yes"},
    "DeviceProtection": {"No", "No internet service", "Yes"},
    "TechSupport": {"No", "No internet service", "Yes"},
    "StreamingTV": {"No", "No internet service", "Yes"},
    "StreamingMovies": {"No", "No internet service", "Yes"},
    "Contract": {"Month-to-month", "One year", "Two year"},
    "PaperlessBilling": {"No", "Yes"},
    "PaymentMethod": {
        "Bank transfer (automatic)",
        "Credit card (automatic)",
        "Electronic check",
        "Mailed check",
    },
}


def ensure_dataset_available():
    if RAW_DATA_PATH.exists():
        return

    DATA_DIR.mkdir(parents=True, exist_ok=True)
    raise FileNotFoundError(
        "Dataset não encontrado. Baixe o arquivo "
        "WA_Fn-UseC_-Telco-Customer-Churn.csv no Kaggle e coloque em "
        f"{RAW_DATA_PATH}. Fonte: {DATASET_SOURCE_URL}"
    )


def load_raw_rows(csv_path):
    rows = []
    with csv_path.open("r", encoding="utf-8") as handle:
        reader = csv.DictReader(handle)
        for raw_row in reader:
            rows.append(raw_row)
    return rows


def coerce_float(value):
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def normalize_row(raw_row):
    row = {}
    for key, value in raw_row.items():
        if key == "customerID":
            continue
        value = "" if value is None else str(value).strip()
        if key == "TotalCharges":
            coerced = coerce_float(value)
            row[key] = coerced if coerced is not None else 0.0
            continue
        if key in {"SeniorCitizen", "tenure"}:
            coerced = coerce_float(value)
            if coerced is None:
                return None
            row[key] = int(coerced)
            continue
        if key in {"MonthlyCharges"}:
            coerced = coerce_float(value)
            if coerced is None:
                return None
            row[key] = float(coerced)
            continue
        if key == TARGET:
            row[key] = 1 if value.lower() == "yes" else 0
            continue
        row[key] = value
    return row


def analyze_dataset(raw_rows, normalized_rows):
    report = {
        "source_rows": len(raw_rows),
        "usable_rows": len(normalized_rows),
        "discarded_rows": len(raw_rows) - len(normalized_rows),
        "missing_values": {},
        "duplicates": {},
        "unexpected_categories": {},
        "negative_values": {},
        "descriptive_statistics": {},
        "target_distribution": {},
        "outlier_policy": (
            "No automatic outlier removal was applied. "
            "The dataset is predominantly categorical, and Random Forest is robust to extreme values. "
            "We preferred conservative cleaning and documentation over aggressive row removal."
        ),
    }

    missing_counts = Counter()
    duplicate_counts = 0
    duplicate_keys = set()
    seen_rows = set()
    negative_counts = Counter()
    unexpected_counts = defaultdict(lambda: {"count": 0, "examples": []})
    numeric_values = defaultdict(list)
    target_counts = Counter()

    for raw_row, row in zip(raw_rows, normalized_rows):
        row_key = tuple(sorted((key, str(value)) for key, value in row.items()))
        if row_key in seen_rows:
            duplicate_counts += 1
            duplicate_keys.add(row_key)
        else:
            seen_rows.add(row_key)

        target_counts[row[TARGET]] += 1

        for key, raw_value in raw_row.items():
            if key in IGNORE_FIELDS:
                continue

            normalized_value = row.get(key)
            raw_text = "" if raw_value is None else str(raw_value).strip()
            if raw_text == "":
                missing_counts[key] += 1

            if key in VALIDATION_NUMERIC_FIELDS:
                numeric_values[key].append(float(normalized_value))
                if float(normalized_value) < 0:
                    negative_counts[key] += 1
                continue

            if key in EXPECTED_CATEGORIES:
                if normalized_value not in EXPECTED_CATEGORIES[key]:
                    unexpected_counts[key]["count"] += 1
                    if normalized_value not in unexpected_counts[key]["examples"] and len(unexpected_counts[key]["examples"]) < 5:
                        unexpected_counts[key]["examples"].append(normalized_value)

    report["missing_values"] = dict(sorted(missing_counts.items()))
    report["duplicates"] = {
        "count": duplicate_counts,
        "unique_duplicate_rows": len(duplicate_keys),
    }
    report["unexpected_categories"] = {
        key: value for key, value in unexpected_counts.items() if value["count"] > 0
    }
    report["negative_values"] = dict(sorted(negative_counts.items()))
    report["target_distribution"] = {
        "churn_0": target_counts.get(0, 0),
        "churn_1": target_counts.get(1, 0),
        "churn_0_pct": round((target_counts.get(0, 0) / len(normalized_rows)) * 100, 2) if normalized_rows else 0,
        "churn_1_pct": round((target_counts.get(1, 0) / len(normalized_rows)) * 100, 2) if normalized_rows else 0,
    }

    for key, values in numeric_values.items():
        if not values:
            continue
        sorted_values = sorted(values)
        quartile_1 = percentile(sorted_values, 25)
        quartile_3 = percentile(sorted_values, 75)
        report["descriptive_statistics"][key] = {
            "count": len(values),
            "mean": round(mean(values), 4),
            "std": round(pstdev(values), 4) if len(values) > 1 else 0.0,
            "min": round(min(values), 4),
            "q1": round(quartile_1, 4),
            "median": round(median(values), 4),
            "q3": round(quartile_3, 4),
            "max": round(max(values), 4),
        }

    return report


def percentile(values, pct):
    if not values:
        return 0.0
    if len(values) == 1:
        return float(values[0])

    position = (len(values) - 1) * (pct / 100)
    lower_index = int(position)
    upper_index = min(lower_index + 1, len(values) - 1)
    fraction = position - lower_index
    lower = values[lower_index]
    upper = values[upper_index]
    return lower + ((upper - lower) * fraction)


def clean_rows(raw_rows):
    normalized_rows = []
    discarded = 0
    for raw_row in raw_rows:
        row = normalize_row(raw_row)
        if row is None:
            discarded += 1
            continue
        normalized_rows.append(row)
    return normalized_rows, discarded


def split_features(rows):
    features = []
    target = []
    for row in rows:
        target.append(int(row[TARGET]))
        features.append({key: value for key, value in row.items() if key != TARGET})
    return features, target


def build_metadata(rows, source_url, report):
    allowed_values = {}
    for row in rows:
        for key, value in row.items():
            if key in IGNORE_FIELDS:
                continue
            if key in NUMERIC_FIELDS:
                continue
            allowed_values.setdefault(key, set()).add(str(value))

    allowed_sorted = {key: sorted(values) for key, values in allowed_values.items()}
    return {
        "feature_names": [key for key in rows[0].keys() if key != TARGET],
        "target": TARGET,
        "allowed_values": allowed_sorted,
        "source_url": source_url,
        "dataset_report_path": str(DATASET_REPORT_PATH.name),
        "decision_threshold": report.get("decision_threshold", 0.5),
    }


def find_best_threshold(y_true, probabilities):
    best_threshold = 0.5
    best_f1 = -1.0
    for step in range(20, 81):
        threshold = step / 100
        predictions = [1 if value >= threshold else 0 for value in probabilities]
        score = f1_score(y_true, predictions, zero_division=0)
        if score > best_f1:
            best_f1 = score
            best_threshold = threshold
    return best_threshold


def calculate_metrics(y_true, probabilities, threshold):
    predictions = [1 if value >= threshold else 0 for value in probabilities]
    return {
        "accuracy": accuracy_score(y_true, predictions),
        "precision": precision_score(y_true, predictions, zero_division=0),
        "recall": recall_score(y_true, predictions, zero_division=0),
        "f1": f1_score(y_true, predictions, zero_division=0),
        "roc_auc": roc_auc_score(y_true, probabilities),
        "decision_threshold": round(threshold, 4),
    }


def calculate_fairness_by_gender(rows, y_true, probabilities, threshold):
    groups = defaultdict(lambda: {"y_true": [], "probabilities": []})
    for row, actual, probability in zip(rows, y_true, probabilities):
        gender = row.get("gender", "Unknown")
        groups[gender]["y_true"].append(actual)
        groups[gender]["probabilities"].append(probability)

    report = {}
    for gender, values in groups.items():
        actual_values = values["y_true"]
        probability_values = values["probabilities"]
        predictions = [1 if value >= threshold else 0 for value in probability_values]
        positives = sum(actual_values)
        report[gender] = {
            "count": len(actual_values),
            "actual_churn": positives,
            "recall": recall_score(actual_values, predictions, zero_division=0),
            "precision": precision_score(actual_values, predictions, zero_division=0),
            "f1": f1_score(actual_values, predictions, zero_division=0),
        }

    if {"Female", "Male"}.issubset(report):
        report["recall_gap_abs"] = abs(report["Female"]["recall"] - report["Male"]["recall"])

    return report


def evaluate_baselines(x_train, y_train, x_val, y_val, x_test, y_test):
    baseline_probabilities = [0.0 for _ in y_test]
    baseline_metrics = calculate_metrics(y_test, baseline_probabilities, 0.5)

    logistic_pipeline = Pipeline(
        steps=[
            ("vectorizer", DictVectorizer(sparse=False)),
            (
                "model",
                LogisticRegression(
                    max_iter=2000,
                    class_weight="balanced",
                    solver="liblinear",
                    random_state=42,
                ),
            ),
        ]
    )
    logistic_pipeline.fit(x_train, y_train)
    val_probabilities = logistic_pipeline.predict_proba(x_val)[:, 1]
    logistic_threshold = find_best_threshold(y_val, val_probabilities)
    logistic_pipeline.fit(x_train + x_val, y_train + y_val)
    test_probabilities = logistic_pipeline.predict_proba(x_test)[:, 1]
    logistic_metrics = calculate_metrics(y_test, test_probabilities, logistic_threshold)

    return {
        "baseline_always_no_churn": baseline_metrics,
        "logistic_regression_balanced": logistic_metrics,
    }


def train_model(features, target):
    x_train, x_test, y_train, y_test = train_test_split(
        features,
        target,
        test_size=0.2,
        random_state=42,
        stratify=target,
    )
    x_train, x_val, y_train, y_val = train_test_split(
        x_train,
        y_train,
        test_size=0.2,
        random_state=42,
        stratify=y_train,
    )

    candidates = [
        {
            "n_estimators": 250,
            "max_depth": None,
            "min_samples_leaf": 2,
            "max_features": "sqrt",
        },
        {
            "n_estimators": 400,
            "max_depth": 12,
            "min_samples_leaf": 2,
            "max_features": "sqrt",
        },
        {
            "n_estimators": 300,
            "max_depth": 16,
            "min_samples_leaf": 1,
            "max_features": "sqrt",
        },
    ]

    evaluation_report = {
        "test_size": len(y_test),
        "validation_size": len(y_val),
        "model_comparison": evaluate_baselines(x_train, y_train, x_val, y_val, x_test, y_test),
    }

    best_pipeline = None
    best_threshold = 0.5
    best_score = -1.0
    best_metrics = None

    for params in candidates:
        pipeline = Pipeline(
            steps=[
                ("vectorizer", DictVectorizer(sparse=False)),
                (
                    "model",
                    RandomForestClassifier(
                        random_state=42,
                        class_weight="balanced",
                        **params,
                    ),
                ),
            ]
        )
        pipeline.fit(x_train, y_train)
        val_probabilities = pipeline.predict_proba(x_val)[:, 1]
        threshold = find_best_threshold(y_val, val_probabilities)
        val_predictions = [1 if value >= threshold else 0 for value in val_probabilities]
        val_f1 = f1_score(y_val, val_predictions, zero_division=0)
        val_auc = roc_auc_score(y_val, val_probabilities)

        score = (val_f1 * 0.7) + (val_auc * 0.3)
        if score > best_score:
            best_score = score
            best_pipeline = pipeline
            best_threshold = threshold
            best_metrics = {
                "validation_f1": val_f1,
                "validation_roc_auc": val_auc,
                "selected_params": params,
            }

    pipeline = best_pipeline
    assert pipeline is not None
    pipeline.fit(x_train + x_val, y_train + y_val)

    probabilities = pipeline.predict_proba(x_test)[:, 1]
    metrics = calculate_metrics(y_test, probabilities, best_threshold)
    if best_metrics is not None:
        metrics["validation_f1"] = round(best_metrics["validation_f1"], 4)
        metrics["validation_roc_auc"] = round(best_metrics["validation_roc_auc"], 4)
        metrics["selected_params"] = best_metrics["selected_params"]
    evaluation_report["model_comparison"]["random_forest_balanced"] = metrics
    return pipeline, metrics, evaluation_report, x_test, y_test, probabilities


def save_artifacts(pipeline, metadata, metrics, report, evaluation_report):
    MODEL_DIR.mkdir(parents=True, exist_ok=True)
    joblib.dump(pipeline, MODEL_PATH)
    METADATA_PATH.write_text(json.dumps(metadata, ensure_ascii=False, indent=2), encoding="utf-8")
    REPORT_PATH.write_text(json.dumps(metrics, ensure_ascii=False, indent=2), encoding="utf-8")
    DATASET_REPORT_PATH.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    EVALUATION_REPORT_PATH.write_text(json.dumps(evaluation_report, ensure_ascii=False, indent=2), encoding="utf-8")


def write_engineering_log(report, metrics, source_url):
    lines = [
        "# Engineering Log",
        "",
        "## Tratamento de dados",
        "",
        f"- Fonte do dataset: `{source_url}`",
        "- `customerID` removido antes da modelagem.",
        "- `TotalCharges` convertido com coerção; valores inválidos ou ausentes viraram `0`.",
        "- Valores ausentes, duplicados, categorias inesperadas e valores negativos foram verificados e registrados.",
        "- Não houve remoção automática de outliers.",
        "",
        "## Justificativa sobre outliers",
        "",
        "O dataset é majoritariamente categórico e o Random Forest é relativamente robusto a valores extremos. ",
        "Optamos por não remover outliers automaticamente para evitar perda de sinal útil em um problema de churn.",
        "",
        "## Resultados do treino",
        "",
        f"- accuracy: {metrics['accuracy']:.4f}",
        f"- precision: {metrics['precision']:.4f}",
        f"- recall: {metrics['recall']:.4f}",
        f"- f1: {metrics['f1']:.4f}",
        f"- roc_auc: {metrics['roc_auc']:.4f}",
        f"- decision_threshold: {metrics['decision_threshold']:.2f}",
        "",
        "## Observações do dataset",
        "",
        f"- linhas brutas: {report['source_rows']}",
        f"- linhas úteis: {report['usable_rows']}",
        f"- linhas descartadas: {report['discarded_rows']}",
        f"- duplicados: {report['duplicates']['count']}",
        "",
        "## Avaliação complementar",
        "",
        "- Foi gerado `model/evaluation_report.json` com baseline, comparação simples de modelo e fairness por gênero.",
        "- A métrica principal segue sendo F1, com atenção especial a recall da classe churn.",
        "",
        "## Próximas leituras",
        "",
        "Se for preciso melhorar mais, o próximo passo natural seria testar engenharia de features, não limpeza agressiva.",
    ]
    ENGINEERING_LOG_PATH.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main():
    ensure_dataset_available()
    source_url = DATASET_SOURCE_URL

    raw_rows = load_raw_rows(RAW_DATA_PATH)
    normalized_rows, discarded_rows = clean_rows(raw_rows)
    dataset_report = analyze_dataset(raw_rows, normalized_rows)
    dataset_report["discarded_rows"] = discarded_rows

    features, target = split_features(normalized_rows)
    pipeline, metrics, evaluation_report, x_test, y_test, probabilities = train_model(features, target)
    dataset_report["decision_threshold"] = metrics["decision_threshold"]
    evaluation_report["fairness_by_gender"] = calculate_fairness_by_gender(
        x_test,
        y_test,
        probabilities,
        metrics["decision_threshold"],
    )
    metadata = build_metadata(normalized_rows, source_url, metrics)
    save_artifacts(pipeline, metadata, metrics, dataset_report, evaluation_report)
    write_engineering_log(dataset_report, metrics, source_url)
    print(json.dumps(metrics, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
