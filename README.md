# aiops-quality-project

Проєкт демонструє inference-сервіс на FastAPI з простим drift detector, метриками Prometheus, Helm-деплоєм, ArgoCD auto-sync та GitLab CI для retrain.

## Компоненти

- FastAPI API для прогнозів
- Drift detector на рівні сервісу
- Prometheus metrics endpoint `/metrics`
- Helm chart для деплою
- ArgoCD Application для GitOps
- GitLab CI job для retrain і оновлення image tag

## Локальний запуск

```bash
python model/train.py
pip install -r app/requirements.txt
uvicorn app.main:app --host 0.0.0.0 --port 8000
```

(.venv) MacBookAir:aiops-quality-project ozzy$ curl -X POST http://localhost:8000/predict \

> -H "Content-Type: application/json" \
>  -d '{"features":[5.1,3.5,1.4,0.2]}'
> {"prediction":0,"class_name":"setosa","drift_detected":true,"message":"Prediction completed"}(.venv) MacBookAir:aiops-quality-project ozzy$
