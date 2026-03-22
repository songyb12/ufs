import type { RhythmStats, RhythmHit, RhythmRating } from '../../hooks/useRhythmScore'

interface RhythmScorePanelProps {
  active: boolean
  stats: RhythmStats
  lastHit: RhythmHit | null
  isMetronomePlaying: boolean
  onStart: () => void
  onStop: () => void
  onReset: () => void
}

const RATING_COLORS: Record<RhythmRating, string> = {
  perfect: 'text-emerald-400',
  good: 'text-sky-400',
  ok: 'text-amber-400',
  miss: 'text-rose-400',
}

const RATING_BG: Record<RhythmRating, string> = {
  perfect: 'bg-emerald-500/20 text-emerald-400',
  good: 'bg-sky-500/20 text-sky-400',
  ok: 'bg-amber-500/20 text-amber-400',
  miss: 'bg-rose-500/20 text-rose-400',
}

const RATING_LABELS: Record<RhythmRating, string> = {
  perfect: 'PERFECT',
  good: 'GOOD',
  ok: 'OK',
  miss: 'MISS',
}

/** Visual offset bar width: maps ±120ms to ±50% of container */
function offsetToPercent(offsetMs: number): number {
  const clamped = Math.max(-120, Math.min(120, offsetMs))
  return (clamped / 120) * 50
}

export function RhythmScorePanel({
  active,
  stats,
  lastHit,
  isMetronomePlaying,
  onStart,
  onStop,
  onReset,
}: RhythmScorePanelProps) {
  const canStart = isMetronomePlaying && !active

  return (
    <section className="bg-slate-800 rounded-lg p-4">
      {/* Header */}
      <div className="flex items-center justify-between mb-3">
        <h3 className="text-sm font-semibold text-slate-300">Rhythm Score</h3>
        <button
          onClick={active ? onStop : onStart}
          disabled={!active && !canStart}
          className={`px-3 py-1 rounded text-xs font-medium transition-colors ${
            active
              ? 'bg-rose-500/20 text-rose-400 hover:bg-rose-500/30'
              : canStart
                ? 'bg-emerald-500/20 text-emerald-400 hover:bg-emerald-500/30'
                : 'bg-slate-700 text-slate-600 cursor-not-allowed'
          }`}
        >
          {active ? 'Stop' : 'Start'}
        </button>
      </div>

      {/* Inactive hint */}
      {!active && !canStart && (
        <p className="text-xs text-slate-600">
          메트로놈을 재생하면 MIDI 입력의 리듬 정확도를 측정할 수 있습니다.
        </p>
      )}

      {!active && canStart && (
        <p className="text-xs text-slate-500">
          Start를 눌러 리듬 채점을 시작하세요. MIDI로 연주하면 비트 대비 타이밍이 측정됩니다.
        </p>
      )}

      {/* Active display */}
      {active && (
        <div className="space-y-3">
          {/* Timing offset visualizer */}
          <div className="relative h-10 bg-slate-900 rounded-lg overflow-hidden">
            {/* Center line (on-beat) */}
            <div className="absolute left-1/2 top-0 bottom-0 w-px bg-slate-600" />
            {/* Perfect zone */}
            <div
              className="absolute top-0 bottom-0 bg-emerald-500/10 border-x border-emerald-500/20"
              style={{ left: `${50 - (30/120)*50}%`, width: `${(60/120)*100}%` }}
            />
            {/* Good zone */}
            <div
              className="absolute top-0 bottom-0 bg-sky-500/5 border-x border-sky-500/10"
              style={{ left: `${50 - (60/120)*50}%`, width: `${(120/120)*100}%` }}
            />

            {/* Labels */}
            <span className="absolute left-1 top-0.5 text-[9px] text-slate-600">EARLY</span>
            <span className="absolute right-1 top-0.5 text-[9px] text-slate-600">LATE</span>

            {/* Hit marker */}
            {lastHit && (
              <div
                className={`absolute top-1 bottom-1 w-2 rounded-full transition-all duration-75 ${
                  lastHit.rating === 'perfect' ? 'bg-emerald-400'
                  : lastHit.rating === 'good' ? 'bg-sky-400'
                  : lastHit.rating === 'ok' ? 'bg-amber-400'
                  : 'bg-rose-400'
                }`}
                style={{ left: `calc(${50 + offsetToPercent(lastHit.offsetMs)}% - 4px)` }}
              />
            )}

            {/* Recent hits (faded dots) */}
            {stats.recentHits.slice(1, 8).map((h, i) => (
              <div
                key={i}
                className="absolute top-3 w-1.5 h-1.5 rounded-full bg-slate-500"
                style={{
                  left: `calc(${50 + offsetToPercent(h.offsetMs)}% - 3px)`,
                  opacity: 0.5 - i * 0.06,
                }}
              />
            ))}
          </div>

          {/* Last hit feedback */}
          {lastHit && (
            <div className="flex items-center justify-center gap-2">
              <span className={`px-3 py-1 rounded-full text-xs font-bold ${RATING_BG[lastHit.rating]}`}>
                {RATING_LABELS[lastHit.rating]}
              </span>
              <span className="text-xs text-slate-500">
                {lastHit.offsetMs > 0 ? '+' : ''}{lastHit.offsetMs}ms
              </span>
            </div>
          )}

          {/* Stats bar */}
          {stats.total > 0 && (
            <>
              <div className="flex items-center justify-between text-xs">
                <div className="flex items-center gap-3">
                  <span className={`font-bold ${
                    stats.accuracy >= 80 ? 'text-emerald-400'
                    : stats.accuracy >= 50 ? 'text-amber-400'
                    : 'text-rose-400'
                  }`}>
                    {stats.accuracy}%
                  </span>
                  <span className="text-slate-500">{stats.total} notes</span>
                  <span className="text-slate-600">
                    avg {stats.avgOffsetMs > 0 ? '+' : ''}{stats.avgOffsetMs}ms
                  </span>
                </div>
                <button
                  onClick={onReset}
                  className="text-slate-600 hover:text-slate-400 transition-colors"
                >
                  Reset
                </button>
              </div>

              {/* Rating breakdown */}
              <div className="flex gap-2 text-[10px]">
                <span className={RATING_COLORS.perfect}>
                  P:{stats.perfect}
                </span>
                <span className={RATING_COLORS.good}>
                  G:{stats.good}
                </span>
                <span className={RATING_COLORS.ok}>
                  OK:{stats.ok}
                </span>
                <span className={RATING_COLORS.miss}>
                  M:{stats.miss}
                </span>
              </div>

              {/* Recent hits mini bar */}
              <div className="flex gap-0.5">
                {stats.recentHits.map((h, i) => (
                  <div
                    key={i}
                    className={`h-2 flex-1 rounded-sm ${
                      h.rating === 'perfect' ? 'bg-emerald-500'
                      : h.rating === 'good' ? 'bg-sky-500'
                      : h.rating === 'ok' ? 'bg-amber-500'
                      : 'bg-rose-500'
                    }`}
                    style={{ opacity: 1 - i * 0.04 }}
                    title={`${h.offsetMs > 0 ? '+' : ''}${h.offsetMs}ms`}
                  />
                ))}
              </div>
            </>
          )}
        </div>
      )}
    </section>
  )
}
