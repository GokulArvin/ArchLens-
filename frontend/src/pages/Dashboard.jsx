import { Link } from 'react-router-dom'
import { Eye, GitBranch, AlertTriangle, ShieldCheck, ArrowRight } from 'lucide-react'

export default function Dashboard() {
  const stats = [
    { label: 'Scrum Sprints', value: '10 Sprints (50 Days)', icon: ShieldCheck, color: 'text-indigo-400' },
    { label: 'Core Modules', value: '7 Modules (A-G)', icon: Eye, color: 'text-emerald-400' },
    { label: 'Verdict Rules', value: '5 Classes (Violation/Missing...)', icon: AlertTriangle, color: 'text-amber-400' },
    { label: 'Git Grounding', value: 'Log, Blame, Diff & Pickaxe', icon: GitBranch, color: 'text-blue-400' },
  ]

  return (
    <div className="space-y-8 max-w-6xl">
      <div>
        <h2 className="text-2xl font-bold text-white tracking-tight">ArchLens Overview</h2>
        <p className="text-slate-400 text-sm mt-1">
          Hybrid CV + Static Program Analysis + Evidence-Grounded LLM Conformance Pipeline
        </p>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
        {stats.map((s, idx) => {
          const Icon = s.icon
          return (
            <div key={idx} className="bg-slate-950/60 border border-slate-800 rounded-xl p-5">
              <div className="flex items-center gap-3">
                <div className={`p-2.5 rounded-lg bg-slate-900 border border-slate-800 ${s.color}`}>
                  <Icon className="w-5 h-5" />
                </div>
                <div>
                  <div className="text-xs text-slate-400">{s.label}</div>
                  <div className="text-sm font-semibold text-white mt-0.5">{s.value}</div>
                </div>
              </div>
            </div>
          )
        })}
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
        <div className="bg-slate-950/60 border border-slate-800 rounded-xl p-6">
          <h3 className="text-lg font-semibold text-white flex items-center gap-2">
            <Eye className="w-5 h-5 text-indigo-400" />
            1. Intended Architecture (G_I)
          </h3>
          <p className="text-slate-400 text-sm mt-2">
            Extract architectural intent directly from software diagrams using Computer Vision (YOLO, U-Net, ViT, CLIP zero-shot classification).
          </p>
          <div className="mt-5">
            <Link
              to="/diagram"
              className="inline-flex items-center gap-2 text-sm font-medium text-indigo-400 hover:text-indigo-300"
            >
              Analyze diagram <ArrowRight className="w-4 h-4" />
            </Link>
          </div>
        </div>

        <div className="bg-slate-950/60 border border-slate-800 rounded-xl p-6">
          <h3 className="text-lg font-semibold text-white flex items-center gap-2">
            <GitBranch className="w-5 h-5 text-blue-400" />
            2. Current Architecture (G_C)
          </h3>
          <p className="text-slate-400 text-sm mt-2">
            Recover the actual implementation architecture via deterministic AST parsing (imports, calls, inheritance) and dependency mapping.
          </p>
          <div className="mt-5">
            <Link
              to="/repository"
              className="inline-flex items-center gap-2 text-sm font-medium text-blue-400 hover:text-blue-300"
            >
              Scan repository <ArrowRight className="w-4 h-4" />
            </Link>
          </div>
        </div>
      </div>
    </div>
  )
}
