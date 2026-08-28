import Link from 'next/link'

export default function TopNav() {
  return (
    <nav className="top-nav">
      <Link href="/dashboard">Dashboard</Link>
      <Link href="/consultas">Consultas</Link>
      <Link href="/reportes">Reportes</Link>
      <Link href="/login">Login</Link>
    </nav>
  )
}
