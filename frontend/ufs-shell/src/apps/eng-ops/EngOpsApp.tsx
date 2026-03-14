import { useState, useEffect } from 'react'

interface EngOpsHealth {
  service: string
  status: string
  version: string
}

export default function EngOpsApp() {
  const [health, setHealth] = useState<EngOpsHealth | null>(null)
  const [healthLoading, setHealthLoading] = useState(true)

  useEffect(() => {
    fetch('/api/eng-ops/health')
      .then((r) => r.ok ? r.json() : null)
      .then((d) => { setHealth(d); setHealthLoading(false) })
      .catch(() => { setHealth(null); setHealthLoading(false) })
  }, [])

  const features = [
    { name: 'Log Parser', desc: 'C언어 HW 검증 로그 파싱', status: 'planned', icon: '📄' },
    { name: 'Daily Report', desc: '자동 일일 요약 리포트 생성', status: 'planned', icon: '📊' },
    { name: 'CSV Export', desc: '파싱된 데이터 CSV 내보내기', status: 'planned', icon: '📁' },
    { name: 'Pattern Detection', desc: '에러 패턴 자동 감지 및 분류', status: 'planned', icon: '🔍' },
    { name: 'Dashboard', desc: '실시간 검증 현황 대시보드', status: 'planned', icon: '📈' },
    { name: 'Alert System', desc: '이상 패턴 발생 시 알림', status: 'planned', icon: '🔔' },
  ]

  const roadmap = [
    { phase: 'Phase 1', title: 'Log Ingestion', desc: '로그 파일 업로드 및 파싱 엔진', eta: 'TBD' },
    { phase: 'Phase 2', title: 'Analysis Engine', desc: '패턴 매칭 및 통계 분석', eta: 'TBD' },
    { phase: 'Phase 3', title: 'Reporting', desc: '자동 리포트 생성 및 알림', eta: 'TBD' },
  ]

  return (
    <div className="max-w-4xl mx-auto animate-fade-in">
      <div className="mb-8">
        <div className="flex items-center gap-3 mb-2">
          <div className="w-10 h-10 rounded-xl flex items-center justify-center" style={{ backgroundColor: '#10b98115' }}>
            <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="#10b981" strokeWidth={1.5}>
              <path strokeLinecap="round" strokeLinejoin="round" d="M10.325 4.317c.426-1.756 2.924-1.756 3.35 0a1.724 1.724 0 002.573 1.066c1.543-.94 3.31.826 2.37 2.37a1.724 1.724 0 001.066 2.573c1.756.426 1.756 2.924 0 3.35a1.724 1.724 0 00-1.066 2.573c.94 1.543-.826 3.31-2.37 2.37a1.724 1.724 0 00-2.573 1.066c-.426 1.756-2.924 1.756-3.35 0a1.724 1.724 0 00-2.573-1.066c-1.543.94-3.31-.826-2.37-2.37a1.724 1.724 0 00-1.066-2.573c-1.756-.426-1.756-2.924 0-3.35a1.724 1.724 0 001.066-2.573c-.94-1.543.826-3.31 2.37-2.37.996.608 2.296.07 2.572-1.065z" />
            </svg>
          </div>
          <div>
            <h1 className="text-xl font-bold text-white">
              Engineering<span className="text-emerald-400">-Ops</span>
            </h1>
            <p className="text-ufs-400 text-xs">HW Verification Log Analysis</p>
          </div>
          {healthLoading ? (
            <span className="text-xs px-2 py-0.5 rounded-full bg-ufs-600 text-ufs-400 animate-pulse">checking...</span>
          ) : health ? (
            <span className="text-xs px-2 py-0.5 rounded-full bg-emerald-500/20 text-emerald-400">
              {health.status} v{health.version}
            </span>
          ) : (
            <span className="text-xs px-2 py-0.5 rounded-full bg-red-500/20 text-red-400">unreachable</span>
          )}
        </div>
      </div>

      {/* Status Banner */}
      <div className="rounded-xl border border-emerald-500/20 bg-emerald-500/5 p-5 mb-6">
        <div className="flex items-center gap-3">
          <div className="w-8 h-8 rounded-lg bg-emerald-500/20 flex items-center justify-center shrink-0">
            <span className="text-emerald-400 text-lg">🔧</span>
          </div>
          <div>
            <p className="text-emerald-300 text-sm font-medium">Prototype Stage</p>
            <p className="text-emerald-400/60 text-xs mt-0.5">
              Service skeleton running on port 8003. Log parsing and analysis features in development.
            </p>
          </div>
        </div>
      </div>

      {/* Planned Features */}
      <h3 className="text-xs font-semibold text-ufs-400 uppercase tracking-wider mb-3">Planned Features ({features.length})</h3>
      <div className="grid grid-cols-1 sm:grid-cols-2 gap-2 mb-8 stagger-children">
        {features.map((f) => (
          <div key={f.name} className="group p-3 rounded-lg bg-ufs-800 border border-ufs-600/30 hover:border-emerald-500/20 transition-all">
            <div className="flex items-center gap-2">
              <span className="text-base">{f.icon}</span>
              <span className="text-sm font-medium text-white">{f.name}</span>
              <span className="ml-auto text-[9px] px-1.5 py-0.5 rounded-full bg-ufs-600 text-ufs-400">{f.status}</span>
            </div>
            <div className="text-xs text-ufs-400 mt-1 ml-7">{f.desc}</div>
          </div>
        ))}
      </div>

      {/* Roadmap */}
      <h3 className="text-xs font-semibold text-ufs-400 uppercase tracking-wider mb-3">Development Roadmap</h3>
      <div className="space-y-3">
        {roadmap.map((item, idx) => (
          <div key={item.phase} className="flex gap-4 items-start">
            <div className="flex flex-col items-center">
              <div className="w-6 h-6 rounded-full bg-ufs-700 border border-ufs-600 flex items-center justify-center text-[10px] text-ufs-400 shrink-0">
                {idx + 1}
              </div>
              {idx < roadmap.length - 1 && (
                <div className="w-px h-8 bg-ufs-700 mt-1" />
              )}
            </div>
            <div className="flex-1 pb-4">
              <div className="flex items-center gap-2">
                <span className="text-xs font-semibold text-emerald-400">{item.phase}</span>
                <span className="text-xs text-white font-medium">{item.title}</span>
                <span className="text-[9px] text-ufs-500 ml-auto">{item.eta}</span>
              </div>
              <p className="text-xs text-ufs-400 mt-0.5">{item.desc}</p>
            </div>
          </div>
        ))}
      </div>
    </div>
  )
}
