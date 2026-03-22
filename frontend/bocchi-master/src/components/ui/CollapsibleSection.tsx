import { useState, type ReactNode } from 'react'

interface Props {
  title: string
  icon?: string
  defaultExpanded?: boolean
  children: ReactNode
}

export function CollapsibleSection({ title, icon, defaultExpanded = false, children }: Props) {
  const [expanded, setExpanded] = useState(defaultExpanded)

  if (!expanded) {
    return (
      <button
        onClick={() => setExpanded(true)}
        className="w-full flex items-center gap-2 px-3 py-2 rounded-lg bg-slate-800/60 hover:bg-slate-700/60 text-slate-400 hover:text-slate-200 text-sm font-medium transition-colors"
      >
        {icon && <span>{icon}</span>}
        <span>{title}</span>
        <svg className="w-3.5 h-3.5 ml-auto" fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 9l-7 7-7-7" />
        </svg>
      </button>
    )
  }

  return (
    <div>
      <button
        onClick={() => setExpanded(false)}
        className="w-full flex items-center gap-2 px-3 py-1.5 mb-2 rounded-lg bg-slate-800/40 text-slate-400 hover:text-slate-200 text-sm font-medium transition-colors"
      >
        {icon && <span>{icon}</span>}
        <span>{title}</span>
        <svg className="w-3.5 h-3.5 ml-auto rotate-180" fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 9l-7 7-7-7" />
        </svg>
      </button>
      {children}
    </div>
  )
}
