# Importaciones Access, enero-junio 2015

El comando `import_legacy_mdb` lee el ZIP con las seis bases Jet 3
`IM201501.mdb` ... `IM201506.mdb`. Usa `mdb-export` instalado en la imagen
del backend. Extrae **solo un MDB a la vez** en un directorio temporal y
procesa el CSV por lotes; no crea registros de staging ni una copia CSV.

```bash
docker compose exec backend python manage.py import_legacy_mdb \
  /app/cargas/wetransfer_im201501-mdb_2026-09-25_1838.zip \
  --validate-only --temp-dir /app/cargas

# Tras respaldar PostgreSQL, cargar y conciliar mes a mes:
docker compose exec backend python manage.py import_legacy_mdb \
  /app/cargas/wetransfer_im201501-mdb_2026-09-25_1838.zip \
  --month 1 --temp-dir /app/cargas
```

La carga exige 274536, 262511, 306900, 280979, 264342 y 319103 filas,
respectivamente. Comprueba período, fecha, partida, valores por ítem y claves
`NUM_IDEN` + `NUM_ITEM` sin duplicados dentro de cada mes. Un error revierte
íntegramente el mes mediante una transacción. Si ya está procesado y su conteo
coincide, repetir el comando omite ese mes. No reemplaza cargas diferentes
existentes del mismo período.

`Importacion.valor_*` guarda los importes **por ítem**; los totales y las
141 columnas originales están bajo `payload_json.legacy_fields`. Los datos
MDB no se almacenan como `raw_columns` del TXT moderno. `fecha_text` usa
`YYYY-MM-DD`, `fecha_date` es la fecha de aceptación (`FEC_ACE`), y
`comuna_importador_codigo` queda vacío porque el MDB no la proporciona.
Cuando falta `DV`, se conserva el registro sin asociarlo automáticamente a
un `ImportadorProbable`.

## Completar catálogo con los meses ya cargados

```bash
docker compose exec backend python manage.py sync_importadores_mdb_2015 --dry-run
docker compose exec backend python manage.py sync_importadores_mdb_2015
```

El comando toma RUT, DV y el nombre original `IMPORT` de las importaciones
MDB almacenadas. Valida el dígito verificador; solo crea entradas
`origen=MDB_2015` si la clave aún no existe y los seis meses coinciden en
**un único nombre** para esa clave (ignorando mayúsculas y espacios repetidos).
Normaliza en mayúsculas el nombre del catálogo; no cambia nombres de entradas
previas ni el nombre original guardado en cada fila.
Las claves con distintos nombres, DV ausente o RUT inválido no producen
entradas nuevas. Finalmente asocia por RUT+DV los registros aún sin vínculo,
mes a mes. Puede repetirse: no duplica entradas ni sobrescribe vínculos.

El ZIP debe estar en el volumen Docker compartido `/app/cargas` para que
`ArchivoCarga.archivo` apunte al original. Se necesita espacio adicional
para el MDB más grande (403 MB) durante cada mes.
