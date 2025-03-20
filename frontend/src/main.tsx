import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import { RouterProvider, createBrowserRouter } from 'react-router-dom'
import Layout from './components/Layout'
import { ThemeProvider } from './theme/ThemeProvider'
import OverviewPage from './pages/OverviewPage'
import RunsPage from './pages/RunsPage'
import RunNewPage from './pages/RunNewPage'
import RunDetailPage from './pages/RunDetailPage'
import ApplicationsPage from './pages/ApplicationsPage'
import DatasetsPage from './pages/DatasetsPage'
import MetricsPage from './pages/MetricsPage'
import ComparePage from './pages/ComparePage'
import RegressionsPage from './pages/RegressionsPage'
import DriftPage from './pages/DriftPage'
import GatesPage from './pages/GatesPage'
import ProvidersPage from './pages/ProvidersPage'
import EvidencePage from './pages/EvidencePage'
import ReportsPage from './pages/ReportsPage'
import SystemPage from './pages/SystemPage'
import NotFoundPage from './pages/NotFoundPage'
import './styles/tokens.css'
import './styles/base.css'
import './styles/components.css'
import './styles/states.css'
import './styles/layout.css'
import './styles/utilities.css'
import './styles/pages.css'

const router = createBrowserRouter([
  {
    path: '/',
    element: <Layout />,
    children: [
      { index: true, element: <OverviewPage /> },
      { path: 'runs', element: <RunsPage /> },
      { path: 'runs/new', element: <RunNewPage /> },
      { path: 'runs/:id', element: <RunDetailPage /> },
      { path: 'applications', element: <ApplicationsPage /> },
      { path: 'datasets', element: <DatasetsPage /> },
      { path: 'metrics', element: <MetricsPage /> },
      { path: 'compare', element: <ComparePage /> },
      { path: 'regressions', element: <RegressionsPage /> },
      { path: 'drift', element: <DriftPage /> },
      { path: 'gates', element: <GatesPage /> },
      { path: 'providers', element: <ProvidersPage /> },
      { path: 'evidence', element: <EvidencePage /> },
      { path: 'reports', element: <ReportsPage /> },
      { path: 'system', element: <SystemPage /> },
      { path: '*', element: <NotFoundPage /> },
    ],
  },
])

const container = document.getElementById('root')
if (!container) throw new Error('Root container #root is missing from index.html')

createRoot(container).render(
  <StrictMode>
    <ThemeProvider>
      <RouterProvider router={router} />
    </ThemeProvider>
  </StrictMode>,
)
