import { useState, useEffect, useCallback } from 'react'
import { getAcademyToday, getAcademyConcepts, getAcademyConcept, getAcademyPatterns } from '../api'
import HelpButton from '../components/HelpButton'
import PageGuide from '../components/PageGuide'
import { useToast } from '../components/Toast'
import Tip from '../components/Tip'

const DIFFICULTY_LABELS = { 1: '\u2B50 \uC785\uBB38', 2: '\u2B50\u2B50 \uC911\uAE09', 3: '\u2B50\u2B50\u2B50 \uC2EC\uD654' }
const ZONE_COLORS = { safe: '#22c55e', warning: '#f59e0b', danger: '#ef4444', neutral: '#94a3b8' }

export default function Academy({ onNavigate, refreshKey }) {
  const toast = useToast()
  const [todayLesson, setTodayLesson] = useState(null)
  const [categories, setCategories] = useState([])
  const [patterns, setPatterns] = useState([])
  const [selectedConcept, setSelectedConcept] = useState(null)
  const [conceptDetail, setConceptDetail] = useState(null)
  const [loading, setLoading] = useState(true)
  const [tab, setTab] = useState('today') // today | concepts | patterns

  const loadData = useCallback(() => {
    setLoading(true)
    Promise.all([
      getAcademyToday().catch(() => null),
      getAcademyConcepts().catch(() => ({ categories: [] })),
      getAcademyPatterns().catch(() => ({ patterns: [] })),
    ])
      .then(([today, cats, pats]) => {
        setTodayLesson(today)
        setCategories(cats?.categories || [])
        setPatterns(pats?.patterns || [])
      })
      .catch(() => toast.error('\uC544\uCE74\uB370\uBBF8 \uB370\uC774\uD130 \uB85C\uB4DC \uC2E4\uD328'))
      .finally(() => setLoading(false))
  }, [])

  useEffect(() => { loadData() }, [loadData, refreshKey])

  const openConcept = async (id) => {
    try {
      const detail = await getAcademyConcept(id)
      setConceptDetail(detail)
      setSelectedConcept(id)
    } catch { toast.error('\uAC1C\uB150 \uB85C\uB4DC \uC2E4\uD328') }
  }

  if (loading) return <div className="loading"><span className="spinner" /> 로딩 중...</div>

  return (
    <div>
      <div className="page-header">
        <div>
          <h2>{'\uD83C\uDF93'} 투자 아카데미</h2>
          <p className="subtitle">{'\uD604\uC7AC \uC2DC\uC7A5\uC744 \uD1B5\uD574 \uBC30\uC6B0\uB294 \uD22C\uC790 \uC9C0\uC2DD'}</p>
        </div>
        <div style={{ display: 'flex', gap: '0.5rem', alignItems: 'center' }}>
          <button className="btn btn-outline" onClick={loadData}>{'\u21BB'} Refresh</button>
          <HelpButton section="academy" onNavigate={onNavigate} />
        </div>
      </div>

      <PageGuide
        pageId="academy"
        title="투자 아카데미 활용법"
        steps={[
          '오늘의 레슨 → 현재 시장 상황 맞춤 교육 콘텐츠',
          '개념 사전 → RSI, 볼린저밴드 등 핵심 지표 해설',
          '역사적 패턴 → 과거 위기/랠리 사례와 교훈',
          '색상 구간 → 녹색(안전), 노랑(주의), 빨강(위험)',
        ]}
        color="#8b5cf6"
      />

      {/* Tab Navigation */}
      <div style={{ display: 'flex', gap: '0.5rem', marginBottom: '1.5rem' }}>
        {[
          ['today', '\uD83D\uDCDA \uC624\uB298\uC758 \uB808\uC2A8', TIPS.tab_today],
          ['concepts', '\uD83D\uDCD6 \uAC1C\uB150 \uC0AC\uC804', TIPS.tab_concepts],
          ['patterns', '\uD83D\uDD0D \uC5ED\uC0AC\uC801 \uD328\uD134', TIPS.tab_patterns],
        ].map(([key, label, tipText]) => (
          <Tip key={key} text={tipText}>
            <button className={`btn ${tab === key ? 'btn-primary' : 'btn-outline'}`}
              onClick={() => { setTab(key); setSelectedConcept(null) }}>
              {label}
            </button>
          </Tip>
        ))}
      </div>

      {/* Today's Lesson Tab */}
      {tab === 'today' && todayLesson && (
        <>
          {/* Why Now Banner */}
          {todayLesson.lesson?.why_now_kr && (
            <div style={{
              background: 'rgba(59,130,246,0.08)', border: '1px solid rgba(59,130,246,0.3)',
              borderRadius: '0.75rem', padding: '1.25rem', marginBottom: '1.5rem',
            }}>
              <div style={{ fontSize: '0.8rem', color: 'var(--blue)', fontWeight: 600, marginBottom: '0.5rem' }}>
                <Tip text={TIPS.why_now} indicator>
                  {'\uD83D\uDCA1'} {'\uC624\uB298 \uC774 \uAC1C\uB150\uC744 \uBC30\uC6B0\uB294 \uC774\uC720'}
                </Tip>
              </div>
              <div style={{ color: 'var(--text-secondary)', fontSize: '0.9rem', lineHeight: 1.6 }}>
                {todayLesson.lesson.why_now_kr}
              </div>
            </div>
          )}

          {/* Concept Card */}
          {todayLesson.lesson?.concept && renderConceptCard(todayLesson.lesson.concept, todayLesson.lesson.current_value, todayLesson.lesson.current_status)}

          {/* Historical Patterns */}
          {todayLesson.historical_patterns?.length > 0 && (
            <div className="card" style={{ marginTop: '1.5rem' }}>
              <h3 style={{ marginBottom: '1rem' }}>
                {'\uD83D\uDD0D'}{' '}
                <Tip text={TIPS.similar_patterns} indicator>{'\uD604\uC7AC\uC640 \uC720\uC0AC\uD55C \uC5ED\uC0AC\uC801 \uC0AC\uB840'}</Tip>
              </h3>
              {todayLesson.historical_patterns.map((p, i) => renderPatternCard(p, i))}
            </div>
          )}
        </>
      )}

      {/* Concepts Dictionary Tab */}
      {tab === 'concepts' && !selectedConcept && (
        <div>
          {categories.map((cat, ci) => (
            <div key={ci} className="card" style={{ marginBottom: '1rem' }}>
              <h3 style={{ marginBottom: '0.75rem' }}>
                <Tip text={TIPS.category_desc[cat.category] || '\uD574\uB2F9 \uCE74\uD14C\uACE0\uB9AC\uC758 \uD22C\uC790 \uAC1C\uB150\uB4E4.'} indicator>
                  {cat.category_kr}
                </Tip>
              </h3>
              <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(200px, 1fr))', gap: '0.5rem' }}>
                {cat.concepts?.map((c) => (
                  <button key={c.id} className="btn btn-outline" onClick={() => openConcept(c.id)}
                    style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', justifyContent: 'flex-start', textAlign: 'left', padding: '0.75rem' }}>
                    <span style={{ fontSize: '1.2rem' }}>{c.icon}</span>
                    <div>
                      <div style={{ fontWeight: 600, fontSize: '0.85rem' }}>{c.name_kr}</div>
                      <div style={{ fontSize: '0.7rem', color: 'var(--text-muted)' }}>
                        <Tip text={TIPS.difficulty[c.difficulty] || ''}>
                          <span>{DIFFICULTY_LABELS[c.difficulty]}</span>
                        </Tip>
                      </div>
                    </div>
                  </button>
                ))}
              </div>
            </div>
          ))}
        </div>
      )}

      {/* Concept Detail */}
      {tab === 'concepts' && selectedConcept && conceptDetail && (
        <div>
          <button className="btn btn-outline" onClick={() => setSelectedConcept(null)} style={{ marginBottom: '1rem' }}>
            {'\u2190'} {'\uBAA9\uB85D\uC73C\uB85C'}
          </button>
          {renderConceptCard(conceptDetail, conceptDetail.current_value, conceptDetail.current_label)}
        </div>
      )}

      {/* Historical Patterns Tab */}
      {tab === 'patterns' && (
        <div>
          {patterns.length === 0 ? (
            <div className="card" style={{ textAlign: 'center', padding: '2rem', color: 'var(--text-muted)' }}>
              {'\uD604\uC7AC \uC2DC\uC7A5 \uC870\uAC74\uACFC \uC720\uC0AC\uD55C \uC5ED\uC0AC\uC801 \uD328\uD134\uC774 \uC5C6\uC2B5\uB2C8\uB2E4. \uC2DC\uC7A5\uC774 \uC548\uC815\uC801\uC778 \uC0C1\uD0DC\uC785\uB2C8\uB2E4.'}
            </div>
          ) : (
            patterns.map((p, i) => renderPatternCard(p, i))
          )}
        </div>
      )}
    </div>
  )
}

function renderConceptCard(concept, currentValue, currentLabel) {
  return (
    <div className="card">
      <div style={{ display: 'flex', alignItems: 'center', gap: '0.75rem', marginBottom: '1rem' }}>
        <span style={{ fontSize: '2rem' }}>{concept.icon}</span>
        <div>
          <h3 style={{ margin: 0, fontSize: '1.1rem' }}>{concept.name_kr}</h3>
          <div style={{ fontSize: '0.8rem', color: 'var(--text-muted)' }}>{concept.name_en}</div>
        </div>
        {concept.difficulty && (
          <Tip text={TIPS.difficulty[concept.difficulty] || ''}>
            <span style={{ marginLeft: 'auto', fontSize: '0.75rem', color: 'var(--text-muted)' }}>
              {DIFFICULTY_LABELS[concept.difficulty]}
            </span>
          </Tip>
        )}
      </div>

      {/* Current Value */}
      {currentValue != null && (
        <div style={{
          background: 'rgba(59,130,246,0.06)', borderRadius: '0.5rem',
          padding: '0.75rem 1rem', marginBottom: '1rem', display: 'flex',
          alignItems: 'center', justifyContent: 'space-between',
        }}>
          <Tip text={TIPS.current_value}>
            <span style={{ fontWeight: 600, color: 'var(--text-primary)' }}>
              {'\uD604\uC7AC \uAC12'}: {typeof currentValue === 'number' ? currentValue.toLocaleString() : currentValue}
            </span>
          </Tip>
          <Tip text={TIPS.current_status}>
            <span className={`badge badge-${currentLabel === '\uC815\uC0C1' || currentLabel === '\uC644\uB9CC\uD55C \uC815\uC0C1' ? 'completed' : currentLabel?.includes('\uACF5\uD3EC') || currentLabel?.includes('\uC5ED\uC804') ? 'sell' : 'hold'}`}>
              {currentLabel || '-'}
            </span>
          </Tip>
        </div>
      )}

      {/* Definition */}
      <div style={{ color: 'var(--text-secondary)', lineHeight: 1.8, fontSize: '0.9rem', marginBottom: '1rem' }}>
        {concept.definition_kr}
      </div>

      {/* Ranges */}
      {concept.ranges?.length > 0 && (
        <div style={{ marginBottom: '1rem' }}>
          <div style={{ fontWeight: 600, fontSize: '0.85rem', marginBottom: '0.5rem', color: 'var(--text-primary)' }}>
            <Tip text={TIPS.ranges_table} indicator>{'\uD574\uC11D \uAE30\uC900'}</Tip>
          </div>
          <div className="table-responsive">
            <table>
              <thead>
                <tr>
                  <th><Tip text={TIPS.range_col} indicator>{'\uBC94\uC704'}</Tip></th>
                  <th>{'\uB808\uC774\uBE14'}</th>
                  <th>{'\uC758\uBBF8'}</th>
                </tr>
              </thead>
              <tbody>
                {concept.ranges.map((r, i) => (
                  <tr key={i}>
                    <td style={{ fontWeight: 600, whiteSpace: 'nowrap' }}>{r.range}</td>
                    <td><span className="badge badge-hold">{r.label}</span></td>
                    <td style={{ fontSize: '0.85rem', color: 'var(--text-secondary)' }}>{r.meaning_kr}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {/* Key Insight */}
      {concept.key_insight_kr && (
        <div style={{
          background: 'rgba(245,158,11,0.08)', border: '1px solid rgba(245,158,11,0.2)',
          borderRadius: '0.5rem', padding: '1rem',
        }}>
          <div style={{ fontWeight: 600, fontSize: '0.85rem', color: '#f59e0b', marginBottom: '0.4rem' }}>
            <Tip text={TIPS.key_insight} indicator>
              {'\uD83D\uDCA1'} Key Insight
            </Tip>
          </div>
          <div style={{ color: 'var(--text-secondary)', fontSize: '0.85rem', lineHeight: 1.7 }}>
            {concept.key_insight_kr}
          </div>
        </div>
      )}
    </div>
  )
}

function renderPatternCard(pattern, index) {
  return (
    <div key={index} style={{
      padding: '1rem', marginBottom: '0.75rem',
      background: 'var(--bg-primary)', borderRadius: '0.5rem',
      border: '1px solid var(--border)',
    }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', marginBottom: '0.5rem' }}>
        <div>
          <div style={{ fontWeight: 700, fontSize: '1rem', color: 'var(--text-primary)' }}>
            {pattern.name_kr}
          </div>
          <div style={{ fontSize: '0.8rem', color: 'var(--text-muted)' }}>
            {pattern.period} | {pattern.trigger_kr}
          </div>
        </div>
        {pattern.match_score && (
          <Tip text={TIPS.match_score}>
            <span className={`badge ${pattern.match_score >= 60 ? 'badge-sell' : 'badge-hold'}`}>
              {'\uC720\uC0AC\uB3C4'} {pattern.match_score}%
            </span>
          </Tip>
        )}
      </div>

      <div style={{ display: 'flex', gap: '1.5rem', marginBottom: '0.75rem', flexWrap: 'wrap' }}>
        <Tip text={TIPS.vix_peak}>
          <div style={{ fontSize: '0.8rem' }}>
            <span style={{ color: 'var(--text-muted)' }}>VIX Peak: </span>
            <span style={{ fontWeight: 600 }}>{pattern.vix_peak}</span>
          </div>
        </Tip>
        <Tip text={TIPS.fg_low}>
          <div style={{ fontSize: '0.8rem' }}>
            <span style={{ color: 'var(--text-muted)' }}>F&G Low: </span>
            <span style={{ fontWeight: 600 }}>{pattern.fg_low}</span>
          </div>
        </Tip>
        <Tip text={TIPS.sp500_drop}>
          <div style={{ fontSize: '0.8rem' }}>
            <span style={{ color: 'var(--text-muted)' }}>S&P 500: </span>
            <span style={{ fontWeight: 600, color: 'var(--red)' }}>{pattern.sp500_drop}%</span>
          </div>
        </Tip>
        <Tip text={TIPS.recovery}>
          <div style={{ fontSize: '0.8rem' }}>
            <span style={{ color: 'var(--text-muted)' }}>{'\uD68C\uBCF5'}: </span>
            <span style={{ fontWeight: 600 }}>{pattern.recovery_months}{'\uAC1C\uC6D4'}</span>
          </div>
        </Tip>
      </div>

      {pattern.match_reasons?.length > 0 && (
        <Tip text={TIPS.match_reasons}>
          <div style={{ fontSize: '0.8rem', color: 'var(--blue)', marginBottom: '0.5rem' }}>
            {'\uC720\uC0AC \uC870\uAC74'}: {pattern.match_reasons.join(', ')}
          </div>
        </Tip>
      )}

      <div style={{
        background: 'rgba(34,197,94,0.06)', borderRadius: '0.4rem',
        padding: '0.75rem', fontSize: '0.85rem', color: 'var(--text-secondary)', lineHeight: 1.6,
      }}>
        <Tip text={TIPS.lesson}>
          <span>{'\uD83D\uDCDD'}</span>
        </Tip>{' '}
        {pattern.lesson_kr}
      </div>
    </div>
  )
}

// ── Tooltip text definitions ──────────────────────────────────────────────
const TIPS = {
  tab_today: '\uC624\uB298 \uC2DC\uC7A5 \uC0C1\uD669\uC5D0 \uAC00\uC7A5 \uAD00\uB828 \uB192\uC740 \uD22C\uC790 \uAC1C\uB150\uC744\n\uC790\uB3D9\uC73C\uB85C \uC120\uC815\uD558\uC5EC \uD559\uC2B5 \uCF58\uD150\uCE20\uB97C \uC81C\uACF5\uD569\uB2C8\uB2E4.',
  tab_concepts: '\uD22C\uC790\uC5D0 \uD544\uC694\uD55C 12\uAC1C \uD575\uC2EC \uAC1C\uB150\uC744\n\uCE74\uD14C\uACE0\uB9AC\uBCC4\uB85C \uBD84\uB958\uD55C \uC0AC\uC804.\n\uAC01 \uAC1C\uB150\uC744 \uD074\uB9AD\uD558\uBA74 \uC0C1\uC138 \uC124\uBA85\uACFC \uD604\uC7AC \uC2DC\uC7A5\uAC12\uC744 \uD568\uAED8 \uD655\uC778.',
  tab_patterns: '\uD604\uC7AC \uC2DC\uC7A5 \uC870\uAC74(VIX, F&G \uB4F1)\uC774 \uACFC\uAC70 \uC5B4\uB5A4 \uC2DC\uAE30\uC640\n\uC720\uC0AC\uD55C\uC9C0 \uBE44\uAD50 \uBD84\uC11D.\n\uACFC\uAC70 \uC0AC\uB840\uC5D0\uC11C \uD22C\uC790 \uAD50\uD6C8\uC744 \uC5BB\uC744 \uC218 \uC788\uC2B5\uB2C8\uB2E4.',
  why_now: 'AI\uAC00 \uD604\uC7AC \uC2DC\uC7A5 \uB370\uC774\uD130\uB97C \uBD84\uC11D\uD558\uC5EC\n\uC624\uB298 \uAC00\uC7A5 \uBC30\uC6CC\uC57C \uD560 \uAC1C\uB150\uC744 \uC120\uC815\uD55C \uC774\uC720.\n\uC608: VIX \uAE09\uB4F1 \u2192 VIX \uAC1C\uB150 \uD559\uC2B5, F&G \uADF9\uB2E8 \u2192 \uACF5\uD3EC/\uD0D0\uC695 \uD559\uC2B5.',
  similar_patterns: '\uD604\uC7AC \uC2DC\uC7A5 \uC870\uAC74\uC774 \uACFC\uAC70 \uC704\uAE30/\uC870\uC815 \uC2DC\uAE30\uC640\n\uC5BC\uB9C8\uB098 \uC720\uC0AC\uD55C\uC9C0 \uBE44\uAD50\uD55C \uACB0\uACFC.\n\uACFC\uAC70 \uD68C\uBCF5 \uAE30\uAC04\uACFC \uD22C\uC790 \uAD50\uD6C8\uC744 \uD568\uAED8 \uC81C\uACF5.',
  match_score: '\uC720\uC0AC\uB3C4 \uC810\uC218 (0~100%).\n\uD604\uC7AC VIX, F&G \uC9C0\uC218, \uAE08\uB9AC \uB4F1\uC774\n\uACFC\uAC70 \uD574\uB2F9 \uC2DC\uAE30\uC758 \uC870\uAC74\uACFC \uC5BC\uB9C8\uB098 \uC77C\uCE58\uD558\uB294\uC9C0 \uBCF4\uC5EC\uC90D\uB2C8\uB2E4.\n60% \uC774\uC0C1\uC774\uBA74 \uB9E4\uC6B0 \uC720\uC0AC\uD55C \uC0C1\uD669.',
  vix_peak: 'VIX Peak: \uD574\uB2F9 \uC2DC\uAE30 VIX \uCD5C\uACE0\uCE58.\nVIX\uB294 \uC2DC\uC7A5 \uACF5\uD3EC/\uBCC0\uB3D9\uC131 \uC9C0\uC218.\n20 \uBBF8\uB9CC \uC815\uC0C1, 30+ \uBD88\uC548, 40+ \uACF5\uD3EC, 80+ \uADF9\uB2E8\uC801 \uACF5\uD3EC.',
  fg_low: 'F&G Low: \uD574\uB2F9 \uC2DC\uAE30 Fear & Greed \uC9C0\uC218 \uCD5C\uC800\uCE58.\n0~100 \uBC94\uC704.\n20 \uBBF8\uB9CC\uC774\uBA74 \uADF9\uB2E8\uC801 \uACF5\uD3EC, \uC5ED\uC0AC\uC801\uC73C\uB85C \uB9E4\uC218 \uAE30\uD68C.',
  sp500_drop: 'S&P 500 \uCD5C\uB300 \uD558\uB77D\uD3ED.\n\uD574\uB2F9 \uC2DC\uAE30 \uACE0\uC810 \uB300\uBE44 \uC5BC\uB9C8\uB098 \uD558\uB77D\uD588\uB294\uC9C0 \uBCF4\uC5EC\uC90D\uB2C8\uB2E4.\n\uD558\uB77D\uD3ED\uC774 \uD074\uC218\uB85D \uD68C\uBCF5 \uD6C4 \uC218\uC775\uB960\uB3C4 \uB192\uC558\uC2B5\uB2C8\uB2E4.',
  recovery: '\uD68C\uBCF5 \uAE30\uAC04.\n\uC800\uC810\uC5D0\uC11C \uC774\uC804 \uACE0\uC810\uC744 \uD68C\uBCF5\uD558\uAE30\uAE4C\uC9C0 \uAC78\uB9B0 \uAC1C\uC6D4 \uC218.\n\uBD84\uD560 \uB9E4\uC218 \uC2DC \uD68C\uBCF5 \uAE30\uAC04\uC744 \uCC38\uACE0\uD558\uC5EC \uC778\uB0B4\uC2EC\uC744 \uAC00\uC9C8 \uC218 \uC788\uC2B5\uB2C8\uB2E4.',
  match_reasons: '\uC720\uC0AC\uD558\uB2E4\uACE0 \uD310\uB2E8\uD55C \uAD6C\uCCB4\uC801 \uADFC\uAC70.\n\uC608: "F&G 12 \u2264 15" = \uD604\uC7AC F&G\uAC00 12\uC774\uACE0, \uD574\uB2F9 \uD328\uD134\uC758\n\uACBD\uACC4\uAC12 15 \uC774\uD558\uC774\uBBC0\uB85C \uC720\uC0AC \uC870\uAC74 \uCDA9\uC871.',
  lesson: '\uD574\uB2F9 \uC2DC\uAE30\uC5D0\uC11C \uC5BB\uC744 \uC218 \uC788\uB294 \uD22C\uC790 \uAD50\uD6C8.\n\uACFC\uAC70 \uC704\uAE30/\uC870\uC815 \uAE30\uAC04\uC758 \uD22C\uC790 \uACB0\uACFC\uB97C \uBC14\uD0D5\uC73C\uB85C\n\uD604\uC7AC \uC801\uC6A9\uD560 \uC218 \uC788\uB294 \uC804\uB7B5\uC744 \uC81C\uC2DC\uD569\uB2C8\uB2E4.',
  current_value: '\uD604\uC7AC \uC2E4\uC2DC\uAC04 \uC2DC\uC7A5\uC5D0\uC11C\uC758 \uD574\uB2F9 \uC9C0\uD45C \uAC12.\n\uC704\uC758 \uD574\uC11D \uAE30\uC900 \uD45C\uC640 \uBE44\uAD50\uD558\uC5EC\n\uD604\uC7AC \uC5B4\uB5A4 \uAD6C\uAC04\uC5D0 \uC788\uB294\uC9C0 \uD655\uC778\uD558\uC138\uC694.',
  current_status: '\uD604\uC7AC \uAC12\uC774 \uC5B4\uB5A4 \uAD6C\uAC04\uC5D0 \uD574\uB2F9\uD558\uB294\uC9C0 \uD45C\uC2DC.\n\uD45C\uC758 \uBC94\uC704/\uB808\uC774\uBE14\uACFC \uB9E4\uCE6D\uB41C \uC0C1\uD0DC \uBC30\uC9C0.',
  ranges_table: '\uD574\uB2F9 \uC9C0\uD45C\uC758 \uC218\uCE58 \uBC94\uC704\uBCC4 \uD574\uC11D \uAE30\uC900.\n\uAC01 \uAD6C\uAC04\uC774 \uC758\uBBF8\uD558\uB294 \uC2DC\uC7A5 \uC0C1\uD0DC\uC640\n\uAD8C\uC7A5 \uD22C\uC790 \uD589\uB3D9\uC744 \uD568\uAED8 \uBCF4\uC5EC\uC90D\uB2C8\uB2E4.',
  range_col: '\uC9C0\uD45C\uC758 \uC218\uCE58 \uBC94\uC704.\n\uD604\uC7AC \uAC12\uC774 \uC5B4\uB290 \uBC94\uC704\uC5D0 \uC18D\uD558\uB294\uC9C0 \uD655\uC778\uD558\uC5EC\n\uC758\uBBF8\uC640 \uD22C\uC790 \uBC29\uD5A5\uC744 \uD310\uB2E8\uD560 \uC218 \uC788\uC2B5\uB2C8\uB2E4.',
  key_insight: '\uD575\uC2EC \uD22C\uC790 \uC778\uC0AC\uC774\uD2B8.\n\uD574\uB2F9 \uAC1C\uB150\uC744 \uC2E4\uC804\uC5D0 \uC801\uC6A9\uD560 \uB54C\n\uBC18\uB4DC\uC2DC \uAE30\uC5B5\uD574\uC57C \uD560 \uD575\uC2EC \uD3EC\uC778\uD2B8.',
  difficulty: {
    1: '\uC785\uBB38 \uB09C\uC774\uB3C4.\n\uD22C\uC790 \uCD08\uBCF4\uC790\uB3C4 \uC27D\uAC8C \uC774\uD574\uD560 \uC218 \uC788\uB294 \uAE30\uBCF8 \uAC1C\uB150.',
    2: '\uC911\uAE09 \uB09C\uC774\uB3C4.\n\uAE30\uBCF8 \uAC1C\uB150\uC744 \uC774\uD574\uD55C \uD6C4 \uD559\uC2B5\uD558\uBA74 \uC88B\uC740 \uAC1C\uB150.',
    3: '\uC2EC\uD654 \uB09C\uC774\uB3C4.\n\uD22C\uC790 \uACBD\uD5D8\uC774 \uC5B4\uB290 \uC815\uB3C4 \uC788\uB294 \uBD84\uC5D0\uAC8C \uC801\uD569\uD55C \uAC1C\uB150.',
  },
  category_desc: {
    macro: '\uAC70\uC2DC\uACBD\uC81C \uC9C0\uD45C\uB4E4.\n\uAE08\uB9AC, \uC218\uC775\uB960 \uACE1\uC120 \uB4F1 \uACBD\uC81C \uC804\uCCB4\uC758 \uBC29\uD5A5\uC744 \uBCF4\uC5EC\uC8FC\uB294 \uC9C0\uD45C.',
    sentiment: '\uC2DC\uC7A5 \uC2EC\uB9AC \uC9C0\uD45C\uB4E4.\nVIX, F&G \uB4F1 \uD22C\uC790\uC790\uB4E4\uC758 \uACF5\uD3EC\uC640 \uD0D0\uC695\uC744 \uCE21\uC815\uD558\uB294 \uC9C0\uD45C.',
    technical: '\uAE30\uC220\uC801 \uBD84\uC11D \uC9C0\uD45C\uB4E4.\nRSI, MACD, \uC774\uACA9\uB3C4 \uB4F1 \uCC28\uD2B8 \uAE30\uBC18 \uB9E4\uB9E4 \uD0C0\uC774\uBC0D \uC9C0\uD45C.',
    risk_management: '\uB9AC\uC2A4\uD06C \uAD00\uB9AC \uAC1C\uB150\uB4E4.\n\uC190\uC808, \uD3EC\uC9C0\uC158 \uC0AC\uC774\uC9D5, R:R \uBE44\uC728 \uB4F1 \uC790\uBCF8 \uBCF4\uC804 \uC804\uB7B5.',
    strategy: '\uD22C\uC790 \uC804\uB7B5 \uAC1C\uB150\uB4E4.\nDCA, \uC139\uD130 \uB85C\uD14C\uC774\uC158, \uC5ED\uBC1C\uC0C1 \uD22C\uC790 \uB4F1 \uC2E4\uC804 \uC804\uB7B5.',
  },
}
