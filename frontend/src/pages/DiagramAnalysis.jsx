import { useState } from 'react'
import { UploadCloud, CheckCircle2, AlertCircle, Loader2 } from 'lucide-react'
import { api } from '../services/api'

export default function DiagramAnalysis() {
  const [file, setFile] = useState(null)
  const [loading, setLoading] = useState(false)
  const [result, setResult] = useState(null)
  const [error, setError] = useState(null)

  const handleUpload = async (e) => {
    e.preventDefault()
    if (!file) return
    setLoading(true)
    setError(null)
    try {
      const data = await api.analyzeDiagram(file)
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
        <h2 className="text-2xl font-bold text-white tracking-tight">Diagram Analysis (Module B)</h2>
        <p className="text-slate-400 text-sm mt-1">
          Upload architecture diagrams to extract components, bounding boxes, and intended graph (G_I).
        </p>
      </div>

      <form onSubmit={handleUpload} className="bg-slate-950/60 border border-slate-800 rounded-xl p-6 space-y-4">
        <label className="border-2 border-dashed border-slate-800 hover:border-slate-700 rounded-lg p-8 flex flex-col items-center justify-center cursor-pointer transition-colors block text-center">
          <UploadCloud className="w-10 h-10 text-indigo-400 mb-2" />
          <span className="text-sm font-medium text-slate-200">
            {file ? file.name : 'Select or drop an architecture diagram (PNG, JPG)'}
          </span>
          <span className="text-xs text-slate-500 mt-1">Supports standard UML, C4 model, Microservice diagrams</span>
          <input
            type="file"
            accept="image/*"
            className="hidden"
            onChange={(e) => setFile(e.target.files[0])}
          />
        </label>

        <button
          type="submit"
          disabled={!file || loading}
          className="w-full bg-indigo-600 hover:bg-indigo-500 disabled:opacity-50 text-white font-medium py-2.5 rounded-lg flex items-center justify-center gap-2 text-sm transition-colors"
        >
          {loading ? (
            <>
              <Loader2 className="w-4 h-4 animate-spin" />
              Running CV Pipeline...
            </>
          ) : (
            'Analyze Diagram'
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
            Extracted Intended Graph (G_I)
          </h3>
          <div className="text-sm text-slate-400">
            Components detected: <strong className="text-white">{result.components?.length || 0}</strong> | 
            Relationships: <strong className="text-white">{result.relationships?.length || 0}</strong>
          </div>
          <pre className="p-4 bg-slate-900 rounded-lg text-xs text-slate-300 overflow-x-auto max-h-96">
            {JSON.stringify(result, null, 2)}
          </pre>
        </div>
      )}
    </div>
  )
}
