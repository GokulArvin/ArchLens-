import { useState } from 'react'
import { useParams } from 'react-router-dom'
import { AlertTriangle, CheckCircle, ShieldAlert, GitCommit } from 'lucide-react'

export default function ConformanceReport() {
  const { id } = useParams()

  return (
    <div className="space-y-6 max-w-4xl">
      <div>
        <h2 className="text-2xl font-bold text-white tracking-tight">Conformance Report</h2>
        <p className="text-slate-400 text-sm mt-1">Report ID: {id || 'Draft Evaluation'}</p>
      </div>

      <div className="bg-slate-950/60 border border-slate-800 rounded-xl p-6">
        <div className="flex items-center gap-3">
          <ShieldAlert className="w-6 h-6 text-amber-400" />
          <h3 className="text-lg font-semibold text-white">Conformance Verdict: VIOLATION</h3>
        </div>
        <p className="text-slate-400 text-sm mt-2">
          Deterministic graph comparison identified cross-layer architectural violations.
        </p>
      </div>
    </div>
  )
}
