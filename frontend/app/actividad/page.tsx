"use client"

import { useEffect, useState } from 'react'
import { useRouter } from 'next/navigation'
import TopNav from '../components/top-nav'

type Periodo = { anio: number; mes: number }
type Detalle = Record<string, unknown> & { periodo_desde?: Periodo; periodo_hasta?: Periodo; filtros?: Record<string, unknown[]>; filtros_columnas?: Record<string, unknown> }
type Registro = { id: number; fecha: string; usuario: string; accion: string; accion_texto: string; modulo: string; detalle: Detalle; ip: string | null }
type Resumen = { usuario_nombre: string; ingresos: number; fallidos: number; consultas: number; excel: number; cargas: number; ultima: string }
type Filtros = { usuario: string; accion: string; modulo: string; desde: string; hasta: string }
type Respuesta = { count: number; pagina: number; paginas: number; results: Registro[]; resumen: Resumen[]; acciones: Record<string, string>; usuarios: string[] }

const MODULOS = ['acceso', 'importaciones', 'exportaciones', 'cargas', 'catalogos', 'usuarios']
const fecha = (value: string) => new Date(value).toLocaleString('es-CL', { dateStyle: 'short', timeStyle: 'short' })
const numero = (value: unknown) => Number(value).toLocaleString('es-CL')
const periodo = (value?: Periodo) => value ? `${String(value.mes).padStart(2, '0')}/${value.anio}` : ''

function describir(detalle: Detalle) {
  const partes: string[] = []
  if (detalle.periodo_desde) partes.push(`${periodo(detalle.periodo_desde)} a ${periodo(detalle.periodo_hasta)}`)
  if (detalle.registros !== undefined) partes.push(`${numero(detalle.registros)} registros`)
  if (detalle.filas !== undefined) partes.push(`${numero(detalle.filas)} filas`)
  const filtros = Object.entries(detalle.filtros ?? {}).map(([key, values]) => `${key}: ${values.length}`)
  if (filtros.length) partes.push(`filtros ${filtros.join(', ')}`)
  const columnas = Object.keys(detalle.filtros_columnas ?? {})
  if (columnas.length) partes.push(`filtro en ${columnas.join(', ')}`)
  for (const key of ['archivo', 'tipo', 'estado', 'rubro', 'tabla', 'registro', 'objetivo']) if (detalle[key]) partes.push(String(detalle[key]))
  if (detalle.duracion_ms !== undefined) partes.push(`${(Number(detalle.duracion_ms) / 1000).toLocaleString('es-CL', { maximumFractionDigits: 1 })} s`)
  return partes.join(' · ')
}

export default function ActividadPage() {
  const router = useRouter()
  const api = process.env.NEXT_PUBLIC_API_BASE_URL ?? 'http://127.0.0.1:8000'
  const [filtros, setFiltros] = useState<Filtros>({ usuario: '', accion: '', modulo: '', desde: '', hasta: '' })
  const [data, setData] = useState<Respuesta | null>(null)
  const [message, setMessage] = useState('')

  function query(next: Filtros, pagina = 1) {
    const params = new URLSearchParams(Object.entries(next).filter(([, value]) => value))
    params.set('pagina', String(pagina))
    return params.toString()
  }

  async function load(next = filtros, pagina = 1) {
    const response = await fetch(`${api}/api/core/actividad/?${query(next, pagina)}`, { credentials: 'include', cache: 'no-store' })
    if (response.status === 403) return router.replace('/dashboard')
    if (!response.ok) return setMessage(`No se pudo cargar la actividad (${response.status}).`)
    setData(await response.json()); setMessage('')
  }

  async function downloadExcel() {
    setMessage('Generando Excel...')
    const response = await fetch(`${api}/api/core/actividad/excel/?${query(filtros)}`, { credentials: 'include' })
    if (!response.ok) return setMessage(`No se pudo generar el Excel (${response.status}).`)
    const url = URL.createObjectURL(await response.blob())
    const link = document.createElement('a'); link.href = url; link.download = 'actividad.xlsx'; link.click(); URL.revokeObjectURL(url)
    setMessage('')
  }

  useEffect(() => {
    const user = JSON.parse(localStorage.getItem('cec_user') ?? '{}')
    if (!user.is_superuser) return router.replace('/dashboard')
    void load()
  }, [])

  function change(field: keyof Filtros, value: string) {
    const next = { ...filtros, [field]: value }
    setFiltros(next); void load(next)
  }

  return <main className="page dashboard-page">
    <TopNav />
    <section className="dashboard-hero"><div><p className="eyebrow">Administración</p><h1>Actividad</h1><p className="lead">Quién usó la plataforma, cuándo y para qué. Se conservan los últimos 12 meses.</p></div><div className="dashboard-meta"><div className="meta-chip">{data ? `${numero(data.count)} registros` : '…'}</div></div></section>
    <section className="panel">
      <div className="catalog-search">
        <select value={filtros.usuario} onChange={(event) => change('usuario', event.target.value)}><option value="">Todos los usuarios</option>{data?.usuarios.map((name) => <option key={name} value={name}>{name}</option>)}</select>
        <select value={filtros.accion} onChange={(event) => change('accion', event.target.value)}><option value="">Todas las acciones</option>{Object.entries(data?.acciones ?? {}).map(([key, label]) => <option key={key} value={key}>{label}</option>)}</select>
        <select value={filtros.modulo} onChange={(event) => change('modulo', event.target.value)}><option value="">Todos los módulos</option>{MODULOS.map((modulo) => <option key={modulo} value={modulo}>{modulo}</option>)}</select>
        <input type="date" aria-label="Desde" value={filtros.desde} onChange={(event) => change('desde', event.target.value)} />
        <input type="date" aria-label="Hasta" value={filtros.hasta} onChange={(event) => change('hasta', event.target.value)} />
        <button type="button" onClick={() => void downloadExcel()} disabled={!data?.count}>Descargar Excel</button>
      </div>
      {message ? <p className="login-message">{message}</p> : null}
    </section>
    <section className="panel">
      <h2>Resumen por usuario</h2>
      <div className="table-wrap"><table className="uploads-table"><thead><tr><th>Usuario</th><th>Ingresos</th><th>Ingresos fallidos</th><th>Consultas</th><th>Excel descargados</th><th>Cargas</th><th>Última actividad</th></tr></thead><tbody>
        {data?.resumen.length ? data.resumen.map((row) => <tr key={row.usuario_nombre}><td>{row.usuario_nombre || 'Sin usuario'}</td><td>{numero(row.ingresos)}</td><td>{numero(row.fallidos)}</td><td>{numero(row.consultas)}</td><td>{numero(row.excel)}</td><td>{numero(row.cargas)}</td><td>{fecha(row.ultima)}</td></tr>) : <tr><td colSpan={7}>Sin actividad para estos filtros.</td></tr>}
      </tbody></table></div>
    </section>
    <section className="panel">
      <h2>Detalle</h2>
      <div className="table-wrap"><table className="uploads-table"><thead><tr><th>Fecha</th><th>Usuario</th><th>Acción</th><th>Módulo</th><th>Detalle</th><th>IP</th></tr></thead><tbody>
        {data?.results.length ? data.results.map((row) => <tr key={row.id}><td>{fecha(row.fecha)}</td><td>{row.usuario}</td><td>{row.accion_texto}</td><td>{row.modulo}</td><td>{describir(row.detalle)}</td><td>{row.ip ?? ''}</td></tr>) : <tr><td colSpan={6}>Sin registros.</td></tr>}
      </tbody></table></div>
      {data && data.paginas > 1 ? <div className="report-pager"><button type="button" disabled={data.pagina <= 1} onClick={() => void load(filtros, data.pagina - 1)}>Anterior</button><span>Página {numero(data.pagina)} de {numero(data.paginas)}</span><button type="button" disabled={data.pagina >= data.paginas} onClick={() => void load(filtros, data.pagina + 1)}>Siguiente</button></div> : null}
    </section>
  </main>
}
