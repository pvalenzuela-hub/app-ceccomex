"use client"

import ReportBuilder, { FilterSpec } from '../components/report-builder'
import { Option } from '../components/searchable-multi-select'

type Importador = { id: number; rut: string; dv: string; nombre: string }

const api = process.env.NEXT_PUBLIC_API_BASE_URL ?? 'http://127.0.0.1:8000'
const importadorOption = (item: Importador): Option => ({ value: String(item.id), label: item.nombre, hint: item.rut ? `${item.rut}-${item.dv}` : 'Sin RUT' })

async function searchImportadores(text: string) {
  const response = await fetch(`${api}/api/reportes/importadores/?q=${encodeURIComponent(text)}`, { credentials: 'include' })
  return response.ok ? (await response.json() as Importador[]).map(importadorOption) : []
}

async function importadorLabels(ids: string[]) {
  const response = await fetch(`${api}/api/reportes/importadores/?ids=${ids.join(',')}`, { credentials: 'include' })
  return response.ok ? Object.fromEntries((await response.json() as Importador[]).map((item) => [String(item.id), item.nombre])) : {}
}

const universe: FilterSpec[] = [
  { type: 'partidas', key: 'partidas' },
  { type: 'remote', key: 'importadores', label: 'Importador', placeholder: 'Nombre o RUT del importador propuesto', search: searchImportadores, labelsFor: importadorLabels },
  { type: 'terms', key: 'marcas', label: 'Marca', placeholder: 'Ej. SAMSUNG — Enter para agregar', help: 'Busca en Mercadería, Marca, Variedad y Otros 1 a 4. Varios términos suman resultados; junto con Producto, deben cumplirse ambos.' },
  { type: 'terms', key: 'productos', label: 'Producto', placeholder: 'Ej. neumáticos — Enter para agregar', help: 'Busca en Mercadería, Marca, Variedad y Otros 1 a 4. Varios términos suman resultados; junto con Marca, deben cumplirse ambos.' },
]

// Out of the universe; existing rubros that use them keep working.
const rubroFilters: FilterSpec[] = [
  { type: 'catalog', key: 'pais_origen_codigo', label: 'País de origen', placeholder: 'Buscar país por nombre o código', catalog: 'PAISES' },
  { type: 'catalog', key: 'pais_adquisicion_codigo', label: 'País de adquisición', placeholder: 'Buscar país por nombre o código', catalog: 'PAISES' },
  { type: 'catalog', key: 'aduana_codigo', label: 'Aduana', placeholder: 'Buscar aduana por nombre o código', catalog: 'ADUANAS' },
  { type: 'catalog', key: 'comuna_importador_codigo', label: 'Comuna importador', placeholder: 'Buscar por nombre o código', catalog: 'COMUNAS' },
  { type: 'catalog', key: 'via_transporte_codigo', label: 'Vía de transporte', placeholder: 'Buscar por nombre o código', catalog: 'VIAS_TRANSPORTE' },
  { type: 'catalog', key: 'regimenes', label: 'Régimen de importación', placeholder: 'Buscar por nombre o código', catalog: 'REGIMENES' },
]

export default function InformesImportacionesPage() {
  return <ReportBuilder kind="importaciones" title="Consulta de Importaciones" lead="Define los datos de salida y limita el universo para ver los resultados en pantalla. Desde ahí puedes filtrar por columna y, si lo necesitas, descargar un Excel." columnSearchPlaceholder="Buscar campo DIN, código o descripción" universe={universe} rubroFilters={rubroFilters} columnFilters />
}
