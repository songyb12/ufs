import { useState, useEffect, useCallback } from 'react'
import { getAcademyToday, getAcademyConcepts, getAcademyConcept, getAcademyPatterns } from '../api'
import HelpButton from '../components/HelpButton'
import PageGuide from '../components/PageGuide'
import { useToast } from '../components/Toast'
import Tip from '../components/Tip'

const DIFFICULTY_LABELS = { 1: '⭐ 입문', 2: '⭐⭐ 중급', 3: '⭐⭐⭐ 심화' }
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
      .catch(() => toast.error('아카데미 데이터 로드 실패'))
      .finally(() => setLoading(false))
  }, [])

  useEffect(() => { loadData() }, [loadData, refreshKey])

  const openConcept = async (id) => {
    try {
      const detail = await getAcademyConcept(id)
      setConceptDetail(detail)
      setSelectedConcept(id)
    } catch { toast.error('개념 로드 실패') }
  }

  if (loading) return <div className="loading"><span className="spinner" /> 로딩 중...</div>

  return (
    <div>
      <div className="page-header">
        <div>
          <h2>{'🎓'} 투자 아카데미</h2>
          <p className="subtitle">{'현재 시장을 통해 배우는 투자 지식'}</p>
        </div>
        <div style={{ display: 'flex', gap: '0.5rem', alignItems: 'center' }}>
          <button className="btn btn-outline" onClick={loadData}>{'↻'} Refresh</button>
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
          ['today', '📚 오늘의 레슨', TIPS.tab_today],
          ['concepts', '📖 개념 사전', TIPS.tab_concepts],
          ['patterns', '🔍 역사적 패턴', TIPS.tab_patterns],
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
                  {'💡'} {'오늘 이 개념을 배우는 이유'}
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
                {'🔍'}{' '}
                <Tip text={TIPS.similar_patterns} indicator>{'현재와 유사한 역사적 사례'}</Tip>
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
                <Tip text={TIPS.category_desc[cat.category] || '해당 카테고리의 투자 개념들.'} indicator>
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
            {'←'} {'목록으로'}
          </button>
          {renderConceptCard(conceptDetail, conceptDetail.current_value, conceptDetail.current_label)}
        </div>
      )}

      {/* Historical Patterns Tab */}
      {tab === 'patterns' && (
        <div>
          {patterns.length === 0 ? (
            <div className="card" style={{ textAlign: 'center', padding: '2rem', color: 'var(--text-muted)' }}>
              {'현재 시장 조건과 유사한 역사적 패턴이 없습니다. 시장이 안정적인 상태입니다.'}
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
              {'현재 값'}: {typeof currentValue === 'number' ? currentValue.toLocaleString() : currentValue}
            </span>
          </Tip>
          <Tip text={TIPS.current_status}>
            <span className={`badge badge-${currentLabel === '정상' || currentLabel === '완만한 정상' ? 'completed' : currentLabel?.includes('공포') || currentLabel?.includes('역전') ? 'sell' : 'hold'}`}>
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
            <Tip text={TIPS.ranges_table} indicator>{'해석 기준'}</Tip>
          </div>
          <div className="table-responsive">
            <table>
              <thead>
                <tr>
                  <th><Tip text={TIPS.range_col} indicator>{'범위'}</Tip></th>
                  <th>{'레이블'}</th>
                  <th>{'의미'}</th>
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
              {'💡'} Key Insight
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
              {'유사도'} {pattern.match_score}%
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
            <span style={{ color: 'var(--text-muted)' }}>{'회복'}: </span>
            <span style={{ fontWeight: 600 }}>{pattern.recovery_months}{'개월'}</span>
          </div>
        </Tip>
      </div>

      {pattern.match_reasons?.length > 0 && (
        <Tip text={TIPS.match_reasons}>
          <div style={{ fontSize: '0.8rem', color: 'var(--blue)', marginBottom: '0.5rem' }}>
            {'유사 조건'}: {pattern.match_reasons.join(', ')}
          </div>
        </Tip>
      )}

      <div style={{
        background: 'rgba(34,197,94,0.06)', borderRadius: '0.4rem',
        padding: '0.75rem', fontSize: '0.85rem', color: 'var(--text-secondary)', lineHeight: 1.6,
      }}>
        <Tip text={TIPS.lesson}>
          <span>{'📝'}</span>
        </Tip>{' '}
        {pattern.lesson_kr}
      </div>
    </div>
  )
}

// ── Tooltip text definitions ──────────────────────────────────────────────
const TIPS = {
  tab_today: '오늘 시장 상황에 가장 관련 높은 투자 개념을\n자동으로 선정하여 학습 콘텐츠를 제공합니다.',
  tab_concepts: '투자에 필요한 12개 핵심 개념을\n카테고리별로 분류한 사전.\n각 개념을 클릭하면 상세 설명과 현재 시장값을 함께 확인.',
  tab_patterns: '현재 시장 조건(VIX, F&G 등)이 과거 어떤 시기와\n유사한지 비교 분석.\n과거 사례에서 투자 교훈을 얻을 수 있습니다.',
  why_now: 'AI가 현재 시장 데이터를 분석하여\n오늘 가장 배워야 할 개념을 선정한 이유.\n예: VIX 급등 → VIX 개념 학습, F&G 극단 → 공포/탐욕 학습.',
  similar_patterns: '현재 시장 조건이 과거 위기/조정 시기와\n얼마나 유사한지 비교한 결과.\n과거 회복 기간과 투자 교훈을 함께 제공.',
  match_score: '유사도 점수 (0~100%).\n현재 VIX, F&G 지수, 금리 등이\n과거 해당 시기의 조건과 얼마나 일치하는지 보여줍니다.\n60% 이상이면 매우 유사한 상황.',
  vix_peak: 'VIX Peak: 해당 시기 VIX 최고치.\nVIX는 시장 공포/변동성 지수.\n20 미만 정상, 30+ 불안, 40+ 공포, 80+ 극단적 공포.',
  fg_low: 'F&G Low: 해당 시기 Fear & Greed 지수 최저치.\n0~100 범위.\n20 미만이면 극단적 공포, 역사적으로 매수 기회.',
  sp500_drop: 'S&P 500 최대 하락폭.\n해당 시기 고점 대비 얼마나 하락했는지 보여줍니다.\n하락폭이 클수록 회복 후 수익률도 높았습니다.',
  recovery: '회복 기간.\n저점에서 이전 고점을 회복하기까지 걸린 개월 수.\n분할 매수 시 회복 기간을 참고하여 인내심을 가질 수 있습니다.',
  match_reasons: '유사하다고 판단한 구체적 근거.\n예: "F&G 12 ≤ 15" = 현재 F&G가 12이고, 해당 패턴의\n경계값 15 이하이므로 유사 조건 충족.',
  lesson: '해당 시기에서 얻을 수 있는 투자 교훈.\n과거 위기/조정 기간의 투자 결과를 바탕으로\n현재 적용할 수 있는 전략을 제시합니다.',
  current_value: '현재 실시간 시장에서의 해당 지표 값.\n위의 해석 기준 표와 비교하여\n현재 어떤 구간에 있는지 확인하세요.',
  current_status: '현재 값이 어떤 구간에 해당하는지 표시.\n표의 범위/레이블과 매칭된 상태 배지.',
  ranges_table: '해당 지표의 수치 범위별 해석 기준.\n각 구간이 의미하는 시장 상태와\n권장 투자 행동을 함께 보여줍니다.',
  range_col: '지표의 수치 범위.\n현재 값이 어느 범위에 속하는지 확인하여\n의미와 투자 방향을 판단할 수 있습니다.',
  key_insight: '핵심 투자 인사이트.\n해당 개념을 실전에 적용할 때\n반드시 기억해야 할 핵심 포인트.',
  difficulty: {
    1: '입문 난이도.\n투자 초보자도 쉽게 이해할 수 있는 기본 개념.',
    2: '중급 난이도.\n기본 개념을 이해한 후 학습하면 좋은 개념.',
    3: '심화 난이도.\n투자 경험이 어느 정도 있는 분에게 적합한 개념.',
  },
  category_desc: {
    macro: '거시경제 지표들.\n금리, 수익률 곡선 등 경제 전체의 방향을 보여주는 지표.',
    sentiment: '시장 심리 지표들.\nVIX, F&G 등 투자자들의 공포와 탐욕을 측정하는 지표.',
    technical: '기술적 분석 지표들.\nRSI, MACD, 이격도 등 차트 기반 매매 타이밍 지표.',
    risk_management: '리스크 관리 개념들.\n손절, 포지션 사이징, R:R 비율 등 자본 보전 전략.',
    strategy: '투자 전략 개념들.\nDCA, 섹터 로테이션, 역발상 투자 등 실전 전략.',
  },
}
