"use client"

import { FormEvent, useEffect, useState } from 'react'

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
        credentials: 'include',
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
    <main className="login-page">
      <section className="login-brand-panel">
        <div className="login-brand-header"><img src="https://cec.cl/wp-content/uploads/2024/10/logo-1024x658.png" alt="CEC Comercio Exterior y Consultoría" /><span>COMEX PLATFORM</span></div>
        <div className="login-brand-copy"><p>Inteligencia para comercio exterior</p><h1>Información clara para decisiones que cruzan fronteras.</h1><div className="login-brand-line" /><span>Importaciones · Exportaciones · Análisis de mercado</span></div>
        <small>CEC S.A. · Santiago, Chile</small>
      </section>

      <section className="login-access-panel">
        <div className="login-access-content">
          <div className="login-status"><i />{backendStatus}</div>
          <p className="eyebrow">Área privada</p>
          <h2>Bienvenido</h2>
          <p className="lead">Ingresa tus credenciales para acceder a CEC COMEX Platform.</p>
          <form className="login-form" onSubmit={handleSubmit}>
            <label>
              Usuario
              <input required name="username" placeholder="Tu usuario" autoComplete="username" />
            </label>
            <label>
              Contraseña
              <input required name="password" type="password" placeholder="••••••••" autoComplete="current-password" />
            </label>
            <button type="submit" disabled={loginLoading}>{loginLoading ? 'Validando acceso...' : 'Ingresar a la plataforma'}<span>→</span></button>
          </form>
          {loginMessage ? <p className="login-message">{loginMessage}</p> : null}
          <p className="login-help">Acceso exclusivo para usuarios autorizados.</p>
        </div>
      </section>
    </main>
  )
}
