"use client"

import Link from 'next/link'
import { usePathname, useRouter } from 'next/navigation'
import { useEffect, useState } from 'react'

export default function TopNav() {
  const router = useRouter()
  const pathname = usePathname()
  const api = process.env.NEXT_PUBLIC_API_BASE_URL ?? 'http://127.0.0.1:8000'
  const [isSuperuser, setIsSuperuser] = useState(false)
  const [connectedUsers, setConnectedUsers] = useState<number | null>(null)

  useEffect(() => { setIsSuperuser(JSON.parse(localStorage.getItem('cec_user') ?? '{}').is_superuser === true) }, [])

  useEffect(() => {
    if (!isSuperuser) return
    const loadConnectedUsers = () => fetch(`${api}/api/core/usuarios-conectados/`, { credentials: 'include' }).then(async (response) => response.ok ? setConnectedUsers((await response.json()).conectados) : null)
    void loadConnectedUsers()
    const timer = window.setInterval(loadConnectedUsers, 30000)
    return () => window.clearInterval(timer)
  }, [api, isSuperuser])

  async function logout() {
    await fetch(`${api}/api/health/`, { credentials: 'include' })
    const csrfToken = document.cookie.split('; ').find((cookie) => cookie.startsWith('csrftoken='))?.split('=')[1] ?? ''
    await fetch(`${api}/api/core/logout/`, { method: 'POST', credentials: 'include', headers: { 'X-CSRFToken': csrfToken } })
    localStorage.removeItem('cec_user')
    router.replace('/login')
  }

  if (pathname === '/login') return null

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
      {isSuperuser ? <div className="nav-presence"><i />{connectedUsers ?? '…'} conectados</div> : null}
      <button className="nav-login link-button" type="button" onClick={() => void logout()}>Salir</button>
    </nav>
  )
}
