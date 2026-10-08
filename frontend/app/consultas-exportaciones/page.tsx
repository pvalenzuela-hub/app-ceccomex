"use client"

import { FormEvent, useState } from 'react'
import TopNav from '../components/top-nav'

type Row = {
  id: number
  numero_ident: string
  item: string
  fecha_text: string
  exportador_codigo: string
  aduana_codigo: string
  aduana_glosa: string
  pais_destino_codigo: string
  pais_destino_glosa: string
  puerto_embarque_glosa: string
  puerto_desembarque_glosa: string
  via_transporte_glosa: string
  partida_arancelaria_codigo: string
  partida_glosa: string
  glosa_mercancia: string
  unidad_medida_glosa: string
  cantidad_mercancia: string
  valor_fob: string
  registro_incompleto: boolean
}

type Detail = {
  numero_ident: string
  items: Row[]
  bultos: Array<{ secuencia: string; tipo_bulto_codigo: string; tipo_bulto_glosa: string; cantidad_bultos: string; marcas: string }>
  documentos: Array<{ secuencia: string; numero_documento: string; fecha_documento_text: string; nave: string; numero_viaje: string }>
}

const filterNames = ['numero_ident', 'exportador_codigo', 'periodo_anio', 'periodo_mes_desde', 'periodo_mes_hasta', 'aduana_codigo', 'pais_destino_codigo', 'puerto_embarque_codigo', 'partida_busqueda', 'mercancia', 'fecha_desde', 'fecha_hasta'] as const
type Filters = Partial<Record<(typeof filterNames)[number], string>>

const money = new Intl.NumberFormat('es-CL', { maximumFractionDigits: 2 })
const months = Array.from({ length: 12 }, (_, index) => new Date(2026, index).toLocaleString('es-CL', { month: 'long' }))

export default function ConsultasExportacionesPage() {
  const api = process.env.NEXT_PUBLIC_API_BASE_URL ?? 'http://127.0.0.1:8000'
  const pageSize = 20
  const [filters, setFilters] = useState<Filters>({})
  const [rows, setRows] = useState<Row[]>([])
  const [total, setTotal] = useState<number | null>(null)
  const [page, setPage] = useState(1)
  const [loading, setLoading] = useState(false)
  const [message, setMessage] = useState('')
  const [partidaText, setPartidaText] = useState('')
  const [partidaOptions, setPartidaOptions] = useState<Array<{ codigo: string; glosa: string }>>([])
  const [detail, setDetail] = useState<Detail | null>(null)

  function params(nextFilters: Filters, nextPage: number) {
    const query = new URLSearchParams()
    Object.entries(nextFilters).forEach(([key, value]) => { if (value) query.set(key, value) })
    query.set('page', String(nextPage))
    query.set('page_size', String(pageSize))
    return query
  }

  async function runSearch(nextPage: number, nextFilters = filters) {
    setLoading(true); setMessage('')
    try {
      const response = await fetch(`${api}/api/consultas/exportaciones/?${params(nextFilters, nextPage)}`, { credentials: 'include', cache: 'no-store' })
      if (!response.ok) return setMessage(`No se pudo consultar (${response.status}).`)
      const data = await response.json()
      setRows(data.results); setTotal(data.count); setPage(data.page)
    } catch (error) {
      setMessage(error instanceof Error ? error.message : 'No se pudo conectar con el backend.')
    } finally { setLoading(false) }
  }

  function handleSearch(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    const form = new FormData(event.currentTarget)
    const nextFilters: Filters = {}
    filterNames.forEach((name) => { const value = String(form.get(name) ?? '').trim(); if (value) nextFilters[name] = value })
    setFilters(nextFilters)
    void runSearch(1, nextFilters)
  }

  async function suggestPartidas(value: string) {
    setPartidaText(value)
    if (value.trim().length < 2) return setPartidaOptions([])
    const response = await fetch(`${api}/api/reportes/importaciones/partidas/?q=${encodeURIComponent(value)}`)
    if (response.ok) setPartidaOptions(await response.json())
  }

  async function openDetail(numero: string) {
    const response = await fetch(`${api}/api/consultas/exportaciones/dus/${encodeURIComponent(numero)}/`, { credentials: 'include' })
    if (response.ok) setDetail(await response.json())
    else setMessage(`No se pudo abrir el DUS ${numero}.`)
  }

  async function exportExcel() {
    setLoading(true); setMessage('Generando Excel...')
    try {
      const response = await fetch(`${api}/api/consultas/exportaciones/exportar/?${params(filters, 1)}`, { credentials: 'include', cache: 'no-store' })
      if (!response.ok) return setMessage(`No se pudo exportar (${response.status}).`)
      const url = URL.createObjectURL(await response.blob())
      const link = document.createElement('a'); link.href = url; link.download = 'consultas_exportaciones.xlsx'; link.click(); URL.revokeObjectURL(url)
      setMessage('Excel generado correctamente.')
    } finally { setLoading(false) }
  }

  return (
    <main className="page dashboard-page">
      <TopNav />
      <section className="dashboard-hero">
        <div>
          <p className="eyebrow">CEC COMEX Platform</p>
          <h1>Consultas de exportaciones</h1>
          <p className="lead">Busca ítems de DUS por período, aduana, destino, arancel o mercadería. Haz clic en un DUS para ver sus bultos y documentos de transporte.</p>
        </div>
        <div className="dashboard-meta"><div className="meta-chip">Exportaciones DUS</div></div>
      </section>

      <section className="panel upload-panel">
        <div className="upload-header"><div><p className="eyebrow">Búsqueda</p><h2>Filtros</h2></div></div>
        <form className="upload-form" onSubmit={handleSearch}>
          <label>Nº DUS<input name="numero_ident" placeholder="Ej. 13300272" /></label>
          <label>Exportador (Nº único)<input name="exportador_codigo" placeholder="Ej. 11758" /></label>
          <label>Año<input name="periodo_anio" type="number" placeholder="2026" /></label>
          <label>Desde mes<select name="periodo_mes_desde" defaultValue=""><option value="">Todos</option>{months.map((month, index) => <option key={month} value={index + 1}>{month}</option>)}</select></label>
          <label>Hasta mes<select name="periodo_mes_hasta" defaultValue=""><option value="">Todos</option>{months.map((month, index) => <option key={month} value={index + 1}>{month}</option>)}</select></label>
          <label>Código aduana<input name="aduana_codigo" placeholder="Ej. 39" /></label>
          <label>Código país destino<input name="pais_destino_codigo" placeholder="Ej. 225" /></label>
          <label>Código puerto embarque<input name="puerto_embarque_codigo" placeholder="Ej. 906" /></label>
          <label className="tariff-search">Arancel / descripción<input name="partida_busqueda" value={partidaText} onChange={(event) => void suggestPartidas(event.target.value)} placeholder="Ej. 0806 o uvas" autoComplete="off" />{partidaOptions.length ? <div className="tariff-options">{partidaOptions.map((partida) => <button key={partida.codigo} type="button" onMouseDown={(event) => event.preventDefault()} onClick={() => { setPartidaText(partida.codigo); setPartidaOptions([]) }}><strong>{partida.codigo}</strong><span>{partida.glosa}</span></button>)}</div> : null}</label>
          <label>Mercadería contiene<input name="mercancia" placeholder="Ej. cerezas" /></label>
          <label>Fecha desde<input name="fecha_desde" type="date" /></label>
          <label>Fecha hasta<input name="fecha_hasta" type="date" /></label>
          <button type="submit" disabled={loading}>{loading ? 'Buscando...' : 'Buscar'}</button>
        </form>
        {message ? <p className="login-message">{message}</p> : null}
      </section>

      <section className="panel">
        <div className="upload-header">
          <div><p className="eyebrow">Resultados</p><h2>{total !== null ? `${total.toLocaleString('es-CL')} ítems` : 'Resultados'}</h2></div>
          <div className="meta-chip">Página {page}</div>
        </div>
        <div className="table-wrap">
          <table className="uploads-table">
            <thead><tr><th>Nº DUS</th><th>Ítem</th><th>Fecha</th><th>Exportador</th><th>Aduana</th><th>País destino</th><th>Puerto embarque</th><th>Arancel</th><th>Mercadería</th><th>Cantidad</th><th>US$ FOB</th></tr></thead>
            <tbody>
              {rows.length ? rows.map((row) => (
                <tr key={row.id}>
                  <td><button type="button" className="link-button" onClick={() => void openDetail(row.numero_ident)}>{row.numero_ident}</button></td>
                  <td>{row.item}</td>
                  <td>{row.fecha_text}</td>
                  <td>{row.exportador_codigo}</td>
                  <td>{row.aduana_glosa || row.aduana_codigo}</td>
                  <td>{row.pais_destino_glosa || row.pais_destino_codigo}</td>
                  <td>{row.puerto_embarque_glosa}</td>
                  <td title={row.partida_glosa}>{row.partida_arancelaria_codigo}{row.registro_incompleto ? ' (truncado)' : ''}</td>
                  <td>{row.glosa_mercancia}</td>
                  <td>{row.cantidad_mercancia} {row.unidad_medida_glosa}</td>
                  <td>{row.valor_fob ? money.format(Number(row.valor_fob)) : ''}</td>
                </tr>
              )) : <tr><td colSpan={11}>{total === null ? 'Ejecuta una búsqueda para ver resultados.' : 'Sin resultados.'}</td></tr>}
            </tbody>
          </table>
        </div>
        <div className="upload-header" style={{ marginTop: '16px' }}>
          <div className="progress-text">{total !== null ? `Mostrando ${rows.length} de ${total.toLocaleString('es-CL')}` : 'Sin búsqueda activa'}</div>
          <div style={{ display: 'flex', gap: '8px' }}>
            <button type="button" className="link-button" disabled={loading || !total} onClick={() => void exportExcel()}>Exportar Excel</button>
            <button type="button" className="link-button" disabled={page <= 1 || loading} onClick={() => void runSearch(page - 1)}>Anterior</button>
            <button type="button" className="link-button" disabled={loading || total === null || page * pageSize >= total} onClick={() => void runSearch(page + 1)}>Siguiente</button>
          </div>
        </div>
      </section>

      {detail ? (
        <div className="modal-backdrop" onClick={() => setDetail(null)}>
          <section className="modal dus-detail" onClick={(event) => event.stopPropagation()}>
            <h2>DUS {detail.numero_ident}</h2>
            <h3>Ítems ({detail.items.length})</h3>
            <div className="table-wrap"><table className="uploads-table"><thead><tr><th>Ítem</th><th>Arancel</th><th>Mercadería</th><th>Cantidad</th><th>US$ FOB</th></tr></thead><tbody>{detail.items.map((item) => <tr key={item.id}><td>{item.item}</td><td title={item.partida_glosa}>{item.partida_arancelaria_codigo}</td><td>{item.glosa_mercancia}</td><td>{item.cantidad_mercancia} {item.unidad_medida_glosa}</td><td>{item.valor_fob ? money.format(Number(item.valor_fob)) : ''}</td></tr>)}</tbody></table></div>
            <h3>Bultos ({detail.bultos.length})</h3>
            <div className="table-wrap"><table className="uploads-table"><thead><tr><th>Nº</th><th>Tipo</th><th>Cantidad</th><th>Identificación</th></tr></thead><tbody>{detail.bultos.length ? detail.bultos.map((bulto) => <tr key={bulto.secuencia}><td>{bulto.secuencia}</td><td>{bulto.tipo_bulto_glosa || bulto.tipo_bulto_codigo}</td><td>{bulto.cantidad_bultos}</td><td>{bulto.marcas}</td></tr>) : <tr><td colSpan={4}>Sin bultos informados.</td></tr>}</tbody></table></div>
            <h3>Documentos de transporte ({detail.documentos.length})</h3>
            <div className="table-wrap"><table className="uploads-table"><thead><tr><th>Nº</th><th>Documento</th><th>Fecha</th><th>Nave</th><th>Viaje</th></tr></thead><tbody>{detail.documentos.length ? detail.documentos.map((doc) => <tr key={doc.secuencia}><td>{doc.secuencia}</td><td>{doc.numero_documento}</td><td>{doc.fecha_documento_text}</td><td>{doc.nave}</td><td>{doc.numero_viaje}</td></tr>) : <tr><td colSpan={5}>Sin documentos informados.</td></tr>}</tbody></table></div>
            <div><button type="button" onClick={() => setDetail(null)}>Cerrar</button></div>
          </section>
        </div>
      ) : null}
    </main>
  )
}
