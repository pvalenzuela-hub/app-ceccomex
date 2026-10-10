from django.db import migrations

INDEXES = (
    ("imp_texto_producto_trgm", "comercio_importacion"),
    ("exp_texto_producto_trgm", "comercio_exportacion"),
)


def create_indexes(apps, schema_editor):
    # PostgreSQL only (tests run on SQLite). Run after `rellenar_texto_producto`: building the GIN index
    # once over filled rows is much faster than maintaining it during the backfill.
    if schema_editor.connection.vendor != "postgresql":
        return
    for name, table in INDEXES:
        schema_editor.execute(f"CREATE INDEX CONCURRENTLY IF NOT EXISTS {name} ON {table} USING gin (texto_producto gin_trgm_ops)")


def drop_indexes(apps, schema_editor):
    if schema_editor.connection.vendor != "postgresql":
        return
    for name, _ in INDEXES:
        schema_editor.execute(f"DROP INDEX CONCURRENTLY IF EXISTS {name}")


class Migration(migrations.Migration):
    atomic = False  # CREATE INDEX CONCURRENTLY cannot run inside a transaction.

    dependencies = [("comercio", "0009_texto_producto")]

    operations = [migrations.RunPython(create_indexes, drop_indexes)]
