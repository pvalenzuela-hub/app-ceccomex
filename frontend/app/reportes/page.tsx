"use client"

import { useEffect, useState } from 'react'
import TopNav from '../components/top-nav'

type Report = {
  id: number
  nombre_archivo: string
  rubro: string
  periodo_anio: number
  periodo_mes: number
  hoja_base: string
  es_acumulado: boolean
  total_registros: number
}

type Detail = {
  nro_linea: number
  rut: string
  dv: string
  importador_nombre: string
  aduana_nombre: string
  pais_origen_nombre: string
  partida_arancelaria_codigo: string
  mercaderia: string
  valor_cif: string
}

export default function ReportesPage() {
  const apiBaseUrl = process.env.NEXT_PUBLIC_API_BASE_URL ?? 'http://127.0.0.1:8000'
  const [reports, setReports] = useState<Report[]>([])
  const [details, setDetails] = useState<Detail[]>([])
  const [selected, setSelected] = useState<Report | null>(null)
  const [message, setMessage] = useState('Cargando reportes sectoriales...')

  useEffect(() => {
    fetch(`${apiBaseUrl}/api/reportes/`, { cache: 'no-store' })
      .then((response) => response.json())
      .then((data) => {
        const nextReports = Array.isArray(data) ? data : []
        setReports(nextReports)
        setMessage(nextReports.length ? `${nextReports.length} reportes disponibles.` : 'No hay reportes cargados todavía.')
      })
      .catch(() => setMessage('No se pudo conectar con el backend.'))
  }, [apiBaseUrl])

  async function selectReport(report: Report) {
    setSelected(report)
    setDetails([])
    setMessage(`Cargando ${report.rubro}...`)
    try {
      const response = await fetch(`${apiBaseUrl}/api/reportes/${report.id}/`, { cache: 'no-store' })
      const data = await response.json()
      setDetails(Array.isArray(data) ? data : [])
      setMessage(`${report.total_registros} filas registradas. Mostrando las primeras ${Array.isArray(data) ? data.length : 0}.`)
    } catch {
      setMessage('No se pudo cargar el detalle del reporte.')
    }
  }

  return (
    <main className="page dashboard-page">
      <TopNav />
      <section className="dashboard-hero">
        <div>
          <p className="eyebrow">Referencia analítica</p>
          <h1>Reportes sectoriales</h1>
          <p className="lead">Bases enriquecidas por rubro, separadas de la importación cruda y vinculadas a importadores probables.</p>
        </div>
        <div className="dashboard-meta"><div className="meta-chip">{reports.length} reportes</div></div>
      </section>

      <section className="panel">
        <p className="login-message">{message}</p>
        <div className="table-wrap">
          <table className="uploads-table">
            <thead><tr><th>Rubro</th><th>Período</th><th>Tipo</th><th>Hoja</th><th>Registros</th><th>Archivo</th></tr></thead>
            <tbody>
              {reports.length ? reports.map((report) => (
                <tr key={report.id} onClick={() => selectReport(report)} className={selected?.id === report.id ? 'row-selected' : ''}>
                  <td>{report.rubro}</td><td>{report.periodo_mes}/{report.periodo_anio}</td><td>{report.es_acumulado ? 'Acumulado' : 'Mensual'}</td><td>{report.hoja_base}</td><td>{report.total_registros}</td><td>{report.nombre_archivo}</td>
                </tr>
              )) : <tr><td colSpan={6}>No hay reportes cargados.</td></tr>}
            </tbody>
          </table>
        </div>
      </section>

      <section className="panel">
        <div className="upload-header"><div><p className="eyebrow">Detalle</p><h2>{selected ? selected.rubro : 'Selecciona un reporte'}</h2></div></div>
        <div className="table-wrap">
          <table className="uploads-table">
            <thead><tr><th>RUT</th><th>Probable importador</th><th>Aduana</th><th>País origen</th><th>Partida</th><th>Mercadería</th><th>CIF</th></tr></thead>
            <tbody>
              {details.length ? details.map((row) => <tr key={row.nro_linea}><td>{row.rut}-{row.dv}</td><td>{row.importador_nombre || 'Sin referencia'}</td><td>{row.aduana_nombre}</td><td>{row.pais_origen_nombre}</td><td>{row.partida_arancelaria_codigo}</td><td>{row.mercaderia}</td><td>{row.valor_cif}</td></tr>) : <tr><td colSpan={7}>Selecciona un reporte para ver su base.</td></tr>}
            </tbody>
          </table>
        </div>
      </section>
    </main>
  )
}
