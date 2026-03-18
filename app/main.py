import os
import time
import pickle
from pathlib import Path
from typing import List

from fastapi import FastAPI
from pydantic import BaseModel
from prometheus_client import Counter, Histogram, generate_latest, CONTENT_TYPE_LATEST
from starlette.responses import Response

APP_DIR = Path(__file__).resolve().parent
MODEL_PATH = Path(os.getenv("MODEL_PATH", APP_DIR.parent / "model" / "model.pkl"))
DRIFT_THRESHOLD = float(os.getenv("DRIFT_THRESHOLD", "8.0"))

REQUEST_COUNT = Counter("inference_requests_total", "Total inference requests")
DRIFT_COUNT = Counter("drift_alerts_total", "Total drift alerts")
REQUEST_LATENCY = Histogram("inference_request_latency_seconds", "Inference latency")

app = FastAPI(title="aiops-quality-project")

model = None


class PredictRequest(BaseModel):
    features: List[float]


class PredictResponse(BaseModel):
    prediction: int
    drift_detected: bool
    message: str


def load_model():
    global model
    with open(MODEL_PATH, "rb") as f:
        model = pickle.load(f)


def detect_drift(features: List[float]) -> bool:
    score = sum(features)
    drift = score > DRIFT_THRESHOLD
    if drift:
        print(f"Drift detected: score={score}, threshold={DRIFT_THRESHOLD}")
        DRIFT_COUNT.inc()
    return drift


def predict(features: List[float]) -> int:
    prediction = model.predict([features])[0]
    return int(prediction)


@app.on_event("startup")
def startup_event():
    load_model()
    print(f"Model loaded from: {MODEL_PATH}")


@app.get("/health")
def health():
    return {"status": "ok"}


@app.get("/metrics")
def metrics():
    return Response(generate_latest(), media_type=CONTENT_TYPE_LATEST)


@app.post("/predict", response_model=PredictResponse)
def predict_endpoint(payload: PredictRequest):
    REQUEST_COUNT.inc()
    start = time.time()

    print(f"Incoming request: {payload.features}")
    drift_detected = detect_drift(payload.features)
    prediction = predict(payload.features)

    REQUEST_LATENCY.observe(time.time() - start)

    return PredictResponse(
        prediction=prediction,
        drift_detected=drift_detected,
        message="Prediction completed",
    )