"use client"

import { FormEvent, useEffect, useState } from 'react'
import { useRouter } from 'next/navigation'
import TopNav from '../components/top-nav'

const blocks = [
  {
    title: 'Etapa I',
    text: 'Base visual para validar alcance funcional antes de implementar procesos reales.',
  },
  {
    title: 'Carga documental',
    text: 'Próximamente permitirá cargar ZIP y registrar el archivo para procesamiento.',
  },
  {
    title: 'Estado actual',
    text: 'Sin parsers ni persistencia de negocio. Solo navegación y layout interno.',
  },
]

const modules = ['Carga de ZIP', 'Procesamiento TXT', 'Staging', 'Consultas', 'Excel']

export default function DashboardPage() {
  const router = useRouter()
  const apiBaseUrl = process.env.NEXT_PUBLIC_API_BASE_URL ?? 'http://127.0.0.1:8000'
  const [userName, setUserName] = useState('Invitado')
  const [ready, setReady] = useState(false)
  const [uploads, setUploads] = useState<Array<{ id: number; nombre_archivo: string; tipo_archivo: string; estado: string; creado: string; staging_count?: number }>>([])
  const [selectedUploadId, setSelectedUploadId] = useState<number | null>(null)
  const [stagingRows, setStagingRows] = useState<Array<{ id: number; nro_linea: number; raw_line: string; procesado: boolean }>>([])
  const [stagingLabel, setStagingLabel] = useState('Selecciona una carga para ver su staging.')
  const [lastUploadStatus, setLastUploadStatus] = useState('')
  const [uploadMessage, setUploadMessage] = useState('')
  const [uploadLoading, setUploadLoading] = useState(false)
  const [activeUpload, setActiveUpload] = useState<{ id: number; nombre_archivo: string; estado: string; total_ok: number; total_registros: number; total_procesados?: number; staging_count?: number; observacion?: string } | null>(null)
  const [systemStats, setSystemStats] = useState({
    totalLoads: 0,
    processedLoads: 0,
    processingLoads: 0,
    importRows: null as number | null,
    consultaRows: null as number | null,
  })
  useEffect(() => {
    const raw = localStorage.getItem('cec_user')
    if (!raw) {
      router.replace('/login')
      return
    }

    try {
      const user = JSON.parse(raw) as { username?: string }
      if (!user.username) {
        router.replace('/login')
        return
      }
      setUserName(user.username)
      setReady(true)

      const refreshUploads = async () => {
        try {
          const res = await fetch(`${apiBaseUrl}/api/comercio/archivos/`, { cache: 'no-store' })
          if (!res.ok) return
          const data = await res.json()
          const nextUploads = Array.isArray(data) ? data : []
          setUploads(nextUploads)
          const current = nextUploads.find((item) => item.estado === 'PROCESANDO' && (item.total_procesados ?? 0) > 0) ?? null
          setActiveUpload(current)
          setSystemStats((currentStats) => ({
            ...currentStats,
            totalLoads: nextUploads.length,
            processedLoads: nextUploads.filter((item) => item.estado === 'PROCESADO').length,
            processingLoads: nextUploads.filter((item) => item.estado === 'PROCESANDO').length,
          }))
        } catch {
          setUploads([])
          setActiveUpload(null)
        }
      }

      fetch(`${apiBaseUrl}/api/core/metrics/`, { cache: 'no-store' })
        .then(async (res) => {
          if (!res.ok) return
          const data = await res.json()
          setSystemStats((current) => ({
            ...current,
            importRows: Number(data.importaciones_totales ?? current.importRows ?? 0),
            consultaRows: Number(data.consultas_guardadas ?? current.consultaRows ?? 0),
          }))
        })
        .catch(() => null)

      refreshUploads()
      const timer = window.setInterval(refreshUploads, 5000)
      return () => window.clearInterval(timer)
    } catch {
      router.replace('/login')
    }
  }, [router, apiBaseUrl])

  async function loadStaging(archivoId: number) {
    setSelectedUploadId(archivoId)
    setStagingLabel(`Staging de carga #${archivoId}`)
    try {
      const response = await fetch(`${apiBaseUrl}/api/comercio/archivos/${archivoId}/staging/`, { cache: 'no-store' })
      if (!response.ok) return
      const data = await response.json()
      setStagingRows(Array.isArray(data) ? data : [])
    } catch {
      setStagingRows([])
    }
  }

  function logout() {
    localStorage.removeItem('cec_user')
    router.replace('/login')
  }

  async function handleUpload(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    setUploadLoading(true)
    setUploadMessage('')

    const formData = new FormData(event.currentTarget)
    const file = formData.get('archivo') as File | null
    if (!file) {
      setUploadMessage('Selecciona un archivo ZIP.')
      setUploadLoading(false)
      return
    }
    if (!file.name.toLowerCase().endsWith('.zip')) {
      setUploadMessage('El archivo debe tener extensión .zip.')
      setUploadLoading(false)
      return
    }
    formData.set('nombre_archivo', file.name)

    try {
      const response = await fetch(`${apiBaseUrl}/api/comercio/upload/`, {
        method: 'POST',
        body: formData,
      })
      const data = await response.json()

      if (!response.ok) {
        setUploadMessage(data?.detail ?? JSON.stringify(data) ?? 'No se pudo registrar la carga.')
        return
      }

      setUploadMessage(`Carga registrada: ${data.nombre_archivo}`)
      setLastUploadStatus(`${data.estado} · ${data.total_ok} filas procesadas`)
      const nextUploads = [{ id: data.id, nombre_archivo: data.nombre_archivo, tipo_archivo: data.tipo_archivo, estado: data.estado, creado: data.creado }, ...uploads].slice(0, 20)
      setUploads(nextUploads)
      setSelectedUploadId(data.id)
      event.currentTarget.reset()

      const listResponse = await fetch(`${apiBaseUrl}/api/comercio/archivos/`, { cache: 'no-store' })
      if (listResponse.ok) {
        const listData = await listResponse.json()
        setUploads(Array.isArray(listData) ? listData : [])
      }

      await loadStaging(data.id)
    } catch {
      setUploadMessage('No se pudo conectar con el backend.')
    } finally {
      setUploadLoading(false)
    }
  }

  if (!ready) {
    return (
      <main className="page">
        <section className="panel dashboard-loading">
          <p className="eyebrow">CEC COMEX Platform</p>
          <h1>Cargando panel</h1>
          <p className="lead">Validando sesión y preparando la vista interna.</p>
        </section>
      </main>
    )
  }

  return (
    <main className="page dashboard-page">
      <TopNav />
      <section className="dashboard-hero">
        <div>
          <p className="eyebrow">CEC COMEX Platform</p>
          <h1>Panel interno de Etapa I</h1>
          <p className="lead">Bienvenido, {userName}. Esta es la vista de contexto antes de conectar las operaciones reales.</p>
        </div>
        <div className="dashboard-meta">
          <div className="meta-chip">Sesión local</div>
          <div className="meta-chip">Carga pendiente</div>
          <button className="link-button" type="button" onClick={() => router.push('/consultas')}>Ir a consultas</button>
          <button className="link-button" type="button" onClick={logout}>Cerrar sesión</button>
        </div>
      </section>

      <section className="dashboard-stats">
        <div className="status-card"><span>Cargas</span><strong>{systemStats.totalLoads}</strong></div>
        <div className="status-card"><span>Procesadas</span><strong>{systemStats.processedLoads}</strong></div>
        <div className="status-card"><span>En proceso</span><strong>{systemStats.processingLoads}</strong></div>
        <div className="status-card"><span>Importaciones</span><strong>{systemStats.importRows ?? '...'}</strong></div>
        <div className="status-card"><span>Consultas</span><strong>{systemStats.consultaRows ?? '...'}</strong></div>
      </section>

      {activeUpload ? (
        <section className="panel progress-panel">
          <div className="upload-header">
            <div>
              <p className="eyebrow">Progreso</p>
              <h2>Carga en background</h2>
            </div>
            <div className="progress-pill progress-procesando">{activeUpload.estado}</div>
          </div>
          <div className="progress-body">
            <div>
              <strong>{activeUpload.nombre_archivo}</strong>
              <p className="progress-text">Procesadas en staging: {activeUpload.total_procesados ?? 0}</p>
              <p className="progress-text">Total esperado: {(activeUpload.staging_count ?? activeUpload.total_registros) || '...'}</p>
              <div className="progress-track" aria-hidden="true">
                <div
                  className="progress-fill"
                  style={{
                    width: `${Math.min(100, ((activeUpload.total_procesados ?? 0) / Math.max(1, activeUpload.staging_count ?? activeUpload.total_registros ?? 1)) * 100)}%`,
                  }}
                />
              </div>
              <p className="progress-caption">{Math.min(100, ((activeUpload.total_procesados ?? 0) / Math.max(1, activeUpload.staging_count ?? activeUpload.total_registros ?? 1)) * 100).toFixed(1)}% del staging procesado</p>
            </div>
            <p className="progress-text">{activeUpload.observacion ?? 'Procesando en segundo plano'}</p>
          </div>
        </section>
      ) : null}

      <section className="dashboard-grid">
        <article className="panel accent-panel">
          <h2>Próximo paso</h2>
          <p className="lead">La siguiente iteración incluirá un formulario de carga de ZIP con validación y registro de archivo.</p>
          {lastUploadStatus ? <p>{lastUploadStatus}</p> : null}
        </article>

        <article className="panel">
          <h2>Notas de arquitectura</h2>
          <ul className="info-list">
            <li>Frontend separado del login.</li>
            <li>Sesión local simple para esta etapa.</li>
            <li>Backend con salud y login básico ya activo.</li>
            <li>Operación real todavía no implementada.</li>
          </ul>
        </article>
      </section>

      <section className="panel upload-panel">
        <div className="upload-header">
          <div>
            <p className="eyebrow">Carga documental</p>
            <h2>Subir ZIP de ejemplo</h2>
          </div>
          <div className="meta-chip">Archivo ZIP</div>
        </div>

        <form className="upload-form" onSubmit={handleUpload}>
          <label>
            Tipo de archivo
            <select name="tipo_archivo" defaultValue="IMP">
              <option value="IMP">Importaciones</option>
              <option value="EXP_BASE">Exportaciones Base</option>
              <option value="EXP_BULTO">Exportaciones Bultos</option>
              <option value="EXP_DOC">Exportaciones Documentos de Transporte</option>
            </select>
          </label>
          <label>
            Archivo ZIP
            <input name="archivo" type="file" accept=".zip" />
          </label>
          <label>
            Año
            <input name="periodo_anio" type="number" placeholder="2025" />
          </label>
          <label>
            Mes
            <input name="periodo_mes" type="number" placeholder="1" min="1" max="12" />
          </label>
          <label>
            Observación
            <textarea name="observacion" rows={3} placeholder="Notas de la carga" />
          </label>
          <button type="submit" disabled={uploadLoading}>{uploadLoading ? 'Registrando...' : 'Registrar carga'}</button>
        </form>
        {uploadMessage ? <p className="login-message">{uploadMessage}</p> : null}
      </section>

      <section className="panel">
        <div className="upload-header">
          <div>
            <p className="eyebrow">Historial</p>
            <h2>Cargas recientes</h2>
          </div>
        </div>
        <div className="table-wrap">
          <table className="uploads-table">
            <thead>
              <tr>
                <th>Archivo</th>
                <th>Tipo</th>
                <th>Estado</th>
                <th>Creado</th>
              </tr>
            </thead>
            <tbody>
              {uploads.length ? uploads.map((item) => (
                <tr key={item.id} onClick={() => loadStaging(item.id)} className={selectedUploadId === item.id ? 'row-selected' : ''}>
                  <td>{item.nombre_archivo}</td>
                  <td>{item.tipo_archivo}</td>
                  <td>{item.estado}</td>
                  <td>{new Date(item.creado).toLocaleString('es-CL')}</td>
                </tr>
              )) : (
                <tr>
                  <td colSpan={4}>No hay cargas registradas.</td>
                </tr>
              )}
            </tbody>
          </table>
        </div>
      </section>

      <section className="panel">
        <div className="upload-header">
          <div>
            <p className="eyebrow">Staging</p>
            <h2>Primeras líneas procesadas</h2>
            <p className="lead">{stagingLabel}</p>
          </div>
        </div>
        <div className="table-wrap">
          <table className="uploads-table">
            <thead>
              <tr>
                <th>Línea</th>
                <th>Contenido</th>
                <th>Estado</th>
              </tr>
            </thead>
            <tbody>
              {stagingRows.length ? stagingRows.map((row) => (
                <tr key={row.id}>
                  <td>{row.nro_linea}</td>
                  <td>{row.raw_line}</td>
                  <td>{row.procesado ? 'OK' : 'Pendiente'}</td>
                </tr>
              )) : (
                <tr>
                  <td colSpan={3}>Selecciona una carga para ver su staging.</td>
                </tr>
              )}
            </tbody>
          </table>
        </div>
      </section>

      <section className="dashboard-blocks">
        {blocks.map((block) => (
          <article className="card explain-card" key={block.title}>
            <h2>{block.title}</h2>
            <p>{block.text}</p>
          </article>
        ))}
      </section>

      <section className="dashboard-modules">
        {modules.map((module) => (
          <article className="module-card" key={module}>
            <span>{module}</span>
            <strong>Pendiente</strong>
          </article>
        ))}
      </section>
    </main>
  )
}
