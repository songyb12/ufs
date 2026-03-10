import { lazy, Suspense } from 'react'
import { Routes, Route, Navigate } from 'react-router-dom'
import { ShellLayout } from './shell/ShellLayout.tsx'

const Home = lazy(() => import('./shell/Home.tsx'))
const BocchiApp = lazy(() => import('./apps/bocchi/BocchiApp.tsx'))
const VibeApp = lazy(() => import('./apps/vibe/VibeApp.tsx'))
const LifeApp = lazy(() => import('./apps/life/LifeApp.tsx'))
const EngOpsApp = lazy(() => import('./apps/eng-ops/EngOpsApp.tsx'))

function LoadingFallback() {
  return (
    <div className="flex items-center justify-center h-64">
      <div className="w-8 h-8 border-2 border-accent border-t-transparent rounded-full animate-spin" />
    </div>
  )
}

export function App() {
  return (
    <Routes>
      <Route element={<ShellLayout />}>
        <Route
          index
          element={
            <Suspense fallback={<LoadingFallback />}>
              <Home />
            </Suspense>
          }
        />
        <Route
          path="bocchi/*"
          element={
            <Suspense fallback={<LoadingFallback />}>
              <BocchiApp />
            </Suspense>
          }
        />
        <Route
          path="vibe/*"
          element={
            <Suspense fallback={<LoadingFallback />}>
              <VibeApp />
            </Suspense>
          }
        />
        <Route
          path="life/*"
          element={
            <Suspense fallback={<LoadingFallback />}>
              <LifeApp />
            </Suspense>
          }
        />
        <Route
          path="eng-ops/*"
          element={
            <Suspense fallback={<LoadingFallback />}>
              <EngOpsApp />
            </Suspense>
          }
        />
        <Route path="*" element={<Navigate to="/" replace />} />
      </Route>
    </Routes>
  )
}
