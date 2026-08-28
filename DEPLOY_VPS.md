# Despliegue VPS

PostgreSQL se ejecuta directamente en el VPS. Frontend, backend, Celery y Redis se ejecutan en Docker Compose.

## Preparación de PostgreSQL

Ejecutar como `root` en el VPS:

```bash
sudo -u postgres createuser --pwprompt cec_user
sudo -u postgres createdb --owner=cec_user cec_comex
```

Para permitir acceso desde la red Docker, agregar una regla restringida en `pg_hba.conf`:

```text
host    cec_comex    cec_user    172.17.0.0/16    scram-sha-256
```

Configurar `listen_addresses` para incluir `172.17.0.1`, reiniciar PostgreSQL y verificar:

```bash
sudo systemctl restart postgresql
sudo -u postgres psql -d cec_comex -c "select current_database();"
```

## Compose

```bash
cd /srv/app-ceccomex
cp .env.production.example .env
chmod 600 .env
docker compose build
docker compose run --rm backend python manage.py migrate
docker compose up -d
docker compose ps
```

El archivo `.env` no se versiona. Antes de construir el frontend, confirmar que `NEXT_PUBLIC_API_BASE_URL` tenga la URL pública correcta.
