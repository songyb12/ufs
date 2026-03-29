import { useState, useEffect, useCallback, useRef } from 'react'

// ── Types & Interfaces ──────────────────────────────────────────────

interface HealthData { service: string; status: string; version: string; db_connected: boolean }
interface DashboardData {
  date: string; routines_total: number; routines_done: number; routines_remaining: number
  routines_completion: number; habits_logged_today: number; habits_total: number
  active_goals: number; schedule_blocks: number
  top_streaks: { name: string; streak: number }[]
  upcoming_deadlines: { title: string; deadline: string; days_remaining: number }[]
  overdue_goals: { title: string; deadline: string }[]
}

interface Routine {
  id: number; name: string; description?: string; category: string; time_slot: string
  duration_min: number; priority: number; repeat_days: string[]; color: string; icon?: string
  is_active: number; sort_order: number
}
interface TodayRoutine extends Routine { log_status: string | null; log_note?: string }
interface RoutineStats { total_logs: number; done: number; skipped: number; partial: number; completion_rate: number }
interface HeatmapEntry { date: string; count: number; status?: string }

interface Habit {
  id: number; name: string; description?: string; target_type: string
  target_value: number; unit: string; color: string; icon?: string; is_active: number
}
interface StreakData { habit_id: number; current_streak: number; longest_streak: number; weekly_rate: number; monthly_rate: number }
interface HabitOverviewItem { habit: Habit; streak: StreakData; recent_logs: { id: number; value: number; date: string }[]; today_value: number }

interface Goal {
  id: number; title: string; description?: string; category: string; deadline?: string
  status: string; progress: number; priority: number; color: string
  milestone_total?: number; milestone_done?: number; days_remaining?: number | null
}
interface Milestone { id: number; title: string; is_completed: number; target_date?: string; sort_order: number }
interface GoalDetail extends Goal { milestones: Milestone[] }

interface ScheduleBlock {
  id: number; date: string; start_time: string; end_time: string; title: string
  priority: number; is_locked: number; note?: string; source: string
}

interface VocabWord {
  id: number; word: string; reading: string; meaning: string; jlpt_level: string
  part_of_speech: string; example_ja?: string; example_ko?: string
  ease_factor?: number; interval_days?: number; repetitions?: number; next_review?: string
}

interface GrammarPoint {
  id: number; grammar_point: string; meaning_ko?: string; meaning_en?: string; meaning?: string
  formation?: string; structure?: string
  jlpt_level: string; category?: string; examples?: { ja: string; ko: string }[]
  srs?: { ease_factor: number; interval_days: number; repetitions: number; next_review: string }
}
interface Paginated<T> { items: T[]; total: number; page: number; per_page: number; total_pages: number }

interface KanjiItem {
  id: number; character: string; meaning_ko: string; meaning_en?: string
  onyomi: string; kunyomi: string; jlpt_level: string; stroke_count?: number
}

interface ReadingPassage {
  id: number; title: string; jlpt_level: string; category?: string; word_count?: number; question_count?: number
  content_jp?: string; content_ko?: string
  questions?: { id: number; question_jp?: string; question_ko?: string; question?: string; options: string[]; correct_answer?: string }[]
}

interface PlayerStats {
  total_xp: number; level: number; xp_current_level: number; xp_next_level: number
  current_streak: number; longest_streak: number; total_reviews: number; total_correct: number
  accuracy: number; combo_best: number
  achievements: { id: string; name: string; icon: string; description: string; xp_bonus: number; unlocked_at: string }[]
  title: { tier: number; name: string; icon: string }
}

interface QuizQuestion { id: number; vocab_id?: number; word?: string; question?: string; reading?: string; options: string[]; correct_answer?: string }

// ── API Helper ──────────────────────────────────────────────────────

const API = '/api/life'

async function api<T>(path: string, opts?: RequestInit): Promise<T> {
  const res = await fetch(`${API}${path}`, {
    headers: { 'Content-Type': 'application/json', ...opts?.headers },
    ...opts,
  })
  if (!res.ok) throw new Error(`HTTP ${res.status}`)
  return res.json()
}

// ── Japanese TTS ────────────────────────────────────────────────────

let _jaVoice: SpeechSynthesisVoice | null = null
let _voiceReady = false

function findJaVoice(): SpeechSynthesisVoice | null {
  if (_voiceReady) return _jaVoice
  const voices = speechSynthesis.getVoices()
  if (voices.length === 0) return null
  _voiceReady = true
  // Prefer female JP voices — Sayaka > Haruka > Ayumi > Nanami > Google
  const prefs = ['sayaka', 'haruka', 'ayumi', 'nanami', 'female', 'google.*ja']
  for (const p of prefs) {
    const re = new RegExp(p, 'i')
    const found = voices.find(v => (v.lang.startsWith('ja') || v.lang === 'ja-JP') && re.test(v.name))
    if (found) { _jaVoice = found; return found }
  }
  // fallback: any Japanese voice
  _jaVoice = voices.find(v => v.lang.startsWith('ja') || v.lang === 'ja-JP') || null
  return _jaVoice
}

// pre-load voices (Chrome loads them async)
if (typeof window !== 'undefined' && window.speechSynthesis) {
  speechSynthesis.onvoiceschanged = () => { _voiceReady = false; findJaVoice() }
  findJaVoice()
}

function speakJa(text: string, rate = 0.9): Promise<void> {
  return new Promise((resolve) => {
    if (!text || typeof window === 'undefined' || !window.speechSynthesis) { resolve(); return }
    speechSynthesis.cancel()
    const u = new SpeechSynthesisUtterance(text)
    u.lang = 'ja-JP'
    u.rate = rate
    u.pitch = 1.15
    const v = findJaVoice()
    if (v) u.voice = v
    u.onend = () => resolve()
    u.onerror = () => resolve()
    speechSynthesis.speak(u)
  })
}

function SpeakBtn({ text, size = 'sm', rate }: { text: string; size?: 'sm' | 'md' | 'lg'; rate?: number }) {
  const [speaking, setSpeaking] = useState(false)
  const cls = { sm: 'text-xs w-6 h-6', md: 'text-sm w-7 h-7', lg: 'text-base w-8 h-8' }[size]
  const handleClick = async (e: React.MouseEvent) => {
    e.stopPropagation()
    setSpeaking(true)
    await speakJa(text, rate)
    setSpeaking(false)
  }
  return (
    <button onClick={handleClick}
      title="발음 듣기"
      className={`${cls} inline-flex items-center justify-center rounded-full hover:bg-violet-500/20 transition-colors active:scale-90 shrink-0 ${
        speaking ? 'text-violet-300 bg-violet-500/20 animate-pulse' : 'text-ufs-400 hover:text-violet-300'
      }`}>
      {speaking ? '🔉' : '🔊'}
    </button>
  )
}

// ── Shared Micro-Components ─────────────────────────────────────────

function Spinner({ size = 'md' }: { size?: 'sm' | 'md' }) {
  const s = size === 'sm' ? 'w-4 h-4 border' : 'w-6 h-6 border-2'
  return <div className={`${s} border-violet-500/30 border-t-violet-500 rounded-full animate-spin`} />
}

function EmptyState({ icon, text }: { icon: string; text: string }) {
  return (
    <div className="flex flex-col items-center justify-center py-12 text-ufs-500">
      <span className="text-3xl mb-2">{icon}</span>
      <span className="text-sm">{text}</span>
    </div>
  )
}

function StatCard({ label, value, color = 'text-violet-400' }: { label: string; value: string | number; color?: string }) {
  return (
    <div className="rounded-lg bg-ufs-800 border border-ufs-600/30 p-3 text-center hover:border-violet-500/30 transition-colors">
      <div className={`text-xl font-bold ${color}`}>{value}</div>
      <div className="text-[10px] text-ufs-400 mt-0.5">{label}</div>
    </div>
  )
}

function ProgressBar({ value, max = 1, color = 'bg-violet-500' }: { value: number; max?: number; color?: string }) {
  const pct = max > 0 ? Math.min(100, Math.round((value / max) * 100)) : 0
  return (
    <div className="w-full h-1.5 rounded-full bg-ufs-700 overflow-hidden">
      <div className={`h-full rounded-full ${color} transition-all duration-300`} style={{ width: `${pct}%` }} />
    </div>
  )
}

function Badge({ text, color = 'bg-violet-500/20 text-violet-300' }: { text: string; color?: string }) {
  return <span className={`text-[10px] px-1.5 py-0.5 rounded-full ${color} font-medium`}>{text}</span>
}

function Btn({ children, onClick, variant = 'primary', disabled, small, className = '' }: {
  children: React.ReactNode; onClick?: () => void; variant?: 'primary' | 'secondary' | 'danger' | 'ghost'
  disabled?: boolean; small?: boolean; className?: string
}) {
  const base = small ? 'text-xs px-2.5 py-1.5 rounded-md' : 'text-sm px-4 py-2 rounded-lg'
  const v = {
    primary: 'bg-violet-500/20 text-violet-300 border border-violet-500/30 hover:bg-violet-500/30',
    secondary: 'bg-ufs-700 text-ufs-300 border border-ufs-600/50 hover:bg-ufs-600 hover:text-white',
    danger: 'bg-red-500/20 text-red-300 border border-red-500/30 hover:bg-red-500/30',
    ghost: 'text-ufs-400 hover:text-white hover:bg-ufs-700',
  }[variant]
  return (
    <button onClick={onClick} disabled={disabled}
      className={`${base} ${v} transition-all active:scale-[0.98] disabled:opacity-40 disabled:pointer-events-none ${className}`}>
      {children}
    </button>
  )
}

function Input({ label, value, onChange, type = 'text', placeholder, className = '' }: {
  label?: string; value: string | number; onChange: (v: string) => void
  type?: string; placeholder?: string; className?: string
}) {
  return (
    <div className={className}>
      {label && <label className="text-[10px] text-ufs-400 uppercase tracking-wider mb-1 block">{label}</label>}
      <input type={type} value={value} onChange={e => onChange(e.target.value)} placeholder={placeholder}
        className="w-full bg-ufs-700 text-sm text-white rounded-md py-1.5 px-2.5 outline-none border border-ufs-600/50 focus:border-violet-500/50 placeholder:text-ufs-500 transition-colors" />
    </div>
  )
}

function Select({ label, value, onChange, options, className = '' }: {
  label?: string; value: string; onChange: (v: string) => void
  options: { value: string; label: string }[]; className?: string
}) {
  return (
    <div className={className}>
      {label && <label className="text-[10px] text-ufs-400 uppercase tracking-wider mb-1 block">{label}</label>}
      <select value={value} onChange={e => onChange(e.target.value)}
        className="w-full bg-ufs-700 text-sm text-white rounded-md py-1.5 px-2 outline-none border border-ufs-600/50 focus:border-violet-500/50 transition-colors">
        {options.map(o => <option key={o.value} value={o.value}>{o.label}</option>)}
      </select>
    </div>
  )
}

const CATEGORIES = [
  { value: 'GENERAL', label: 'General' }, { value: 'HEALTH', label: 'Health' },
  { value: 'WORK', label: 'Work' }, { value: 'STUDY', label: 'Study' },
  { value: 'SELF_DEV', label: 'Self Dev' }, { value: 'SOCIAL', label: 'Social' },
  { value: 'CREATIVE', label: 'Creative' },
]
const TIME_SLOTS = [
  { value: 'FLEXIBLE', label: 'Flexible' }, { value: 'MORNING', label: 'Morning' },
  { value: 'AFTERNOON', label: 'Afternoon' }, { value: 'EVENING', label: 'Evening' },
]
const DAYS = ['mon', 'tue', 'wed', 'thu', 'fri', 'sat', 'sun']
const JLPT_LEVELS = [
  { value: '', label: 'All' }, { value: 'N5', label: 'N5' }, { value: 'N4', label: 'N4' },
  { value: 'N3', label: 'N3' }, { value: 'N2', label: 'N2' }, { value: 'N1', label: 'N1' },
]
const CAT_COLORS: Record<string, string> = {
  HEALTH: 'bg-emerald-500/20 text-emerald-300', WORK: 'bg-blue-500/20 text-blue-300',
  STUDY: 'bg-amber-500/20 text-amber-300', SELF_DEV: 'bg-pink-500/20 text-pink-300',
  SOCIAL: 'bg-cyan-500/20 text-cyan-300', CREATIVE: 'bg-orange-500/20 text-orange-300',
  GENERAL: 'bg-ufs-600/50 text-ufs-300',
}

// ── Tab: Dashboard ──────────────────────────────────────────────────

function DashboardTab({ onNavigate }: { onNavigate: (tab: string) => void }) {
  const [data, setData] = useState<DashboardData | null>(null)
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    api<DashboardData>('/dashboard').then(setData).catch(() => {}).finally(() => setLoading(false))
  }, [])

  if (loading) return <div className="flex justify-center py-12"><Spinner /></div>
  if (!data) return <EmptyState icon="📊" text="Failed to load dashboard" />

  return (
    <div className="animate-fade-in space-y-6">
      <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
        <StatCard label="Routines Done" value={`${data.routines_done}/${data.routines_total}`} color="text-violet-400" />
        <StatCard label="Habits Logged" value={`${data.habits_logged_today}/${data.habits_total}`} color="text-blue-400" />
        <StatCard label="Active Goals" value={data.active_goals} color="text-emerald-400" />
        <StatCard label="Completion" value={`${Math.round(data.routines_completion * 100)}%`} color="text-amber-400" />
      </div>

      {/* Quick Actions */}
      <div className="flex gap-2 flex-wrap">
        <Btn onClick={() => onNavigate('routines')} small>✓ Check Routines</Btn>
        <Btn onClick={() => onNavigate('habits')} small variant="secondary">📊 Log Habit</Btn>
        <Btn onClick={() => onNavigate('vocab')} small variant="secondary">📚 Start Review</Btn>
        <Btn onClick={() => onNavigate('finance')} small variant="secondary">💰 Finance</Btn>
      </div>

      {/* Top Streaks */}
      {data.top_streaks.length > 0 && (
        <div className="rounded-xl bg-ufs-800 border border-ufs-600/30 p-4">
          <h3 className="text-xs font-semibold text-ufs-400 uppercase tracking-wider mb-3">Top Streaks</h3>
          <div className="space-y-2">
            {data.top_streaks.map((s, i) => (
              <div key={s.name} className="flex items-center justify-between text-sm">
                <div className="flex items-center gap-2">
                  <span className="text-[10px] text-ufs-500 w-4">{i + 1}.</span>
                  <span className="text-white">{s.name}</span>
                </div>
                <span className="text-amber-400 font-mono font-bold">{s.streak}d</span>
              </div>
            ))}
          </div>
        </div>
      )}

      <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
        {/* Upcoming Deadlines */}
        {data.upcoming_deadlines.length > 0 && (
          <div className="rounded-xl bg-ufs-800 border border-ufs-600/30 p-4">
            <h3 className="text-xs font-semibold text-ufs-400 uppercase tracking-wider mb-3">Upcoming Deadlines</h3>
            <div className="space-y-2">
              {data.upcoming_deadlines.slice(0, 5).map(d => (
                <div key={d.title} className="flex justify-between text-sm">
                  <span className="text-white truncate">{d.title}</span>
                  <span className="text-amber-400 text-xs shrink-0 ml-2">{d.days_remaining}d left</span>
                </div>
              ))}
            </div>
          </div>
        )}

        {/* Overdue Goals */}
        {data.overdue_goals.length > 0 && (
          <div className="rounded-xl bg-red-500/5 border border-red-500/20 p-4">
            <h3 className="text-xs font-semibold text-red-400 uppercase tracking-wider mb-3">Overdue</h3>
            <div className="space-y-2">
              {data.overdue_goals.slice(0, 5).map(g => (
                <div key={g.title} className="text-sm text-red-300">{g.title}</div>
              ))}
            </div>
          </div>
        )}
      </div>
    </div>
  )
}

// ── Tab: Routines ───────────────────────────────────────────────────

function RoutinesTab() {
  const [view, setView] = useState<'today' | 'all' | 'stats'>('today')
  const [today, setToday] = useState<TodayRoutine[]>([])
  const [all, setAll] = useState<Routine[]>([])
  const [stats, setStats] = useState<RoutineStats | null>(null)
  const [heatmap, setHeatmap] = useState<HeatmapEntry[]>([])
  const [loading, setLoading] = useState(true)
  const [showForm, setShowForm] = useState(false)
  const [form, setForm] = useState({ name: '', category: 'GENERAL', time_slot: 'FLEXIBLE', duration_min: '30', priority: '3', repeat_days: DAYS.slice(0, 5) })

  const loadToday = useCallback(() => {
    api<TodayRoutine[]>('/routines/today').then(setToday).catch(() => {}).finally(() => setLoading(false))
  }, [])

  useEffect(() => { loadToday() }, [loadToday])

  const loadAll = useCallback(() => {
    api<Routine[]>('/routines?active_only=false').then(setAll).catch(() => {})
  }, [])

  const loadStats = useCallback(() => {
    Promise.all([
      api<RoutineStats>('/routines/stats').then(setStats).catch(() => {}),
      api<HeatmapEntry[]>('/routines/heatmap').then(setHeatmap).catch(() => {}),
    ])
  }, [])

  useEffect(() => { if (view === 'all') loadAll(); if (view === 'stats') loadStats() }, [view, loadAll, loadStats])

  const toggleCheck = async (r: TodayRoutine) => {
    try {
      if (r.log_status === 'DONE') {
        await api(`/routines/${r.id}/check`, { method: 'DELETE' })
      } else {
        await api(`/routines/${r.id}/check`, { method: 'POST', body: JSON.stringify({ status: 'DONE' }) })
      }
      loadToday()
    } catch { /* ignore */ }
  }

  const createRoutine = async () => {
    try {
      await api('/routines', {
        method: 'POST',
        body: JSON.stringify({ ...form, duration_min: parseInt(form.duration_min), priority: parseInt(form.priority), repeat_days: form.repeat_days }),
      })
      setShowForm(false)
      setForm({ name: '', category: 'GENERAL', time_slot: 'FLEXIBLE', duration_min: '30', priority: '3', repeat_days: DAYS.slice(0, 5) })
      loadToday(); loadAll()
    } catch { /* ignore */ }
  }

  if (loading) return <div className="flex justify-center py-12"><Spinner /></div>

  return (
    <div className="animate-fade-in space-y-4">
      <div className="flex items-center gap-2 flex-wrap">
        {(['today', 'all', 'stats'] as const).map(v => (
          <Btn key={v} onClick={() => setView(v)} variant={view === v ? 'primary' : 'ghost'} small>
            {v === 'today' ? "Today's" : v === 'all' ? 'All Routines' : 'Stats'}
          </Btn>
        ))}
        <Btn onClick={() => setShowForm(!showForm)} small variant="secondary">+ New</Btn>
      </div>

      {/* Create Form */}
      {showForm && (
        <div className="rounded-lg bg-ufs-800 border border-violet-500/30 p-4 space-y-3 animate-fade-in">
          <Input label="Name" value={form.name} onChange={v => setForm(f => ({ ...f, name: v }))} placeholder="Morning Workout" />
          <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
            <Select label="Category" value={form.category} onChange={v => setForm(f => ({ ...f, category: v }))} options={CATEGORIES} />
            <Select label="Time Slot" value={form.time_slot} onChange={v => setForm(f => ({ ...f, time_slot: v }))} options={TIME_SLOTS} />
            <Input label="Duration (min)" value={form.duration_min} onChange={v => setForm(f => ({ ...f, duration_min: v }))} type="number" />
            <Input label="Priority (1-5)" value={form.priority} onChange={v => setForm(f => ({ ...f, priority: v }))} type="number" />
          </div>
          <div>
            <label className="text-[10px] text-ufs-400 uppercase tracking-wider mb-1 block">Repeat Days</label>
            <div className="flex gap-1">
              {DAYS.map(d => (
                <button key={d} onClick={() => setForm(f => ({
                  ...f, repeat_days: f.repeat_days.includes(d) ? f.repeat_days.filter(x => x !== d) : [...f.repeat_days, d]
                }))}
                  className={`text-[10px] w-8 h-7 rounded ${form.repeat_days.includes(d) ? 'bg-violet-500/30 text-violet-300 border border-violet-500/40' : 'bg-ufs-700 text-ufs-400 border border-ufs-600/50'} transition-colors`}>
                  {d.charAt(0).toUpperCase() + d.slice(1, 2)}
                </button>
              ))}
            </div>
          </div>
          <div className="flex gap-2">
            <Btn onClick={createRoutine} small disabled={!form.name.trim()}>Create</Btn>
            <Btn onClick={() => setShowForm(false)} small variant="ghost">Cancel</Btn>
          </div>
        </div>
      )}

      {/* Today View */}
      {view === 'today' && (
        <div className="space-y-1.5">
          {today.length === 0 ? <EmptyState icon="✨" text="No routines for today" /> :
            today.map(r => (
              <div key={r.id} className="flex items-center gap-3 rounded-lg bg-ufs-800 border border-ufs-600/30 p-3 hover:border-violet-500/20 transition-all group"
                style={{ borderLeftWidth: 3, borderLeftColor: r.color }}>
                <button onClick={() => toggleCheck(r)}
                  className={`w-5 h-5 rounded-md border-2 flex items-center justify-center shrink-0 transition-colors ${
                    r.log_status === 'DONE' ? 'bg-violet-500 border-violet-500 text-white' : 'border-ufs-500 hover:border-violet-400'
                  }`}>
                  {r.log_status === 'DONE' && <span className="text-[10px]">✓</span>}
                </button>
                <div className="flex-1 min-w-0">
                  <div className={`text-sm font-medium ${r.log_status === 'DONE' ? 'text-ufs-400 line-through' : 'text-white'}`}>{r.name}</div>
                  <div className="flex items-center gap-2 mt-0.5">
                    <Badge text={r.category} color={CAT_COLORS[r.category] || CAT_COLORS.GENERAL} />
                    <span className="text-[10px] text-ufs-500">{r.time_slot} · {r.duration_min}min</span>
                  </div>
                </div>
                <span className="text-xs text-ufs-500 opacity-0 group-hover:opacity-100 transition-opacity">P{r.priority}</span>
              </div>
            ))}
        </div>
      )}

      {/* All View */}
      {view === 'all' && (
        <div className="space-y-1.5">
          {all.length === 0 ? <EmptyState icon="📋" text="No routines created yet" /> :
            all.map(r => (
              <div key={r.id} className={`flex items-center gap-3 rounded-lg bg-ufs-800 border border-ufs-600/30 p-3 ${!r.is_active ? 'opacity-50' : ''}`}
                style={{ borderLeftWidth: 3, borderLeftColor: r.color }}>
                <div className="flex-1 min-w-0">
                  <span className="text-sm text-white">{r.name}</span>
                  <div className="flex gap-2 mt-0.5">
                    <Badge text={r.category} color={CAT_COLORS[r.category] || CAT_COLORS.GENERAL} />
                    <span className="text-[10px] text-ufs-500">{r.repeat_days.join(', ')}</span>
                  </div>
                </div>
                <span className="text-[10px] text-ufs-500">{r.duration_min}m</span>
              </div>
            ))}
        </div>
      )}

      {/* Stats View */}
      {view === 'stats' && stats && (
        <div className="space-y-4">
          <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
            <StatCard label="Done" value={stats.done} color="text-emerald-400" />
            <StatCard label="Skipped" value={stats.skipped} color="text-amber-400" />
            <StatCard label="Partial" value={stats.partial} color="text-blue-400" />
            <StatCard label="Completion" value={`${Math.round(stats.completion_rate * 100)}%`} color="text-violet-400" />
          </div>
          {/* Heatmap */}
          {heatmap.length > 0 && (
            <div className="rounded-xl bg-ufs-800 border border-ufs-600/30 p-4">
              <h3 className="text-xs font-semibold text-ufs-400 uppercase tracking-wider mb-3">90-Day Heatmap</h3>
              <div className="grid grid-cols-[repeat(13,1fr)] gap-0.5">
                {heatmap.slice(-91).map((h, i) => (
                  <div key={i} title={`${h.date}: ${h.count}`}
                    className={`w-full aspect-square rounded-sm ${h.count >= 3 ? 'bg-violet-500' : h.count === 2 ? 'bg-violet-500/60' : h.count === 1 ? 'bg-violet-500/30' : 'bg-ufs-700'}`} />
                ))}
              </div>
            </div>
          )}
        </div>
      )}
    </div>
  )
}

// ── Tab: Habits ─────────────────────────────────────────────────────

function HabitsTab() {
  const [overview, setOverview] = useState<HabitOverviewItem[]>([])
  const [loading, setLoading] = useState(true)
  const [showForm, setShowForm] = useState(false)
  const [form, setForm] = useState({ name: '', target_type: 'DAILY', target_value: '1', unit: '회', color: '#6366f1' })

  const load = useCallback(() => {
    api<HabitOverviewItem[]>('/habits/overview').then(setOverview).catch(() => {}).finally(() => setLoading(false))
  }, [])
  useEffect(() => { load() }, [load])

  const increment = async (id: number) => {
    try {
      await api(`/habits/${id}/increment`, { method: 'PATCH', body: JSON.stringify({ delta: 1 }) })
      load()
    } catch { /* ignore */ }
  }

  const create = async () => {
    try {
      await api('/habits', {
        method: 'POST',
        body: JSON.stringify({ ...form, target_value: parseFloat(form.target_value) }),
      })
      setShowForm(false); setForm({ name: '', target_type: 'DAILY', target_value: '1', unit: '회', color: '#6366f1' })
      load()
    } catch { /* ignore */ }
  }

  if (loading) return <div className="flex justify-center py-12"><Spinner /></div>

  return (
    <div className="animate-fade-in space-y-4">
      <div className="flex gap-2">
        <Btn onClick={() => setShowForm(!showForm)} small variant="secondary">+ New Habit</Btn>
      </div>

      {showForm && (
        <div className="rounded-lg bg-ufs-800 border border-violet-500/30 p-4 space-y-3 animate-fade-in">
          <Input label="Name" value={form.name} onChange={v => setForm(f => ({ ...f, name: v }))} placeholder="Exercise" />
          <div className="grid grid-cols-3 gap-3">
            <Select label="Type" value={form.target_type} onChange={v => setForm(f => ({ ...f, target_type: v }))}
              options={[{ value: 'DAILY', label: 'Daily' }, { value: 'WEEKLY', label: 'Weekly' }, { value: 'COUNT', label: 'Count' }]} />
            <Input label="Target" value={form.target_value} onChange={v => setForm(f => ({ ...f, target_value: v }))} type="number" />
            <Input label="Unit" value={form.unit} onChange={v => setForm(f => ({ ...f, unit: v }))} />
          </div>
          <div className="flex gap-2">
            <Btn onClick={create} small disabled={!form.name.trim()}>Create</Btn>
            <Btn onClick={() => setShowForm(false)} small variant="ghost">Cancel</Btn>
          </div>
        </div>
      )}

      {overview.length === 0 ? <EmptyState icon="📊" text="No habits tracked yet" /> : (
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-3">
          {overview.map(({ habit: h, streak, today_value }) => (
            <div key={h.id} className="rounded-lg bg-ufs-800 border border-ufs-600/30 p-4 hover:border-violet-500/30 transition-all group"
              style={{ borderTopWidth: 3, borderTopColor: h.color }}>
              <div className="flex items-center justify-between mb-2">
                <span className="text-sm font-medium text-white">{h.name}</span>
                {streak.current_streak > 0 && (
                  <span className="text-[10px] text-amber-400 font-mono">🔥 {streak.current_streak}d</span>
                )}
              </div>
              <div className="flex items-center gap-2 mb-2">
                <span className="text-lg font-bold text-violet-400">{today_value}</span>
                <span className="text-xs text-ufs-500">/ {h.target_value} {h.unit}</span>
              </div>
              <ProgressBar value={today_value} max={h.target_value} />
              <div className="flex items-center justify-between mt-3">
                <span className="text-[10px] text-ufs-500">{h.target_type} · Best: {streak.longest_streak}d</span>
                <button onClick={() => increment(h.id)}
                  className="w-8 h-8 rounded-lg bg-violet-500/20 text-violet-300 hover:bg-violet-500/30 transition-colors flex items-center justify-center text-lg font-bold opacity-60 group-hover:opacity-100">
                  +
                </button>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  )
}

// ── Tab: Goals ──────────────────────────────────────────────────────

function GoalsTab() {
  const [goals, setGoals] = useState<Goal[]>([])
  const [expanded, setExpanded] = useState<number | null>(null)
  const [detail, setDetail] = useState<GoalDetail | null>(null)
  const [loading, setLoading] = useState(true)
  const [showForm, setShowForm] = useState(false)
  const [form, setForm] = useState({ title: '', category: 'GENERAL', deadline: '', priority: '3' })
  const [milestoneTitle, setMilestoneTitle] = useState('')

  const load = useCallback(() => {
    api<Goal[]>('/goals').then(setGoals).catch(() => {}).finally(() => setLoading(false))
  }, [])
  useEffect(() => { load() }, [load])

  const expand = async (id: number) => {
    if (expanded === id) { setExpanded(null); setDetail(null); return }
    setExpanded(id)
    try { setDetail(await api<GoalDetail>(`/goals/${id}`)) } catch { /* ignore */ }
  }

  const createGoal = async () => {
    try {
      await api('/goals', {
        method: 'POST',
        body: JSON.stringify({ ...form, priority: parseInt(form.priority), deadline: form.deadline || undefined }),
      })
      setShowForm(false); setForm({ title: '', category: 'GENERAL', deadline: '', priority: '3' })
      load()
    } catch { /* ignore */ }
  }

  const toggleMilestone = async (goalId: number, ms: Milestone) => {
    try {
      const action = ms.is_completed ? 'uncomplete' : 'complete'
      await api(`/goals/${goalId}/milestones/${ms.id}/${action}`, { method: 'PATCH' })
      setDetail(await api<GoalDetail>(`/goals/${goalId}`))
      load()
    } catch { /* ignore */ }
  }

  const addMilestone = async (goalId: number) => {
    if (!milestoneTitle.trim()) return
    try {
      await api(`/goals/${goalId}/milestones`, { method: 'POST', body: JSON.stringify({ title: milestoneTitle }) })
      setMilestoneTitle('')
      setDetail(await api<GoalDetail>(`/goals/${goalId}`))
      load()
    } catch { /* ignore */ }
  }

  const updateProgress = async (goalId: number, progress: number) => {
    try {
      await api(`/goals/${goalId}/progress`, { method: 'PATCH', body: JSON.stringify({ progress }) })
      load()
    } catch { /* ignore */ }
  }

  if (loading) return <div className="flex justify-center py-12"><Spinner /></div>

  return (
    <div className="animate-fade-in space-y-4">
      <Btn onClick={() => setShowForm(!showForm)} small variant="secondary">+ New Goal</Btn>

      {showForm && (
        <div className="rounded-lg bg-ufs-800 border border-violet-500/30 p-4 space-y-3 animate-fade-in">
          <Input label="Title" value={form.title} onChange={v => setForm(f => ({ ...f, title: v }))} placeholder="Learn N3 Japanese" />
          <div className="grid grid-cols-3 gap-3">
            <Select label="Category" value={form.category} onChange={v => setForm(f => ({ ...f, category: v }))}
              options={[
                { value: 'GENERAL', label: 'General' }, { value: 'CAREER', label: 'Career' },
                { value: 'HEALTH', label: 'Health' }, { value: 'FINANCE', label: 'Finance' },
                { value: 'SKILL', label: 'Skill' }, { value: 'RELATIONSHIP', label: 'Relationship' },
              ]} />
            <Input label="Deadline" value={form.deadline} onChange={v => setForm(f => ({ ...f, deadline: v }))} type="date" />
            <Input label="Priority (1-5)" value={form.priority} onChange={v => setForm(f => ({ ...f, priority: v }))} type="number" />
          </div>
          <div className="flex gap-2">
            <Btn onClick={createGoal} small disabled={!form.title.trim()}>Create</Btn>
            <Btn onClick={() => setShowForm(false)} small variant="ghost">Cancel</Btn>
          </div>
        </div>
      )}

      {goals.length === 0 ? <EmptyState icon="🎯" text="No goals set yet" /> : (
        <div className="space-y-2">
          {goals.map(g => (
            <div key={g.id} className="rounded-lg bg-ufs-800 border border-ufs-600/30 overflow-hidden hover:border-violet-500/20 transition-all">
              <div className="p-4 cursor-pointer" onClick={() => expand(g.id)}>
                <div className="flex items-center justify-between mb-2">
                  <div className="flex items-center gap-2">
                    <span className="text-sm font-medium text-white">{g.title}</span>
                    <Badge text={g.category} color={CAT_COLORS[g.category] || CAT_COLORS.GENERAL} />
                    <Badge text={g.status} color={g.status === 'ACTIVE' ? 'bg-emerald-500/20 text-emerald-300' : 'bg-ufs-600/50 text-ufs-400'} />
                  </div>
                  <span className="text-xs text-ufs-500">{expanded === g.id ? '▲' : '▼'}</span>
                </div>
                <ProgressBar value={g.progress} />
                <div className="flex items-center gap-3 mt-2 text-[10px] text-ufs-500">
                  <span>{Math.round(g.progress * 100)}%</span>
                  {g.milestone_total != null && <span>📌 {g.milestone_done}/{g.milestone_total}</span>}
                  {g.deadline && <span>📅 {g.deadline}{g.days_remaining != null && ` (${g.days_remaining}d)`}</span>}
                </div>
              </div>

              {expanded === g.id && detail && (
                <div className="border-t border-ufs-600/30 p-4 bg-ufs-900/50 space-y-3 animate-fade-in">
                  {/* Progress Slider */}
                  <div>
                    <label className="text-[10px] text-ufs-400 uppercase tracking-wider mb-1 block">Progress</label>
                    <input type="range" min={0} max={100} value={Math.round(detail.progress * 100)}
                      onChange={e => updateProgress(g.id, parseInt(e.target.value) / 100)}
                      className="w-full accent-violet-500" />
                  </div>

                  {/* Milestones */}
                  <div>
                    <h4 className="text-[10px] text-ufs-400 uppercase tracking-wider mb-2">Milestones</h4>
                    {detail.milestones.length === 0 ? <span className="text-xs text-ufs-500">No milestones</span> : (
                      <div className="space-y-1">
                        {detail.milestones.map(ms => (
                          <div key={ms.id} className="flex items-center gap-2">
                            <button onClick={() => toggleMilestone(g.id, ms)}
                              className={`w-4 h-4 rounded border flex items-center justify-center shrink-0 text-[9px] transition-colors ${
                                ms.is_completed ? 'bg-violet-500 border-violet-500 text-white' : 'border-ufs-500 hover:border-violet-400'
                              }`}>
                              {ms.is_completed ? '✓' : ''}
                            </button>
                            <span className={`text-sm ${ms.is_completed ? 'text-ufs-400 line-through' : 'text-white'}`}>{ms.title}</span>
                          </div>
                        ))}
                      </div>
                    )}
                    <div className="flex gap-2 mt-2">
                      <input value={milestoneTitle} onChange={e => setMilestoneTitle(e.target.value)} placeholder="New milestone..."
                        className="flex-1 bg-ufs-700 text-xs text-white rounded-md py-1 px-2 outline-none border border-ufs-600/50 focus:border-violet-500/50 placeholder:text-ufs-500"
                        onKeyDown={e => e.key === 'Enter' && addMilestone(g.id)} />
                      <Btn onClick={() => addMilestone(g.id)} small disabled={!milestoneTitle.trim()}>Add</Btn>
                    </div>
                  </div>
                </div>
              )}
            </div>
          ))}
        </div>
      )}
    </div>
  )
}

// ── Tab: Scheduler ──────────────────────────────────────────────────

function SchedulerTab() {
  const [blocks, setBlocks] = useState<ScheduleBlock[]>([])
  const [view, setView] = useState<'today' | 'week'>('today')
  const [loading, setLoading] = useState(true)
  const [showForm, setShowForm] = useState(false)
  const [form, setForm] = useState({ date: new Date().toISOString().slice(0, 10), start_time: '09:00', end_time: '10:00', title: '', priority: '3' })

  const load = useCallback(() => {
    const ep = view === 'week' ? '/schedule/week' : '/schedule/today'
    api<ScheduleBlock[]>(ep).then(setBlocks).catch(() => {}).finally(() => setLoading(false))
  }, [view])
  useEffect(() => { load() }, [load])

  const createBlock = async () => {
    try {
      await api('/schedule/blocks', { method: 'POST', body: JSON.stringify({ ...form, priority: parseInt(form.priority) }) })
      setShowForm(false); load()
    } catch { /* ignore */ }
  }

  const autoGenerate = async () => {
    try {
      await api('/schedule/generate', { method: 'POST', body: JSON.stringify({}) })
      load()
    } catch { /* ignore */ }
  }

  const deleteBlock = async (id: number) => {
    try { await api(`/schedule/blocks/${id}`, { method: 'DELETE' }); load() } catch { /* ignore */ }
  }

  const HOUR_HEIGHT = 48
  const START_HOUR = 6
  const END_HOUR = 24
  const hours = Array.from({ length: END_HOUR - START_HOUR }, (_, i) => START_HOUR + i)

  const timeToPos = (t: string) => {
    const [h, m] = t.split(':').map(Number)
    return (h - START_HOUR) * HOUR_HEIGHT + (m / 60) * HOUR_HEIGHT
  }

  if (loading) return <div className="flex justify-center py-12"><Spinner /></div>

  // Group blocks by date for week view
  const byDate: Record<string, ScheduleBlock[]> = {}
  blocks.forEach(b => { (byDate[b.date] ||= []).push(b) })
  const dates = [...new Set(blocks.map(b => b.date))].sort()

  return (
    <div className="animate-fade-in space-y-4">
      <div className="flex items-center gap-2 flex-wrap">
        <Btn onClick={() => setView('today')} small variant={view === 'today' ? 'primary' : 'ghost'}>Today</Btn>
        <Btn onClick={() => setView('week')} small variant={view === 'week' ? 'primary' : 'ghost'}>Week</Btn>
        <Btn onClick={() => setShowForm(!showForm)} small variant="secondary">+ Block</Btn>
        <Btn onClick={autoGenerate} small variant="secondary">⚡ Auto-Generate</Btn>
      </div>

      {showForm && (
        <div className="rounded-lg bg-ufs-800 border border-violet-500/30 p-4 space-y-3 animate-fade-in">
          <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
            <Input label="Date" value={form.date} onChange={v => setForm(f => ({ ...f, date: v }))} type="date" />
            <Input label="Start" value={form.start_time} onChange={v => setForm(f => ({ ...f, start_time: v }))} type="time" />
            <Input label="End" value={form.end_time} onChange={v => setForm(f => ({ ...f, end_time: v }))} type="time" />
            <Input label="Priority" value={form.priority} onChange={v => setForm(f => ({ ...f, priority: v }))} type="number" />
          </div>
          <Input label="Title" value={form.title} onChange={v => setForm(f => ({ ...f, title: v }))} placeholder="Team Meeting" />
          <div className="flex gap-2">
            <Btn onClick={createBlock} small disabled={!form.title.trim()}>Create</Btn>
            <Btn onClick={() => setShowForm(false)} small variant="ghost">Cancel</Btn>
          </div>
        </div>
      )}

      {/* Timeline */}
      {view === 'today' ? (
        <div className="rounded-xl bg-ufs-800 border border-ufs-600/30 p-4 overflow-auto">
          {blocks.length === 0 ? <EmptyState icon="📅" text="No blocks scheduled" /> : (
            <div className="relative" style={{ height: (END_HOUR - START_HOUR) * HOUR_HEIGHT }}>
              {hours.map(h => (
                <div key={h} className="absolute w-full border-t border-ufs-600/20 flex items-start" style={{ top: (h - START_HOUR) * HOUR_HEIGHT }}>
                  <span className="text-[9px] text-ufs-500 w-10 -mt-1.5 shrink-0">{String(h).padStart(2, '0')}:00</span>
                </div>
              ))}
              {blocks.map(b => {
                const top = timeToPos(b.start_time)
                const h = timeToPos(b.end_time) - top
                return (
                  <div key={b.id} className="absolute left-12 right-2 rounded-md bg-violet-500/20 border border-violet-500/30 px-2 py-1 overflow-hidden group hover:bg-violet-500/25 transition-colors"
                    style={{ top, height: Math.max(h, 20) }}>
                    <div className="flex items-center justify-between">
                      <span className="text-xs text-white font-medium truncate">{b.title}</span>
                      <button onClick={() => deleteBlock(b.id)} className="text-[10px] text-red-400 opacity-0 group-hover:opacity-100 transition-opacity">×</button>
                    </div>
                    <span className="text-[9px] text-ufs-400">{b.start_time}-{b.end_time}</span>
                  </div>
                )
              })}
            </div>
          )}
        </div>
      ) : (
        <div className="grid grid-cols-7 gap-1">
          {dates.map(d => (
            <div key={d} className="rounded-lg bg-ufs-800 border border-ufs-600/30 p-2 min-h-[120px]">
              <div className="text-[10px] text-ufs-400 mb-2 font-semibold">{new Date(d + 'T00:00').toLocaleDateString('ko', { weekday: 'short', day: 'numeric' })}</div>
              {(byDate[d] || []).map(b => (
                <div key={b.id} className="text-[10px] bg-violet-500/15 border border-violet-500/20 rounded px-1.5 py-0.5 mb-0.5 truncate text-violet-300">
                  {b.start_time} {b.title}
                </div>
              ))}
            </div>
          ))}
        </div>
      )}
    </div>
  )
}

// ── Tab: Vocab SRS ──────────────────────────────────────────────────

function VocabTab() {
  const [mode, setMode] = useState<'home' | 'review' | 'browse'>('home')
  const [dueCards, setDueCards] = useState<VocabWord[]>([])
  const [dueCount, setDueCount] = useState(0)
  const [currentIdx, setCurrentIdx] = useState(0)
  const [showAnswer, setShowAnswer] = useState(false)
  const [browse, setBrowse] = useState<VocabWord[]>([])
  const [search, setSearch] = useState('')
  const [level, setLevel] = useState('')
  const [lastResult, setLastResult] = useState<{ xp?: number; achievements?: string[] } | null>(null)
  const startTime = useRef(0)

  useEffect(() => {
    api<{ total: number }>('/japanese/review/due/count').then(d => setDueCount(d.total)).catch(() => {})
  }, [])

  const startReview = async () => {
    try {
      const cards = await api<VocabWord[]>('/japanese/review/due?limit=20')
      if (cards.length === 0) return
      setDueCards(cards); setCurrentIdx(0); setShowAnswer(false); setMode('review')
      startTime.current = Date.now()
    } catch { /* ignore */ }
  }

  const submitReview = async (quality: number) => {
    const card = dueCards[currentIdx]
    if (!card) return
    try {
      const res = await api<{ xp?: { total_xp: number }; new_achievements?: { name: string }[] }>(`/japanese/review/${card.id}`, {
        method: 'POST',
        // eslint-disable-next-line react-hooks/purity -- Date.now() called in async event handler, not during render
        body: JSON.stringify({ quality, time_ms: Date.now() - startTime.current }),
      })
      setLastResult({ xp: res.xp?.total_xp, achievements: res.new_achievements?.map(a => a.name) })
      if (currentIdx < dueCards.length - 1) {
        // eslint-disable-next-line react-hooks/purity -- Date.now() called in async event handler, not during render
        setCurrentIdx(i => i + 1); setShowAnswer(false); startTime.current = Date.now()
      } else {
        setMode('home')
        api<{ total: number }>('/japanese/review/due/count').then(d => setDueCount(d.total)).catch(() => {})
      }
    } catch { /* ignore */ }
  }

  const loadBrowse = useCallback(() => {
    const params = new URLSearchParams()
    if (search) params.set('search', search)
    if (level) params.set('jlpt_level', level)
    params.set('limit', '50')
    api<VocabWord[]>(`/japanese/vocab?${params}`).then(setBrowse).catch(() => {})
  }, [search, level])

  useEffect(() => { if (mode === 'browse') loadBrowse() }, [mode, loadBrowse])

  const card = dueCards[currentIdx]

  if (mode === 'review' && card) {
    return (
      <div className="animate-fade-in max-w-lg mx-auto space-y-6">
        <div className="flex items-center justify-between">
          <span className="text-xs text-ufs-400">{currentIdx + 1} / {dueCards.length}</span>
          <Btn onClick={() => setMode('home')} small variant="ghost">Exit</Btn>
        </div>
        <ProgressBar value={currentIdx + 1} max={dueCards.length} />

        <div className="rounded-xl bg-ufs-800 border border-ufs-600/30 p-8 text-center min-h-[240px] flex flex-col items-center justify-center">
          <div className="flex items-center gap-2 mb-2">
            <div className="text-3xl font-bold text-white">{card.word}</div>
            <SpeakBtn text={card.word} size="lg" />
          </div>
          <Badge text={card.jlpt_level} />
          {!showAnswer ? (
            <button onClick={() => setShowAnswer(true)}
              className="mt-6 px-6 py-3 rounded-lg bg-violet-500/20 text-violet-300 border border-violet-500/30 hover:bg-violet-500/30 transition-all text-sm">
              Show Answer
            </button>
          ) : (
            <div className="mt-4 animate-fade-in">
              <div className="flex items-center justify-center gap-1.5 text-lg text-violet-300 mb-1">{card.reading} <SpeakBtn text={card.reading} /></div>
              <div className="text-sm text-ufs-300 mb-2">{card.meaning}</div>
              {card.example_ja && <div className="flex items-center justify-center gap-1.5 text-xs text-ufs-400 mt-2 italic">{card.example_ja} <SpeakBtn text={card.example_ja} rate={0.8} /></div>}
              {card.example_ko && <div className="text-xs text-ufs-500">{card.example_ko}</div>}
            </div>
          )}
        </div>

        {showAnswer && (
          <div className="grid grid-cols-5 gap-2 animate-fade-in">
            {[
              { q: 0, label: 'Again', color: 'bg-red-500/20 text-red-300 border-red-500/30' },
              { q: 1, label: '1', color: 'bg-orange-500/20 text-orange-300 border-orange-500/30' },
              { q: 2, label: '2', color: 'bg-amber-500/20 text-amber-300 border-amber-500/30' },
              { q: 3, label: 'Hard', color: 'bg-yellow-500/20 text-yellow-300 border-yellow-500/30' },
              { q: 4, label: 'Good', color: 'bg-emerald-500/20 text-emerald-300 border-emerald-500/30' },
            ].map(({ q, label, color }) => (
              <button key={q} onClick={() => submitReview(q)}
                className={`py-2.5 rounded-lg border text-sm font-medium transition-all hover:scale-105 active:scale-95 ${color}`}>
                {label}
              </button>
            ))}
          </div>
        )}

        {lastResult && lastResult.xp && (
          <div className="text-center text-xs text-violet-400 animate-fade-in">+{lastResult.xp} XP</div>
        )}
      </div>
    )
  }

  if (mode === 'browse') {
    return (
      <div className="animate-fade-in space-y-4">
        <div className="flex items-center gap-2">
          <Btn onClick={() => setMode('home')} small variant="ghost">← Back</Btn>
          <Input value={search} onChange={setSearch} placeholder="Search..." className="flex-1" />
          <Select value={level} onChange={setLevel} options={JLPT_LEVELS} className="w-20" />
        </div>
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-2">
          {browse.map(v => (
            <div key={v.id} className="rounded-lg bg-ufs-800 border border-ufs-600/30 p-3 hover:border-violet-500/20 transition-colors">
              <div className="flex items-center gap-2">
                <span className="text-lg font-bold text-white">{v.word}</span>
                <SpeakBtn text={v.word} />
                <Badge text={v.jlpt_level} />
              </div>
              <div className="text-sm text-violet-300">{v.reading}</div>
              <div className="text-xs text-ufs-400 mt-0.5">{v.meaning}</div>
            </div>
          ))}
        </div>
      </div>
    )
  }

  // Home
  return (
    <div className="animate-fade-in max-w-md mx-auto space-y-6 text-center py-8">
      <div className="text-4xl">📚</div>
      <div>
        <div className="text-2xl font-bold text-white">{dueCount}</div>
        <div className="text-sm text-ufs-400">cards due for review</div>
      </div>
      <div className="flex gap-3 justify-center">
        <Btn onClick={startReview} disabled={dueCount === 0}>Start Review</Btn>
        <Btn onClick={() => setMode('browse')} variant="secondary">Browse Vocab</Btn>
      </div>
    </div>
  )
}

// ── Tab: Grammar ────────────────────────────────────────────────────

function GrammarTab() {
  const [mode, setMode] = useState<'list' | 'review'>('list')
  const [items, setItems] = useState<GrammarPoint[]>([])
  const [dueItems, setDueItems] = useState<GrammarPoint[]>([])
  const [currentIdx, setCurrentIdx] = useState(0)
  const [showAnswer, setShowAnswer] = useState(false)
  const [loading, setLoading] = useState(true)
  const [level, setLevel] = useState('')

  useEffect(() => {
    const params = level ? `?jlpt_level=${level}&per_page=100` : '?per_page=100'
    api<Paginated<GrammarPoint>>(`/japanese/grammar/list${params}`).then(d => setItems(d.items)).catch(() => {}).finally(() => setLoading(false))
  }, [level])

  const startReview = async () => {
    try {
      const due = await api<GrammarPoint[]>('/japanese/grammar/review/due?limit=20')
      if (due.length === 0) return
      setDueItems(due); setCurrentIdx(0); setShowAnswer(false); setMode('review')
    } catch { /* ignore */ }
  }

  const submitReview = async (quality: number) => {
    const item = dueItems[currentIdx]
    if (!item) return
    try {
      await api(`/japanese/grammar/review/${item.id}`, { method: 'POST', body: JSON.stringify({ quality }) })
      if (currentIdx < dueItems.length - 1) { setCurrentIdx(i => i + 1); setShowAnswer(false) }
      else setMode('list')
    } catch { /* ignore */ }
  }

  if (mode === 'review' && dueItems[currentIdx]) {
    const g = dueItems[currentIdx]
    return (
      <div className="animate-fade-in max-w-lg mx-auto space-y-6">
        <div className="flex items-center justify-between">
          <span className="text-xs text-ufs-400">{currentIdx + 1} / {dueItems.length}</span>
          <Btn onClick={() => setMode('list')} small variant="ghost">Exit</Btn>
        </div>
        <ProgressBar value={currentIdx + 1} max={dueItems.length} />
        <div className="rounded-xl bg-ufs-800 border border-ufs-600/30 p-8 text-center min-h-[200px] flex flex-col items-center justify-center">
          <div className="flex items-center gap-2 mb-1">
            <div className="text-xl font-bold text-white">{g.grammar_point}</div>
            <SpeakBtn text={g.grammar_point} size="md" />
          </div>
          <div className="text-sm text-ufs-400">{g.formation || g.structure}</div>
          {!showAnswer ? (
            <button onClick={() => setShowAnswer(true)} className="mt-4 px-6 py-2 rounded-lg bg-violet-500/20 text-violet-300 border border-violet-500/30 text-sm">Show</button>
          ) : (
            <div className="mt-4 animate-fade-in">
              <div className="text-sm text-violet-300 mb-2">{g.meaning_ko || g.meaning_en || g.meaning}</div>
              {g.examples?.slice(0, 2).map((ex, i) => (
                <div key={i} className="flex items-center justify-center gap-1.5 text-xs text-ufs-400 mt-1"><span className="text-white">{ex.ja}</span> <SpeakBtn text={ex.ja} /> → {ex.ko}</div>
              ))}
            </div>
          )}
        </div>
        {showAnswer && (
          <div className="grid grid-cols-4 gap-2 animate-fade-in">
            {[{ q: 0, l: 'Again' }, { q: 2, l: 'Hard' }, { q: 4, l: 'Good' }, { q: 5, l: 'Easy' }].map(({ q, l }) => (
              <Btn key={q} onClick={() => submitReview(q)} small variant={q <= 2 ? 'danger' : 'primary'}>{l}</Btn>
            ))}
          </div>
        )}
      </div>
    )
  }

  if (loading) return <div className="flex justify-center py-12"><Spinner /></div>

  return (
    <div className="animate-fade-in space-y-4">
      <div className="flex items-center gap-2">
        <Btn onClick={startReview} small>Review Due</Btn>
        <Select value={level} onChange={setLevel} options={JLPT_LEVELS} className="w-20" />
      </div>
      {items.length === 0 ? <EmptyState icon="📝" text="No grammar points" /> : (
        <div className="space-y-1.5">
          {items.map(g => (
            <div key={g.id} className="rounded-lg bg-ufs-800 border border-ufs-600/30 p-3 hover:border-violet-500/20 transition-colors">
              <div className="flex items-center gap-2 mb-0.5">
                <span className="text-sm font-medium text-white">{g.grammar_point}</span>
                <SpeakBtn text={g.grammar_point} />
                <Badge text={g.jlpt_level} />
                {g.category && <span className="text-[10px] text-ufs-500">{g.category}</span>}
              </div>
              <div className="text-xs text-ufs-400">{g.meaning_ko || g.meaning_en || g.meaning}</div>
              <div className="text-[10px] text-ufs-500 mt-0.5 font-mono">{g.formation || g.structure}</div>
            </div>
          ))}
        </div>
      )}
    </div>
  )
}

// ── Tab: Kanji ──────────────────────────────────────────────────────

function KanjiTab() {
  const [mode, setMode] = useState<'grid' | 'quiz'>('grid')
  const [items, setItems] = useState<KanjiItem[]>([])
  const [loading, setLoading] = useState(true)
  const [level, setLevel] = useState('N5')
  const [quiz, setQuiz] = useState<{ questions: { id: number; character: string; options: string[]; correct_answer: string }[]; current: number; score: number; answered: boolean; selected: string | null }>({ questions: [], current: 0, score: 0, answered: false, selected: null })

  useEffect(() => {
    api<Paginated<KanjiItem>>(`/japanese/kanji?jlpt_level=${level}&per_page=100`).then(d => setItems(d.items)).catch(() => {}).finally(() => setLoading(false))
  }, [level])

  const startQuiz = async (type: 'reading' | 'meaning') => {
    try {
      const res = await api<{ questions: { kanji_id: number; character: string; choices: string[]; answer: string; meaning_ko?: string }[] }>(`/japanese/kanji/quiz/${type}?jlpt_level=${level}&count=10`)
      const qs = (res.questions || []).map(q => ({ id: q.kanji_id, character: q.character, options: q.choices, correct_answer: q.answer }))
      if (qs.length === 0) return
      setQuiz({ questions: qs, current: 0, score: 0, answered: false, selected: null })
      setMode('quiz')
    } catch { /* ignore */ }
  }

  const answer = (opt: string) => {
    if (quiz.answered) return
    const correct = opt === quiz.questions[quiz.current].correct_answer
    setQuiz(q => ({ ...q, answered: true, selected: opt, score: correct ? q.score + 1 : q.score }))
  }

  const nextQuestion = () => {
    if (quiz.current < quiz.questions.length - 1) {
      setQuiz(q => ({ ...q, current: q.current + 1, answered: false, selected: null }))
    } else {
      setMode('grid')
    }
  }

  if (mode === 'quiz' && quiz.questions.length > 0) {
    const q = quiz.questions[quiz.current]
    const done = quiz.current === quiz.questions.length - 1 && quiz.answered
    return (
      <div className="animate-fade-in max-w-md mx-auto space-y-6">
        <div className="flex items-center justify-between">
          <span className="text-xs text-ufs-400">{quiz.current + 1}/{quiz.questions.length} — Score: {quiz.score}</span>
          <Btn onClick={() => setMode('grid')} small variant="ghost">Exit</Btn>
        </div>
        <ProgressBar value={quiz.current + 1} max={quiz.questions.length} />
        <div className="text-center">
          <div className="flex items-center justify-center gap-2 mb-4">
            <span className="text-5xl font-bold text-white">{q.character}</span>
            <SpeakBtn text={q.character} size="lg" />
          </div>
          <div className="grid grid-cols-2 gap-2">
            {q.options.map(opt => {
              let cls = 'bg-ufs-700 text-white border border-ufs-600/50 hover:border-violet-500/50'
              if (quiz.answered) {
                if (opt === q.correct_answer) cls = 'bg-emerald-500/30 text-emerald-300 border border-emerald-500/50'
                else if (opt === quiz.selected) cls = 'bg-red-500/30 text-red-300 border border-red-500/50'
                else cls = 'bg-ufs-700/50 text-ufs-500 border border-ufs-600/30'
              }
              return (
                <button key={opt} onClick={() => answer(opt)} disabled={quiz.answered}
                  className={`py-3 px-4 rounded-lg text-sm transition-all ${cls}`}>{opt}</button>
              )
            })}
          </div>
        </div>
        {quiz.answered && (
          <div className="text-center animate-fade-in">
            {done ? (
              <div className="space-y-2">
                <div className="text-lg font-bold text-white">Final Score: {quiz.score}/{quiz.questions.length}</div>
                <Btn onClick={() => setMode('grid')}>Done</Btn>
              </div>
            ) : <Btn onClick={nextQuestion}>Next →</Btn>}
          </div>
        )}
      </div>
    )
  }

  if (loading) return <div className="flex justify-center py-12"><Spinner /></div>

  return (
    <div className="animate-fade-in space-y-4">
      <div className="flex items-center gap-2 flex-wrap">
        <Select value={level} onChange={v => { setLevel(v); setLoading(true) }} options={JLPT_LEVELS.filter(l => l.value)} className="w-20" />
        <Btn onClick={() => startQuiz('reading')} small>Reading Quiz</Btn>
        <Btn onClick={() => startQuiz('meaning')} small variant="secondary">Meaning Quiz</Btn>
      </div>
      {items.length === 0 ? <EmptyState icon="🔤" text="No kanji for this level" /> : (
        <div className="grid grid-cols-3 sm:grid-cols-5 lg:grid-cols-7 gap-2">
          {items.map(k => (
            <div key={k.id} className="rounded-lg bg-ufs-800 border border-ufs-600/30 p-3 text-center hover:border-violet-500/30 transition-colors group" title={`${k.onyomi} / ${k.kunyomi}`}>
              <div className="flex items-center justify-center gap-0.5">
                <span className="text-2xl font-bold text-white group-hover:text-violet-300 transition-colors">{k.character}</span>
                <SpeakBtn text={k.kunyomi?.split('、')[0]?.replace(/[-.]/g, '') || k.character} />
              </div>
              <div className="text-[10px] text-ufs-400 mt-1 truncate">{k.meaning_ko}</div>
              <div className="text-[9px] text-ufs-500 mt-0.5 truncate">{k.onyomi}</div>
            </div>
          ))}
        </div>
      )}
    </div>
  )
}

// ── Tab: Reading ────────────────────────────────────────────────────

function ReadingTab() {
  const [passages, setPassages] = useState<ReadingPassage[]>([])
  const [active, setActive] = useState<ReadingPassage | null>(null)
  const [answers, setAnswers] = useState<Record<number, string>>({})
  const [result, setResult] = useState<{ score: number; total: number; details: { question_id: number; is_correct: boolean; correct_answer: string }[] } | null>(null)
  const [loading, setLoading] = useState(true)
  const [level, setLevel] = useState('')

  useEffect(() => {
    const params = level ? `?jlpt_level=${level}` : ''
    api<Paginated<ReadingPassage>>(`/japanese/reading${params}`).then(d => setPassages(d.items)).catch(() => {}).finally(() => setLoading(false))
  }, [level])

  const openPassage = async (id: number) => {
    try {
      const p = await api<ReadingPassage>(`/japanese/reading/${id}`)
      setActive(p); setAnswers({}); setResult(null)
    } catch { /* ignore */ }
  }

  const submit = async () => {
    if (!active) return
    try {
      const res = await api<{ correct: number; total: number; score_percent: number; details: { question_id: number; is_correct: boolean; correct_answer: string }[] }>(
        `/japanese/reading/${active.id}/submit`, { method: 'POST', body: JSON.stringify({ answers }) })
      setResult({ score: res.correct, total: res.total, details: res.details || [] })
    } catch { /* ignore */ }
  }

  if (active) {
    return (
      <div className="animate-fade-in max-w-2xl mx-auto space-y-4">
        <Btn onClick={() => { setActive(null); setResult(null) }} small variant="ghost">← Back</Btn>
        <div className="rounded-xl bg-ufs-800 border border-ufs-600/30 p-6">
          <div className="flex items-center gap-2 mb-1">
            <h2 className="text-lg font-bold text-white">{active.title}</h2>
            <Badge text={active.jlpt_level} />
          </div>
          {(active.content_jp) && (
            <div className="mt-4">
              <div className="flex items-start gap-2">
                <div className="text-sm text-ufs-300 leading-relaxed whitespace-pre-wrap border-l-2 border-violet-500/30 pl-4 flex-1">{active.content_jp}</div>
                <SpeakBtn text={active.content_jp} size="md" rate={0.75} />
              </div>
            </div>
          )}
        </div>

        {active.questions && active.questions.length > 0 && (
          <div className="space-y-4">
            {active.questions.map((q, qi) => {
              const r = result?.details.find(r => r.question_id === q.id)
              return (
                <div key={q.id} className="rounded-lg bg-ufs-800 border border-ufs-600/30 p-4">
                  <div className="text-sm text-white mb-2">Q{qi + 1}. {q.question_ko || q.question_jp || q.question}</div>
                  <div className="grid grid-cols-2 gap-2">
                    {q.options.map((opt, oi) => {
                      const letter = String.fromCharCode(97 + oi)
                      let cls = 'bg-ufs-700 text-ufs-300 border border-ufs-600/50 hover:border-violet-500/50'
                      if (answers[q.id] === letter) cls = 'bg-violet-500/20 text-violet-300 border border-violet-500/50'
                      if (r) {
                        if (letter === r.correct_answer) cls = 'bg-emerald-500/20 text-emerald-300 border border-emerald-500/40'
                        else if (letter === answers[q.id] && !r.is_correct) cls = 'bg-red-500/20 text-red-300 border border-red-500/40'
                      }
                      return (
                        <button key={oi} onClick={() => !result && setAnswers(a => ({ ...a, [q.id]: letter }))}
                          disabled={!!result} className={`py-2 px-3 rounded-md text-xs text-left transition-all ${cls}`}>{opt}</button>
                      )
                    })}
                  </div>
                </div>
              )
            })}
            {!result ? (
              <Btn onClick={submit} disabled={Object.keys(answers).length !== active.questions.length}>Submit Answers</Btn>
            ) : (
              <div className="rounded-lg bg-violet-500/10 border border-violet-500/30 p-4 text-center animate-fade-in">
                <div className="text-lg font-bold text-white">{result.score}/{result.total}</div>
                <div className="text-xs text-ufs-400">{Math.round((result.score / result.total) * 100)}% correct</div>
              </div>
            )}
          </div>
        )}
      </div>
    )
  }

  if (loading) return <div className="flex justify-center py-12"><Spinner /></div>

  return (
    <div className="animate-fade-in space-y-4">
      <Select value={level} onChange={setLevel} options={JLPT_LEVELS} className="w-24" />
      {passages.length === 0 ? <EmptyState icon="📖" text="No reading passages" /> : (
        <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
          {passages.map(p => (
            <button key={p.id} onClick={() => openPassage(p.id)}
              className="text-left rounded-lg bg-ufs-800 border border-ufs-600/30 p-4 hover:border-violet-500/30 transition-all">
              <div className="flex items-center gap-2 mb-1">
                <span className="text-sm font-medium text-white">{p.title}</span>
                <Badge text={p.jlpt_level} />
              </div>
              {p.category && <span className="text-[10px] text-ufs-500">{p.category}</span>}
            </button>
          ))}
        </div>
      )}
    </div>
  )
}

// ── Tab: Writing ────────────────────────────────────────────────────

function WritingTab() {
  const [exType, setExType] = useState<'translation' | 'sentence-order' | 'grammar-usage'>('translation')
  const [exercise, setExercise] = useState<{ id: number; prompt: string; hint?: string } | null>(null)
  const [answer, setAnswer] = useState('')
  const [result, setResult] = useState<{ is_correct: boolean; correct_answer: string; feedback?: string } | null>(null)
  const [loading, setLoading] = useState(false)

  const loadExercise = useCallback(async () => {
    setLoading(true); setResult(null); setAnswer('')
    try {
      const ex = await api<{ exercise_id: number; id?: number; prompt?: string; prompt_ko?: string; prompt_jp?: string; hint?: string; question?: string; sentence?: string }>(`/japanese/writing/${exType}`)
      setExercise({ id: ex.exercise_id || ex.id || 0, prompt: ex.prompt_ko || ex.prompt || ex.question || ex.sentence || '', hint: ex.hint || ex.prompt_jp })
    } catch { /* ignore */ }
    setLoading(false)
  }, [exType])

  // eslint-disable-next-line react-hooks/set-state-in-effect -- loadExercise sets loading synchronously before first await; unavoidable for UX
  useEffect(() => { void loadExercise() }, [loadExercise])

  const submit = async () => {
    if (!exercise || !answer.trim()) return
    try {
      const res = await api<{ is_correct: boolean; correct_answer: string; feedback?: string; correct_jp?: string }>(`/japanese/writing/check/${exercise.id}`, {
        method: 'POST', body: JSON.stringify({ user_answer: answer }),
      })
      if (!res.correct_answer && res.correct_jp) res.correct_answer = res.correct_jp
      setResult(res)
    } catch { /* ignore */ }
  }

  return (
    <div className="animate-fade-in max-w-lg mx-auto space-y-4">
      <div className="flex gap-2">
        {(['translation', 'sentence-order', 'grammar-usage'] as const).map(t => (
          <Btn key={t} onClick={() => setExType(t)} small variant={exType === t ? 'primary' : 'ghost'}>
            {t === 'translation' ? '翻訳' : t === 'sentence-order' ? '語順' : '文法'}
          </Btn>
        ))}
      </div>

      {loading ? <div className="flex justify-center py-8"><Spinner /></div> : exercise ? (
        <div className="space-y-4">
          <div className="rounded-xl bg-ufs-800 border border-ufs-600/30 p-6">
            <div className="text-sm text-white leading-relaxed">{exercise.prompt}</div>
            {exercise.hint && <div className="text-xs text-ufs-500 mt-2">Hint: {exercise.hint}</div>}
          </div>

          <textarea value={answer} onChange={e => setAnswer(e.target.value)} placeholder="Write your answer..."
            className="w-full bg-ufs-700 text-sm text-white rounded-lg py-3 px-4 outline-none border border-ufs-600/50 focus:border-violet-500/50 placeholder:text-ufs-500 h-24 resize-none" />

          {!result ? (
            <Btn onClick={submit} disabled={!answer.trim()}>Check Answer</Btn>
          ) : (
            <div className={`rounded-lg p-4 animate-fade-in ${result.is_correct ? 'bg-emerald-500/10 border border-emerald-500/30' : 'bg-red-500/10 border border-red-500/30'}`}>
              <div className="text-sm font-medium mb-1">{result.is_correct ? '✓ Correct!' : '✗ Incorrect'}</div>
              <div className="text-xs text-ufs-300">Answer: {result.correct_answer}</div>
              {result.feedback && <div className="text-xs text-ufs-400 mt-1">{result.feedback}</div>}
              <Btn onClick={loadExercise} small variant="secondary" className="mt-3">Next Exercise</Btn>
            </div>
          )}
        </div>
      ) : <EmptyState icon="✍️" text="No exercises available" />}
    </div>
  )
}

// ── Tab: Quiz ───────────────────────────────────────────────────────

function QuizTab() {
  const [phase, setPhase] = useState<'config' | 'active' | 'results'>('config')
  const [config, setConfig] = useState({ quiz_type: 'flashcard', jlpt_level: 'N5', count: '10' })
  const [questions, setQuestions] = useState<QuizQuestion[]>([])
  const [current, setCurrent] = useState(0)
  const [userAnswers, setUserAnswers] = useState<{ question_id: number; answer: string }[]>([])
  const [results, setResults] = useState<{ score: number; total: number; xp_earned?: number } | null>(null)
  const [timer, setTimer] = useState(0)
  const timerRef = useRef<ReturnType<typeof setInterval> | null>(null)

  const start = async () => {
    try {
      const res = await api<{ questions: (QuizQuestion & { vocab_id?: number })[] }>('/japanese/quiz/start', {
        method: 'POST',
        body: JSON.stringify({ ...config, count: parseInt(config.count) }),
      })
      if (!res.questions?.length) return
      const qs = res.questions.map((q, i) => ({ ...q, id: q.id || q.vocab_id || i }))
      setQuestions(qs); setCurrent(0); setUserAnswers([]); setTimer(0); setPhase('active')
      timerRef.current = setInterval(() => setTimer(t => t + 1), 1000)
    } catch { /* ignore */ }
  }

  const answerQuestion = (ans: string) => {
    const q = questions[current]
    setUserAnswers(a => [...a, { question_id: q.id, answer: ans }])
    if (current < questions.length - 1) setCurrent(c => c + 1)
    else submitAll([...userAnswers, { question_id: q.id, answer: ans }])
  }

  const submitAll = async (answers: { question_id: number; answer: string }[]) => {
    if (timerRef.current) clearInterval(timerRef.current)
    try {
      const res = await api<{ correct: number; total: number; score?: number; xp_earned?: number; accuracy?: number }>('/japanese/quiz/submit', {
        method: 'POST',
        body: JSON.stringify({ quiz_type: config.quiz_type, answers, time_seconds: timer, jlpt_level: config.jlpt_level }),
      })
      setResults({ score: res.correct ?? res.score ?? 0, total: res.total, xp_earned: res.xp_earned }); setPhase('results')
    } catch { setPhase('config') }
  }

  useEffect(() => { return () => { if (timerRef.current) clearInterval(timerRef.current) } }, [])

  if (phase === 'active' && questions[current]) {
    const q = questions[current]
    return (
      <div className="animate-fade-in max-w-md mx-auto space-y-6">
        <div className="flex items-center justify-between">
          <span className="text-xs text-ufs-400">{current + 1}/{questions.length}</span>
          <span className="text-xs text-ufs-400 font-mono">{Math.floor(timer / 60)}:{String(timer % 60).padStart(2, '0')}</span>
        </div>
        <ProgressBar value={current + 1} max={questions.length} />
        <div className="text-center">
          <div className="text-2xl font-bold text-white mb-4">{q.word || q.question}</div>
          <div className="grid grid-cols-2 gap-2">
            {q.options.map((opt, i) => (
              <button key={i} onClick={() => answerQuestion(opt)}
                className="py-3 px-4 rounded-lg bg-ufs-700 text-white border border-ufs-600/50 hover:border-violet-500/50 hover:bg-violet-500/10 transition-all text-sm">{opt}</button>
            ))}
          </div>
        </div>
      </div>
    )
  }

  if (phase === 'results' && results) {
    const pct = Math.round((results.score / results.total) * 100)
    return (
      <div className="animate-fade-in max-w-md mx-auto text-center space-y-6 py-8">
        <div className="text-5xl">{pct >= 80 ? '🎉' : pct >= 50 ? '👍' : '💪'}</div>
        <div>
          <div className="text-3xl font-bold text-white">{results.score}/{results.total}</div>
          <div className="text-sm text-ufs-400">{pct}% · {Math.floor(timer / 60)}:{String(timer % 60).padStart(2, '0')}</div>
        </div>
        {results.xp_earned && <div className="text-violet-400 text-sm">+{results.xp_earned} XP</div>}
        <Btn onClick={() => setPhase('config')}>Try Again</Btn>
      </div>
    )
  }

  return (
    <div className="animate-fade-in max-w-md mx-auto space-y-6 py-8">
      <h2 className="text-lg font-bold text-white text-center">Quiz Setup</h2>
      <Select label="Type" value={config.quiz_type} onChange={v => setConfig(c => ({ ...c, quiz_type: v }))}
        options={[
          { value: 'flashcard', label: 'Flashcard' }, { value: 'meaning', label: 'Meaning' },
          { value: 'reading', label: 'Reading' }, { value: 'time_attack', label: 'Time Attack' },
        ]} />
      <Select label="JLPT Level" value={config.jlpt_level} onChange={v => setConfig(c => ({ ...c, jlpt_level: v }))}
        options={JLPT_LEVELS.filter(l => l.value)} />
      <Input label="Questions" value={config.count} onChange={v => setConfig(c => ({ ...c, count: v }))} type="number" />
      <Btn onClick={start} className="w-full">Start Quiz</Btn>
    </div>
  )
}

// ── Tab: Analytics ──────────────────────────────────────────────────

function AnalyticsTab() {
  const [mastery, setMastery] = useState<Record<string, number> | null>(null)
  const [streak, setStreak] = useState<{ current_streak: number; longest_streak: number; last_study_date: string } | null>(null)
  const [curve, setCurve] = useState<{ date: string; reviews: number; correct: number }[]>([])
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    Promise.all([
      api<{ levels?: Record<string, Record<string, number>> } & Record<string, number>>('/japanese/analytics/mastery')
        .then(d => {
          // API returns {levels: {N5: {bronze: x, ...}}} — flatten to totals
          if (d.levels) {
            const totals: Record<string, number> = {}
            Object.values(d.levels).forEach(lvl => {
              Object.entries(lvl).forEach(([tier, count]) => { totals[tier] = (totals[tier] || 0) + count })
            })
            setMastery(totals)
          } else { setMastery(d) }
        }).catch(() => {}),
      api<{ current_streak: number; longest_streak: number; last_study_date: string }>('/japanese/analytics/streak').then(setStreak).catch(() => {}),
      api<{ daily?: { date: string; reviews: number; correct: number }[] } | { date: string; reviews: number; correct: number }[]>('/japanese/analytics/learning-curve?days=30')
        .then(d => setCurve(Array.isArray(d) ? d : (d as { daily: { date: string; reviews: number; correct: number }[] }).daily || []))
        .catch(() => {}),
    ]).finally(() => setLoading(false))
  }, [])

  if (loading) return <div className="flex justify-center py-12"><Spinner /></div>

  const maxReviews = Math.max(...curve.map(c => c.reviews), 1)
  const masteryTiers = [
    { key: 'master', label: 'Master', color: 'bg-amber-400' },
    { key: 'diamond', label: 'Diamond', color: 'bg-cyan-400' },
    { key: 'gold', label: 'Gold', color: 'bg-yellow-400' },
    { key: 'silver', label: 'Silver', color: 'bg-gray-300' },
    { key: 'bronze', label: 'Bronze', color: 'bg-amber-600' },
  ]

  return (
    <div className="animate-fade-in space-y-6">
      {/* Streak */}
      {streak && (
        <div className="grid grid-cols-3 gap-3">
          <StatCard label="Current Streak" value={`${streak.current_streak}d`} color="text-amber-400" />
          <StatCard label="Longest Streak" value={`${streak.longest_streak}d`} color="text-violet-400" />
          <StatCard label="Last Study" value={streak.last_study_date || '-'} color="text-ufs-300" />
        </div>
      )}

      {/* Mastery Distribution */}
      {mastery && (
        <div className="rounded-xl bg-ufs-800 border border-ufs-600/30 p-4">
          <h3 className="text-xs font-semibold text-ufs-400 uppercase tracking-wider mb-3">Mastery Distribution</h3>
          <div className="space-y-2">
            {masteryTiers.map(t => {
              const val = mastery[t.key] || 0
              const total = Object.values(mastery).reduce((a, b) => a + b, 0) || 1
              return (
                <div key={t.key} className="flex items-center gap-2">
                  <span className="text-[10px] text-ufs-400 w-16">{t.label}</span>
                  <div className="flex-1 h-3 bg-ufs-700 rounded-full overflow-hidden">
                    <div className={`h-full rounded-full ${t.color} transition-all duration-500`} style={{ width: `${(val / total) * 100}%` }} />
                  </div>
                  <span className="text-[10px] text-ufs-400 w-8 text-right">{val}</span>
                </div>
              )
            })}
          </div>
        </div>
      )}

      {/* Learning Curve */}
      {curve.length > 0 && (
        <div className="rounded-xl bg-ufs-800 border border-ufs-600/30 p-4">
          <h3 className="text-xs font-semibold text-ufs-400 uppercase tracking-wider mb-3">30-Day Activity</h3>
          <div className="flex items-end gap-0.5 h-24">
            {curve.map((d, i) => (
              <div key={i} className="flex-1 flex flex-col items-center justify-end" title={`${d.date}: ${d.reviews} reviews`}>
                <div className="w-full bg-violet-500/60 rounded-t-sm transition-all hover:bg-violet-500"
                  style={{ height: `${(d.reviews / maxReviews) * 100}%`, minHeight: d.reviews > 0 ? 2 : 0 }} />
              </div>
            ))}
          </div>
          <div className="flex justify-between text-[8px] text-ufs-500 mt-1">
            <span>{curve[0]?.date.slice(5)}</span>
            <span>{curve[curve.length - 1]?.date.slice(5)}</span>
          </div>
        </div>
      )}
    </div>
  )
}

// ── Tab: Gamification ───────────────────────────────────────────────

function GamificationTab() {
  const [player, setPlayer] = useState<PlayerStats | null>(null)
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    api<PlayerStats>('/japanese/player').then(setPlayer).catch(() => {}).finally(() => setLoading(false))
  }, [])

  if (loading) return <div className="flex justify-center py-12"><Spinner /></div>
  if (!player) return <EmptyState icon="🏆" text="Start studying to unlock gamification!" />

  const xpPct = player.xp_next_level > 0 ? Math.round((player.xp_current_level / player.xp_next_level) * 100) : 0

  return (
    <div className="animate-fade-in space-y-6">
      {/* Player Card */}
      <div className="rounded-xl bg-ufs-800 border border-violet-500/30 p-6 text-center">
        <div className="text-3xl mb-1">{player.title?.icon || '🎓'}</div>
        <div className="text-lg font-bold text-white">{player.title?.name || 'Beginner'}</div>
        <div className="text-sm text-violet-400 mb-3">Level {player.level}</div>
        <div className="max-w-xs mx-auto">
          <ProgressBar value={player.xp_current_level} max={player.xp_next_level} />
          <div className="text-[10px] text-ufs-500 mt-1">{player.xp_current_level} / {player.xp_next_level} XP ({xpPct}%)</div>
        </div>
      </div>

      {/* Stats Grid */}
      <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
        <StatCard label="Total XP" value={player.total_xp.toLocaleString()} color="text-violet-400" />
        <StatCard label="Reviews" value={player.total_reviews} color="text-blue-400" />
        <StatCard label="Accuracy" value={`${Math.round(player.accuracy)}%`} color="text-emerald-400" />
        <StatCard label="Best Combo" value={player.combo_best} color="text-amber-400" />
      </div>

      {/* Streak */}
      <div className="grid grid-cols-2 gap-3">
        <div className="rounded-lg bg-ufs-800 border border-ufs-600/30 p-4 text-center">
          <div className="text-2xl font-bold text-amber-400">🔥 {player.current_streak}</div>
          <div className="text-[10px] text-ufs-400 mt-0.5">Current Streak</div>
        </div>
        <div className="rounded-lg bg-ufs-800 border border-ufs-600/30 p-4 text-center">
          <div className="text-2xl font-bold text-violet-400">⭐ {player.longest_streak}</div>
          <div className="text-[10px] text-ufs-400 mt-0.5">Longest Streak</div>
        </div>
      </div>

      {/* Achievements */}
      {player.achievements.length > 0 && (
        <div className="rounded-xl bg-ufs-800 border border-ufs-600/30 p-4">
          <h3 className="text-xs font-semibold text-ufs-400 uppercase tracking-wider mb-3">
            Achievements ({player.achievements.length})
          </h3>
          <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-4 gap-2">
            {player.achievements.map(a => (
              <div key={a.id} className="rounded-lg bg-violet-500/10 border border-violet-500/20 p-3 text-center hover:bg-violet-500/15 transition-colors">
                <div className="text-xl mb-1">{a.icon}</div>
                <div className="text-[10px] font-medium text-white">{a.name}</div>
                <div className="text-[9px] text-ufs-500 mt-0.5">{a.description}</div>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  )
}

// ── Tab: Finance ────────────────────────────────────────────────────

interface FinCard { id: number; name: string; issuer: string; card_type: string; color: string; icon?: string; billing_day?: number; annual_fee: number; annual_fee_waived: number; benefits?: FinBenefit[] }
interface FinBenefit { id: number; card_id: number; category: string; merchant?: string; benefit_type: string; benefit_value: number; benefit_unit: string; monthly_limit?: number; min_spend?: number }
interface FinSub { id: number; name: string; category: string; price: number; billing_cycle: string; card_id?: number; card_name?: string; is_free_bundled: number; bundled_via?: string; benefits: string[]; benefits_json?: string; usage_check_interval: number; last_used_at?: string; icon?: string; memo?: string; is_active: number }
interface FinExpense { id: number; date: string; amount: number; category: string; merchant?: string; card_id?: number; card_name?: string; description?: string }
interface FinAsset { id: number; name: string; asset_type: string; institution?: string; balance: number; currency: string; memo?: string }
interface FinAlert { id: number; name: string; severity: string; days_inactive: number; price: number; icon?: string }
interface FinDash { monthly_spend: number; monthly_budget: number; budget_remaining: number; subscription_total: number; subscription_count: number; free_bundled_savings: number; net_worth: number; unused_alerts: FinAlert[]; top_categories: { category: string; total: number; count: number }[]; card_spend: { id: number; name: string; color: string; total: number }[] }

type FinView = 'overview' | 'subscriptions' | 'cards' | 'expenses' | 'assets'
const FIN_VIEW_META: { id: FinView; label: string; icon: string }[] = [
  { id: 'overview', label: '총괄', icon: '📊' },
  { id: 'subscriptions', label: '구독', icon: '🔄' },
  { id: 'cards', label: '카드', icon: '💳' },
  { id: 'expenses', label: '지출', icon: '💸' },
  { id: 'assets', label: '자산', icon: '🏦' },
]
const EXP_CATS = [
  { value: 'FOOD', label: '식비' }, { value: 'TRANSPORT', label: '교통' },
  { value: 'SHOPPING', label: '쇼핑' }, { value: 'ENTERTAINMENT', label: '여가' },
  { value: 'UTILITY', label: '공과금' }, { value: 'HEALTH', label: '건강' },
  { value: 'EDUCATION', label: '교육' }, { value: 'CAFE', label: '카페' },
  { value: 'CONVENIENCE', label: '편의점' }, { value: 'OTHER', label: '기타' },
]
const ASSET_TYPES = [
  { value: 'CASH', label: '현금' }, { value: 'SAVINGS', label: '예금' },
  { value: 'INVESTMENT', label: '투자' }, { value: 'RETIREMENT', label: '연금' },
  { value: 'LOAN', label: '대출' }, { value: 'OTHER', label: '기타' },
]

function formatKRW(n: number | null | undefined): string {
  if (n == null || isNaN(n)) return '0'
  if (n === 0) return '0'
  const abs = Math.abs(n)
  const sign = n < 0 ? '-' : ''
  if (abs >= 100000000) return `${sign}${(abs / 100000000).toFixed(1)}억`
  if (abs >= 10000) return `${sign}${(abs / 10000).toFixed(1)}만`
  return n.toLocaleString()
}

function FinanceTab() {
  const [view, setView] = useState<FinView>('overview')
  const [dash, setDash] = useState<FinDash | null>(null)
  const [subs, setSubs] = useState<FinSub[]>([])
  const [cards, setCards] = useState<FinCard[]>([])
  const [expenses, setExpenses] = useState<FinExpense[]>([])
  const [assets, setAssets] = useState<FinAsset[]>([])
  const [loading, setLoading] = useState(true)
  const [busy, setBusy] = useState(false)

  // Expense form
  const [expForm, setExpForm] = useState({ date: new Date().toISOString().slice(0, 10), amount: '', category: 'FOOD', merchant: '', card_id: '', description: '' })
  const [showExpForm, setShowExpForm] = useState(false)

  // Asset form
  const [assetForm, setAssetForm] = useState({ name: '', asset_type: 'CASH', institution: '', balance: '' })
  const [showAssetForm, setShowAssetForm] = useState(false)

  const refresh = useCallback(async () => {
    setLoading(true)
    try {
      if (view === 'overview') {
        const d = await api<FinDash>('/finance/dashboard')
        setDash(d)
      } else if (view === 'subscriptions') {
        setSubs(await api<FinSub[]>('/finance/subscriptions'))
      } else if (view === 'cards') {
        const cc = await api<FinCard[]>('/finance/cards')
        // load benefits for each card
        const withBenefits = await Promise.all(cc.map(async c => {
          const b = await api<FinBenefit[]>(`/finance/cards/${c.id}/benefits`)
          return { ...c, benefits: b }
        }))
        setCards(withBenefits)
      } else if (view === 'expenses') {
        const [exp, cc] = await Promise.all([
          api<FinExpense[]>('/finance/expenses'),
          api<FinCard[]>('/finance/cards'),
        ])
        setExpenses(exp)
        setCards(cc)
      } else if (view === 'assets') {
        setAssets(await api<FinAsset[]>('/finance/assets'))
      }
    } catch { /* ignore */ }
    setLoading(false)
  }, [view])

  useEffect(() => { refresh() }, [refresh])

  const [usedId, setUsedId] = useState<number | null>(null)
  const logUsage = async (subId: number) => {
    try {
      setBusy(true)
      await api(`/finance/subscriptions/${subId}/use`, { method: 'POST' })
      setUsedId(subId)
      setTimeout(() => setUsedId(null), 2000)
      refresh()
    } catch { /* ignore */ } finally { setBusy(false) }
  }

  const addExpense = async () => {
    const amt = Number(expForm.amount)
    if (!amt || isNaN(amt)) return
    try {
      setBusy(true)
      await api('/finance/expenses', {
        method: 'POST',
        body: JSON.stringify({
          ...expForm,
          amount: amt,
          card_id: expForm.card_id ? parseInt(expForm.card_id) : null,
        }),
      })
      setExpForm({ date: new Date().toISOString().slice(0, 10), amount: '', category: 'FOOD', merchant: '', card_id: '', description: '' })
      setShowExpForm(false)
      refresh()
    } catch { /* ignore */ } finally { setBusy(false) }
  }

  const deleteExpense = async (id: number) => {
    if (!confirm('이 지출을 삭제하시겠습니까?')) return
    try {
      await api(`/finance/expenses/${id}`, { method: 'DELETE' })
      refresh()
    } catch { /* ignore */ }
  }

  const addAsset = async () => {
    const bal = Number(assetForm.balance)
    if (!assetForm.name || isNaN(bal)) return
    try {
      setBusy(true)
      await api('/finance/assets', {
        method: 'POST',
        body: JSON.stringify({ ...assetForm, balance: bal }),
      })
      setAssetForm({ name: '', asset_type: 'CASH', institution: '', balance: '' })
      setShowAssetForm(false)
      refresh()
    } catch { /* ignore */ } finally { setBusy(false) }
  }

  const deleteAsset = async (id: number) => {
    if (!confirm('이 자산을 삭제하시겠습니까?')) return
    try {
      await api(`/finance/assets/${id}`, { method: 'DELETE' })
      refresh()
    } catch { /* ignore */ }
  }

  // Sub-nav
  const subNav = (
    <div className="flex items-center gap-1 mb-4">
      {FIN_VIEW_META.map(v => (
        <button key={v.id} onClick={() => setView(v.id)}
          className={`px-3 py-1.5 text-xs font-medium rounded-md transition-all ${
            view === v.id ? 'text-violet-300 bg-violet-500/10 border border-violet-500/30' : 'text-ufs-400 hover:text-white hover:bg-ufs-700/50 border border-transparent'
          }`}>
          {v.icon} {v.label}
        </button>
      ))}
    </div>
  )

  if (loading) return <>{subNav}<div className="flex justify-center py-12"><Spinner /></div></>

  // ── Overview ──
  if (view === 'overview' && dash) {
    const sevColor: Record<string, string> = { WARNING: 'text-amber-400 bg-amber-500/10 border-amber-500/20', CRITICAL: 'text-orange-400 bg-orange-500/10 border-orange-500/20', WASTE: 'text-red-400 bg-red-500/10 border-red-500/20' }
    return (
      <div className="animate-fade-in space-y-4">
        {subNav}
        <div className="grid grid-cols-2 sm:grid-cols-4 gap-2">
          <StatCard label="이번 달 지출" value={`₩${formatKRW(dash.monthly_spend)}`} color="text-blue-400" />
          <StatCard label="구독 합계" value={`₩${formatKRW(dash.subscription_total)}/월`} color="text-violet-400" />
          <StatCard label="무료 절약" value={`₩${formatKRW(dash.free_bundled_savings)}`} color="text-emerald-400" />
          <StatCard label="순자산" value={`₩${formatKRW(dash.net_worth)}`} color="text-cyan-400" />
        </div>

        {dash.unused_alerts.length > 0 && (
          <div className="rounded-xl bg-red-500/5 border border-red-500/20 p-4">
            <h3 className="text-xs font-bold text-red-400 mb-2">⚠️ 놓치고 있는 혜택 ({dash.unused_alerts.length}건)</h3>
            <div className="space-y-1.5">
              {dash.unused_alerts.map(a => (
                <div key={a.id} className={`flex items-center justify-between rounded-lg border p-2.5 ${sevColor[a.severity] || sevColor.WARNING}`}>
                  <span className="text-xs font-medium">{a.icon} {a.name}</span>
                  <span className="text-[10px]">{Math.round(a.days_inactive)}일째 미사용{a.price > 0 && ` · ₩${formatKRW(a.price)}/월`}</span>
                </div>
              ))}
            </div>
          </div>
        )}

        {dash.top_categories.length > 0 && (
          <div className="rounded-xl bg-ufs-800 border border-ufs-600/30 p-4">
            <h3 className="text-xs font-semibold text-ufs-400 uppercase tracking-wider mb-3">카테고리별 지출</h3>
            <div className="space-y-2">
              {dash.top_categories.map(c => {
                const maxAmt = dash.top_categories[0]?.total || 1
                return (
                  <div key={c.category} className="flex items-center gap-2">
                    <span className="text-xs text-ufs-300 w-16 shrink-0">{EXP_CATS.find(e => e.value === c.category)?.label || c.category}</span>
                    <div className="flex-1 h-4 bg-ufs-700 rounded-full overflow-hidden">
                      <div className="h-full bg-violet-500/60 rounded-full transition-all" style={{ width: `${(c.total / maxAmt) * 100}%` }} />
                    </div>
                    <span className="text-xs text-ufs-400 w-20 text-right">₩{formatKRW(c.total)}</span>
                  </div>
                )
              })}
            </div>
          </div>
        )}

        {dash.card_spend.length > 0 && (
          <div className="rounded-xl bg-ufs-800 border border-ufs-600/30 p-4">
            <h3 className="text-xs font-semibold text-ufs-400 uppercase tracking-wider mb-3">카드별 사용</h3>
            <div className="grid grid-cols-2 gap-2">
              {dash.card_spend.map(c => (
                <div key={c.id || 'cash'} className="rounded-lg p-3 border border-ufs-600/30" style={{ borderLeftColor: c.color || '#6366f1', borderLeftWidth: 3 }}>
                  <div className="text-xs text-white font-medium">{c.name || '현금'}</div>
                  <div className="text-sm font-bold text-violet-400">₩{formatKRW(c.total)}</div>
                </div>
              ))}
            </div>
          </div>
        )}
      </div>
    )
  }

  // ── Subscriptions ──
  if (view === 'subscriptions') {
    const totalPaid = subs.filter(s => s.is_active && !s.is_free_bundled).reduce((a, s) => a + s.price, 0)
    const totalFree = subs.filter(s => s.is_active && s.is_free_bundled).reduce((a, s) => a + s.price, 0)
    return (
      <div className="animate-fade-in space-y-4">
        {subNav}
        <div className="grid grid-cols-3 gap-2">
          <StatCard label="월 구독료" value={`₩${formatKRW(totalPaid)}`} color="text-violet-400" />
          <StatCard label="무료 절약" value={`₩${formatKRW(totalFree)}`} color="text-emerald-400" />
          <StatCard label="구독 수" value={subs.length} />
        </div>
        {subs.length === 0 ? <EmptyState icon="🔄" text="구독 없음" /> : <div className="space-y-2">
          {subs.map(s => {
            const daysSince = s.last_used_at ? Math.round((Date.now() - new Date(s.last_used_at).getTime()) / 86400000) : 999
            const statusColor = daysSince <= s.usage_check_interval ? 'bg-emerald-500' : daysSince <= s.usage_check_interval * 2 ? 'bg-amber-500' : 'bg-red-500'
            return (
              <div key={s.id} className="rounded-lg bg-ufs-800 border border-ufs-600/30 p-4 hover:border-violet-500/20 transition-colors">
                <div className="flex items-center justify-between mb-2">
                  <div className="flex items-center gap-2">
                    <div className={`w-2 h-2 rounded-full ${statusColor}`} />
                    <span className="text-sm font-medium text-white">{s.icon} {s.name}</span>
                    {s.is_free_bundled ? (
                      <Badge text={`무료 (${s.bundled_via})`} color="bg-emerald-500/20 text-emerald-300" />
                    ) : (
                      <Badge text={`₩${formatKRW(s.price)}/${s.billing_cycle === 'YEARLY' ? '년' : s.billing_cycle === 'WEEKLY' ? '주' : '월'}`} />
                    )}
                  </div>
                  <Btn onClick={() => logUsage(s.id)} small variant={usedId === s.id ? 'primary' : 'ghost'}>
                    {usedId === s.id ? '✓ 기록됨!' : '✓ 사용'}
                  </Btn>
                </div>
                {s.benefits.length > 0 && (
                  <div className="flex flex-wrap gap-1 ml-4">
                    {s.benefits.map((b, i) => (
                      <span key={i} className="text-[10px] px-1.5 py-0.5 rounded bg-ufs-700 text-ufs-400">{b}</span>
                    ))}
                  </div>
                )}
                <div className="text-[10px] text-ufs-500 ml-4 mt-1">
                  {s.last_used_at ? `마지막 사용: ${daysSince}일 전` : '사용 기록 없음'}
                  {s.card_name && ` · ${s.card_name}`}
                </div>
              </div>
            )
          })}
        </div>}
      </div>
    )
  }

  // ── Cards ──
  if (view === 'cards') {
    return (
      <div className="animate-fade-in space-y-4">
        {subNav}
        {cards.length === 0 ? <EmptyState icon="💳" text="등록된 카드 없음" /> : <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
          {cards.map(c => (
            <div key={c.id} className="rounded-xl border border-ufs-600/30 p-5 relative overflow-hidden" style={{ background: `linear-gradient(135deg, ${c.color}15, ${c.color}05)` }}>
              <div className="absolute top-3 right-3 text-2xl opacity-30">{c.icon}</div>
              <div className="text-lg font-bold text-white mb-0.5">{c.name}</div>
              <div className="text-xs text-ufs-400 mb-3">{c.issuer} · {c.card_type}{c.billing_day ? ` · 결제일 ${c.billing_day}일` : ''}</div>
              {c.benefits && c.benefits.length > 0 && (
                <div className="space-y-1">
                  <div className="text-[10px] text-ufs-500 uppercase tracking-wider">혜택</div>
                  {c.benefits.map(b => (
                    <div key={b.id} className="flex items-center justify-between text-xs">
                      <span className="text-ufs-300">{b.merchant || EXP_CATS.find(e => e.value === b.category)?.label || b.category}</span>
                      <span className="text-violet-300 font-medium">
                        {b.benefit_unit === 'FREE' ? '무료' : `${b.benefit_value}${b.benefit_unit === 'PERCENT' ? '%' : '원'} ${b.benefit_type === 'CASHBACK' ? '캐시백' : b.benefit_type === 'POINT' ? '적립' : '할인'}`}
                        {b.monthly_limit ? ` (월 ${formatKRW(b.monthly_limit)} 한도)` : ''}
                      </span>
                    </div>
                  ))}
                </div>
              )}
            </div>
          ))}
        </div>}
      </div>
    )
  }

  // ── Expenses ──
  if (view === 'expenses') {
    return (
      <div className="animate-fade-in space-y-4">
        {subNav}
        <div className="flex items-center justify-between">
          <Btn onClick={() => setShowExpForm(!showExpForm)} small>{showExpForm ? '취소' : '+ 지출 기록'}</Btn>
        </div>
        {showExpForm && (
          <div className="rounded-xl bg-ufs-800 border border-ufs-600/30 p-4 space-y-3 animate-fade-in">
            <div className="grid grid-cols-2 gap-2">
              <Input label="날짜" type="date" value={expForm.date} onChange={v => setExpForm(f => ({ ...f, date: v }))} />
              <Input label="금액 (원)" type="number" value={expForm.amount} onChange={v => setExpForm(f => ({ ...f, amount: v }))} placeholder="10000" />
            </div>
            <div className="grid grid-cols-3 gap-2">
              <Select label="카테고리" value={expForm.category} onChange={v => setExpForm(f => ({ ...f, category: v }))} options={EXP_CATS} />
              <Input label="가맹점" value={expForm.merchant} onChange={v => setExpForm(f => ({ ...f, merchant: v }))} placeholder="스타벅스" />
              <Select label="결제 카드" value={expForm.card_id} onChange={v => setExpForm(f => ({ ...f, card_id: v }))}
                options={[{ value: '', label: '현금' }, ...cards.map(c => ({ value: String(c.id), label: c.name }))]} />
            </div>
            <Input label="메모" value={expForm.description} onChange={v => setExpForm(f => ({ ...f, description: v }))} placeholder="아메리카노" />
            <Btn onClick={addExpense} small disabled={busy}>{busy ? '저장 중...' : '저장'}</Btn>
          </div>
        )}
        {expenses.length === 0 ? <EmptyState icon="💸" text="지출 기록 없음" /> : (
          <div className="space-y-1.5">
            {expenses.map(e => (
              <div key={e.id} className="flex items-center justify-between rounded-lg bg-ufs-800 border border-ufs-600/30 p-3 hover:border-violet-500/20 transition-colors">
                <div className="flex items-center gap-3">
                  <div>
                    <div className="text-xs text-ufs-500">{e.date}</div>
                    <div className="text-sm text-white">{e.merchant || e.description || EXP_CATS.find(c => c.value === e.category)?.label || e.category}</div>
                  </div>
                  <Badge text={EXP_CATS.find(c => c.value === e.category)?.label || e.category} />
                  {e.card_name && <span className="text-[10px] text-ufs-500">{e.card_name}</span>}
                </div>
                <div className="flex items-center gap-2">
                  <span className="text-sm font-bold text-red-400">-₩{formatKRW(e.amount)}</span>
                  <button onClick={() => deleteExpense(e.id)} title="삭제" aria-label="지출 삭제"
                    className="text-ufs-500 hover:text-red-400 text-xs">✕</button>
                </div>
              </div>
            ))}
          </div>
        )}
      </div>
    )
  }

  // ── Assets ──
  if (view === 'assets') {
    const grouped = ASSET_TYPES.map(t => ({
      ...t,
      items: assets.filter(a => a.asset_type === t.value),
      total: assets.filter(a => a.asset_type === t.value).reduce((s, a) => s + a.balance, 0),
    })).filter(g => g.items.length > 0)
    const netWorth = assets.reduce((s, a) => s + a.balance, 0)
    return (
      <div className="animate-fade-in space-y-4">
        {subNav}
        <div className="grid grid-cols-2 gap-2">
          <StatCard label="순자산" value={`₩${formatKRW(netWorth)}`} color="text-cyan-400" />
          <StatCard label="자산 항목" value={assets.length} />
        </div>
        <Btn onClick={() => setShowAssetForm(!showAssetForm)} small>{showAssetForm ? '취소' : '+ 자산 추가'}</Btn>
        {showAssetForm && (
          <div className="rounded-xl bg-ufs-800 border border-ufs-600/30 p-4 space-y-3 animate-fade-in">
            <div className="grid grid-cols-2 gap-2">
              <Input label="이름" value={assetForm.name} onChange={v => setAssetForm(f => ({ ...f, name: v }))} placeholder="국민은행 예금" />
              <Select label="유형" value={assetForm.asset_type} onChange={v => setAssetForm(f => ({ ...f, asset_type: v }))} options={ASSET_TYPES} />
            </div>
            <div className="grid grid-cols-2 gap-2">
              <Input label="기관" value={assetForm.institution} onChange={v => setAssetForm(f => ({ ...f, institution: v }))} placeholder="KB국민은행" />
              <Input label="잔액 (원)" type="number" value={assetForm.balance} onChange={v => setAssetForm(f => ({ ...f, balance: v }))} placeholder="1000000" />
            </div>
            <Btn onClick={addAsset} small disabled={busy}>{busy ? '저장 중...' : '저장'}</Btn>
          </div>
        )}
        {grouped.length === 0 && !showAssetForm && <EmptyState icon="🏦" text="자산 없음 — 위 버튼으로 추가하세요" />}
        {grouped.map(g => (
          <div key={g.value}>
            <div className="flex items-center justify-between mb-2">
              <span className="text-xs font-semibold text-ufs-400 uppercase tracking-wider">{g.label}</span>
              <span className="text-xs text-violet-400">₩{formatKRW(g.total)}</span>
            </div>
            <div className="space-y-1.5">
              {g.items.map(a => (
                <div key={a.id} className="flex items-center justify-between rounded-lg bg-ufs-800 border border-ufs-600/30 p-3">
                  <div>
                    <div className="text-sm text-white">{a.name}</div>
                    {a.institution && <div className="text-[10px] text-ufs-500">{a.institution}</div>}
                  </div>
                  <div className="flex items-center gap-2">
                    <span className={`text-sm font-bold ${a.balance >= 0 ? 'text-emerald-400' : 'text-red-400'}`}>
                      {a.balance < 0 ? '-' : ''}₩{formatKRW(Math.abs(a.balance))}
                    </span>
                    <button onClick={() => deleteAsset(a.id)} title="삭제" aria-label="자산 삭제"
                      className="text-ufs-500 hover:text-red-400 text-xs">✕</button>
                  </div>
                </div>
              ))}
            </div>
          </div>
        ))}
      </div>
    )
  }

  return <>{subNav}<EmptyState icon="💰" text="Finance" /></>
}

// ── Tab Config ──────────────────────────────────────────────────────

const CORE_TABS = [
  { id: 'dashboard', label: 'Dashboard', icon: '📊' },
  { id: 'routines', label: 'Routines', icon: '🔄' },
  { id: 'habits', label: 'Habits', icon: '✅' },
  { id: 'goals', label: 'Goals', icon: '🎯' },
  { id: 'scheduler', label: 'Schedule', icon: '📅' },
  { id: 'finance', label: 'Finance', icon: '💰' },
]

const JP_TABS = [
  { id: 'vocab', label: 'Vocab SRS', icon: '📚' },
  { id: 'grammar', label: 'Grammar', icon: '📝' },
  { id: 'kanji', label: 'Kanji', icon: '🔤' },
  { id: 'reading', label: 'Reading', icon: '📖' },
  { id: 'writing', label: 'Writing', icon: '✍️' },
  { id: 'quiz', label: 'Quiz', icon: '🎮' },
  { id: 'analytics', label: 'Analytics', icon: '📈' },
  { id: 'gamification', label: 'Player', icon: '🏆' },
]

// ── Main Component ──────────────────────────────────────────────────

export default function LifeApp() {
  const [activeTab, setActiveTab] = useState('dashboard')
  const [health, setHealth] = useState<HealthData | null>(null)
  const [jpExpanded, setJpExpanded] = useState(false)

  useEffect(() => {
    const check = () => fetch(`${API}/health`).then(r => r.ok ? r.json() : null).then(setHealth).catch(() => setHealth(null))
    check(); const interval = setInterval(check, 30000); return () => clearInterval(interval)
  }, [])

  const isJpTab = JP_TABS.some(t => t.id === activeTab)

  const renderTab = () => {
    switch (activeTab) {
      case 'dashboard': return <DashboardTab onNavigate={setActiveTab} />
      case 'routines': return <RoutinesTab />
      case 'habits': return <HabitsTab />
      case 'goals': return <GoalsTab />
      case 'scheduler': return <SchedulerTab />
      case 'finance': return <FinanceTab />
      case 'vocab': return <VocabTab />
      case 'grammar': return <GrammarTab />
      case 'kanji': return <KanjiTab />
      case 'reading': return <ReadingTab />
      case 'writing': return <WritingTab />
      case 'quiz': return <QuizTab />
      case 'analytics': return <AnalyticsTab />
      case 'gamification': return <GamificationTab />
      default: return <DashboardTab onNavigate={setActiveTab} />
    }
  }

  return (
    <div className="max-w-5xl mx-auto">
      {/* Header */}
      <div className="flex items-center gap-3 mb-4">
        <div className="w-8 h-8 rounded-lg flex items-center justify-center" style={{ backgroundColor: '#8b5cf615' }}>
          <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="#8b5cf6" strokeWidth={1.5}>
            <path strokeLinecap="round" strokeLinejoin="round" d="M8 7V3m8 4V3m-9 8h10M5 21h14a2 2 0 002-2V7a2 2 0 00-2-2H5a2 2 0 00-2 2v12a2 2 0 002 2z" />
          </svg>
        </div>
        <div className="flex-1">
          <h1 className="text-lg font-bold text-white">Life<span className="text-violet-400">-Master</span></h1>
        </div>
        {health ? (
          <Badge text={`${health.status} v${health.version}`} color={health.status === 'healthy' ? 'bg-emerald-500/20 text-emerald-400' : 'bg-red-500/20 text-red-400'} />
        ) : (
          <Badge text="offline" color="bg-red-500/20 text-red-400" />
        )}
      </div>

      {/* Tab Bar */}
      <div className="relative flex items-center flex-wrap gap-0.5 mb-6 pb-1 border-b border-ufs-600/30">
        {CORE_TABS.map(t => (
          <button key={t.id} onClick={() => { setActiveTab(t.id); setJpExpanded(false) }}
            className={`shrink-0 px-3 py-2 text-xs font-medium rounded-t-md transition-all ${
              activeTab === t.id ? 'text-violet-300 bg-violet-500/10 border-b-2 border-violet-500' : 'text-ufs-400 hover:text-white hover:bg-ufs-700/50'
            }`}>
            <span className="mr-1">{t.icon}</span>{t.label}
          </button>
        ))}

        {/* Japanese dropdown */}
        <div className="relative ml-1">
          <button onClick={() => setJpExpanded(!jpExpanded)}
            className={`shrink-0 px-3 py-2 text-xs font-medium rounded-t-md transition-all flex items-center gap-1 ${
              isJpTab ? 'text-violet-300 bg-violet-500/10 border-b-2 border-violet-500' : 'text-ufs-400 hover:text-white hover:bg-ufs-700/50'
            }`}>
            🇯🇵 Japanese {isJpTab && <span className="text-[9px]">({JP_TABS.find(t => t.id === activeTab)?.label})</span>}
            <span className="text-[9px]">{jpExpanded ? '▲' : '▼'}</span>
          </button>
          {jpExpanded && (
            <>
              <div className="fixed inset-0 z-40" onClick={() => setJpExpanded(false)} />
              <div className="absolute top-full left-0 mt-1 z-50 bg-ufs-800 border border-ufs-600/50 rounded-lg shadow-xl py-1 min-w-[160px] animate-fade-in">
                {JP_TABS.map(t => (
                  <button key={t.id} onClick={() => { setActiveTab(t.id); setJpExpanded(false) }}
                    className={`w-full text-left px-3 py-2 text-xs transition-colors flex items-center gap-2 ${
                      activeTab === t.id ? 'text-violet-300 bg-violet-500/10' : 'text-ufs-300 hover:text-white hover:bg-ufs-700'
                    }`}>
                    <span>{t.icon}</span>{t.label}
                  </button>
                ))}
              </div>
            </>
          )}
        </div>
      </div>

      {/* Tab Content */}
      <div className="min-h-[400px]">{renderTab()}</div>
    </div>
  )
}
