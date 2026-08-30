import Link from 'next/link'

export default function TopNav() {
  return (
    <nav className="top-nav">
      <p className="nav-brand">CEC COMEX</p>
      <div className="nav-links">
        <Link href="/dashboard">Dashboard</Link>
        <Link href="/consultas">Consultas</Link>
        <Link href="/catalogos">Catálogos</Link>
        <Link href="/reportes">Reportes</Link>
      </div>
      <Link className="nav-login" href="/login">Salir</Link>
    </nav>
  )
}
