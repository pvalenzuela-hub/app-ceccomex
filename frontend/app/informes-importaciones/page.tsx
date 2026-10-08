"use client"

import { useCallback, useEffect, useState } from 'react'
import SearchableMultiSelect, { Option } from '../components/searchable-multi-select'
import TopNav from '../components/top-nav'

type Column = { key: string; label: string; default: boolean }
type Catalog = { codigo: string; glosa: string }
type Filters = Record<string, string[]>
type Periodo = { anio: number; mes: number }
type Rango = { desde: Periodo; hasta: Periodo }
type Rubro = { id: number; nombre: string; configuracion_json: { columnas?: string[]; filtros?: Filters; periodo?: Rango } }
type Informe = { id: number; estado: 'PENDIENTE' | 'PROCESANDO' | 'LISTO' | 'ERROR'; filas_total: number; filas_procesadas: number; error: string; nombre_descarga: string }

const MONTHS = Array.from({ length: 12 }, (_, index) => new Date(2026, index).toLocaleString('es-CL', { month: 'long' }))
const periodKey = (periodo: Periodo) => periodo.anio * 100 + periodo.mes
const periodLabel = (periodo: Periodo) => `${MONTHS[periodo.mes - 1]} ${periodo.anio}`
const sleep = (ms: number) => new Promise((resolve) => window.setTimeout(resolve, ms))

function csrfToken() {
  return document.cookie.split('; ').find((cookie) => cookie.startsWith('csrftoken='))?.split('=')[1] ?? ''
}

type Importador = { id: number; rut: string; dv: string; nombre: string }

// Filters beyond the main universe; kept so existing rubros keep working.
const otherCatalogFields = [
  ['comuna_importador_codigo', 'Comuna importador', 'COMUNAS'], ['via_transporte_codigo', 'Vía de transporte', 'VIAS_TRANSPORTE'],
  ['regimenes', 'Régimen de importación', 'REGIMENES'],
] as const

const toOptions = (items: Catalog[] = []): Option[] => items.map((item) => ({ value: item.codigo, label: item.glosa }))
const importadorOption = (item: Importador): Option => ({ value: String(item.id), label: item.nombre, hint: item.rut ? `${item.rut}-${item.dv}` : 'Sin RUT' })

export default function InformesImportacionesPage() {
  const api = process.env.NEXT_PUBLIC_API_BASE_URL ?? 'http://127.0.0.1:8000'
  const [columns, setColumns] = useState<Column[]>([])
  const [selected, setSelected] = useState<string[]>([])
  const [catalogs, setCatalogs] = useState<Record<string, Catalog[]>>({})
  const [filters, setFilters] = useState<Filters>({})
  const [partidaText, setPartidaText] = useState('')
  const [partidas, setPartidas] = useState<Catalog[]>([])
  const [rubros, setRubros] = useState<Rubro[]>([])
  const [rubroName, setRubroName] = useState('')
  const [editing, setEditing] = useState<Rubro | null>(null)
  const [showRubroDialog, setShowRubroDialog] = useState(false)
  const [periodos, setPeriodos] = useState<Periodo[]>([])
  const [rango, setRango] = useState<Rango>(() => { const now = { anio: new Date().getFullYear(), mes: new Date().getMonth() + 1 }; return { desde: now, hasta: now } })
  const [progress, setProgress] = useState('')
  const [message, setMessage] = useState('')
  const [generating, setGenerating] = useState(false)
  const [columnSearch, setColumnSearch] = useState('')
  const [productText, setProductText] = useState('')
  const [importadorLabels, setImportadorLabels] = useState<Record<string, string>>({})

  async function loadRubros() {
    const response = await fetch(`${api}/api/reportes/importaciones/rubros/`)
    if (response.ok) setRubros(await response.json())
  }

  useEffect(() => {
    void fetch(`${api}/api/health/`, { credentials: 'include' })
    void (async () => {
      const response = await fetch(`${api}/api/reportes/importaciones/configuracion/`)
      if (!response.ok) return setMessage('No se pudo cargar la configuración.')
      const data = await response.json()
      setColumns(data.columnas)
      setSelected(data.columnas.filter((column: Column) => column.default).map((column: Column) => column.key))
      setCatalogs(data.catalogos)
      setPeriodos(data.periodos ?? [])
      if (data.periodos?.length) setRango({ desde: data.periodos[0], hasta: data.periodos[0] })
    })()
    void loadRubros()
  }, [])

  function setFilter(name: string, values: string[]) { setFilters({ ...filters, [name]: values }) }
  function toggleColumn(key: string) { setSelected(selected.includes(key) ? selected.filter((item) => item !== key) : [...selected, key]) }
  const searchImportadores = useCallback(async (text: string) => {
    const response = await fetch(`${api}/api/reportes/importadores/?q=${encodeURIComponent(text)}`)
    return response.ok ? (await response.json() as Importador[]).map(importadorOption) : []
  }, [api])

  function addProduct() {
    const term = productText.trim()
    if (term && !(filters.productos ?? []).some((item) => item.toLowerCase() === term.toLowerCase())) setFilter('productos', [...(filters.productos ?? []), term])
    setProductText('')
  }

  function recover(rubro: Rubro) {
    setSelected(rubro.configuracion_json.columnas ?? [])
    setFilters(rubro.configuracion_json.filtros ?? {})
    if (rubro.configuracion_json.periodo) setRango(rubro.configuracion_json.periodo)
    const ids = rubro.configuracion_json.filtros?.importadores ?? []
    if (ids.length) void fetch(`${api}/api/reportes/importadores/?ids=${ids.join(',')}`).then(async (response) => {
      if (response.ok) setImportadorLabels(Object.fromEntries((await response.json() as Importador[]).map((item) => [String(item.id), item.nombre])))
    })
    setEditing(rubro)
    setMessage(`Rubro "${rubro.nombre}" recuperado.`)
  }

  async function searchPartidas(value: string) {
    setPartidaText(value)
    if (value.trim().length < 2) return setPartidas([])
    const response = await fetch(`${api}/api/reportes/importaciones/partidas/?q=${encodeURIComponent(value)}`)
    if (response.ok) setPartidas(await response.json())
  }

  async function saveRubro() {
    if (!rubroName.trim()) return setMessage('Indique un nombre para el rubro.')
    await fetch(`${api}/api/health/`, { credentials: 'include' })
    const body = { nombre: rubroName.trim(), configuracion_json: { columnas: selected, filtros: filters, periodo: rango } }
    const url = editing ? `${api}/api/reportes/importaciones/rubros/${editing.id}/` : `${api}/api/reportes/importaciones/rubros/`
    const response = await fetch(url, { method: editing ? 'PUT' : 'POST', credentials: 'include', headers: { 'Content-Type': 'application/json', 'X-CSRFToken': csrfToken() }, body: JSON.stringify(body) })
    if (!response.ok) return setMessage(`No se pudo guardar el rubro (${response.status}).`)
    setShowRubroDialog(false); setRubroName(''); setEditing(null); await loadRubros(); setMessage('Rubro guardado.')
  }

  async function deleteRubro(rubro: Rubro) {
    if (!window.confirm(`¿Eliminar el rubro "${rubro.nombre}"?`)) return
    const response = await fetch(`${api}/api/reportes/importaciones/rubros/${rubro.id}/`, { method: 'DELETE', credentials: 'include', headers: { 'X-CSRFToken': csrfToken() } })
    if (response.ok) { await loadRubros(); setMessage('Rubro eliminado.') }
  }

  function setRangoPart(part: 'desde' | 'hasta', field: 'anio' | 'mes', value: string) {
    setRango({ ...rango, [part]: { ...rango[part], [field]: Number(value) } })
  }

  async function execute() {
    if (periodKey(rango.desde) > periodKey(rango.hasta)) return setMessage('El período desde no puede ser posterior al período hasta.')
    setGenerating(true); setMessage(''); setProgress('Enviando solicitud...')
    try {
      await fetch(`${api}/api/health/`, { credentials: 'include' })
      // Keep the catalog order of columns.
      const columnas = columns.map((column) => column.key).filter((key) => selected.includes(key))
      const response = await fetch(`${api}/api/reportes/importaciones/exportar/`, { method: 'POST', credentials: 'include', headers: { 'Content-Type': 'application/json', 'X-CSRFToken': csrfToken() }, body: JSON.stringify({ columnas, filtros: filters, periodo_desde: rango.desde, periodo_hasta: rango.hasta }) })
      if (!response.ok) return setMessage((await response.json().catch(() => null))?.detail ?? `No se pudo generar el Excel (${response.status}).`)
      let informe: Informe = await response.json()
      // Large ranges are generated by the background worker; poll until the file is ready.
      while (informe.estado === 'PENDIENTE' || informe.estado === 'PROCESANDO') {
        setProgress(informe.estado === 'PENDIENTE' ? 'En cola...' : `Procesando ${informe.filas_procesadas.toLocaleString('es-CL')} de ${informe.filas_total.toLocaleString('es-CL')} filas...`)
        await sleep(2500)
        const status = await fetch(`${api}/api/reportes/informes/${informe.id}/`, { credentials: 'include', cache: 'no-store' })
        if (!status.ok) return setMessage(`No se pudo consultar el avance (${status.status}).`)
        informe = await status.json()
      }
      if (informe.estado === 'ERROR') return setMessage(informe.error || 'No se pudo generar el informe.')
      setProgress('Descargando archivo...')
      const file = await fetch(`${api}/api/reportes/informes/${informe.id}/descargar/`, { credentials: 'include' })
      if (!file.ok) return setMessage(`No se pudo descargar el informe (${file.status}).`)
      const url = URL.createObjectURL(await file.blob())
      const link = document.createElement('a'); link.href = url; link.download = informe.nombre_descarga; link.click(); URL.revokeObjectURL(url)
      setMessage(`Informe generado y descargado: ${informe.filas_total.toLocaleString('es-CL')} filas (${periodLabel(rango.desde)} a ${periodLabel(rango.hasta)}).`)
    } finally { setGenerating(false); setProgress('') }
  }

  // Every year from the first loaded month to the current year, so ranges can include months not loaded yet.
  const knownYears = [...periodos.map((item) => item.anio), rango.desde.anio, rango.hasta.anio, new Date().getFullYear()]
  const years = Array.from({ length: Math.max(...knownYears) - Math.min(...knownYears) + 1 }, (_, index) => Math.max(...knownYears) - index)
  const periodSelect = (part: 'desde' | 'hasta', label: string) => <div className="period-field"><span>{label}</span><div><select disabled={generating} value={rango[part].mes} onChange={(event) => setRangoPart(part, 'mes', event.target.value)}>{MONTHS.map((month, index) => <option key={month} value={index + 1}>{month}</option>)}</select><select disabled={generating} value={rango[part].anio} onChange={(event) => setRangoPart(part, 'anio', event.target.value)}>{years.map((year) => <option key={year} value={year}>{year}</option>)}</select></div></div>

  const visibleColumns = columns.filter((column) => column.label.toLowerCase().includes(columnSearch.toLowerCase()) || column.key.toLowerCase().includes(columnSearch.toLowerCase()))

  return <main className="page dashboard-page report-page">
    <TopNav />
    <section className="report-heading"><div><p className="eyebrow">Constructor de informes</p><h1>Importaciones DIN</h1><p className="lead">Define los datos de salida y limita el universo antes de generar tu archivo Excel.</p></div><div className="report-selection-summary"><strong>{selected.length}</strong><span>columnas<br />seleccionadas</span></div></section>
    <section className="panel report-rubros"><div><p className="eyebrow">Configuraciones</p><h2>Rubros guardados</h2></div><select defaultValue="" onChange={(event) => { const rubro = rubros.find((item) => item.id === Number(event.target.value)); if (rubro) recover(rubro) }}><option value="">Seleccionar una configuración</option>{rubros.map((rubro) => <option key={rubro.id} value={rubro.id}>{rubro.nombre}</option>)}</select><button type="button" onClick={() => { setEditing(null); setRubroName(''); setShowRubroDialog(true) }}>Crear rubro</button>{editing ? <button type="button" onClick={() => { setRubroName(editing.nombre); setShowRubroDialog(true) }}>Actualizar</button> : null}{editing ? <button type="button" className="link-button" onClick={() => deleteRubro(editing)}>Eliminar</button> : null}</section>
    {message ? <p className="login-message">{message}</p> : null}
    <section className="report-layout report-workspace">
      <section className="panel report-columns-panel"><header><div><span className="report-step">01</span><p className="eyebrow">Salida del archivo</p><h2>Columnas a exportar</h2></div><button type="button" className="link-button" onClick={() => setSelected([])}>Limpiar selección</button></header><div className="column-search"><input value={columnSearch} onChange={(event) => setColumnSearch(event.target.value)} placeholder="Buscar campo DIN, código o descripción" /><span>{visibleColumns.length} disponibles</span></div><div className="column-picker">{visibleColumns.map((column) => <label key={column.key} className={selected.includes(column.key) ? 'is-selected' : ''}><input type="checkbox" checked={selected.includes(column.key)} onChange={() => toggleColumn(column.key)} /><span>{column.label}</span></label>)}</div></section>
      <section className="panel report-filters-panel"><header><div><span className="report-step">02</span><p className="eyebrow">Universo de datos</p><h2>Filtros y aranceles</h2></div><p>Opcionales</p></header><div className="report-period">{periodSelect('desde', 'Desde (mes - año)')}{periodSelect('hasta', 'Hasta (mes - año)')}<small>{periodos.length ? `Meses cargados: ${periodos.map(periodLabel).join(', ')}` : ''}</small></div><div className="report-filters report-universe">
        <div className="searchable-select product-terms"><label className="tariff-search"><span>Productos / Marca{(filters.productos ?? []).length ? ` (${(filters.productos ?? []).length})` : ''}</span><div className="term-input"><input value={productText} onChange={(event) => setProductText(event.target.value)} onKeyDown={(event) => { if (event.key === 'Enter') { event.preventDefault(); addProduct() } }} placeholder="Ej. SAMSUNG o neumáticos — Enter para agregar" /><button type="button" onClick={addProduct}>Agregar</button></div><small>Busca en Mercadería, Marca, Variedad y Otros 1 a 4. Varios términos suman resultados.</small></label>{(filters.productos ?? []).length ? <div className="selected-values">{(filters.productos ?? []).map((term) => <button key={term} type="button" onClick={() => setFilter('productos', (filters.productos ?? []).filter((item) => item !== term))}>{term} ×</button>)}</div> : null}</div>
        <SearchableMultiSelect label="Importador" placeholder="Nombre o RUT del importador propuesto" selected={filters.importadores ?? []} onChange={(values) => setFilter('importadores', values)} search={searchImportadores} selectedLabels={importadorLabels} />
        <SearchableMultiSelect label="País de origen" placeholder="Buscar país por nombre o código" selected={filters.pais_origen_codigo ?? []} onChange={(values) => setFilter('pais_origen_codigo', values)} options={toOptions(catalogs.PAISES)} />
        <SearchableMultiSelect label="País de adquisición" placeholder="Buscar país por nombre o código" selected={filters.pais_adquisicion_codigo ?? []} onChange={(values) => setFilter('pais_adquisicion_codigo', values)} options={toOptions(catalogs.PAISES)} />
        <div className="searchable-select"><label className="tariff-search"><span>Arancel por código o glosa{(filters.partidas ?? []).length ? ` (${(filters.partidas ?? []).length})` : ''}</span><input value={partidaText} onChange={(event) => void searchPartidas(event.target.value)} placeholder="Ej. 8528 o motocicletas" />{partidas.length ? <div className="tariff-options tariff-options-multi">{partidas.map((partida) => { const selectedPartida = (filters.partidas ?? []).includes(partida.codigo); return <button key={partida.codigo} type="button" onClick={() => setFilter('partidas', selectedPartida ? (filters.partidas ?? []).filter((item) => item !== partida.codigo) : [...(filters.partidas ?? []), partida.codigo])}><input type="checkbox" checked={selectedPartida} readOnly /><strong>{partida.codigo}</strong><span>{partida.glosa}</span></button> })}</div> : null}</label>{(filters.partidas ?? []).length ? <div className="selected-values">{(filters.partidas ?? []).map((codigo) => <button key={codigo} type="button" onClick={() => setFilter('partidas', (filters.partidas ?? []).filter((item) => item !== codigo))}>{codigo} ×</button>)}</div> : null}</div>
        <SearchableMultiSelect label="Aduana" placeholder="Buscar aduana por nombre o código" selected={filters.aduana_codigo ?? []} onChange={(values) => setFilter('aduana_codigo', values)} options={toOptions(catalogs.ADUANAS)} />
      </div>
      <details className="report-other-filters"><summary>Otros filtros (comuna, vía, régimen)</summary><div className="report-filters">{otherCatalogFields.map(([key, label, group]) => <SearchableMultiSelect key={key} label={label} placeholder="Buscar por nombre o código" selected={filters[key] ?? []} onChange={(values) => setFilter(key, values)} options={toOptions(catalogs[group])} />)}</div></details><footer><div><span className="report-step">03</span><strong>Generar archivo</strong><p>{generating ? progress : `${periodLabel(rango.desde)} a ${periodLabel(rango.hasta)}. Se guarda con el rubro.`}</p></div><button type="button" className="report-run" disabled={!selected.length || generating} onClick={() => void execute()}>{generating ? 'Generando informe...' : 'Generar Excel'}</button></footer></section>
    </section>
    {showRubroDialog ? <div className="modal-backdrop"><section className="modal"><h2>{editing ? 'Actualizar rubro' : 'Crear rubro'}</h2><label>Nombre<input value={rubroName} onChange={(event) => setRubroName(event.target.value)} autoFocus /></label><div><button type="button" onClick={saveRubro}>Guardar</button><button type="button" className="link-button" onClick={() => setShowRubroDialog(false)}>Cancelar</button></div></section></div> : null}
  </main>
}
