"use client"

import { useEffect, useState } from 'react'
import TopNav from '../components/top-nav'

type Column = { key: string; label: string; default: boolean }
type Catalog = { codigo: string; glosa: string }
type Filters = Record<string, string[]>
type Rubro = { id: number; nombre: string; configuracion_json: { columnas?: string[]; filtros?: Filters } }

function csrfToken() {
  return document.cookie.split('; ').find((cookie) => cookie.startsWith('csrftoken='))?.split('=')[1] ?? ''
}

const catalogFields = [
  ['aduana_codigo', 'Aduana', 'ADUANAS'], ['comuna_importador_codigo', 'Comuna importador', 'COMUNAS'],
  ['pais_origen_codigo', 'País de origen', 'PAISES'], ['via_transporte_codigo', 'Vía de transporte', 'VIAS_TRANSPORTE'],
  ['regimenes', 'Régimen de importación', 'REGIMENES'],
] as const

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
  const [showRunDialog, setShowRunDialog] = useState(false)
  const [periodoMes, setPeriodoMes] = useState(String(new Date().getMonth() + 1))
  const [periodoAnio, setPeriodoAnio] = useState(String(new Date().getFullYear()))
  const [message, setMessage] = useState('')
  const [generating, setGenerating] = useState(false)

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
    })()
    void loadRubros()
  }, [])

  function setFilter(name: string, values: string[]) { setFilters({ ...filters, [name]: values }) }
  function toggleColumn(key: string) { setSelected(selected.includes(key) ? selected.filter((item) => item !== key) : [...selected, key]) }
  function recover(rubro: Rubro) {
    setSelected(rubro.configuracion_json.columnas ?? [])
    setFilters(rubro.configuracion_json.filtros ?? {})
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
    const body = { nombre: rubroName.trim(), configuracion_json: { columnas: selected, filtros: filters } }
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

  async function execute() {
    setGenerating(true); setMessage('Generando el reporte. Su solicitud está siendo procesada...')
    try {
      await fetch(`${api}/api/health/`, { credentials: 'include' })
      const response = await fetch(`${api}/api/reportes/importaciones/exportar/`, { method: 'POST', credentials: 'include', headers: { 'Content-Type': 'application/json', 'X-CSRFToken': csrfToken() }, body: JSON.stringify({ columnas: selected, filtros: filters, periodo_mes: periodoMes, periodo_anio: periodoAnio }) })
      if (!response.ok) return setMessage(`No se pudo generar el Excel (${response.status}).`)
      const url = URL.createObjectURL(await response.blob())
      const link = document.createElement('a'); link.href = url; link.download = `informe_importaciones_${periodoAnio}_${periodoMes}.xlsx`; link.click(); URL.revokeObjectURL(url)
      setShowRunDialog(false); setMessage('Reporte generado y descargado correctamente.')
    } finally { setGenerating(false) }
  }

  return <main className="page dashboard-page">
    <TopNav />
    <section className="dashboard-hero"><div><p className="eyebrow">Informes</p><h1>Importaciones</h1><p className="lead">Configure las columnas y filtros del informe DIN para descargarlo en Excel.</p></div></section>
    <section className="panel report-toolbar">
      <select defaultValue="" onChange={(event) => { const rubro = rubros.find((item) => item.id === Number(event.target.value)); if (rubro) recover(rubro) }}><option value="">Recuperar rubro guardado</option>{rubros.map((rubro) => <option key={rubro.id} value={rubro.id}>{rubro.nombre}</option>)}</select>
      <button type="button" onClick={() => { setEditing(null); setRubroName(''); setShowRubroDialog(true) }}>+ Crear rubro</button>
      {editing ? <button type="button" onClick={() => { setRubroName(editing.nombre); setShowRubroDialog(true) }}>... Actualizar rubro</button> : null}
      {editing ? <button type="button" className="link-button" onClick={() => deleteRubro(editing)}>x Eliminar rubro</button> : null}
      <button type="button" className="report-run" disabled={!selected.length || generating} onClick={() => setShowRunDialog(true)}>{generating ? 'Generando reporte...' : 'Generar Excel'}</button>
    </section>
    {message ? <p className="login-message">{message}</p> : null}
    <section className="report-layout">
      <section className="panel"><p className="eyebrow">Salida</p><h2>Columnas a exportar</h2><div className="column-picker">{columns.map((column) => <label key={column.key}><input type="checkbox" checked={selected.includes(column.key)} onChange={() => toggleColumn(column.key)} /> {column.label}</label>)}</div></section>
       <section className="panel"><p className="eyebrow">Filtros</p><h2>Catálogos</h2><div className="report-filters">{catalogFields.map(([key, label, group]) => <label key={key}>{label}<select multiple value={filters[key] ?? []} onChange={(event) => setFilter(key, Array.from(event.target.selectedOptions, (option) => option.value))}>{(catalogs[group] ?? []).map((item) => <option key={item.codigo} value={item.codigo}>{item.codigo} - {item.glosa}</option>)}</select></label>)}</div>
       <label className="tariff-search">Arancel por código o glosa<input value={partidaText} onChange={(event) => void searchPartidas(event.target.value)} placeholder="Ej. 8528 o motocicletas" />{partidas.length ? <div className="tariff-options tariff-options-multi">{partidas.map((partida) => { const selectedPartida = (filters.partidas ?? []).includes(partida.codigo); return <button key={partida.codigo} type="button" onClick={() => setFilter('partidas', selectedPartida ? (filters.partidas ?? []).filter((item) => item !== partida.codigo) : [...(filters.partidas ?? []), partida.codigo])}><input type="checkbox" checked={selectedPartida} readOnly /><strong>{partida.codigo}</strong><span>{partida.glosa}</span></button> })}</div> : null}</label>
       {(filters.partidas ?? []).length ? <div className="selected-values">Aranceles: {(filters.partidas ?? []).map((codigo) => <button key={codigo} type="button" onClick={() => setFilter('partidas', (filters.partidas ?? []).filter((item) => item !== codigo))}>{codigo} ×</button>)}</div> : null}</section>
    </section>
    {showRubroDialog ? <div className="modal-backdrop"><section className="modal"><h2>{editing ? 'Actualizar rubro' : 'Crear rubro'}</h2><label>Nombre<input value={rubroName} onChange={(event) => setRubroName(event.target.value)} autoFocus /></label><div><button type="button" onClick={saveRubro}>Guardar</button><button type="button" className="link-button" onClick={() => setShowRubroDialog(false)}>Cancelar</button></div></section></div> : null}
    {showRunDialog ? <div className="modal-backdrop"><section className="modal"><h2>Periodo del informe</h2>{generating ? <p className="login-message">Generando el reporte. Su solicitud está siendo procesada...</p> : null}<label>Mes<select disabled={generating} value={periodoMes} onChange={(event) => setPeriodoMes(event.target.value)}>{Array.from({ length: 12 }, (_, index) => <option key={index} value={index + 1}>{new Date(2026, index).toLocaleString('es-CL', { month: 'long' })}</option>)}</select></label><label>Año<input disabled={generating} type="number" value={periodoAnio} onChange={(event) => setPeriodoAnio(event.target.value)} /></label><div><button type="button" disabled={generating} onClick={() => void execute()}>{generating ? 'Generando reporte...' : 'Generar Excel'}</button><button type="button" className="link-button" disabled={generating} onClick={() => setShowRunDialog(false)}>Cancelar</button></div></section></div> : null}
  </main>
}
