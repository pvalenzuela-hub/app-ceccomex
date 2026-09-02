"use client"

import { FormEvent, useEffect, useState } from 'react'
import { useRouter } from 'next/navigation'
import TopNav from '../components/top-nav'

type User = { id: number; username: string; first_name: string; last_name: string; email: string; is_active: boolean; is_staff: boolean; is_superuser: boolean }

function csrfToken() { return document.cookie.split('; ').find((cookie) => cookie.startsWith('csrftoken='))?.split('=')[1] ?? '' }

export default function UsuariosPage() {
  const router = useRouter()
  const api = process.env.NEXT_PUBLIC_API_BASE_URL ?? 'http://127.0.0.1:8000'
  const [users, setUsers] = useState<User[]>([])
  const [message, setMessage] = useState('')
  const [passwordUser, setPasswordUser] = useState<User | null>(null)

  async function loadUsers() {
    const response = await fetch(`${api}/api/core/usuarios/`, { credentials: 'include' })
    if (response.status === 403) return router.replace('/dashboard')
    if (response.ok) setUsers(await response.json())
  }

  useEffect(() => {
    const user = JSON.parse(localStorage.getItem('cec_user') ?? '{}')
    if (!user.is_superuser) return router.replace('/dashboard')
    void loadUsers()
  }, [])

  async function createUser(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    const form = new FormData(event.currentTarget)
    await fetch(`${api}/api/health/`, { credentials: 'include' })
    const response = await fetch(`${api}/api/core/usuarios/`, { method: 'POST', credentials: 'include', headers: { 'Content-Type': 'application/json', 'X-CSRFToken': csrfToken() }, body: JSON.stringify(Object.fromEntries(form)) })
    const data = await response.json().catch(() => ({}))
    if (!response.ok) return setMessage(data.detail ?? 'No se pudo crear el usuario.')
    event.currentTarget.reset(); setMessage('Usuario creado correctamente.'); await loadUsers()
  }

  async function changePassword(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    if (!passwordUser) return
    const password = String(new FormData(event.currentTarget).get('password') ?? '')
    await fetch(`${api}/api/health/`, { credentials: 'include' })
    const response = await fetch(`${api}/api/core/usuarios/${passwordUser.id}/contrasena/`, { method: 'POST', credentials: 'include', headers: { 'Content-Type': 'application/json', 'X-CSRFToken': csrfToken() }, body: JSON.stringify({ password }) })
    const data = await response.json().catch(() => ({}))
    if (!response.ok) return setMessage(data.detail ?? 'No se pudo cambiar la contraseña.')
    setPasswordUser(null); setMessage(`Contraseña actualizada para ${passwordUser.username}.`)
  }

  return <main className="page dashboard-page"><TopNav /><section className="dashboard-hero"><div><p className="eyebrow">Administración</p><h1>Usuarios y perfiles</h1><p className="lead">Solo los superusuarios pueden administrar accesos.</p></div></section><section className="report-layout"><section className="panel"><h2>Crear usuario</h2><form className="login-form" onSubmit={createUser}><label>Usuario<input required name="username" /></label><label>Nombre<input name="first_name" /></label><label>Apellido<input name="last_name" /></label><label>Correo<input name="email" type="email" /></label><label>Contraseña<input required minLength={8} name="password" type="password" /></label><label><input name="is_staff" type="checkbox" /> Acceso administrativo Django</label><button type="submit">Crear usuario</button></form>{message ? <p className="login-message">{message}</p> : null}</section><section className="panel"><h2>Usuarios existentes</h2><div className="column-picker">{users.map((user) => <div key={user.id}><p><strong>{user.username}</strong> · {[user.first_name, user.last_name].filter(Boolean).join(' ') || 'Sin nombre'} · {user.is_superuser ? 'Superuser' : user.is_staff ? 'Staff' : 'Usuario'} · {user.is_active ? 'Activo' : 'Inactivo'}</p><button type="button" className="link-button" onClick={() => setPasswordUser(user)}>Cambiar contraseña</button></div>)}</div></section></section>{passwordUser ? <div className="modal-backdrop"><section className="modal"><h2>Cambiar contraseña</h2><p>Usuario: <strong>{passwordUser.username}</strong></p><form className="login-form" onSubmit={changePassword}><label>Nueva contraseña<input required minLength={8} name="password" type="password" autoFocus /></label><div><button type="submit">Guardar contraseña</button><button type="button" className="link-button" onClick={() => setPasswordUser(null)}>Cancelar</button></div></form></section></div> : null}</main>
}
