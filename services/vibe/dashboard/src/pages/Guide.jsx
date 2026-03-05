import { useState } from 'react'

const sections = [
  {
    id: 'quickstart',
    icon: '🚀',
    title: '빠른 시작',
    content: [
      {
        heading: 'VIBE란?',
        text: 'VIBE는 7단계 퀀트 분석 파이프라인을 통해 KR/US 시장의 투자 시그널을 자동 생성하는 투자 인텔리전스 시스템입니다.',
      },
      {
        heading: '파이프라인 7단계',
        items: [
          'S1 (데이터 수집) — pykrx/yfinance로 OHLCV + 매크로 데이터 수집',
          'S2 (기술적 분석) — RSI, MACD, 볼린저 밴드, 이격도 등 기술 지표 산출',
          'S3 (매크로 분석) — VIX, DXY, 금리, 환율 등 거시경제 컨텍스트 반영',
          'S4 (수급 분석, KR) — 외국인/기관 수급 데이터 반영',
          'S5 (Hard Limit) — RSI>65/이격도>105% 강제 HOLD, 매수 차단 필터',
          'S6 (시그널 생성) — 종합 스코어링 → BUY/SELL/HOLD 최종 시그널',
          'S7 (Red-Team) — 규칙 기반 교차 검증으로 시그널 신뢰도 확보',
        ],
      },
      {
        heading: '자동 실행 스케줄',
        items: [
          'KR 파이프라인 — 매일 16:00 KST (07:00 UTC)',
          'US 파이프라인 — 매일 17:00 EST (22:00 UTC)',
          '결과 알림 — Discord Webhook 자동 전송',
        ],
      },
    ],
  },
  {
    id: 'overview',
    icon: '⌂',
    title: '오버뷰',
    content: [
      {
        heading: '페이지 구성',
        text: '대시보드 메인 화면으로, 시스템 전체 상태를 한눈에 파악할 수 있습니다.',
      },
      {
        heading: 'KPI 카드',
        items: [
          'BUY/SELL Signals — 최신 파이프라인의 매수/매도 시그널 수',
          'Hard Limits — RSI/이격도 기준 강제 HOLD 처리된 종목 수',
          'Portfolio P&L — 포트폴리오 전체 수익률 (%)',
          'KR/US Pipeline — 파이프라인 마지막 실행 상태 및 시각',
        ],
      },
      {
        heading: 'Sentiment 위젯',
        items: [
          'Fear & Greed Index — 0~100 게이지 (Extreme Fear → Extreme Greed)',
          'Put/Call Ratio — 1.0 이상이면 약세 심리',
          'VIX Term Structure — 양수면 정상(콘탱고), 음수면 공포(백워데이션)',
        ],
      },
      {
        heading: '차트 & 테이블',
        items: [
          'Signal Distribution — BUY/SELL/HOLD 비율 파이 차트',
          'Top Signals by Score — 스코어 절대값 기준 상위 종목 바 차트',
          'Latest Signals — 최신 시그널 목록, 종목 클릭 시 상세 모달 표시',
        ],
      },
      {
        heading: '자동 갱신',
        text: '데이터는 5분마다 자동으로 갱신됩니다. 수동 새로고침 없이 최신 상태를 유지합니다.',
      },
    ],
  },
  {
    id: 'signals',
    icon: '⚡',
    title: '시그널',
    content: [
      {
        heading: '시그널 히스토리',
        text: '파이프라인이 생성한 모든 시그널의 이력을 조회합니다.',
      },
      {
        heading: '필터 사용법',
        items: [
          'Market — KR, US 또는 전체 (ALL)',
          'Signal — BUY, SELL, HOLD 또는 전체',
          '기간 — 7일 / 30일 / 90일 선택',
        ],
      },
      {
        heading: '테이블 칼럼',
        items: [
          'Symbol — 종목 코드 (클릭 시 상세 모달)',
          'Signal — BUY/SELL/HOLD 뱃지',
          'Score — 7단계 파이프라인 종합 점수 (-100~+100)',
          'RSI — 상대강도지수 (14일 기준)',
          'Hard Limit — 안전 필터 발동 여부',
          'Confidence — Red-Team 검증 후 신뢰도 (%)',
        ],
      },
      {
        heading: '성과 추적 (Performance)',
        items: [
          'Hit Rate T+5 — 시그널 발생 5일 후 방향 일치율',
          'Hit Rate T+20 — 시그널 발생 20일 후 방향 일치율',
          'Avg Return — 시그널 기준 평균 수익률',
        ],
      },
    ],
  },
  {
    id: 'portfolio',
    icon: '💼',
    title: '포트폴리오',
    content: [
      {
        heading: '포트폴리오 관리',
        text: '보유 종목의 손익 현황을 실시간으로 관리하고, 포지션을 직접 추가/수정/삭제할 수 있습니다.',
      },
      {
        heading: 'Holdings 테이블',
        items: [
          'Symbol — 종목 코드 (클릭 시 상세 모달)',
          'Qty / Avg Price — 보유 수량 및 평균 단가',
          'Current Price — 현재가 (최신 수집 기준)',
          'P&L / P&L % — 평가손익 및 수익률',
          '편집/삭제 — 각 행의 액션 버튼',
        ],
      },
      {
        heading: '포지션 추가',
        items: [
          '"+ 포지션 추가" 버튼 클릭',
          'Symbol, Market(KR/US), 수량, 평균 단가 입력',
          'Quick Add — 종목 코드만으로 빠른 등록 (현재가 기준)',
        ],
      },
      {
        heading: '시나리오 분석',
        text: '포트폴리오 시나리오 분석 카드에서 Bullish/Bearish/Base 케이스별 예상 P&L을 확인할 수 있습니다.',
      },
    ],
  },
  {
    id: 'backtest',
    icon: '🧪',
    title: '백테스트',
    content: [
      {
        heading: '백테스트란?',
        text: '과거 데이터에 현재 파이프라인 전략을 적용하여 성과를 검증하는 시뮬레이션입니다.',
      },
      {
        heading: '서머리 카드',
        items: [
          'Total Runs — 누적 백테스트 실행 횟수',
          'Best Hit Rate — 전체 백테스트 중 최고 적중률',
          'Avg Sharpe — 평균 샤프 비율 (위험 대비 수익)',
        ],
      },
      {
        heading: '결과 테이블',
        items: [
          '행 클릭 — 개별 트레이드 상세 내역 확장',
          'Period — 백테스트 기간',
          'Hit Rate — 시그널 방향 적중률',
          'Sharpe — 샤프 비율',
          'Max DD — 최대 낙폭 (Maximum Drawdown)',
        ],
      },
      {
        heading: '실행 방법',
        items: [
          '"KR 백테스트 실행" 또는 "US 백테스트 실행" 버튼 클릭',
          '실행 완료 후 결과 테이블에 자동 추가',
          '트레이드 상세에서 각 종목의 진입/청산 가격, 수익률 확인 가능',
        ],
      },
    ],
  },
  {
    id: 'system',
    icon: '⚙',
    title: '시스템',
    content: [
      {
        heading: '시스템 상태',
        items: [
          'Service Health — API 서버 헬스 체크 상태',
          'Database — 연결 상태, 테이블 수, 가격/시그널 레코드 수',
          'Scheduler — 등록된 스케줄러 잡 목록 및 다음 실행 시각',
        ],
      },
      {
        heading: '파이프라인 실행',
        items: [
          '"KR 파이프라인" / "US 파이프라인" — 수동 실행 트리거',
          'Pipeline Runs — 최근 실행 이력 (상태, 소요시간, 완료 단계)',
        ],
      },
      {
        heading: '알림 설정',
        items: [
          '알림 임계값을 DB에서 관리 (하드코딩 대체)',
          'rsi_warning_threshold — RSI 경고 기준값 (기본: 58)',
          'stop_loss_pct — 손절 비율 (기본: 0.08 = 8%)',
          '각 설정값 옆 "저장" 버튼으로 즉시 반영',
        ],
      },
      {
        heading: '알림 히스토리',
        text: '발송된 알림의 이력을 확인합니다 — 시각, 유형, 조건, 발송 채널을 기록합니다.',
      },
      {
        heading: '월간 리포트',
        items: [
          '매월 1일 07:00 UTC 자동 생성 (스케줄러)',
          '"리포트 생성" 버튼으로 수동 생성 가능',
          '시그널 수, 적중률, 평균 수익률, Top/Worst 종목 집계',
        ],
      },
      {
        heading: '워치리스트 관리',
        items: [
          '감시 종목 추가/삭제',
          '종목 코드, 마켓(KR/US), 이름 입력',
          '삭제 시 해당 종목은 다음 파이프라인 실행부터 제외',
        ],
      },
    ],
  },
  {
    id: 'symbol-modal',
    icon: '🔍',
    title: '종목 상세 모달',
    content: [
      {
        heading: '사용 방법',
        text: '오버뷰, 시그널, 포트폴리오, 백테스트 페이지에서 종목 코드를 클릭하면 상세 모달이 열립니다.',
      },
      {
        heading: '차트',
        items: [
          '종가 라인 차트 — 30/60/120/200 일 기간 선택',
          'X축 = 날짜, Y축 = 종가 (자동 스케일)',
        ],
      },
      {
        heading: '핵심 지표 카드',
        items: [
          'Close — 최신 종가',
          'RSI (14) — 상대강도지수',
          'Volume — 최근 거래량',
        ],
      },
      {
        heading: '최근 시그널',
        text: '해당 종목의 최근 시그널 이력 테이블 (날짜, 시그널, 스코어, Hard Limit 여부).',
      },
      {
        heading: '닫기',
        text: 'ESC 키 또는 모달 외부 클릭, × 버튼으로 닫을 수 있습니다.',
      },
    ],
  },
  {
    id: 'hard-limits',
    icon: '🛡️',
    title: 'Hard Limit 규칙',
    content: [
      {
        heading: 'Hard Limit이란?',
        text: '과매수 상태에서의 무리한 매수를 방지하는 안전 장치입니다. 조건 충족 시 파이프라인 스코어와 관계없이 강제 HOLD 처리됩니다.',
      },
      {
        heading: '강제 HOLD 조건',
        items: [
          'RSI > 65 → 과매수 영역, 자동 HOLD',
          '이격도 > 105% → 이동평균 대비 과열, 자동 HOLD',
        ],
      },
      {
        heading: '매수 차단 조건',
        items: [
          'KR 시장: RSI > 50 이면 BUY 시그널 차단',
          'US 시장: RSI > 55 이면 BUY 시그널 차단',
        ],
      },
      {
        heading: '적용 범위',
        text: 'S5 단계에서 적용되며, S6/S7에서 생성된 시그널보다 항상 우선합니다.',
      },
    ],
  },
]

export default function Guide({ onNavigate, initialSection }) {
  const [activeSection, setActiveSection] = useState(
    initialSection && sections.find(s => s.id === initialSection) ? initialSection : 'quickstart'
  )
  const active = sections.find(s => s.id === activeSection) || sections[0]

  return (
    <div>
      <div className="page-header">
        <div>
          <h2>📖 사용 가이드</h2>
          <p className="subtitle">VIBE 대시보드 기능별 매뉴얼</p>
        </div>
      </div>

      {/* Section Tabs */}
      <div className="guide-tabs">
        {sections.map(s => (
          <button
            key={s.id}
            className={`guide-tab ${activeSection === s.id ? 'active' : ''}`}
            onClick={() => setActiveSection(s.id)}
          >
            <span className="guide-tab-icon">{s.icon}</span>
            {s.title}
          </button>
        ))}
      </div>

      {/* Section Content */}
      <div className="guide-content">
        <div className="guide-section-header">
          <span className="guide-section-icon">{active.icon}</span>
          <h3>{active.title}</h3>
        </div>

        {active.content.map((block, i) => (
          <div key={i} className="guide-block">
            <h4 className="guide-block-title">{block.heading}</h4>
            {block.text && <p className="guide-block-text">{block.text}</p>}
            {block.items && (
              <ul className="guide-list">
                {block.items.map((item, j) => {
                  const [label, ...rest] = item.split(' — ')
                  return (
                    <li key={j}>
                      {rest.length > 0
                        ? <><strong>{label}</strong> — {rest.join(' — ')}</>
                        : item
                      }
                    </li>
                  )
                })}
              </ul>
            )}
          </div>
        ))}

        {/* Quick nav to related page */}
        {active.id !== 'quickstart' && active.id !== 'hard-limits' && active.id !== 'symbol-modal' && (
          <div className="guide-nav-hint">
            <button
              className="btn btn-outline"
              onClick={() => onNavigate && onNavigate(active.id)}
            >
              {active.icon} {active.title} 페이지로 이동 →
            </button>
          </div>
        )}
      </div>
    </div>
  )
}
