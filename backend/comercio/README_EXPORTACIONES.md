# Exportaciones DUS (TXT mensuales de Aduana)

Cada mes trae tres TXT separados por `;`, según
`doc-req/export/descripcion-y-estructura-de-datos- dus.xlsx`:

| Archivo | Tipo | Columnas | Modelo |
|---|---|---|---|
| `Exportaciones <mes> <año>.txt` | `EXP_BASE` | 84 (DUS + ítem) | `Exportacion` (una fila por ítem) |
| `... – Bultos.txt` | `EXP_BULTO` | 6 | `ExportacionBulto` |
| `... – Documentos de Transporte.txt` | `EXP_DOC` | 7 | `ExportacionDocTransporte` |

```bash
# Validar sin escribir (uno o más ZIP; cada ZIP puede traer 1 a 3 TXT):
docker compose exec backend python manage.py import_exportaciones \
  /app/cargas/exportaciones-marzo2026.zip --validate-only

# Tras respaldar PostgreSQL, cargar:
docker compose exec backend python manage.py import_exportaciones \
  /app/cargas/exportaciones-marzo2026.zip
```

- El período se toma de `FECHAACEPT`; toda fila de otro mes, fecha o monto
  inválido, o clave duplicada (`NUMEROIDENT`+`NUMEROITEM`, o +secuencia en
  bultos/documentos) revierte el archivo completo.
- Lee por streaming y separa solo por LF: algunos campos traen `\r` o TAB
  sueltos. Codificación Latin-1.
- Aduana corta algunas líneas de ancho fijo (p. ej. 18 ítems de enero 2025
  terminan en `NOMBRE`; algunos documentos sin `NUMEROVIAJE`). Se cargan con
  `registro_incompleto=True`.
- Montos con coma decimal se guardan con punto. Los campos `*_dus`
  (FOB total, flete, seguro, CIF, valor líquido retorno) son totales del DUS
  repetidos en cada ítem: **no sumarlos por ítem**; usar `valor_fob` (FOBUS).
- `exportador_codigo` es el `NRO_EXPORTADOR` correlativo anónimo, no un RUT.
- Las 84 columnas originales no vacías quedan en `payload_json.dus_fields`.
- Repetir el mismo archivo lo omite; si ya hay otros datos del mismo tipo y
  período exige `--replace`.

La subida web (`/api/comercio/upload/`) usa el mismo cargador: carga el TXT
del ZIP que corresponde al tipo elegido (Base, Bultos o Documentos).

## Consultas e informes

Requieren sesión iniciada.

- `GET /api/consultas/exportaciones/` — búsqueda paginada (Nº DUS, exportador,
  año/meses, aduana, país destino, puerto embarque, arancel o su glosa,
  mercadería, fechas); `.../exportar/` descarga el mismo filtro en Excel y
  `.../dus/<numero>/` devuelve ítems, bultos y documentos de un DUS.
  Página: `/consultas-exportaciones`.
- `GET /api/reportes/exportaciones/configuracion/` y
  `POST /api/reportes/exportaciones/exportar/` — constructor de informes por
  mes: columnas con glosas de catálogo, las 84 columnas DUS, totales de bultos
  y naves por DUS. Página: `/informes-exportaciones`. Los Excel se escriben con
  XlsxWriter (un mes completo ≈ 40 s) y los montos van como números.
