import type { Metadata } from 'next'
import type { ReactNode } from 'react'
import './globals.css'
import SessionGate from './components/session-gate'

export const metadata: Metadata = {
  title: 'CEC COMEX Platform',
  description: 'Plataforma de ingesta y consulta para importaciones y exportaciones',
}

export default function RootLayout({ children }: { children: ReactNode }) {
  return (
    <html lang="es">
      <body><SessionGate>{children}</SessionGate></body>
    </html>
  )
}
