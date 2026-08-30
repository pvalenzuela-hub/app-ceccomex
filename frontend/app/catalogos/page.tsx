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

const emptyCode = { grupo: 'ADUANA', codigo: '', glosa: '', vigente: true, origen: 'MANUAL', pendiente_revision: false, observacion: '' }
const emptyPartida = { codigo: '', glosa: '', vigente: true, origen: 'MANUAL', observacion: '' }

function csrfToken() {
  return document.cookie.split('; ').find((cookie) => cookie.startsWith('csrftoken='))?.split('=')[1] ?? ''
}

export default function CatalogosPage() {
  const apiBaseUrl = process.env.NEXT_PUBLIC_API_BASE_URL ?? 'http://127.0.0.1:8000'
  const [section, setSection] = useState<'codigos' | 'partidas'>('codigos')
  const [codes, setCodes] = useState<CatalogoCodigo[]>([])
  const [partidas, setPartidas] = useState<Partida[]>([])
  const [codeForm, setCodeForm] = useState(emptyCode)
  const [partidaForm, setPartidaForm] = useState(emptyPartida)
  const [editingId, setEditingId] = useState<number | null>(null)
  const [message, setMessage] = useState('')
  const [loading, setLoading] = useState(true)

  async function loadCatalogs() {
    setLoading(true)
    try {
      const [codesResponse, partidasResponse] = await Promise.all([
        fetch(`${apiBaseUrl}/api/catalogos/codigos/`, { cache: 'no-store' }),
        fetch(`${apiBaseUrl}/api/catalogos/partidas/`, { cache: 'no-store' }),
      ])
      setCodes(codesResponse.ok ? await codesResponse.json() : [])
      setPartidas(partidasResponse.ok ? await partidasResponse.json() : [])
    } catch {
      setMessage('No se pudieron cargar los catálogos.')
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    fetch(`${apiBaseUrl}/api/health/`, { credentials: 'include' }).finally(loadCatalogs)
  }, [])

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
    loadCatalogs()
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
    loadCatalogs()
  }

  const rows = section === 'codigos' ? codes : partidas

  return (
    <main className="page catalog-page">
      <TopNav />
      <section className="catalog-heading">
        <div>
          <p className="eyebrow">Administración</p>
          <h1>Catálogos base</h1>
          <p className="lead">Mantén códigos, glosas y partidas disponibles antes de procesar importaciones.</p>
        </div>
        <div className="catalog-tabs">
          <button className={section === 'codigos' ? 'is-active' : ''} onClick={() => { setSection('codigos'); resetForm() }}>Códigos generales</button>
          <button className={section === 'partidas' ? 'is-active' : ''} onClick={() => { setSection('partidas'); resetForm() }}>Partidas arancelarias</button>
        </div>
      </section>

      <section className="catalog-layout">
        <form className="panel catalog-form" onSubmit={save}>
          <div className="upload-header"><h2>{editingId ? 'Editar registro' : 'Nuevo registro'}</h2><button className="link-button" type="button" onClick={resetForm}>Limpiar</button></div>
          {section === 'codigos' ? <>
            <label>Grupo<input value={codeForm.grupo} onChange={(event) => setCodeForm({ ...codeForm, grupo: event.target.value.toUpperCase() })} required /></label>
            <label>Código<input value={codeForm.codigo} onChange={(event) => setCodeForm({ ...codeForm, codigo: event.target.value })} required /></label>
            <label>Glosa<textarea rows={3} value={codeForm.glosa} onChange={(event) => setCodeForm({ ...codeForm, glosa: event.target.value })} /></label>
            <label>Origen<input value={codeForm.origen} onChange={(event) => setCodeForm({ ...codeForm, origen: event.target.value.toUpperCase() })} required /></label>
            <label>Observación<textarea rows={2} value={codeForm.observacion} onChange={(event) => setCodeForm({ ...codeForm, observacion: event.target.value })} /></label>
            <label className="check-label"><input type="checkbox" checked={codeForm.vigente} onChange={(event) => setCodeForm({ ...codeForm, vigente: event.target.checked })} />Vigente</label>
            <label className="check-label"><input type="checkbox" checked={codeForm.pendiente_revision} onChange={(event) => setCodeForm({ ...codeForm, pendiente_revision: event.target.checked })} />Pendiente de revisión</label>
          </> : <>
            <label>Código arancelario<input value={partidaForm.codigo} onChange={(event) => setPartidaForm({ ...partidaForm, codigo: event.target.value })} required /></label>
            <label>Glosa<textarea rows={3} value={partidaForm.glosa} onChange={(event) => setPartidaForm({ ...partidaForm, glosa: event.target.value })} required /></label>
            <label>Origen<input value={partidaForm.origen} onChange={(event) => setPartidaForm({ ...partidaForm, origen: event.target.value.toUpperCase() })} required /></label>
            <label>Observación<textarea rows={2} value={partidaForm.observacion} onChange={(event) => setPartidaForm({ ...partidaForm, observacion: event.target.value })} /></label>
            <label className="check-label"><input type="checkbox" checked={partidaForm.vigente} onChange={(event) => setPartidaForm({ ...partidaForm, vigente: event.target.checked })} />Vigente</label>
          </>}
          <button className="catalog-save" type="submit">{editingId ? 'Guardar cambios' : 'Crear registro'}</button>
          {message ? <p className="login-message">{message}</p> : null}
        </form>

        <section className="panel catalog-table-panel">
          <div className="upload-header"><div><p className="eyebrow">Registros</p><h2>{loading ? 'Cargando...' : `${rows.length} disponibles`}</h2></div><button className="link-button" onClick={loadCatalogs}>Actualizar</button></div>
          <div className="table-wrap"><table className="uploads-table"><thead><tr>{section === 'codigos' ? <th>Grupo</th> : null}<th>Código</th><th>Glosa</th><th>Estado</th><th /></tr></thead><tbody>
            {rows.map((row) => <tr key={row.id}><td>{section === 'codigos' ? (row as CatalogoCodigo).grupo : null}</td><td>{row.codigo}</td><td>{row.glosa || '-'}</td><td>{row.vigente ? 'Vigente' : 'Inactivo'}</td><td className="catalog-actions"><button onClick={() => { setEditingId(row.id); if (section === 'codigos') setCodeForm(row as CatalogoCodigo); else setPartidaForm(row as Partida) }}>Editar</button><button onClick={() => remove(row.id)}>Eliminar</button></td></tr>)}
            {!loading && rows.length === 0 ? <tr><td colSpan={section === 'codigos' ? 5 : 4}>Aún no hay registros.</td></tr> : null}
          </tbody></table></div>
        </section>
      </section>
    </main>
  )
}
