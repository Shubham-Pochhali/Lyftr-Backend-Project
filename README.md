# Lyftr AI — Backend Assignment

A FastAPI-based backend service implementing secure webhook ingestion, message storage with idempotency, filtering, pagination, analytics, health endpoints, metrics, and full Docker Compose deployment.

---

## Features

### **Webhook (POST /webhook)**
- Validates **HMAC-SHA256** signature using `X-Signature`
- Validates payload using **Pydantic**
- Ensures **idempotent inserts** via `message_id` primary key  
- Returns `{ "status": "ok" }` for both new and duplicate messages  
- Structured **JSON logging** for each request  

### **Messages API (GET /messages)**
- Pagination: `limit`, `offset`
- Filters: `from`, `since`, `q`
- Deterministic ordering: `ts ASC`, `message_id ASC`
- Returns:  
  ```json
  { "data": [...], "total": 0, "limit": 0, "offset": 0 }
  ```

### **Stats (GET /stats)**
Provides:
- `total_messages`
- `senders_count`
- `messages_per_sender` (top 10)
- `first_message_ts`
- `last_message_ts`

### **Health Endpoints**
- `GET /health/live` – always returns 200 once running  
- `GET /health/ready` – checks DB connectivity and `WEBHOOK_SECRET`

### **Metrics (GET /metrics)**
Prometheus-style metrics:
- `http_requests_total`
- `webhook_requests_total`
- Request latency buckets

---

## Project Structure
```
app/
  main.py
  config.py
  models.py
  storage.py
  logging_utils.py
  metrics.py
requirements.txt
Dockerfile
docker-compose.yml
Makefile
README.md
```

---

## Running the Project

### Optional Environment Variables
```
WEBHOOK_SECRET=testsecret
DATABASE_URL=sqlite:////data/app.db
```

### Start the service
```sh
make up
```
or:
```sh
docker compose up -d --build
```

### View logs
```sh
make logs
```

### Stop containers
```sh
make down
```

Service runs at:  
👉 **http://localhost:8000**

---

## Testing Webhook Signature

### Sample Python script:
```python
import hmac, hashlib
secret = "testsecret"
body = b'{"message_id":"m1","from":"+919876543210","to":"+14155550100","ts":"2025-01-15T10:00:00Z","text":"Hello"}'
print(hmac.new(secret.encode(), body, hashlib.sha256).hexdigest())
```

Use the generated hex value as **X-Signature**.

---

## Design Notes (Summary)
- Signature verification uses **raw body bytes** and `hmac.compare_digest`
- Idempotency via **primary key constraint** on `message_id`
- Pagination returns **total count** independent of limit/offset
- Stats computed with **SQL aggregation**
- Metrics stored in **in-memory counters** and exposed in Prometheus format
- Logging middleware outputs **one structured JSON line per request**
