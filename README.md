# AIOps Quality Project

## Опис проєкту

`aiops-quality-project` — це фінальний MLOps/AIOps-проєкт з inference-сервісом на FastAPI, який розгортається в Kubernetes через Helm і Argo CD, експортує метрики для Prometheus, візуалізується в Grafana та містить базову перевірку дрейфу вхідних даних.

У проєкті використано просту навчальну модель `LogisticRegression`, натреновану на датасеті Iris. Сервіс приймає 4 числові ознаки, повертає індекс класу та його назву (`setosa`, `versicolor`, `virginica`).

## Структура проєкту

```text
aiops-quality-project/
├── app/
│   ├── main.py
│   └── requirements.txt
├── model/
│   ├── train.py
│   └── model.pkl
├── helm/
│   ├── Chart.yaml
│   ├── values.yaml
│   └── templates/
│       ├── deployment.yaml
│       ├── service.yaml
│       └── servicemonitor.yaml
├── argocd/
│   └── application.yaml
├── grafana/
│   └── dashboards.json
├── prometheus/
│   └── additionalScrapeConfigs.yaml
├── .gitlab-ci.yml
├── Dockerfile
└── README.md
```

## Архітектура рішення

* **FastAPI** — inference API з endpoint'ами `/health`, `/predict`, `/metrics`
* **Scikit-learn** — модель `LogisticRegression` для Iris
* **Helm** — опис Kubernetes-маніфестів
* **Argo CD** — GitOps-деплой із Git-репозиторію
* **Prometheus** — збір метрик із `/metrics`
* **Grafana** — візуалізація requests, latency, drift alerts
* **GitLab CI** — підготовлений pipeline для retrain, build і update Helm

## Що реалізовано

### 1. Inference-сервіс

Сервіс реалізовано у `app/main.py`.

Основні можливості:

* завантаження моделі при старті
* окрема функція `predict(features)`
* окрема функція `detect_drift(features)`
* логування вхідних запитів
* Prometheus-метрики:

  * `inference_requests_total`
  * `drift_alerts_total`
  * `inference_request_latency_seconds`

### 2. Drift detector

Для спрощеної демонстрації використано rule-based drift detection:

* обчислюється сума вхідних ознак
* якщо сума більша за `DRIFT_THRESHOLD`, вважається, що спрацював drift detector
* у логах з’являється повідомлення `Drift detected: ...`
* збільшується лічильник `drift_alerts_total`

Поточне значення:

* `DRIFT_THRESHOLD = 15.0`

### 3. Helm + Argo CD

У `helm/` описано:

* `Deployment`
* `Service`
* `ServiceMonitor`

У `argocd/application.yaml` створено `Application` з:

* `auto-sync`
* `prune: true`
* `selfHeal: true`

### 4. Моніторинг

Після встановлення `kube-prometheus-stack` у кластері з’явився CRD `ServiceMonitor`, а сервіс успішно почав віддавати метрики в Prometheus.

У Grafana імпортовано dashboard з трьома панелями:

* `Requests per minute`
* `Latency p95`
* `Drift alerts`

### 5. CI для retrain

У `.gitlab-ci.yml` підготовлено 3 стадії:

* `retrain-model`
* `build-image`
* `update-helm`

Логіка:

1. `retrain-model` запускає `python model/train.py`
2. `build-image` збирає та пушить Docker-образ
3. `update-helm` оновлює `helm/values.yaml` новим тегом образу

> Примітка: для повного автоматичного циклу потрібно підставити реальний Git remote та секрети CI.

## Як запустити локально

### 1. Навчити модель

```bash
python model/train.py
```

### 2. Запустити API локально

```bash
uvicorn app.main:app --host 0.0.0.0 --port 8000
```

### 3. Перевірити health

```bash
curl http://localhost:8000/health
```

Очікувана відповідь:

```json
{"status":"ok"}
```

### 4. Перевірити predict

```bash
curl -X POST http://localhost:8000/predict \
  -H "Content-Type: application/json" \
  -d '{"features":[5.1,3.5,1.4,0.2]}'
```

Очікувана відповідь:

```json
{"prediction":0,"class_name":"setosa","drift_detected":false,"message":"Prediction completed"}
```

## Як зібрати Docker image

Для EKS на `amd64` я збирав образ так:

```bash
docker buildx build \
  --platform linux/amd64 \
  -t i1inandrii/aiops-quality-project:amd64-v1 \
  --push .
```

Або локально:

```bash
docker build -t i1inandrii/aiops-quality-project:latest .
docker push i1inandrii/aiops-quality-project:latest
```

## Як розгорнути в Kubernetes

### 1. Створити EKS-кластер

Приклад команди:

```bash
eksctl create cluster \
  --name aiops-quality-cluster \
  --region eu-central-1 \
  --version 1.31 \
  --nodegroup-name general \
  --node-type t3.medium \
  --nodes 2 \
  --nodes-min 2 \
  --nodes-max 2 \
  --managed
```

### 2. Створити namespace

```bash
kubectl create namespace argocd --dry-run=client -o yaml | kubectl apply -f -
kubectl create namespace application --dry-run=client -o yaml | kubectl apply -f -
kubectl create namespace monitoring --dry-run=client -o yaml | kubectl apply -f -
kubectl create namespace logging --dry-run=client -o yaml | kubectl apply -f -
```

### 3. Встановити Argo CD

```bash
kubectl apply -n argocd --server-side --force-conflicts \
  -f https://raw.githubusercontent.com/argoproj/argo-cd/stable/manifests/install.yaml
```

### 4. Застосувати Argo CD Application

```bash
kubectl apply -f argocd/application.yaml
```

### 5. Встановити monitoring stack

```bash
helm repo add prometheus-community https://prometheus-community.github.io/helm-charts
helm repo update

helm upgrade --install monitoring-stack prometheus-community/kube-prometheus-stack \
  -n monitoring \
  --create-namespace \
  --set grafana.enabled=true \
  --set alertmanager.enabled=false \
  --set prometheus.prometheusSpec.serviceMonitorSelectorNilUsesHelmValues=false
```

### 6. Оновити sync після появи CRD

```bash
kubectl annotate application aiops-quality-project -n argocd argocd.argoproj.io/refresh=hard --overwrite
kubectl patch application aiops-quality-project -n argocd --type merge -p '{"operation":{"sync":{"prune":true,"syncOptions":["CreateNamespace=true"]}}}'
```

## Як перевірити, що все працює

### Argo CD

```bash
kubectl get applications -n argocd
```

Фактичний результат:

```text
NAME                    SYNC STATUS   HEALTH STATUS
aiops-quality-project   Synced        Healthy
```

### Pods

```bash
kubectl get pods -n application
```

Фактичний результат:

```text
NAME                                     READY   STATUS    RESTARTS   AGE
aiops-quality-project-7fbfb665c6-z5sm7   1/1     Running   0          22m
```

### ServiceMonitor

```bash
kubectl get servicemonitor -n application
```

### Port-forward до API

```bash
kubectl port-forward svc/aiops-quality-project -n application 8000:8000
```

### Health check

```bash
curl http://localhost:8000/health
```

### Predict check

```bash
curl -X POST http://localhost:8000/predict \
  -H "Content-Type: application/json" \
  -d '{"features":[5.1,3.5,1.4,0.2]}'
```

Фактична відповідь:

```json
{"prediction":0,"class_name":"setosa","drift_detected":false,"message":"Prediction completed"}
```

## Як перевірити логування

```bash
kubectl logs -n application deployment/aiops-quality-project --tail=50
```

Фрагмент реальних логів:

```text
Incoming request: [5.1, 3.5, 1.4, 0.2]
Incoming request: [6.7, 3.1, 4.7, 1.5]
Drift detected: score=16.0, threshold=15.0
Incoming request: [7.2, 3.6, 6.1, 2.5]
Drift detected: score=19.4, threshold=15.0
Incoming request: [10.0, 10.0, 10.0, 10.0]
Drift detected: score=40.0, threshold=15.0
```

## Як перевірити drift detector

Виклик із явно аномальними даними:

```bash
curl -X POST http://localhost:8000/predict \
  -H "Content-Type: application/json" \
  -d '{"features":[10.0,10.0,10.0,10.0]}'
```

Очікування:

* у логах з’явиться `Drift detected`
* у метриці `drift_alerts_total` значення збільшиться
* у Grafana оновиться панель `Drift alerts`

## Як перевірити метрики

```bash
curl http://localhost:8000/metrics | grep -E "inference_requests_total|drift_alerts_total|inference_request_latency"
```

Фактичний фрагмент:

```text
# HELP inference_requests_total Total inference requests
inference_requests_total 1.0
# HELP drift_alerts_total Total drift alerts
drift_alerts_total 0.0
# TYPE inference_request_latency_seconds histogram
inference_request_latency_seconds_count 1.0
```

## Як відкрити Grafana

### Пароль admin

```bash
kubectl get secret -n monitoring monitoring-stack-grafana -o jsonpath="{.data.admin-password}" | base64 -d ; echo
```

### Port-forward

```bash
kubectl port-forward -n monitoring svc/monitoring-stack-grafana 3000:80
```

Після цього Grafana доступна на:

```text
http://localhost:3000
```

Логін:

```text
admin
```

### Dashboard

Імпортовано dashboard `AIOps Quality Project` з панелями:

* `Latency p95`
* `Requests per minute`
* `Drift alerts`

## Як працює retrain pipeline

Файл `.gitlab-ci.yml` містить такі job:

### retrain-model

```yaml
retrain-model:
  stage: train
  image: python:3.11
  script:
    - pip install scikit-learn
    - python model/train.py
```

### build-image

```yaml
build-image:
  stage: build
  image: docker:27
  services:
    - docker:27-dind
```

### update-helm

Оновлює тег контейнера в `helm/values.yaml`.

## Які CI-змінні потрібні

Для GitLab CI потрібні змінні:

* `DOCKERHUB_USERNAME`
* `DOCKERHUB_PASSWORD`
* `GITLAB_PUSH_TOKEN`

Також використовується:

* `CI_COMMIT_SHORT_SHA`

## Як оновити модель

1. Змінити код у `model/train.py`
2. Перенавчити модель:

   ```bash
   python model/train.py
   ```
3. Зібрати та запушити новий образ
4. Оновити тег у `helm/values.yaml`
5. Закомітити зміни в `final-project`
6. Argo CD автоматично підтягне нову версію

## Висновок

У проєкті реалізовано повний базовий ланцюжок MLOps/AIOps:

* inference API на FastAPI
* модель, що завантажується при старті
* drift detection
* логування запитів
* метрики Prometheus
* dashboard у Grafana
* Helm deployment
* GitOps через Argo CD
* підготовлений retrain pipeline через GitLab CI

Проєкт успішно розгорнуто в EKS-кластері, застосунок відповідає на запити, логи містять події drift detection, а метрики відображаються в Grafana.
