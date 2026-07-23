from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime, timezone


@dataclass
class MonitoringSnapshot:
    predictions: int
    average_latency_ms: float
    fallbacks: int
    risk_counts: dict
    fallback_rate: float


class MonitoringStore:
    def __init__(self, log_path):
        self.log_path = log_path
        self.log_path.parent.mkdir(parents=True, exist_ok=True)

    def append(self, payload):
        record = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            **payload,
        }
        with self.log_path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(record, ensure_ascii=False) + "\n")

    def snapshot(self):
        if not self.log_path.exists():
            return MonitoringSnapshot(
                predictions=0,
                average_latency_ms=0.0,
                fallbacks=0,
                risk_counts={"LOW": 0, "MEDIUM": 0, "HIGH": 0},
                fallback_rate=0.0,
            )

        count = 0
        fallback_count = 0
        total_latency = 0.0
        risk_counts = {"LOW": 0, "MEDIUM": 0, "HIGH": 0}

        with self.log_path.open("r", encoding="utf-8") as handle:
            for line in handle:
                line = line.strip()
                if not line:
                    continue
                try:
                    record = json.loads(line)
                except json.JSONDecodeError:
                    continue

                count += 1
                total_latency += float(record.get("latency_ms", 0.0))
                if record.get("fallback_used"):
                    fallback_count += 1
                classification = record.get("classification")
                if classification in risk_counts:
                    risk_counts[classification] += 1

        average_latency = total_latency / count if count else 0.0
        return MonitoringSnapshot(
            predictions=count,
            average_latency_ms=round(average_latency, 2),
            fallbacks=fallback_count,
            risk_counts=risk_counts,
            fallback_rate=round(fallback_count / count, 4) if count else 0.0,
        )
