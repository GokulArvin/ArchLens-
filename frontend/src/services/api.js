import axios from 'axios'

const API_BASE = '/api/v1'

export const api = {
  analyzeDiagram: async (file) => {
    const formData = new FormData()
    formData.append('file', file)
    const res = await axios.post(`${API_BASE}/analyze-diagram`, formData)
    return res.data
  },
  analyzeRepository: async (repoPath, language = 'python') => {
    const res = await axios.post(`${API_BASE}/analyze-repository`, {
      repo_path: repoPath,
      language,
    })
    return res.data
  },
  checkConformance: async (intendedGraph, currentGraph) => {
    const res = await axios.post(`${API_BASE}/check-conformance/inline`, {
      intended_graph: intendedGraph,
      current_graph: currentGraph,
    })
    return res.data
  },
  analyzeViolation: async (violation, repoPath, sourceFile, targetSymbol) => {
    const res = await axios.post(`${API_BASE}/analyze-violation`, {
      violation,
      repo_path: repoPath,
      source_file: sourceFile,
      target_symbol: targetSymbol,
    })
    return res.data
  },
  getReport: async (reportId) => {
    const res = await axios.get(`${API_BASE}/report/${reportId}`)
    return res.data
  },
}
