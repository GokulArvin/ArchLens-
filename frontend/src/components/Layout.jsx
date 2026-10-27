import { Outlet, Link, useLocation } from 'react-router-dom'
import { Eye, GitBranch, Layers, AlertTriangle, FileText } from 'lucide-react'

export default function Layout() {
  const location = useLocation()

  const navItems = [
    { path: '/', label: 'Dashboard', icon: Layers },
    { path: '/diagram', label: 'Diagram Analysis', icon: Eye },
    { path: '/repository', label: 'Repository Analysis', icon: GitBranch },
  ]

  return (
    <div className="flex h-screen bg-slate-900 text-slate-100">
      {/* Sidebar */}
      <aside className="w-64 bg-slate-950 border-r border-slate-800 flex flex-col">
        <div className="p-6 border-b border-slate-800">
          <div className="flex items-center gap-2">
            <Eye className="w-7 h-7 text-indigo-400" />
            <h1 className="text-xl font-bold tracking-tight text-white">ArchLens</h1>
          </div>
          <p className="text-xs text-slate-400 mt-1">Architecture Conformance</p>
        </div>

        <nav className="flex-1 p-4 space-y-1">
          {navItems.map((item) => {
            const Icon = item.icon
            const active = location.pathname === item.path
            return (
              <Link
                key={item.path}
                to={item.path}
                className={`flex items-center gap-3 px-3 py-2.5 rounded-lg text-sm font-medium transition-colors ${
                  active
                    ? 'bg-indigo-600 text-white'
                    : 'text-slate-400 hover:text-white hover:bg-slate-900'
                }`}
              >
                <Icon className="w-4 h-4" />
                {item.label}
              </Link>
            )
          })}
        </nav>

        <div className="p-4 border-t border-slate-800 text-xs text-slate-500">
          v0.1.0 • Scrum Sprint 1
        </div>
      </aside>

      {/* Main Content */}
      <main className="flex-1 overflow-y-auto">
        <header className="h-16 border-b border-slate-800 bg-slate-900/50 backdrop-blur px-8 flex items-center justify-between">
          <span className="text-sm text-slate-400">
            Multimodal Architecture Conformance Checking
          </span>
          <div className="flex items-center gap-2">
            <span className="inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium bg-emerald-500/10 text-emerald-400 border border-emerald-500/20">
              ● API Online
            </span>
          </div>
        </header>

        <div className="p-8">
          <Outlet />
        </div>
      </main>
    </div>
  )
}
