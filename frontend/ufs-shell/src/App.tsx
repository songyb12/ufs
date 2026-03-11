import { lazy, Suspense } from 'react'
import { Routes, Route } from 'react-router-dom'
import { ShellLayout } from './shell/ShellLayout.tsx'
import { ErrorBoundary } from './shared/ErrorBoundary.tsx'

const Home = lazy(() => import('./shell/Home.tsx'))
const BocchiApp = lazy(() => import('./apps/bocchi/BocchiApp.tsx'))
const VibeApp = lazy(() => import('./apps/vibe/VibeApp.tsx'))
const LifeApp = lazy(() => import('./apps/life/LifeApp.tsx'))
const EngOpsApp = lazy(() => import('./apps/eng-ops/EngOpsApp.tsx'))
const NotFound = lazy(() => import('./shell/NotFound.tsx'))

function LoadingFallback() {
  return (
    <div className="flex items-center justify-center h-64">
      <div className="w-8 h-8 border-2 border-accent border-t-transparent rounded-full animate-spin" />
    </div>
  )
}

function LazyRoute({ children, appName }: { children: React.ReactNode; appName?: string }) {
  return (
    <ErrorBoundary appName={appName}>
      <Suspense fallback={<LoadingFallback />}>
        {children}
      </Suspense>
    </ErrorBoundary>
  )
}

export function App() {
  return (
    <Routes>
      <Route element={<ShellLayout />}>
        <Route index element={<LazyRoute><Home /></LazyRoute>} />
        <Route path="bocchi/*" element={<LazyRoute appName="Bocchi-master"><BocchiApp /></LazyRoute>} />
        <Route path="vibe/*" element={<LazyRoute appName="VIBE"><VibeApp /></LazyRoute>} />
        <Route path="life/*" element={<LazyRoute appName="Life-Master"><LifeApp /></LazyRoute>} />
        <Route path="eng-ops/*" element={<LazyRoute appName="Engineering-Ops"><EngOpsApp /></LazyRoute>} />
        <Route path="*" element={<LazyRoute><NotFound /></LazyRoute>} />
      </Route>
    </Routes>
  )
}
