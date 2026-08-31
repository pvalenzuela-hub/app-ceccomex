"use client"

import { FormEvent, useEffect, useState } from 'react'
import TopNav from '../components/top-nav'

type Row = {
  id: number
  numero_ident: string
  item: string
  fecha_text: string
  aduana_codigo: string
  comuna_importador_codigo?: string
  pais_origen_codigo: string
  partida_arancelaria_codigo: string
  glosa_mercancia: string
  valor_fob: string
  creado: string
  aduana?: { codigo: string; glosa: string; pendiente_revision?: boolean }
  comuna_importador?: { codigo: string; glosa: string; pendiente_revision?: boolean }
  pais_origen?: { codigo: string; glosa: string; pendiente_revision?: boolean }
  partida?: { codigo: string; glosa: string; pendiente_revision?: boolean }
}

type PendingCode = {
  campo: string
  codigo: string
  glosa: string
  vigente: boolean
  pendiente_revision: boolean
}

function pendingLabel(campo: string) {
  if (campo === 'aduana_codigo') return 'Aduana'
  if (campo === 'pais_origen_codigo') return 'País'
  if (campo === 'via_transporte_codigo') return 'Vía'
  if (campo === 'partida_arancelaria_codigo') return 'Partida'
  return campo
}

function pendingTone(campo: string) {
  if (campo === 'aduana_codigo') return 'pending-badge-aduana'
  if (campo === 'pais_origen_codigo') return 'pending-badge-pais'
  if (campo === 'via_transporte_codigo') return 'pending-badge-via'
  if (campo === 'partida_arancelaria_codigo') return 'pending-badge-partida'
  return 'pending-badge-default'
}

type SearchFilters = {
  numero_ident: string
  periodo_anio: string
  periodo_mes: string
  periodo_mes_desde: string
  periodo_mes_hasta: string
  aduana_codigo: string
  partida_arancelaria_codigo: string
  pais_origen_codigo: string
  fecha_desde: string
  fecha_hasta: string
  partida_busqueda: string
}

export default function ConsultasPage() {
  const apiBaseUrl = process.env.NEXT_PUBLIC_API_BASE_URL ?? 'http://127.0.0.1:8000'
  const [rows, setRows] = useState<Row[]>([])
  const [loading, setLoading] = useState(false)
  const [message, setMessage] = useState('')
  const [resultCount, setResultCount] = useState<number | null>(null)
  const [pendingCodes, setPendingCodes] = useState<PendingCode[]>([])
  const [page, setPage] = useState(1)
  const [pageSize] = useState(20)
  const [totalCount, setTotalCount] = useState<number | null>(null)
  const [favorites, setFavorites] = useState<Array<{ id: number; nombre: string; filtros_json: SearchFilters }>>([])
  const [favoriteName, setFavoriteName] = useState('')
  const [columnFilters, setColumnFilters] = useState({ numero: '', aduana: '', pais: '', partida: '', producto: '' })
  const [partidaOptions, setPartidaOptions] = useState<Array<{ codigo: string; glosa: string }>>([])
  const [filters, setFilters] = useState<SearchFilters>({
    numero_ident: '',
    periodo_anio: '',
    periodo_mes: '',
    periodo_mes_desde: '',
    periodo_mes_hasta: '',
    aduana_codigo: '',
    partida_arancelaria_codigo: '',
    pais_origen_codigo: '',
    fecha_desde: '',
    fecha_hasta: '',
    partida_busqueda: '',
  })

  async function loadFavorites() {
    const response = await fetch(`${apiBaseUrl}/api/consultas/favoritos/`)
    if (response.ok) setFavorites(await response.json())
  }

  useEffect(() => { void loadFavorites() }, [])

  async function runSearch(nextPage: number, nextFilters = filters) {
    setLoading(true)
    setMessage('')
    const params = new URLSearchParams()
    if (nextFilters.numero_ident) params.set('numero_ident', nextFilters.numero_ident)
    if (nextFilters.periodo_anio) params.set('periodo_anio', nextFilters.periodo_anio)
    if (nextFilters.periodo_mes) params.set('periodo_mes', nextFilters.periodo_mes)
    if (nextFilters.periodo_mes_desde) params.set('periodo_mes_desde', nextFilters.periodo_mes_desde)
    if (nextFilters.periodo_mes_hasta) params.set('periodo_mes_hasta', nextFilters.periodo_mes_hasta)
    if (nextFilters.aduana_codigo) params.set('aduana_codigo', nextFilters.aduana_codigo)
    if (nextFilters.partida_arancelaria_codigo) params.set('partida_arancelaria_codigo', nextFilters.partida_arancelaria_codigo)
    if (nextFilters.partida_busqueda) params.set('partida_busqueda', nextFilters.partida_busqueda)
    if (nextFilters.pais_origen_codigo) params.set('pais_origen_codigo', nextFilters.pais_origen_codigo)
    if (nextFilters.fecha_desde) params.set('fecha_desde', nextFilters.fecha_desde)
    if (nextFilters.fecha_hasta) params.set('fecha_hasta', nextFilters.fecha_hasta)
    params.set('page', String(nextPage))
    params.set('page_size', String(pageSize))

    try {
      const response = await fetch(`${apiBaseUrl}/api/consultas/importaciones/?${params.toString()}`, { cache: 'no-store' })
      const rawText = await response.text()
      const data = rawText ? JSON.parse(rawText) : {}
      const results = Array.isArray(data?.results) ? data.results : []
      setRows(results)
      setPage(Number(data?.page ?? nextPage))
      const count = Number(data?.count ?? results.length)
      setTotalCount(count)
      setResultCount(results.length)
      setMessage(response.ok ? `Resultados: ${count}` : 'No se pudo consultar.')
    } catch (error) {
      setRows([])
      setMessage(error instanceof Error ? error.message : 'No se pudo conectar con el backend.')
    } finally {
      setLoading(false)
    }
  }

  async function loadPendingCodes() {
    try {
      const response = await fetch(`${apiBaseUrl}/api/consultas/pendientes-revision/?limit=20`, { cache: 'no-store' })
      const rawText = await response.text()
      const data = rawText ? JSON.parse(rawText) : {}
      setPendingCodes(Array.isArray(data?.results) ? data.results : [])
    } catch {
      setPendingCodes([])
    }
  }

  function buildQueryParams(nextFilters = filters, nextPage = page) {
    const params = new URLSearchParams()
    if (nextFilters.numero_ident) params.set('numero_ident', nextFilters.numero_ident)
    if (nextFilters.periodo_anio) params.set('periodo_anio', nextFilters.periodo_anio)
    if (nextFilters.periodo_mes) params.set('periodo_mes', nextFilters.periodo_mes)
    if (nextFilters.periodo_mes_desde) params.set('periodo_mes_desde', nextFilters.periodo_mes_desde)
    if (nextFilters.periodo_mes_hasta) params.set('periodo_mes_hasta', nextFilters.periodo_mes_hasta)
    if (nextFilters.aduana_codigo) params.set('aduana_codigo', nextFilters.aduana_codigo)
    if (nextFilters.partida_arancelaria_codigo) params.set('partida_arancelaria_codigo', nextFilters.partida_arancelaria_codigo)
    if (nextFilters.partida_busqueda) params.set('partida_busqueda', nextFilters.partida_busqueda)
    if (nextFilters.pais_origen_codigo) params.set('pais_origen_codigo', nextFilters.pais_origen_codigo)
    if (nextFilters.fecha_desde) params.set('fecha_desde', nextFilters.fecha_desde)
    if (nextFilters.fecha_hasta) params.set('fecha_hasta', nextFilters.fecha_hasta)
    params.set('page', String(nextPage))
    params.set('page_size', String(pageSize))
    return params
  }

  async function exportResults() {
    setLoading(true)
    try {
      const params = buildQueryParams(filters, page)
      const response = await fetch(`${apiBaseUrl}/api/consultas/importaciones/exportar/?${params.toString()}`, {
        cache: 'no-store',
      })
      if (!response.ok) {
        setMessage(`No se pudo exportar (${response.status})`)
        return
      }
      const blob = await response.blob()
      const url = window.URL.createObjectURL(blob)
      const link = document.createElement('a')
      link.href = url
      link.download = 'consultas_importaciones.xlsx'
      document.body.appendChild(link)
      link.click()
      link.remove()
      window.URL.revokeObjectURL(url)
      setMessage('Excel generado correctamente.')
    } catch (error) {
      setMessage(error instanceof Error ? error.message : 'No se pudo exportar.')
    } finally {
      setLoading(false)
    }
  }

  async function handleSearch(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    const formData = new FormData(event.currentTarget)
    const nextFilters = {
      numero_ident: String(formData.get('numero_ident') ?? '').trim(),
      periodo_anio: String(formData.get('periodo_anio') ?? '').trim(),
      periodo_mes: String(formData.get('periodo_mes') ?? '').trim(),
      periodo_mes_desde: String(formData.get('periodo_mes_desde') ?? '').trim(),
      periodo_mes_hasta: String(formData.get('periodo_mes_hasta') ?? '').trim(),
      aduana_codigo: String(formData.get('aduana_codigo') ?? '').trim(),
      partida_arancelaria_codigo: String(formData.get('partida_arancelaria_codigo') ?? '').trim(),
      pais_origen_codigo: String(formData.get('pais_origen_codigo') ?? '').trim(),
      fecha_desde: String(formData.get('fecha_desde') ?? '').trim(),
      fecha_hasta: String(formData.get('fecha_hasta') ?? '').trim(),
      partida_busqueda: String(formData.get('partida_busqueda') ?? '').trim(),
    }
    setFilters(nextFilters)
    await runSearch(1, nextFilters)
    void loadPendingCodes()
  }

  async function saveFavorite() {
    if (!favoriteName.trim()) return setMessage('Asigna un nombre al favorito.')
    const response = await fetch(`${apiBaseUrl}/api/consultas/favoritos/`, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ nombre: favoriteName.trim(), filtros_json: filters }) })
    if (!response.ok) return setMessage('No se pudo guardar el favorito.')
    setFavoriteName('')
    await loadFavorites()
    setMessage('Favorito guardado.')
  }

  async function suggestPartidas(value: string) {
    if (value.trim().length < 2) {
      setPartidaOptions([])
      return
    }
    const response = await fetch(`${apiBaseUrl}/api/catalogos/partidas/?search=${encodeURIComponent(value)}&page_size=12`)
    if (!response.ok) return
    const data = await response.json()
    setPartidaOptions(Array.isArray(data.results) ? data.results : [])
  }

  const visibleRows = rows.filter((row) =>
    row.numero_ident.includes(columnFilters.numero) &&
    row.aduana_codigo.toLowerCase().includes(columnFilters.aduana.toLowerCase()) &&
    row.pais_origen_codigo.toLowerCase().includes(columnFilters.pais.toLowerCase()) &&
    `${row.partida_arancelaria_codigo} ${row.partida?.glosa ?? ''}`.toLowerCase().includes(columnFilters.partida.toLowerCase()) &&
    row.glosa_mercancia.toLowerCase().includes(columnFilters.producto.toLowerCase())
  )

  return (
    <main className="page dashboard-page">
      <TopNav />
      <section className="dashboard-hero">
        <div>
          <p className="eyebrow">CEC COMEX Platform</p>
          <h1>Consultas</h1>
          <p className="lead">Busca importaciones ya materializadas en una vista separada del panel operativo.</p>
        </div>
        <div className="dashboard-meta">
          <div className="meta-chip">Importaciones</div>
        </div>
      </section>

      <section className="panel upload-panel">
        <div className="upload-header">
          <div>
            <p className="eyebrow">Búsqueda</p>
            <h2>Filtros avanzados</h2>
            <p className="lead">{resultCount !== null ? `${resultCount} filas en esta página` : 'Ejecuta una búsqueda para ver resultados.'}</p>
          </div>
        </div>

        <form className="upload-form" onSubmit={handleSearch}>
          <label>
            Número de identificación
            <input name="numero_ident" type="text" placeholder="Ej. 12345678-9" />
          </label>
          <label>
            Año
            <input name="periodo_anio" type="number" placeholder="2025" />
          </label>
          <label>
            Mes exacto
            <input name="periodo_mes" type="number" min="1" max="12" placeholder="1" />
          </label>
          <label>Desde mes<select name="periodo_mes_desde" defaultValue={filters.periodo_mes_desde}><option value="">Todos</option>{Array.from({ length: 12 }, (_, index) => <option key={index + 1} value={index + 1}>{new Date(2026, index).toLocaleString('es', { month: 'long' })}</option>)}</select></label>
          <label>Hasta mes<select name="periodo_mes_hasta" defaultValue={filters.periodo_mes_hasta}><option value="">Todos</option>{Array.from({ length: 12 }, (_, index) => <option key={index + 1} value={index + 1}>{new Date(2026, index).toLocaleString('es', { month: 'long' })}</option>)}</select></label>
          <label>
            Aduana
            <input name="aduana_codigo" type="text" placeholder="Ej. 001" />
          </label>
          <label className="tariff-search">Arancel / descripción<input name="partida_busqueda" type="text" value={filters.partida_busqueda} onChange={(event) => { const value = event.target.value; setFilters({ ...filters, partida_busqueda: value }); void suggestPartidas(value) }} placeholder="Ej. 8528 o motocicletas" />{partidaOptions.length ? <div className="tariff-options">{partidaOptions.map((partida) => <button key={partida.codigo} type="button" onMouseDown={(event) => event.preventDefault()} onClick={() => { setFilters({ ...filters, partida_busqueda: partida.codigo }); setPartidaOptions([]) }}><strong>{partida.codigo}</strong><span>{partida.glosa}</span></button>)}</div> : null}</label>
          <label>
            País origen
            <input name="pais_origen_codigo" type="text" placeholder="Ej. CL" />
          </label>
          <label>
            Fecha desde
            <input name="fecha_desde" type="date" />
          </label>
          <label>
            Fecha hasta
            <input name="fecha_hasta" type="date" />
          </label>
          <button type="submit" disabled={loading}>{loading ? 'Buscando...' : 'Buscar'}</button>
        </form>

        {message ? <p className="login-message">{message}</p> : null}
        <div className="favorite-bar"><select onChange={(event) => { const favorite = favorites.find((item) => item.id === Number(event.target.value)); if (favorite) { setFilters(favorite.filtros_json); void runSearch(1, favorite.filtros_json) } }} defaultValue=""><option value="">Mis favoritos</option>{favorites.map((favorite) => <option key={favorite.id} value={favorite.id}>{favorite.nombre}</option>)}</select><input value={favoriteName} onChange={(event) => setFavoriteName(event.target.value)} placeholder="Nombre del favorito" /><button type="button" onClick={saveFavorite}>Guardar filtros</button></div>
      </section>

      <section className="panel">
        <div className="upload-header">
          <div>
            <p className="eyebrow">Resultados</p>
            <h2>{totalCount !== null ? `${totalCount} coincidencias` : 'Resultados'}</h2>
          </div>
          <div className="meta-chip">Página {page}</div>
        </div>
        <div className="table-wrap">
          <table className="uploads-table">
            <thead>
              <tr>
                <th>Número</th>
                <th>Ítem</th>
                <th>Fecha</th>
                <th>Aduana código</th>
                <th>Aduana nombre</th>
                <th>Comuna imp.</th>
                <th>País código</th>
                <th>País origen</th>
                <th>Partida</th>
                <th>FOB</th>
              </tr>
            </thead>
            <tbody>
              <tr className="column-filters"><td><input placeholder="Filtrar" onChange={(event) => setColumnFilters({ ...columnFilters, numero: event.target.value })} /></td><td /><td /><td><input placeholder="Aduana" onChange={(event) => setColumnFilters({ ...columnFilters, aduana: event.target.value })} /></td><td /><td /><td><input placeholder="País" onChange={(event) => setColumnFilters({ ...columnFilters, pais: event.target.value })} /></td><td><input placeholder="Partida" onChange={(event) => setColumnFilters({ ...columnFilters, partida: event.target.value })} /></td><td><input placeholder="Producto" onChange={(event) => setColumnFilters({ ...columnFilters, producto: event.target.value })} /></td></tr>
              {visibleRows.length ? visibleRows.map((row) => (
                <tr key={row.id}>
                  <td>{row.numero_ident}</td>
                  <td>{row.item}</td>
                  <td>{row.fecha_text}</td>
                  <td>{row.aduana_codigo}</td>
                  <td>{row.aduana?.glosa || 'Sin glosa'}</td>
                  <td>{row.comuna_importador_codigo || '—'}</td>
                  <td>{row.pais_origen_codigo}</td>
                  <td>{row.pais_origen?.glosa || 'Sin glosa'}</td>
                  <td>{row.partida?.glosa || row.partida_arancelaria_codigo}</td>
                  <td>{row.valor_fob}</td>
                </tr>
              )) : (
                <tr>
            <td colSpan={10}>Sin resultados todavía.</td>
                </tr>
              )}
            </tbody>
          </table>
        </div>
        <div className="upload-header" style={{ marginTop: '16px' }}>
          <div className="progress-text">{totalCount !== null ? `Mostrando ${rows.length} de ${totalCount}` : 'Sin búsqueda activa'}</div>
          <div style={{ display: 'flex', gap: '8px' }}>
            <button type="button" className="link-button" disabled={loading || totalCount === null} onClick={exportResults}>Exportar Excel</button>
            <button type="button" className="link-button" disabled={page <= 1 || loading} onClick={() => runSearch(page - 1)}>Anterior</button>
            <button type="button" className="link-button" disabled={loading || totalCount === null || page * pageSize >= totalCount} onClick={() => runSearch(page + 1)}>Siguiente</button>
          </div>
        </div>
      </section>

      <section className="panel">
        <div className="upload-header">
          <div>
            <p className="eyebrow">Pendientes</p>
            <h2>Códigos a revisar</h2>
            <p className="lead">{pendingCodes.length ? `${pendingCodes.length} códigos detectados` : 'Ejecuta una búsqueda para detectar códigos no catalogados.'}</p>
          </div>
        </div>
        <div className="table-wrap">
          <table className="uploads-table">
            <thead>
              <tr>
                <th>Campo</th>
                <th>Código</th>
                <th>Glosa</th>
              </tr>
            </thead>
            <tbody>
              {pendingCodes.length ? pendingCodes.map((item, index) => (
                <tr key={`${item.campo}-${item.codigo}-${index}`}>
                  <td><span className={`pending-badge ${pendingTone(item.campo)}`}>{pendingLabel(item.campo)}</span></td>
                  <td>{item.codigo}</td>
                  <td>{item.glosa || 'Sin catálogo'}</td>
                </tr>
              )) : (
                <tr>
                  <td colSpan={3}>Sin pendientes detectados todavía.</td>
                </tr>
              )}
            </tbody>
          </table>
        </div>
      </section>
    </main>
  )
}
