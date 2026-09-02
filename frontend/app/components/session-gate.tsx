"use client"

import { ReactNode, useEffect, useState } from 'react'
import { usePathname, useRouter } from 'next/navigation'

export default function SessionGate({ children }: { children: ReactNode }) {
  const pathname = usePathname()
  const router = useRouter()
  const [ready, setReady] = useState(pathname === '/login')
  const api = process.env.NEXT_PUBLIC_API_BASE_URL ?? 'http://127.0.0.1:8000'

  useEffect(() => {
    if (pathname === '/login') { setReady(true); return }
    setReady(false)
    fetch(`${api}/api/core/sesion/`, { credentials: 'include' }).then(async (response) => {
      if (!response.ok) throw new Error('Sesión no iniciada')
      localStorage.setItem('cec_user', JSON.stringify(await response.json()))
      setReady(true)
    }).catch(() => {
      localStorage.removeItem('cec_user')
      router.replace('/login')
    })
  }, [api, pathname, router])

  if (!ready) return <main className="page"><section className="panel dashboard-loading"><p className="eyebrow">CEC COMEX Platform</p><h1>Validando sesión</h1></section></main>
  return <>{children}</>
}
