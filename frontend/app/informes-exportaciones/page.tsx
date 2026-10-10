"use client"

import ReportBuilder, { FilterSpec } from '../components/report-builder'

const universe: FilterSpec[] = [
  { type: 'terms', key: 'productos', label: 'Productos / Marca', placeholder: 'Ej. cerezas o RED GLOBE — Enter para agregar', help: 'Busca en Mercadería y Variedades 1 a 6 del DUS. Varios términos suman resultados.' },
  { type: 'terms', key: 'exportadores', label: 'Exportador', placeholder: 'Nº único del exportador — Enter para agregar', help: 'El DUS identifica al exportador con un número único anónimo (no RUT); lo ves en Consultas Exportaciones.' },
  { type: 'catalog', key: 'pais_destino_codigo', label: 'País de destino', placeholder: 'Buscar país por nombre o código', catalog: 'PAISES' },
  { type: 'catalog', key: 'puerto_embarque_codigo', label: 'Puerto de embarque', placeholder: 'Buscar puerto por nombre o código', catalog: 'PUERTOS' },
  { type: 'catalog', key: 'puerto_desembarque_codigo', label: 'Puerto de desembarque', placeholder: 'Buscar puerto por nombre o código', catalog: 'PUERTOS' },
  { type: 'partidas', key: 'partidas' },
  { type: 'catalog', key: 'aduana_codigo', label: 'Aduana', placeholder: 'Buscar aduana por nombre o código', catalog: 'ADUANAS' },
]

const otherFilters: FilterSpec[] = [
  { type: 'catalog', key: 'via_transporte_codigo', label: 'Vía de transporte', placeholder: 'Buscar por nombre o código', catalog: 'VIAS_TRANSPORTE' },
  { type: 'catalog', key: 'region_origen_codigo', label: 'Región de origen', placeholder: 'Buscar por nombre o código', catalog: 'REGIONES' },
]

export default function InformesExportacionesPage() {
  return <ReportBuilder kind="exportaciones" title="Exportaciones DUS" lead="Una fila por ítem del DUS. Los valores “DUS” (FOB total, flete, seguro, CIF, líquido retorno) se repiten en cada ítem: no los sumes por ítem." columnSearchPlaceholder="Buscar campo DUS, código o descripción" universe={universe} otherFilters={{ summary: 'Otros filtros (vía, región)', filters: otherFilters }} />
}
