"use client"

import Link from 'next/link'
import { useRouter } from 'next/navigation'
import { useEffect, useState } from 'react'

export default function TopNav() {
  const router = useRouter()
  const api = process.env.NEXT_PUBLIC_API_BASE_URL ?? 'http://127.0.0.1:8000'
  const [isSuperuser, setIsSuperuser] = useState(false)

  useEffect(() => { setIsSuperuser(JSON.parse(localStorage.getItem('cec_user') ?? '{}').is_superuser === true) }, [])

  async function logout() {
    await fetch(`${api}/api/health/`, { credentials: 'include' })
    const csrfToken = document.cookie.split('; ').find((cookie) => cookie.startsWith('csrftoken='))?.split('=')[1] ?? ''
    await fetch(`${api}/api/core/logout/`, { method: 'POST', credentials: 'include', headers: { 'X-CSRFToken': csrfToken } })
    localStorage.removeItem('cec_user')
    router.replace('/login')
  }

  return (
    <nav className="top-nav">
      <p className="nav-brand">CEC COMEX</p>
      <div className="nav-links">
        <Link href="/dashboard">Dashboard</Link>
        <Link href="/consultas">Consultas</Link>
        <Link href="/informes-importaciones">Informes Importaciones</Link>
        <Link href="/catalogos">Catálogos</Link>
        <Link href="/reportes">Reportes</Link>
        {isSuperuser ? <Link href="/usuarios">Usuarios</Link> : null}
      </div>
      <button className="nav-login link-button" type="button" onClick={() => void logout()}>Salir</button>
    </nav>
  )
}
