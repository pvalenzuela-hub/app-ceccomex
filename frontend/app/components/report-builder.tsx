"use client"

import { useEffect, useRef, useState } from 'react'
import SearchableMultiSelect, { Option } from './searchable-multi-select'
import TopNav from './top-nav'

type Column = { key: string; label: string; default: boolean }
type Catalog = { codigo: string; glosa: string }
type Filters = Record<string, string[]>
type Periodo = { anio: number; mes: number }
type Rango = { desde: Periodo; hasta: Periodo }
type Rubro = { id: number; nombre: string; configuracion_json: { columnas?: string[]; filtros?: Filters; periodo?: Rango } }
type Totales = { cif_usd: number; fob_usd: number; cantidad: number; cantidades_por_unidad: { unidad: string; glosa: string; cantidad: number }[]; documentos: number; documentos_con_cif?: number }
type VistaPrevia = { columnas: { key: string; label: string }[]; filas: (string | number)[][]; pagina: number; paginas: number; por_pagina: number; registros: number; totales: Totales | null; totales_omitidos: boolean }
type Solicitud = { columnas: string[]; filtros: Filters; periodo_desde: Periodo; periodo_hasta: Periodo }
type Informe = { id: number; estado: 'PENDIENTE' | 'PROCESANDO' | 'LISTO' | 'ERROR'; filas_total: number; filas_procesadas: number; error: string; nombre_descarga: string }

/** One filter of the "Universo de datos" panel; `key` is the name sent in `filtros`. */
export type FilterSpec =
  | { type: 'terms'; key: string; label: string; placeholder: string; help: string }
  | { type: 'catalog'; key: string; label: string; placeholder: string; catalog: string }
  | { type: 'remote'; key: string; label: string; placeholder: string; search: (text: string) => Promise<Option[]>; labelsFor: (ids: string[]) => Promise<Record<string, string>> }
  | { type: 'partidas'; key: 'partidas' }

export type ReportBuilderProps = {
  /** API segment: /api/reportes/<kind>/{configuracion,rubros,vista-previa,exportar}/ */
  kind: 'importaciones' | 'exportaciones'
  title: string
  lead: string
  columnSearchPlaceholder: string
  universe: FilterSpec[]
  /** Filters outside the universe: only shown when a saved rubro uses them, so they can be seen and removed. */
  rubroFilters: FilterSpec[]
  /** Text filter on every column of the results. */
  columnFilters?: boolean
}

const MONTHS = Array.from({ length: 12 }, (_, index) => new Date(2026, index).toLocaleString('es-CL', { month: 'long' }))
const periodKey = (periodo: Periodo) => periodo.anio * 100 + periodo.mes
const periodLabel = (periodo: Periodo) => `${MONTHS[periodo.mes - 1]} ${periodo.anio}`
const sleep = (ms: number) => new Promise((resolve) => window.setTimeout(resolve, ms))
const usd = (value: number) => `US$ ${value.toLocaleString('es-CL', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`
const count = (value: number) => value.toLocaleString('es-CL')
const PAGE_SIZES = [10, 25, 50, 100, 200]
const cell = (value: string | number) => typeof value === 'number' ? value.toLocaleString('es-CL', { useGrouping: false, maximumFractionDigits: 6 }) : value
const toOptions = (items: Catalog[] = []): Option[] => items.map((item) => ({ value: item.codigo, label: item.glosa }))

function csrfToken() {
  return document.cookie.split('; ').find((cookie) => cookie.startsWith('csrftoken='))?.split('=')[1] ?? ''
}

function TermsFilter({ spec, values, onChange }: { spec: Extract<FilterSpec, { type: 'terms' }>; values: string[]; onChange: (values: string[]) => void }) {
  const [text, setText] = useState('')
  function add() {
    const term = text.trim()
    if (term && !values.some((item) => item.toLowerCase() === term.toLowerCase())) onChange([...values, term])
    setText('')
  }
  return <div className="searchable-select product-terms"><label className="tariff-search"><span>{spec.label}{values.length ? ` (${values.length})` : ''}</span><div className="term-input"><input value={text} onChange={(event) => setText(event.target.value)} onKeyDown={(event) => { if (event.key === 'Enter') { event.preventDefault(); add() } }} placeholder={spec.placeholder} /><button type="button" onClick={add}>Agregar</button></div><small>{spec.help}</small></label>{values.length ? <div className="selected-values">{values.map((term) => <button key={term} type="button" onClick={() => onChange(values.filter((item) => item !== term))}>{term} ×</button>)}</div> : null}</div>
}

export default function ReportBuilder({ kind, title, lead, columnSearchPlaceholder, universe, rubroFilters, columnFilters = false }: ReportBuilderProps) {
  const api = process.env.NEXT_PUBLIC_API_BASE_URL ?? 'http://127.0.0.1:8000'
  const base = `${api}/api/reportes/${kind}`
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
  const [remoteLabels, setRemoteLabels] = useState<Record<string, Record<string, string>>>({})
  const [preview, setPreview] = useState<VistaPrevia | null>(null)
  const [solicitud, setSolicitud] = useState<Solicitud | null>(null)
  const [loadingPreview, setLoadingPreview] = useState(false)
  const [pageSize, setPageSize] = useState(PAGE_SIZES[0])
  const [columnDrafts, setColumnDrafts] = useState<Record<string, string>>({})
  const [appliedColumnFilters, setAppliedColumnFilters] = useState<Record<string, string>>({})
  const previewRun = useRef(0)

  async function loadRubros() {
    const response = await fetch(`${base}/rubros/`, { credentials: 'include' })
    if (response.ok) setRubros(await response.json())
  }

  useEffect(() => {
    void fetch(`${api}/api/health/`, { credentials: 'include' })
    void (async () => {
      const response = await fetch(`${base}/configuracion/`, { credentials: 'include' })
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

  function closePreview() {
    previewRun.current += 1
    setPreview(null); setSolicitud(null); setLoadingPreview(false); setColumnDrafts({}); setAppliedColumnFilters({})
  }

  // The Excel must match what is on screen: changing the query discards the results and any response in flight.
  useEffect(closePreview, [selected, filters, rango])

  function setFilter(name: string, values: string[]) { setFilters({ ...filters, [name]: values }) }
  function toggleColumn(key: string) { setSelected(selected.includes(key) ? selected.filter((item) => item !== key) : [...selected, key]) }

  function recover(rubro: Rubro) {
    const saved = rubro.configuracion_json.filtros ?? {}
    setSelected(rubro.configuracion_json.columnas ?? [])
    setFilters(saved)
    if (rubro.configuracion_json.periodo) setRango(rubro.configuracion_json.periodo)
    for (const spec of [...universe, ...rubroFilters]) {
      const ids = saved[spec.key] ?? []
      if (spec.type === 'remote' && ids.length) void spec.labelsFor(ids).then((labels) => setRemoteLabels((current) => ({ ...current, [spec.key]: labels })))
    }
    setEditing(rubro)
    setMessage(`Rubro "${rubro.nombre}" recuperado.`)
  }

  async function searchPartidas(value: string) {
    setPartidaText(value)
    if (value.trim().length < 2) return setPartidas([])
    const response = await fetch(`${api}/api/reportes/importaciones/partidas/?q=${encodeURIComponent(value)}`, { credentials: 'include' })
    if (response.ok) setPartidas(await response.json())
  }

  async function saveRubro() {
    if (!rubroName.trim()) return setMessage('Indique un nombre para el rubro.')
    await fetch(`${api}/api/health/`, { credentials: 'include' })
    const body = { nombre: rubroName.trim(), configuracion_json: { columnas: selected, filtros: filters, periodo: rango } }
    const url = editing ? `${base}/rubros/${editing.id}/` : `${base}/rubros/`
    const response = await fetch(url, { method: editing ? 'PUT' : 'POST', credentials: 'include', headers: { 'Content-Type': 'application/json', 'X-CSRFToken': csrfToken() }, body: JSON.stringify(body) })
    if (!response.ok) return setMessage((await response.json().catch(() => null))?.nombre?.[0] ?? `No se pudo guardar el rubro (${response.status}).`)
    setShowRubroDialog(false); setRubroName(''); setEditing(null); await loadRubros(); setMessage('Rubro guardado.')
  }

  async function deleteRubro(rubro: Rubro) {
    if (!window.confirm(`¿Eliminar el rubro "${rubro.nombre}"?`)) return
    const response = await fetch(`${base}/rubros/${rubro.id}/`, { method: 'DELETE', credentials: 'include', headers: { 'X-CSRFToken': csrfToken() } })
    if (response.ok) { await loadRubros(); setMessage('Rubro eliminado.') }
  }

  function setRangoPart(part: 'desde' | 'hasta', field: 'anio' | 'mes', value: string) {
    setRango({ ...rango, [part]: { ...rango[part], [field]: Number(value) } })
  }

  async function loadPreview(pagina: number, porPagina = pageSize, filtrosColumnas = appliedColumnFilters) {
    if (periodKey(rango.desde) > periodKey(rango.hasta)) return setMessage('El período desde no puede ser posterior al período hasta.')
    // Keep the catalog order of columns.
    const request: Solicitud = solicitud ?? { columnas: columns.map((column) => column.key).filter((key) => selected.includes(key)), filtros: filters, periodo_desde: rango.desde, periodo_hasta: rango.hasta }
    const run = ++previewRun.current
    setLoadingPreview(true); setMessage('')
    try {
      await fetch(`${api}/api/health/`, { credentials: 'include' })
      // Totals are the slow part and only change with the filters, not with the page.
      const totales = !preview || !solicitud || filtrosColumnas !== appliedColumnFilters
      const response = await fetch(`${base}/vista-previa/`, { method: 'POST', credentials: 'include', headers: { 'Content-Type': 'application/json', 'X-CSRFToken': csrfToken() }, body: JSON.stringify({ ...request, filtros_columnas: filtrosColumnas, pagina, por_pagina: porPagina, totales }) })
      if (run !== previewRun.current) return
      if (!response.ok) return setMessage((await response.json().catch(() => null))?.detail ?? `No se pudieron cargar los resultados (${response.status}).`)
      const data: VistaPrevia = await response.json()
      if (run !== previewRun.current) return
      setSolicitud(request); setPageSize(porPagina); setAppliedColumnFilters(filtrosColumnas)
      setPreview(totales ? data : { ...data, totales: preview?.totales ?? null })
    } finally { if (run === previewRun.current) setLoadingPreview(false) }
  }

  function applyColumnFilters(drafts = columnDrafts) {
    const next = Object.fromEntries(Object.entries(drafts).map(([key, value]) => [key, value.trim()]).filter(([, value]) => value))
    const unchanged = JSON.stringify(next) === JSON.stringify(appliedColumnFilters)
    if (!unchanged && !loadingPreview) void loadPreview(1, pageSize, next)
  }

  async function execute() {
    if (!solicitud) return
    setGenerating(true); setMessage(''); setProgress('Enviando solicitud...')
    try {
      await fetch(`${api}/api/health/`, { credentials: 'include' })
      const response = await fetch(`${base}/exportar/`, { method: 'POST', credentials: 'include', headers: { 'Content-Type': 'application/json', 'X-CSRFToken': csrfToken() }, body: JSON.stringify({ ...solicitud, filtros_columnas: appliedColumnFilters }) })
      if (!response.ok) return setMessage((await response.json().catch(() => null))?.detail ?? `No se pudo generar el Excel (${response.status}).`)
      let informe: Informe = await response.json()
      // Reports are generated by the background worker; poll until the file is ready.
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
      setMessage(`Informe generado y descargado: ${informe.filas_total.toLocaleString('es-CL')} filas (${periodLabel(solicitud.periodo_desde)} a ${periodLabel(solicitud.periodo_hasta)}).`)
    } finally { setGenerating(false); setProgress('') }
  }

  // Every year from the first loaded month to the current year, so ranges can include months not loaded yet.
  const knownYears = [...periodos.map((item) => item.anio), rango.desde.anio, rango.hasta.anio, new Date().getFullYear()]
  const years = Array.from({ length: Math.max(...knownYears) - Math.min(...knownYears) + 1 }, (_, index) => Math.max(...knownYears) - index)
  const periodSelect = (part: 'desde' | 'hasta', label: string) => <div className="period-field"><span>{label}</span><div><select disabled={generating} value={rango[part].mes} onChange={(event) => setRangoPart(part, 'mes', event.target.value)}>{MONTHS.map((month, index) => <option key={month} value={index + 1}>{month}</option>)}</select><select disabled={generating} value={rango[part].anio} onChange={(event) => setRangoPart(part, 'anio', event.target.value)}>{years.map((year) => <option key={year} value={year}>{year}</option>)}</select></div></div>

  const documento = kind === 'importaciones' ? 'DIN' : 'DUS'
  const activeRubroFilters = rubroFilters.filter((spec) => (filters[spec.key] ?? []).length)
  const visibleColumns = columns.filter((column) => column.label.toLowerCase().includes(columnSearch.toLowerCase()) || column.key.toLowerCase().includes(columnSearch.toLowerCase()))

  function renderFilter(spec: FilterSpec) {
    const values = filters[spec.key] ?? []
    if (spec.type === 'terms') return <TermsFilter key={spec.key} spec={spec} values={values} onChange={(next) => setFilter(spec.key, next)} />
    if (spec.type === 'catalog') return <SearchableMultiSelect key={spec.key} label={spec.label} placeholder={spec.placeholder} selected={values} onChange={(next) => setFilter(spec.key, next)} options={toOptions(catalogs[spec.catalog])} />
    if (spec.type === 'remote') return <SearchableMultiSelect key={spec.key} label={spec.label} placeholder={spec.placeholder} selected={values} onChange={(next) => setFilter(spec.key, next)} search={spec.search} selectedLabels={remoteLabels[spec.key]} />
    return <div key="partidas" className="searchable-select"><label className="tariff-search"><span>Partida arancelaria{values.length ? ` (${values.length})` : ''}</span><input value={partidaText} onChange={(event) => void searchPartidas(event.target.value)} placeholder="Ej. 8528 o motocicletas" />{partidas.length ? <div className="tariff-options tariff-options-multi">{partidas.map((partida) => { const isSelected = values.includes(partida.codigo); return <button key={partida.codigo} type="button" onClick={() => setFilter('partidas', isSelected ? values.filter((item) => item !== partida.codigo) : [...values, partida.codigo])}><input type="checkbox" checked={isSelected} readOnly /><strong>{partida.codigo}</strong><span>{partida.glosa}</span></button> })}</div> : null}</label>{values.length ? <div className="selected-values">{values.map((codigo) => <button key={codigo} type="button" onClick={() => setFilter('partidas', values.filter((item) => item !== codigo))}>{codigo} ×</button>)}</div> : null}</div>
  }

  return <main className="page dashboard-page report-page">
    <TopNav />
    <section className="report-heading"><div><p className="eyebrow">Constructor de consultas</p><h1>{title}</h1><p className="lead">{lead}</p></div><div className="report-selection-summary"><strong>{selected.length}</strong><span>columnas<br />seleccionadas</span></div></section>
    <section className="panel report-rubros"><div><p className="eyebrow">Configuraciones</p><h2>Rubros guardados</h2></div><select defaultValue="" onChange={(event) => { const rubro = rubros.find((item) => item.id === Number(event.target.value)); if (rubro) recover(rubro) }}><option value="">Seleccionar una configuración</option>{rubros.map((rubro) => <option key={rubro.id} value={rubro.id}>{rubro.nombre}</option>)}</select><button type="button" onClick={() => { setEditing(null); setRubroName(''); setShowRubroDialog(true) }}>Crear rubro</button>{editing ? <button type="button" onClick={() => { setRubroName(editing.nombre); setShowRubroDialog(true) }}>Actualizar</button> : null}{editing ? <button type="button" className="link-button" onClick={() => deleteRubro(editing)}>Eliminar</button> : null}</section>
    {message ? <p className="login-message">{message}</p> : null}
    <section className="report-layout report-workspace">
      <section className="panel report-columns-panel"><header><div><span className="report-step">01</span><p className="eyebrow">Datos de salida</p><h2>Columnas a mostrar</h2></div><button type="button" className="link-button" onClick={() => setSelected([])}>Limpiar selección</button></header><div className="column-search"><input value={columnSearch} onChange={(event) => setColumnSearch(event.target.value)} placeholder={columnSearchPlaceholder} /><span>{visibleColumns.length} disponibles</span></div><div className="column-picker">{visibleColumns.map((column) => <label key={column.key} className={selected.includes(column.key) ? 'is-selected' : ''}><input type="checkbox" checked={selected.includes(column.key)} onChange={() => toggleColumn(column.key)} /><span>{column.label}</span></label>)}</div></section>
      <section className="panel report-filters-panel"><header><div><span className="report-step">02</span><p className="eyebrow">Universo de datos</p><h2>Filtros y aranceles</h2></div><p>Opcionales</p></header><div className="report-period">{periodSelect('desde', 'Desde (mes - año)')}{periodSelect('hasta', 'Hasta (mes - año)')}<small>{periodos.length ? `Meses cargados: ${periodos.map(periodLabel).join(', ')}` : ''}</small></div><div className="report-filters report-universe">
        {universe.map(renderFilter)}
      </div>
      {activeRubroFilters.length ? <div className="report-other-filters"><strong>Filtros adicionales de este rubro</strong><p>Siguen aplicándose. Si los quitas, no volverán a aparecer aquí.</p><div className="report-filters">{activeRubroFilters.map(renderFilter)}</div></div> : null}<footer><div><span className="report-step">03</span><strong>Consultar</strong><p>{`${periodLabel(rango.desde)} a ${periodLabel(rango.hasta)}. Se guarda con el rubro.`}</p></div><button type="button" className="report-run" disabled={!selected.length || loadingPreview || generating} onClick={() => void loadPreview(1)}>{loadingPreview ? 'Calculando...' : 'Ver resultados'}</button></footer></section>
    </section>
    {preview ? <div className="modal-backdrop"><section className="report-preview" role="dialog" aria-modal="true" aria-label={`Resultados de ${title}`}>
      <header><div><p className="eyebrow">Resultados</p><h2>{title}</h2></div><div className="report-preview-action"><button type="button" className="report-excel" disabled={generating || !preview.registros} onClick={() => void execute()}>{generating ? 'Generando Excel...' : 'Descargar Excel'}</button><button type="button" className="link-button" disabled={generating} onClick={closePreview}>Cerrar</button></div></header>
      {generating ? <p className="report-preview-note">{progress}</p> : null}
      {message ? <p className="login-message report-preview-note">{message}</p> : null}
      <div className="report-totals">
        <div><span>Registros (ítems)</span><strong>{count(preview.registros)}</strong></div>
        {preview.totales ? <><div><span>{documento}</span><strong>{count(preview.totales.documentos)}</strong></div><div><span>USD CIF</span><strong>{usd(preview.totales.cif_usd)}</strong></div><div><span>USD FOB</span><strong>{usd(preview.totales.fob_usd)}</strong></div><div><span>Cantidad</span>{preview.totales.cantidades_por_unidad.length ? preview.totales.cantidades_por_unidad.map((item) => <strong key={item.unidad} className="report-total-unit">{count(item.cantidad)} {item.glosa || item.unidad}</strong>) : <strong>0</strong>}</div></> : null}
      </div>
      {preview.totales_omitidos ? <p className="report-preview-note">Son demasiados registros para calcular los totales en línea. Acota el período o agrega filtros para verlos.</p> : <p className="report-preview-note">Los montos suman solo los ítems que cumplen los filtros, sin repetir los totales de cada {documento}.{kind === 'exportaciones' && preview.totales ? ` El DUS no trae CIF por ítem: se reparte según el FOB, y solo ${count(preview.totales.documentos_con_cif ?? 0)} de ${count(preview.totales.documentos)} DUS declaran CIF.` : ''} Las cantidades se muestran por unidad de medida porque no se pueden sumar entre sí.</p>}
      <div className="report-preview-toolbar"><label>Mostrando <select value={pageSize} disabled={loadingPreview} onChange={(event) => void loadPreview(1, Number(event.target.value))}>{PAGE_SIZES.map((size) => <option key={size} value={size}>{size}</option>)}</select> registros por página</label>{columnFilters ? <small>Escribe en una columna y presiona Enter para filtrar.</small> : null}{Object.keys(appliedColumnFilters).length ? <button type="button" className="link-button" disabled={loadingPreview} onClick={() => { setColumnDrafts({}); applyColumnFilters({}) }}>Limpiar filtros</button> : null}{loadingPreview ? <small>Actualizando...</small> : null}</div>
      <div className="table-wrap"><table className="uploads-table report-preview-table"><thead><tr>{preview.columnas.map((column) => <th key={column.key}>{column.label}</th>)}</tr>{columnFilters ? <tr className="report-column-filters">{preview.columnas.map((column) => <th key={column.key}><input aria-label={`Filtrar ${column.label}`} placeholder="Filtrar" value={columnDrafts[column.key] ?? ''} onChange={(event) => setColumnDrafts({ ...columnDrafts, [column.key]: event.target.value })} onKeyDown={(event) => { if (event.key === 'Enter') applyColumnFilters() }} onBlur={() => applyColumnFilters()} /></th>)}</tr> : null}</thead><tbody>{preview.filas.length ? preview.filas.map((fila, index) => <tr key={index}>{fila.map((value, position) => <td key={preview.columnas[position].key}>{cell(value)}</td>)}</tr>) : <tr><td colSpan={preview.columnas.length}>No hay registros para estos filtros y período.</td></tr>}</tbody></table></div>
      <div className="report-pager"><button type="button" disabled={loadingPreview || preview.pagina <= 1} onClick={() => void loadPreview(preview.pagina - 1)}>Anterior</button><span>Página {count(preview.pagina)} de {count(preview.paginas)}</span><button type="button" disabled={loadingPreview || preview.pagina >= preview.paginas} onClick={() => void loadPreview(preview.pagina + 1)}>Siguiente</button></div>
    </section></div> : null}
    {showRubroDialog ? <div className="modal-backdrop"><section className="modal"><h2>{editing ? 'Actualizar rubro' : 'Crear rubro'}</h2><label>Nombre<input value={rubroName} onChange={(event) => setRubroName(event.target.value)} autoFocus /></label><div><button type="button" onClick={saveRubro}>Guardar</button><button type="button" className="link-button" onClick={() => setShowRubroDialog(false)}>Cancelar</button></div></section></div> : null}
  </main>
}
