"use client"

import { useEffect, useState } from 'react'
import TopNav from '../components/top-nav'

type Column = { key: string; label: string; default: boolean }
type Catalog = { codigo: string; glosa: string }
type Filters = Record<string, string[]>
type Periodo = { anio: number; mes: number }

function csrfToken() {
  return document.cookie.split('; ').find((cookie) => cookie.startsWith('csrftoken='))?.split('=')[1] ?? ''
}

const catalogFields = [
  ['aduana_codigo', 'Aduana', 'ADUANAS'], ['pais_destino_codigo', 'País de destino', 'PAISES'],
  ['puerto_embarque_codigo', 'Puerto de embarque', 'PUERTOS'], ['puerto_desembarque_codigo', 'Puerto de desembarque', 'PUERTOS'],
  ['via_transporte_codigo', 'Vía de transporte', 'VIAS_TRANSPORTE'], ['region_origen_codigo', 'Región de origen', 'REGIONES'],
] as const

const monthName = (mes: number) => new Date(2026, mes - 1).toLocaleString('es-CL', { month: 'long' })

export default function InformesExportacionesPage() {
  const api = process.env.NEXT_PUBLIC_API_BASE_URL ?? 'http://127.0.0.1:8000'
  const [columns, setColumns] = useState<Column[]>([])
  const [selected, setSelected] = useState<string[]>([])
  const [catalogs, setCatalogs] = useState<Record<string, Catalog[]>>({})
  const [periodos, setPeriodos] = useState<Periodo[]>([])
  const [periodo, setPeriodo] = useState('')
  const [filters, setFilters] = useState<Filters>({})
  const [partidaText, setPartidaText] = useState('')
  const [partidas, setPartidas] = useState<Catalog[]>([])
  const [columnSearch, setColumnSearch] = useState('')
  const [message, setMessage] = useState('')
  const [generating, setGenerating] = useState(false)

  useEffect(() => {
    void fetch(`${api}/api/health/`, { credentials: 'include' })
    void (async () => {
      const response = await fetch(`${api}/api/reportes/exportaciones/configuracion/`, { credentials: 'include' })
      if (!response.ok) return setMessage('No se pudo cargar la configuración.')
      const data = await response.json()
      setColumns(data.columnas)
      setSelected(data.columnas.filter((column: Column) => column.default).map((column: Column) => column.key))
      setCatalogs(data.catalogos)
      setPeriodos(data.periodos)
      if (data.periodos.length) setPeriodo(`${data.periodos[0].anio}-${data.periodos[0].mes}`)
    })()
  }, [api])

  function setFilter(name: string, values: string[]) { setFilters({ ...filters, [name]: values }) }
  function toggleColumn(key: string) { setSelected(selected.includes(key) ? selected.filter((item) => item !== key) : [...selected, key]) }

  async function searchPartidas(value: string) {
    setPartidaText(value)
    if (value.trim().length < 2) return setPartidas([])
    const response = await fetch(`${api}/api/reportes/importaciones/partidas/?q=${encodeURIComponent(value)}`)
    if (response.ok) setPartidas(await response.json())
  }

  async function execute() {
    const [anio, mes] = periodo.split('-')
    if (!anio || !mes) return setMessage('No hay períodos de exportaciones cargados.')
    setGenerating(true); setMessage('Generando el informe. Un mes completo puede tardar cerca de un minuto...')
    try {
      await fetch(`${api}/api/health/`, { credentials: 'include' })
      // Keep the catalog order of columns, as the import report does.
      const columnas = columns.map((column) => column.key).filter((key) => selected.includes(key))
      const response = await fetch(`${api}/api/reportes/exportaciones/exportar/`, { method: 'POST', credentials: 'include', headers: { 'Content-Type': 'application/json', 'X-CSRFToken': csrfToken() }, body: JSON.stringify({ columnas, filtros: filters, periodo_anio: anio, periodo_mes: mes }) })
      if (!response.ok) return setMessage(`No se pudo generar el Excel (${response.status}).`)
      const url = URL.createObjectURL(await response.blob())
      const link = document.createElement('a'); link.href = url; link.download = `informe_exportaciones_${anio}_${mes.padStart(2, '0')}.xlsx`; link.click(); URL.revokeObjectURL(url)
      setMessage('Informe generado y descargado correctamente.')
    } finally { setGenerating(false) }
  }

  const visibleColumns = columns.filter((column) => `${column.label} ${column.key}`.toLowerCase().includes(columnSearch.toLowerCase()))

  return <main className="page dashboard-page report-page">
    <TopNav />
    <section className="report-heading"><div><p className="eyebrow">Constructor de informes</p><h1>Exportaciones DUS</h1><p className="lead">Una fila por ítem del DUS. Los valores &quot;DUS&quot; (FOB total, flete, seguro, CIF, líquido retorno) se repiten en cada ítem: no los sumes por ítem.</p></div><div className="report-selection-summary"><strong>{selected.length}</strong><span>columnas<br />seleccionadas</span></div></section>
    {message ? <p className="login-message">{message}</p> : null}
    <section className="report-layout report-workspace">
      <section className="panel report-columns-panel"><header><div><span className="report-step">01</span><p className="eyebrow">Salida del archivo</p><h2>Columnas a exportar</h2></div><div style={{ display: 'flex', gap: '8px' }}><button type="button" className="link-button" onClick={() => setSelected(columns.filter((column) => column.default).map((column) => column.key))}>Predeterminadas</button><button type="button" className="link-button" onClick={() => setSelected([])}>Limpiar selección</button></div></header><div className="column-search"><input value={columnSearch} onChange={(event) => setColumnSearch(event.target.value)} placeholder="Buscar campo DUS, código o descripción" /><span>{visibleColumns.length} disponibles</span></div><div className="column-picker">{visibleColumns.map((column) => <label key={column.key} className={selected.includes(column.key) ? 'is-selected' : ''}><input type="checkbox" checked={selected.includes(column.key)} onChange={() => toggleColumn(column.key)} /><span>{column.label}</span></label>)}</div></section>
      <section className="panel report-filters-panel"><header><div><span className="report-step">02</span><p className="eyebrow">Universo de datos</p><h2>Filtros y aranceles</h2></div><p>Opcionales</p></header><div className="report-filters">{catalogFields.map(([key, label, group]) => <label key={key}><span>{label}</span><select multiple value={filters[key] ?? []} onChange={(event) => setFilter(key, Array.from(event.target.selectedOptions, (option) => option.value))}>{(catalogs[group] ?? []).map((item) => <option key={item.codigo} value={item.codigo}>{item.codigo} - {item.glosa}</option>)}</select></label>)}</div><label className="tariff-search"><span>Arancel por código o glosa</span><input value={partidaText} onChange={(event) => void searchPartidas(event.target.value)} placeholder="Ej. 0806 o uvas" />{partidas.length ? <div className="tariff-options tariff-options-multi">{partidas.map((partida) => { const isSelected = (filters.partidas ?? []).includes(partida.codigo); return <button key={partida.codigo} type="button" onClick={() => setFilter('partidas', isSelected ? (filters.partidas ?? []).filter((item) => item !== partida.codigo) : [...(filters.partidas ?? []), partida.codigo])}><input type="checkbox" checked={isSelected} readOnly /><strong>{partida.codigo}</strong><span>{partida.glosa}</span></button> })}</div> : null}</label>{(filters.partidas ?? []).length ? <div className="selected-values">{(filters.partidas ?? []).map((codigo) => <button key={codigo} type="button" onClick={() => setFilter('partidas', (filters.partidas ?? []).filter((item) => item !== codigo))}>{codigo} ×</button>)}</div> : null}<footer><div><span className="report-step">03</span><strong>Generar archivo</strong><label>Período <select value={periodo} disabled={generating} onChange={(event) => setPeriodo(event.target.value)}>{periodos.map((item) => <option key={`${item.anio}-${item.mes}`} value={`${item.anio}-${item.mes}`}>{monthName(item.mes)} {item.anio}</option>)}</select></label></div><button type="button" className="report-run" disabled={!selected.length || !periodo || generating} onClick={() => void execute()}>{generating ? 'Generando informe...' : 'Generar Excel'}</button></footer></section>
    </section>
  </main>
}
