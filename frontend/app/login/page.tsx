"use client"

import Link from 'next/link'
import { FormEvent, useEffect, useState } from 'react'
import TopNav from '../components/top-nav'

export default function LoginPage() {
  const [backendStatus, setBackendStatus] = useState('Verificando...')
  const [loginMessage, setLoginMessage] = useState('')
  const [loginLoading, setLoginLoading] = useState(false)
  const apiBaseUrl = process.env.NEXT_PUBLIC_API_BASE_URL ?? 'http://127.0.0.1:8000'

  useEffect(() => {
    fetch(`${apiBaseUrl}/api/health/`, { cache: 'no-store' })
      .then(async (res) => {
        const data = await res.json()
        setBackendStatus(data.status === 'ok' ? 'Backend conectado' : 'Backend no responde')
      })
      .catch(() => setBackendStatus('Backend no disponible en ' + apiBaseUrl))
  }, [apiBaseUrl])

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    setLoginLoading(true)
    setLoginMessage('')
    const formData = new FormData(event.currentTarget)
    try {
      const response = await fetch(`${apiBaseUrl}/api/core/login-check/`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          username: String(formData.get('username') || ''),
          password: String(formData.get('password') || ''),
        }),
      })
      const data = await response.json().catch(() => ({}))
      if (!response.ok || !data.ok) {
        setLoginMessage(data.message ?? `No se pudo iniciar sesión (${response.status})`)
        return
      }
      localStorage.setItem('cec_user', JSON.stringify(data.user))
      window.location.href = '/dashboard'
    } catch {
      setLoginMessage(`No se pudo conectar con el backend en ${apiBaseUrl}`)
    } finally {
      setLoginLoading(false)
    }
  }

  return (
    <main className="page login-page">
      <TopNav />
      <section className="topbar">
        <div>
          <p className="eyebrow">CEC COMEX Platform</p>
          <h1>Acceso al sistema</h1>
        </div>
        <div className="status-pill">{backendStatus}</div>
      </section>

      <section className="hero-grid login-grid">
        <article className="panel login-panel">
          <h2>Iniciar sesión</h2>
          <p className="lead">Ingresa con tu usuario de Django para acceder al panel interno.</p>
          <form className="login-form" onSubmit={handleSubmit}>
            <label>
              Usuario
              <input name="username" placeholder="admin" autoComplete="username" />
            </label>
            <label>
              Contraseña
              <input name="password" type="password" placeholder="••••••••" autoComplete="current-password" />
            </label>
            <button type="submit" disabled={loginLoading}>{loginLoading ? 'Entrando...' : 'Entrar'}</button>
          </form>
          {loginMessage ? <p className="login-message">{loginMessage}</p> : null}
        </article>

        <article className="panel">
          <h2>Estado</h2>
          <p className="lead">{backendStatus}</p>
          <p><Link href="/">Ir al panel interno</Link></p>
        </article>
      </section>
    </main>
  )
}
