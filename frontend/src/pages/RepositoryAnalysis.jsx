import { useState } from 'react'
import { GitBranch, CheckCircle2, AlertCircle, Loader2 } from 'lucide-react'
import { api } from '../services/api'

export default function RepositoryAnalysis() {
  const [repoPath, setRepoPath] = useState('')
  const [language, setLanguage] = useState('python')
  const [loading, setLoading] = useState(false)
  const [result, setResult] = useState(null)
  const [error, setError] = useState(null)

  const handleScan = async (e) => {
    e.preventDefault()
    if (!repoPath) return
    setLoading(true)
    setError(null)
    try {
      const data = await api.analyzeRepository(repoPath, language)
      setResult(data)
    } catch (err) {
      setError(err?.response?.data?.detail || err.message)
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="space-y-6 max-w-4xl">
      <div>
        <h2 className="text-2xl font-bold text-white tracking-tight">Repository Analysis (Module D)</h2>
        <p className="text-slate-400 text-sm mt-1">
          Perform deterministic AST parsing to extract the current architecture graph (G_C).
        </p>
      </div>

      <form onSubmit={handleScan} className="bg-slate-950/60 border border-slate-800 rounded-xl p-6 space-y-4">
        <div>
          <label className="block text-xs font-semibold uppercase tracking-wider text-slate-400 mb-2">
            Repository Path
          </label>
          <input
            type="text"
            value={repoPath}
            onChange={(e) => setRepoPath(e.target.value)}
            placeholder="e.g. C:/Users/.../projects/my-app"
            className="w-full bg-slate-900 border border-slate-800 rounded-lg px-4 py-2.5 text-sm text-slate-100 placeholder-slate-500 focus:outline-none focus:border-indigo-500"
          />
        </div>

        <div>
          <label className="block text-xs font-semibold uppercase tracking-wider text-slate-400 mb-2">
            Language
          </label>
          <select
            value={language}
            onChange={(e) => setLanguage(e.target.value)}
            className="w-full bg-slate-900 border border-slate-800 rounded-lg px-4 py-2.5 text-sm text-slate-100 focus:outline-none focus:border-indigo-500"
          >
            <option value="python">Python (AST Parser)</option>
            <option value="java">Java (Tree-sitter)</option>
          </select>
        </div>

        <button
          type="submit"
          disabled={!repoPath || loading}
          className="w-full bg-blue-600 hover:bg-blue-500 disabled:opacity-50 text-white font-medium py-2.5 rounded-lg flex items-center justify-center gap-2 text-sm transition-colors"
        >
          {loading ? (
            <>
              <Loader2 className="w-4 h-4 animate-spin" />
              Scanning AST & Dependencies...
            </>
          ) : (
            'Scan Repository'
          )}
        </button>
      </form>

      {error && (
        <div className="p-4 bg-rose-500/10 border border-rose-500/20 text-rose-300 rounded-xl flex items-center gap-3 text-sm">
          <AlertCircle className="w-5 h-5 flex-shrink-0" />
          {error}
        </div>
      )}

      {result && (
        <div className="bg-slate-950/60 border border-slate-800 rounded-xl p-6 space-y-4">
          <h3 className="text-lg font-semibold text-white flex items-center gap-2">
            <CheckCircle2 className="w-5 h-5 text-emerald-400" />
            Current Architecture Graph (G_C)
          </h3>
          <div className="text-sm text-slate-400">
            Components: <strong className="text-white">{result.components?.length || 0}</strong> | 
            Dependencies: <strong className="text-white">{result.relationships?.length || 0}</strong>
          </div>
          <pre className="p-4 bg-slate-900 rounded-lg text-xs text-slate-300 overflow-x-auto max-h-96">
            {JSON.stringify(result, null, 2)}
          </pre>
        </div>
      )}
    </div>
  )
}
