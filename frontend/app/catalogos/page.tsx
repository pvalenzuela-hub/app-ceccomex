"use client"

import { FormEvent, useEffect, useState } from 'react'
import TopNav from '../components/top-nav'

type CatalogoCodigo = {
  id: number
  grupo: string
  codigo: string
  glosa: string
  vigente: boolean
  origen: string
  pendiente_revision: boolean
  observacion: string
}

type Partida = Omit<CatalogoCodigo, 'grupo' | 'pendiente_revision'>
type PerfilImportador = { id: number; rut: string; dv: string; nombre: string; total_evidencias: number; primer_periodo_anio: number; primer_periodo_mes: number; ultimo_periodo_anio: number; ultimo_periodo_mes: number; aranceles_json: Array<{ valor: string; ocurrencias: number }>; rubros_json: Array<{ valor: string; ocurrencias: number }> }

const emptyCode = { grupo: 'ADUANA', codigo: '', glosa: '', vigente: true, origen: 'MANUAL', pendiente_revision: false, observacion: '' }
const emptyPartida = { codigo: '', glosa: '', vigente: true, origen: 'MANUAL', observacion: '' }
const catalogGroups = [
  ['aduanas', 'Aduanas'], ['bancos_comerciales', 'Bancos comerciales'], ['clausulas_compra_venta', 'Cláusulas compra/venta'], ['articulos_denuncia', 'Artículos de denuncia'], ['comunas', 'Comunas'], ['formas_pago', 'Formas de pago'], ['formas_pago_gravamen', 'Pago gravámenes'], ['modalidades_venta', 'Modalidades de venta'], ['monedas', 'Monedas'], ['paises', 'Países'], ['puertos', 'Puertos'], ['regiones', 'Regiones'], ['tipos_bulto', 'Tipos de bulto'], ['tipos_cuenta', 'Tipos de cuenta'], ['tipos_carga', 'Tipos de carga'], ['tipos_operacion_din', 'Tipos operación DIN'], ['unidades_medida', 'Unidades de medida'], ['via_transporte', 'Vías de transporte'], ['origen_divisas', 'Origen divisas'], ['vistos_buenos', 'Vistos buenos'], ['regimen_importacion', 'Régimen importación'], ['claves_economicas', 'Claves económicas'], ['zonas_economicas', 'Zonas económicas'], ['claves_economicas_exportacion', 'Claves económicas exportación'],
]

function csrfToken() {
  return document.cookie.split('; ').find((cookie) => cookie.startsWith('csrftoken='))?.split('=')[1] ?? ''
}

export default function CatalogosPage() {
  const apiBaseUrl = process.env.NEXT_PUBLIC_API_BASE_URL ?? 'http://127.0.0.1:8000'
  const [section, setSection] = useState<'codigos' | 'partidas' | 'perfiles'>('codigos')
  const [rows, setRows] = useState<Array<CatalogoCodigo | Partida | PerfilImportador>>([])
  const [totalRows, setTotalRows] = useState(0)
  const [page, setPage] = useState(1)
  const [search, setSearch] = useState('')
  const [group, setGroup] = useState('')
  const [codeForm, setCodeForm] = useState(emptyCode)
  const [partidaForm, setPartidaForm] = useState(emptyPartida)
  const [editingId, setEditingId] = useState<number | null>(null)
  const [message, setMessage] = useState('')
  const [loading, setLoading] = useState(true)

  async function loadCatalogs(nextPage = page, nextSearch = search) {
    setLoading(true)
    try {
      const endpoint = section === 'perfiles' ? `${apiBaseUrl}/api/reportes/perfiles-importadores/?page=${nextPage}&search=${encodeURIComponent(nextSearch)}` : `${apiBaseUrl}/api/catalogos/${section}/?page=${nextPage}&page_size=25&search=${encodeURIComponent(nextSearch)}&grupo=${encodeURIComponent(group)}`
      const response = await fetch(endpoint, { cache: 'no-store', credentials: 'include' })
      const data = response.ok ? await response.json() : { count: 0, results: [] }
      setRows(Array.isArray(data.results) ? data.results : [])
      setTotalRows(Number(data.count ?? 0))
    } catch {
      setMessage('No se pudieron cargar los catálogos.')
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => { fetch(`${apiBaseUrl}/api/health/`, { credentials: 'include' }) }, [apiBaseUrl])
  useEffect(() => { loadCatalogs() }, [section, page])

  function resetForm() {
    setEditingId(null)
    setCodeForm(emptyCode)
    setPartidaForm(emptyPartida)
  }

  async function save(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    const isCodes = section === 'codigos'
    const endpoint = `${apiBaseUrl}/api/catalogos/${isCodes ? 'codigos' : 'partidas'}/${editingId ? `${editingId}/` : ''}`
    const response = await fetch(endpoint, {
      method: editingId ? 'PUT' : 'POST',
      credentials: 'include',
      headers: { 'Content-Type': 'application/json', 'X-CSRFToken': csrfToken() },
      body: JSON.stringify(isCodes ? codeForm : partidaForm),
    })
    if (!response.ok) {
      setMessage('No se pudo guardar. Verifica que el código no esté duplicado.')
      return
    }
    setMessage(editingId ? 'Catálogo actualizado.' : 'Catálogo creado.')
    resetForm()
    loadCatalogs(page)
  }

  async function remove(id: number) {
    if (!window.confirm('¿Eliminar este registro?')) return
    const endpoint = `${apiBaseUrl}/api/catalogos/${section}/${id}/`
    const response = await fetch(endpoint, { method: 'DELETE', credentials: 'include', headers: { 'X-CSRFToken': csrfToken() } })
    if (!response.ok) {
      setMessage('No se pudo eliminar el registro porque puede estar en uso.')
      return
    }
    setMessage('Registro eliminado.')
    if (editingId === id) resetForm()
    loadCatalogs(page)
  }

  const totalPages = Math.max(1, Math.ceil(totalRows / 25))

  function changeSection(nextSection: 'codigos' | 'partidas' | 'perfiles') {
    setSection(nextSection)
    setRows([])
    setTotalRows(0)
    setPage(1)
    setSearch('')
    setGroup('')
    resetForm()
  }

  function searchCatalogs(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    setPage(1)
    loadCatalogs(1)
  }

  return (
    <main className={`page catalog-page catalog-${section}`}>
      <TopNav />
      <section className="catalog-heading">
        <div>
          <p className="eyebrow">Administración</p>
          <h1>Catálogos base</h1>
          <p className="lead">Mantén códigos, glosas y partidas disponibles antes de procesar importaciones.</p>
        </div>
        <div className="catalog-tabs">
           <button className={section === 'codigos' ? 'is-active' : ''} onClick={() => changeSection('codigos')}>Códigos generales</button>
           <button className={section === 'partidas' ? 'is-active' : ''} onClick={() => changeSection('partidas')}>Partidas arancelarias</button>
           <button className={section === 'perfiles' ? 'is-active' : ''} onClick={() => changeSection('perfiles')}>Perfiles importadores</button>
        </div>
      </section>

      <section className="catalog-layout">
        {section !== 'perfiles' ? <form className="panel catalog-form" onSubmit={save}>
          <div className="upload-header"><h2>{editingId ? 'Editar registro' : 'Nuevo registro'}</h2><button className="link-button" type="button" onClick={resetForm}>Limpiar</button></div>
          {section === 'codigos' ? <>
            <label>Grupo<select value={codeForm.grupo} onChange={(event) => setCodeForm({ ...codeForm, grupo: event.target.value })} disabled={Boolean(editingId)} required>{catalogGroups.map(([value, label]) => <option key={value} value={value}>{label}</option>)}</select>{editingId ? <small>El grupo no se puede modificar después de crear el código.</small> : null}</label>
            <label>Código<input value={codeForm.codigo} onChange={(event) => setCodeForm({ ...codeForm, codigo: event.target.value })} required /></label>
            <label>Glosa<textarea rows={3} value={codeForm.glosa} onChange={(event) => setCodeForm({ ...codeForm, glosa: event.target.value })} /></label>
            <label>Origen<input value={codeForm.origen} onChange={(event) => setCodeForm({ ...codeForm, origen: event.target.value.toUpperCase() })} required /></label>
            <label>Observación<textarea rows={2} value={codeForm.observacion} onChange={(event) => setCodeForm({ ...codeForm, observacion: event.target.value })} /></label>
            <fieldset className="status-choice"><legend>Estado</legend><label><input type="radio" name="codigo-estado" checked={codeForm.vigente} onChange={() => setCodeForm({ ...codeForm, vigente: true, pendiente_revision: false })} /> Vigente</label><label><input type="radio" name="codigo-estado" checked={codeForm.pendiente_revision} onChange={() => setCodeForm({ ...codeForm, vigente: false, pendiente_revision: true })} /> Pendiente de revisión</label></fieldset>
          </> : <>
            <label>Código arancelario<input value={partidaForm.codigo} onChange={(event) => setPartidaForm({ ...partidaForm, codigo: event.target.value })} required /></label>
            <label>Glosa<textarea rows={3} value={partidaForm.glosa} onChange={(event) => setPartidaForm({ ...partidaForm, glosa: event.target.value })} required /></label>
            <label>Origen<input value={partidaForm.origen} onChange={(event) => setPartidaForm({ ...partidaForm, origen: event.target.value.toUpperCase() })} required /></label>
            <label>Observación<textarea rows={2} value={partidaForm.observacion} onChange={(event) => setPartidaForm({ ...partidaForm, observacion: event.target.value })} /></label>
            <label className="check-label"><input type="checkbox" checked={partidaForm.vigente} onChange={(event) => setPartidaForm({ ...partidaForm, vigente: event.target.checked })} />Vigente</label>
          </>}
          <button className="catalog-save" type="submit">{editingId ? 'Guardar cambios' : 'Crear registro'}</button>
          {message ? <p className="login-message">{message}</p> : null}
        </form> : null}

        <section className="panel catalog-table-panel">
          <div className="catalog-list-header"><div><p className="eyebrow">{section === 'perfiles' ? 'Base histórica' : 'Registros'}</p><h2>{loading ? 'Cargando...' : `${totalRows.toLocaleString('es-CL')} disponibles`}</h2></div><button className="link-button" onClick={() => loadCatalogs()}>Actualizar</button></div>
          <form className="catalog-search" onSubmit={searchCatalogs}>{section === 'codigos' ? <select value={group} onChange={(event) => setGroup(event.target.value)}><option value="">Todos los catálogos</option>{catalogGroups.map(([value, label]) => <option key={value} value={value}>{label}</option>)}</select> : null}<input value={search} onChange={(event) => setSearch(event.target.value)} placeholder={section === 'perfiles' ? 'Buscar por RUT, DV o nombre' : section === 'partidas' ? 'Código desde el inicio o texto de glosa' : 'Buscar por código o glosa'} /><button type="submit">Buscar</button></form>
          {section === 'perfiles' ? <div className="table-wrap"><table className="uploads-table"><thead><tr><th>RUT</th><th>Importador</th><th>Evidencias</th><th>Último período</th><th>Aranceles frecuentes</th></tr></thead><tbody>{(rows as PerfilImportador[]).map((profile) => <tr key={profile.id}><td>{profile.rut}-{profile.dv}</td><td><strong>{profile.nombre}</strong><br /><small>{(profile.rubros_json ?? []).slice(0, 2).map((rubro) => rubro.valor).join(' · ')}</small></td><td>{profile.total_evidencias}</td><td>{profile.ultimo_periodo_mes}/{profile.ultimo_periodo_anio}</td><td>{(profile.aranceles_json ?? []).slice(0, 3).map((arancel) => arancel.valor).join(', ') || '-'}</td></tr>)}{!loading && rows.length === 0 ? <tr><td colSpan={5}>No se encontraron perfiles.</td></tr> : null}</tbody></table></div> : <div className="table-wrap"><table className="uploads-table"><thead><tr>{section === 'codigos' ? <th>Grupo</th> : null}<th>Código</th><th>Glosa</th><th>Estado</th><th /></tr></thead><tbody>{rows.map((row) => <tr key={row.id}><td>{section === 'codigos' ? (row as CatalogoCodigo).grupo : null}</td><td>{(row as CatalogoCodigo).codigo}</td><td>{(row as CatalogoCodigo).glosa || '-'}</td><td>{(row as CatalogoCodigo).vigente ? 'Vigente' : 'Inactivo'}</td><td className="catalog-actions"><button onClick={() => { setEditingId(row.id); if (section === 'codigos') setCodeForm(row as CatalogoCodigo); else setPartidaForm(row as Partida) }}>Editar</button><button onClick={() => remove(row.id)}>Eliminar</button></td></tr>)}{!loading && rows.length === 0 ? <tr><td colSpan={section === 'codigos' ? 5 : 4}>No se encontraron registros.</td></tr> : null}</tbody></table></div>}
          <footer className="catalog-pagination"><span>Página {page} de {totalPages}</span><div><button disabled={page === 1} onClick={() => setPage(page - 1)}>Anterior</button><button disabled={page === totalPages} onClick={() => setPage(page + 1)}>Siguiente</button></div></footer>
        </section>
      </section>
    </main>
  )
}
