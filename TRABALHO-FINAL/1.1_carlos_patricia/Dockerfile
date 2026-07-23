FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

COPY requirements.txt .
RUN pip install --upgrade pip && pip install -r requirements.txt

COPY app ./app
COPY static ./static
COPY templates ./templates
COPY model/model.joblib ./model/model.joblib
COPY model/metadata.json ./model/metadata.json
COPY model/dataset_report.json ./model/dataset_report.json
COPY model/evaluation_report.json ./model/evaluation_report.json

RUN mkdir -p /app/logs

EXPOSE 8000

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
