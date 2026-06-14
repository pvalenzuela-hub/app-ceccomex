# Desarrollo local

## Redis

Levantar Redis con Docker:

```bash
docker run --name cec-comex-redis -p 6379:6379 -d redis:7-alpine
```

Si no tienes Docker ni Redis instalado, usa modo eager:

```bash
export CELERY_TASK_ALWAYS_EAGER=1
export CELERY_BROKER_URL=memory://
```

## Celery worker

```bash
cd backend
CELERY_BROKER_URL=redis://127.0.0.1:6379/0 ./.venv/bin/celery -A config worker -l info
```

## Django

```bash
cd backend
./.venv/bin/python manage.py runserver 0.0.0.0:8000
```
