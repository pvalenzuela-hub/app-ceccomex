"use client"

import ReportBuilder, { FilterSpec } from '../components/report-builder'
import { Option } from '../components/searchable-multi-select'

type Importador = { id: number; rut: string; dv: string; nombre: string }

const api = process.env.NEXT_PUBLIC_API_BASE_URL ?? 'http://127.0.0.1:8000'
const importadorOption = (item: Importador): Option => ({ value: String(item.id), label: item.nombre, hint: item.rut ? `${item.rut}-${item.dv}` : 'Sin RUT' })

async function searchImportadores(text: string) {
  const response = await fetch(`${api}/api/reportes/importadores/?q=${encodeURIComponent(text)}`)
  return response.ok ? (await response.json() as Importador[]).map(importadorOption) : []
}

async function importadorLabels(ids: string[]) {
  const response = await fetch(`${api}/api/reportes/importadores/?ids=${ids.join(',')}`)
  return response.ok ? Object.fromEntries((await response.json() as Importador[]).map((item) => [String(item.id), item.nombre])) : {}
}

const universe: FilterSpec[] = [
  { type: 'terms', key: 'productos', label: 'Productos / Marca', placeholder: 'Ej. SAMSUNG o neumáticos — Enter para agregar', help: 'Busca en Mercadería, Marca, Variedad y Otros 1 a 4. Varios términos suman resultados.' },
  { type: 'remote', key: 'importadores', label: 'Importador', placeholder: 'Nombre o RUT del importador propuesto', search: searchImportadores, labelsFor: importadorLabels },
  { type: 'catalog', key: 'pais_origen_codigo', label: 'País de origen', placeholder: 'Buscar país por nombre o código', catalog: 'PAISES' },
  { type: 'catalog', key: 'pais_adquisicion_codigo', label: 'País de adquisición', placeholder: 'Buscar país por nombre o código', catalog: 'PAISES' },
  { type: 'partidas', key: 'partidas' },
  { type: 'catalog', key: 'aduana_codigo', label: 'Aduana', placeholder: 'Buscar aduana por nombre o código', catalog: 'ADUANAS' },
]

// Filters beyond the main universe; kept so existing rubros keep working.
const otherFilters: FilterSpec[] = [
  { type: 'catalog', key: 'comuna_importador_codigo', label: 'Comuna importador', placeholder: 'Buscar por nombre o código', catalog: 'COMUNAS' },
  { type: 'catalog', key: 'via_transporte_codigo', label: 'Vía de transporte', placeholder: 'Buscar por nombre o código', catalog: 'VIAS_TRANSPORTE' },
  { type: 'catalog', key: 'regimenes', label: 'Régimen de importación', placeholder: 'Buscar por nombre o código', catalog: 'REGIMENES' },
]

export default function InformesImportacionesPage() {
  return <ReportBuilder kind="importaciones" title="Importaciones DIN" lead="Define los datos de salida y limita el universo antes de generar tu archivo Excel." columnSearchPlaceholder="Buscar campo DIN, código o descripción" universe={universe} otherFilters={{ summary: 'Otros filtros (comuna, vía, régimen)', filters: otherFilters }} />
}
