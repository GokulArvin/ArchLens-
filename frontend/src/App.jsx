import { BrowserRouter, Routes, Route } from 'react-router-dom'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import Dashboard from './pages/Dashboard'
import DiagramAnalysis from './pages/DiagramAnalysis'
import RepositoryAnalysis from './pages/RepositoryAnalysis'
import ConformanceReport from './pages/ConformanceReport'
import Layout from './components/Layout'

const queryClient = new QueryClient()

export default function App() {
  return (
    <QueryClientProvider client={queryClient}>
      <BrowserRouter>
        <Routes>
          <Route path="/" element={<Layout />}>
            <Route index element={<Dashboard />} />
            <Route path="diagram" element={<DiagramAnalysis />} />
            <Route path="repository" element={<RepositoryAnalysis />} />
            <Route path="report/:id" element={<ConformanceReport />} />
          </Route>
        </Routes>
      </BrowserRouter>
    </QueryClientProvider>
  )
}
