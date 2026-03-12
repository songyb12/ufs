import { useState, useEffect } from 'react'

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
      {
        heading: '대시보드 페이지 구성',
        items: [
          '⌂ 오버뷰 — 전체 시스템 상태 한눈에 보기',
          '⚡ 시그널 — 시그널 이력 조회 및 성과 추적',
          '💼 포트폴리오 — 보유 종목 관리, AI 분석, 임포트',
          '🧪 백테스트 — 과거 데이터 기반 전략 검증',
          '📊 시황 — AI 시장 분석 브리핑',
          '🔍 스크리닝 — 신규 종목 발굴 및 후보 관리',
          '🛡 리스크 — 포트폴리오 리스크 분석 및 이벤트 캘린더',
          '⚙ 시스템 — 파이프라인 실행, 설정, 알림 관리',
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
          'Portfolio P&L — 전체 그룹 포트폴리오 수익률 (%)',
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
          'Top Signals by Score — 스코어 절대값 기준 상위 종목 바 차트 (중복 제거)',
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
        heading: '시그널 트렌드 차트',
        items: [
          'BUY/SELL/HOLD 일별 시그널 수 추이 라인 차트',
          'Legend — 각 시그널 유형별 색상 구분',
          'XAxis — MM-DD 형식 날짜 표시',
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
        text: '보유 종목의 손익 현황을 실시간으로 관리하고, 포지션을 직접 추가/수정/삭제할 수 있습니다. 포트폴리오 그룹별로 독립 관리가 가능합니다.',
      },
      {
        heading: '포트폴리오 그룹',
        items: [
          '그룹별 독립 관리 — US, KR, 테마별 등 자유롭게 분류',
          '그룹 탭 전환 — 상단 탭으로 즉시 전환',
          '그룹 생성/삭제 — "+ 새 그룹" 버튼으로 추가',
        ],
      },
      {
        heading: 'AI 포트폴리오 분석',
        items: [
          '🤖 AI 분석 패널 — 보유 종목 테이블 위에 위치, "펼치기" 클릭',
          '프리셋 질문 — 종합 분석, 리스크 진단, 매수 후보, 손절/익절 판단',
          '커스텀 질문 — 자유롭게 포트폴리오에 대해 질문 가능',
          'LLM이 현재 보유 종목 데이터 + 시장 데이터를 종합하여 한국어로 매수/매도 추천 제공',
          '대화 이력 — 연속 질문 가능, 이전 맥락 참조',
        ],
      },
      {
        heading: 'Holdings 테이블',
        items: [
          'Symbol — 종목 코드 (클릭 시 상세 모달)',
          '매입가 / 현재가 — 매입 단가 및 최신 수집 기준 현재가',
          '수익률 — 평가손익률 (P&L %)',
          '투자금액 — 포지션 규모 (금액 또는 주식수로 전환 가능)',
          '손절 경고 — -7% 이하 빨간 하이라이트, -5% 이하 노란 주의 표시',
          '가격 날짜 — 3일 이상 오래된 데이터에 ⚠ 경고 표시',
        ],
      },
      {
        heading: '포지션 추가 & 임포트',
        items: [
          '"+ 포지션 추가" 버튼 — Symbol, Market, 수량/금액, 매입가 입력',
          'Quick Add — 종목 코드만으로 빠른 등록 (현재가 기준)',
          '📷 이미지 임포트 — 증권사 앱 스크린샷 AI 분석',
          '텍스트 붙여넣기 — 탭/쉼표 구분 데이터 파싱',
          '🔄 현재가 갱신 — 전체 종목 최신 가격 업데이트',
        ],
      },
      {
        heading: '섹터별 투자 비중',
        text: '보유 종목의 섹터 분포를 파이 차트로 시각화합니다. 2개 이상 섹터가 있을 때 표시됩니다.',
      },
      {
        heading: '종목 퇴출 관리',
        items: [
          '수동 퇴출 — 개별 종목 "퇴출" 버튼 클릭',
          '일괄 손절 — -7% 이하 종목 한번에 퇴출',
          '퇴출 이력 — 손절/익절/수동 사유별 이력 조회',
        ],
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
        text: 'VIBE 파이프라인의 시그널을 과거 시장 데이터에 적용하여, 실제로 매매했을 때의 성과를 시뮬레이션합니다.',
      },
      {
        heading: '실행 방법',
        items: [
          '"Run KR" / "Run US" — 해당 마켓 백테스트 실행',
          '기간 설정 — 날짜 직접 선택 또는 프리셋 사용',
          '프리셋 — 최근 1년(기본), 2022 하락장, 2020 코로나, 2023-24 회복기, 전체(2020~)',
          '결과 테이블 — 행 클릭 시 개별 트레이드 상세 확장',
        ],
      },
      {
        heading: '성과 비교 차트',
        text: '2개 이상의 완료된 백테스트가 있으면 적중률, Sharpe, 총수익률을 비교하는 수평 바 차트가 자동 표시됩니다.',
      },
      {
        heading: '주요 성과 지표',
        items: [
          'Hit Rate (적중률) — BUY 후 수익 발생 비율. 60% 이상이면 양호',
          'Avg Return (평균 수익률) — 전체 트레이드의 평균 수익률 (%)',
          'Sharpe Ratio — 위험 대비 수익. 1.0 이상 양호, 2.0 이상 우수',
          'Max Drawdown — 최고점 대비 최대 하락폭',
          'Total Return — 백테스트 기간 전체 누적 수익률',
          'Profit Factor — 총 수익 / 총 손실. 1.5 이상이면 양호',
        ],
      },
      {
        heading: '주의사항',
        items: [
          '백테스트 결과는 과거 성과이며, 미래 수익을 보장하지 않습니다',
          '충분한 가격 데이터(최소 60일)가 있어야 의미 있는 결과가 나옵니다',
        ],
      },
    ],
  },
  {
    id: 'market-brief',
    icon: '📊',
    title: '시황',
    content: [
      {
        heading: 'AI 시황 분석',
        text: 'Claude AI가 VIBE 데이터베이스의 실시간 데이터(매크로, 센티먼트, 시그널, 포트폴리오)를 종합하여 한국어 시장 분석을 제공합니다.',
      },
      {
        heading: '구성 요소',
        items: [
          '매크로 카드 — DXY, VIX, US10Y, USD/KRW 등 핵심 매크로 지표',
          '센티먼트 추이 차트 — Fear & Greed Index, Put/Call Ratio 최근 30일 트렌드',
          '시그널 서머리 — BUY/SELL/HOLD 분포 요약',
          '브리핑 히스토리 — 과거 생성된 시황 브리핑 열람',
        ],
      },
      {
        heading: 'AI 대화형 분석',
        items: [
          '🤖 AI 분석 — 자유 질문 입력 또는 "시장 분석" 버튼 클릭',
          '다중 턴 대화 — 연속 질문으로 심층 분석 가능',
          '오류 발생 시 — 대화 이력에 오류 메시지 표시 (빨간색)',
          '대화 초기화 — 2개 이상 대화 시 초기화 버튼 활성화',
        ],
      },
      {
        heading: '브리핑 생성',
        items: [
          '"브리핑 생성" 버튼 — 최신 데이터 기반 시황 리포트 자동 생성',
          'LLM ON 시 — Claude AI가 시장 코멘터리 추가',
          'LLM OFF 시 — 규칙 기반 데이터 요약만 제공',
        ],
      },
    ],
  },
  {
    id: 'macro',
    icon: '🌐',
    title: '매크로',
    content: [
      {
        heading: '매크로 인텔리전스',
        text: '기존 수집 데이터(VIX, DXY, 금리, 환율, 센티먼트)를 종합하여 시장 레짐 분류, 스태그플레이션 모니터링, 크로스마켓 추천을 제공합니다.',
      },
      {
        heading: '시장 레짐 감지',
        items: [
          '리스크 축 — VIX(40%) + F&G(30%) + Put/Call(15%) + VIX 기간구조(10%) + 금리스프레드(5%)',
          '드라이버 축 — 기술적 강도 vs 펀더멘탈 강도 비교',
          '결합 레이블 — "리스크온 / 모멘텀 주도" 등 4×3 조합',
          '레짐 유형 — 안일(Complacent), 리스크온(Risk-On), 리스크오프(Risk-Off), 패닉(Panic)',
        ],
      },
      {
        heading: '스태그플레이션 지수 (0-100)',
        items: [
          'Gold/Copper 비율 (30%) — >600 위험, <400 양호',
          'Yield Curve (25%) — 역전 시 경기침체 신호',
          '유가 압력 (20%) — WTI >$90 인플레이션 압력',
          'DXY 긴축 (15%) — 강달러 = EM 국가 압박',
          '구리 수요 (10%) — 약세 = 경기 둔화 신호',
          '수준 — 양호(<30) / 주의(30-50) / 경계(50-70) / 위험(>70)',
        ],
      },
      {
        heading: '크로스마켓 추천',
        items: [
          '5팩터 모델 — FX 추세, 변동성, 금리환경, 수급방향, 시그널 모멘텀',
          '추천 유형 — KR유리 / US유리 / 양쪽유리 / 관망',
          '레이더 차트 — KR vs US 5축 비교 시각화',
          '액션 아이템 — 구체적 한국어 투자 조언 (VIX/환율/시장 기반)',
        ],
      },
      {
        heading: '매크로 추세 차트',
        items: [
          'VIX, Fear & Greed, Yield Spread, USD/KRW, DXY 시계열',
          '기간 선택 — 7일 / 30일 / 90일',
          'Tooltip — 각 지표 상세 값 표시',
        ],
      },
    ],
  },
  {
    id: 'fund-flow',
    icon: '💰',
    title: '자금흐름',
    content: [
      {
        heading: '자금흐름 추적',
        text: 'KR 시장 외국인/기관 수급과 US ETF 프록시 플로우를 추적하고, 섹터별 자금 흐름과 테마 랭킹을 제공합니다.',
      },
      {
        heading: '크로스마켓 플로우 차트',
        items: [
          'KR 외국인 순매수 (Bar) + US Risk Appetite (Line) 결합 차트',
          'US Risk Appetite — SPY/QQQ/IWM 상승 + TLT 하락 = Risk-On',
          'SPY 일간 변동률 점선 오버레이',
        ],
      },
      {
        heading: '섹터별 자금흐름',
        items: [
          'fund_flow_kr 데이터 존재 시 — 외국인/기관 순매수 수평 바 차트',
          '데이터 부재 시 — 시그널 기반 섹터 강도 차트로 폴백',
          '상위 10개 섹터 표시',
        ],
      },
      {
        heading: '섹터 로테이션',
        items: [
          '현재 5일 vs 이전 5일 섹터 순위 비교',
          'Inflow / Outflow / Stable 시그널',
          '시그널 폴백 — Buy-Dominant / Sell-Dominant / Mixed',
          '순위 변동 화살표 표시 (↑/↓)',
        ],
      },
      {
        heading: '테마 히트맵 & 랭킹',
        items: [
          'Treemap — 크기=자금유입량 또는 시그널 강도, 색상=유입(녹)/유출(적)',
          '테마 스코어 — 자금흐름(50%) + 시그널 강도(50%) 결합',
          'Hot/Cold/Neutral 시그널 뱃지',
          'ETF 제외 — 개별 주식 섹터만 테마 분석',
        ],
      },
      {
        heading: '기간 선택',
        items: [
          '5일 / 10일 / 30일 선택 가능',
          '새로고침 버튼으로 최신 데이터 로드',
        ],
      },
    ],
  },
  {
    id: 'screening',
    icon: '🔍',
    title: '스크리닝',
    content: [
      {
        heading: '스크리닝이란?',
        text: '워치리스트 외 종목 중 기술적 조건을 충족하는 신규 매수 후보를 자동으로 발굴하는 기능입니다.',
      },
      {
        heading: '사용 방법',
        items: [
          'Market 선택 — KR 또는 US 마켓 선택',
          'Scan 기간 — 3/5/10/30일 룩백 기간 설정',
          '"Scan" 버튼 — 선택한 마켓에서 후보 종목 스캔 실행',
          '결과 확인 — 발견된 후보 종목이 테이블에 표시',
        ],
      },
      {
        heading: '스크리닝 조건',
        items: [
          'Volume Spike — 20일 평균 대비 거래량 급증 감지',
          'New High — 신고가 돌파 종목 감지',
          'Breakout — 주요 이동평균선 돌파 종목 감지',
        ],
      },
      {
        heading: '후보 테이블',
        items: [
          'Symbol — 종목 코드 (클릭 시 상세 모달)',
          'Score — 스크리닝 점수 (trigger_value 기반)',
          'RSI / Volume Ratio — 최신 기술 지표 (DB에서 조회)',
          'Price Change — 최근 가격 변동률',
          'Reason — 스크리닝 트리거 설명',
          'Status — pending/approved/rejected',
          '정렬 — Symbol, Score, Price Change 클릭 정렬',
        ],
      },
    ],
  },
  {
    id: 'risk',
    icon: '🛡',
    title: '리스크',
    content: [
      {
        heading: '리스크 대시보드',
        text: '포트폴리오의 리스크 요인을 시각적으로 분석합니다. 섹터 집중도, 포지션 비중, 예정 이벤트를 한곳에서 관리합니다.',
      },
      {
        heading: '리스크 카드',
        items: [
          'Total Positions — 전체 포트폴리오 그룹의 보유 종목 수',
          'Sectors — 분산 투자 섹터 수',
          'Top 5 Concentration — 상위 5종목 비중 합계 (70%+ 빨강, 50%+ 노랑)',
          'Upcoming Events — 설정 기간 내 예정 이벤트 수',
        ],
      },
      {
        heading: '차트',
        items: [
          'Sector Exposure — 섹터별 투자 비중 파이 차트 (%)',
          'Top 5 Position Weight — 상위 5종목 비중 수평 바 차트',
        ],
      },
      {
        heading: '이벤트 캘린더',
        items: [
          'Upcoming — D-day 표시, 3일이내 빨강, 7일이내 노랑 하이라이트',
          '이벤트 유형 — FOMC(🏦), 옵션 만기(📅), 휴일(🎉)',
          'Seed Events — FOMC, 옵션만기 등 정기 이벤트 자동 등록',
          'Recent Past — 최근 지나간 이벤트 참고용 표시',
        ],
      },
      {
        heading: 'Position Risk Detail',
        items: [
          '종목별 비중 게이지바 — 전체 대비 비중 시각화',
          'P&L 색상 — 수익 초록, 손실 빨강',
          '위험 하이라이트 — -7% 이하 손실 종목 빨간 배경',
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
          'rsi_warning_threshold — RSI 경고 기준값 (기본: 58)',
          'stop_loss_pct — 손절 비율 (기본: 0.08 = 8%)',
          '각 설정값 옆 "저장" 버튼으로 즉시 반영',
        ],
      },
      {
        heading: 'LLM 설정',
        items: [
          '시스템 탭에서 LLM ON/OFF 제어',
          '모델 정보 — 현재 사용 중인 LLM 모델 표시',
          '상태 확인 — API 키 유효성 및 연결 상태',
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
      {
        heading: '월간 리포트',
        items: [
          '매월 1일 07:00 UTC 자동 생성 (스케줄러)',
          '"리포트 생성" 버튼으로 수동 생성 가능',
          '시그널 수, 적중률, 평균 수익률, Top/Worst 종목 집계',
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
        text: '오버뷰, 시그널, 포트폴리오, 백테스트, 스크리닝, 리스크 페이지에서 종목 코드를 클릭하면 상세 모달이 열립니다.',
      },
      {
        heading: '차트',
        items: [
          '종가+거래량 복합 차트 — 30/60/120/200 일 기간 선택',
          '왼쪽 Y축 = 종가, 오른쪽 Y축 = 거래량 (반투명 바)',
          'Tooltip — 종가, 거래량 한국어 라벨 표시',
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
          'KR 시장 — RSI > 50 이면 BUY 시그널 차단',
          'US 시장 — RSI > 55 이면 BUY 시그널 차단',
        ],
      },
      {
        heading: '적용 범위',
        text: 'S5 단계에서 적용되며, S6/S7에서 생성된 시그널보다 항상 우선합니다.',
      },
    ],
  },
  {
    id: 'llm',
    icon: '🤖',
    title: 'LLM 기능 & 비용',
    content: [
      {
        heading: 'LLM 기능 개요',
        text: 'Claude Haiku 4.5 모델을 사용하여 파이프라인 단계 강화 + AI 분석 기능을 제공합니다. 규칙 기반 분석은 항상 동작하며, LLM은 선택적으로 추가 품질을 제공합니다.',
      },
      {
        heading: '파이프라인 LLM 기능',
        items: [
          'S7 Red-Team (LLM_RED_TEAM_ENABLED) — BUY 시그널에 대해 반박 논거 제시',
          'S8 한국어 해설 (LLM_EXPLANATION_ENABLED) — 전 종목 시그널 한국어 해설 자동 생성',
          'S9 시나리오 (LLM_SCENARIO_ENABLED) — 보유/후보 종목 트레이드 시나리오 생성',
        ],
      },
      {
        heading: 'AI 분석 기능 (대시보드)',
        items: [
          '📊 시황 AI 분석 — 실시간 매크로+시그널 데이터 기반 시장 분석',
          '💼 포트폴리오 AI 분석 — 보유 종목별 매수/매도/유지 추천',
          '프리셋 질문 — 종합 분석, 리스크 진단, 매수 후보, 손절 판단',
          '자유 질문 — 포트폴리오나 시장에 대해 자유롭게 대화형 질문',
        ],
      },
      {
        heading: '월간 비용 요약 (하루 2회 실행 기준)',
        items: [
          'S7 Red-Team — ~$0.66/월',
          'S8 한국어 해설 — ~$0.42/월',
          'S9 시나리오 — ~$0.19/월',
          'AI 분석 (대화형) — 사용량에 따라 변동 (~$0.01/회)',
          '전체 합계 — ~$1.3/월 (모든 기능 활성화 시)',
          '모델 — Claude Haiku 4.5 (claude-haiku-4-5-20251001)',
        ],
      },
      {
        heading: '설정 방법',
        items: [
          '.env 파일에 LLM_API_KEY 설정 (Anthropic API Key)',
          'LLM_RED_TEAM_ENABLED=true — Red-Team 활성화',
          'LLM_EXPLANATION_ENABLED=true — 한국어 해설 활성화',
          'LLM_SCENARIO_ENABLED=true — 시나리오 분석 활성화',
          'Docker 재시작 필요 — docker compose up -d vibe',
          '비용 0원 운영 — 모든 LLM 기능 OFF. 규칙 기반만으로 충분히 동작',
        ],
      },
    ],
  },
]

export default function Guide({ onNavigate, initialSection }) {
  const [activeSection, setActiveSection] = useState(
    initialSection && sections.find(s => s.id === initialSection) ? initialSection : 'quickstart'
  )

  useEffect(() => {
    if (initialSection && sections.find(s => s.id === initialSection)) {
      setActiveSection(initialSection)
    }
  }, [initialSection])

  const active = sections.find(s => s.id === activeSection) || sections[0]

  // Pages that have a corresponding navigation target
  const navigablePages = new Set(['overview', 'signals', 'portfolio', 'backtest', 'market-brief', 'macro', 'fund-flow', 'screening', 'risk', 'system'])

  return (
    <div>
      <div className="page-header">
        <div>
          <h2>{'📖'} 사용 가이드</h2>
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
        {navigablePages.has(active.id) && (
          <div className="guide-nav-hint">
            <button
              className="btn btn-outline"
              onClick={() => onNavigate && onNavigate(active.id)}
            >
              {active.icon} {active.title} 페이지로 이동 {'→'}
            </button>
          </div>
        )}
      </div>
    </div>
  )
}
