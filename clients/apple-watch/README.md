# LifeWatch - UFS Apple Watch App

Life-Master 서비스와 연동되는 Apple Watch 앱. 생활습관 관리에 최적화.

## 기능
- **대시보드**: 오늘의 루틴/습관/목표 요약
- **루틴**: 시간대별 목록 + 워치에서 바로 체크
- **습관**: 스트릭 확인 + 탭하여 기록 추가
- **목표**: 진행률 + D-day 확인
- **컴플리케이션**: 시계 화면에 완료율/스트릭 표시

## 기술 스택
- watchOS 10+ / SwiftUI
- Life-Master REST API 연동 (http://서버:8004)
- Pushover 푸시 알림 (Life-Master 설정에서 활성화)

## 빌드

### Xcode 프로젝트로 빌드
1. Xcode 15+ 에서 `File > New > Project > watchOS > App`
2. Product Name: `LifeWatch`, Bundle ID: `com.ufs.lifewatch`
3. `LifeWatch WatchKit App/` 하위 Swift 파일들을 프로젝트에 드래그
4. 빌드 타겟: watchOS 10.0

### 서버 설정
앱 내 설정 화면에서 Life-Master 서버 URL 입력:
```
http://192.168.0.100:8004
```

## 구조

```
LifeWatch WatchKit App/
├── LifeWatchApp.swift          # 앱 엔트리 + TabView
├── Models/
│   └── LifeModels.swift        # Life-Master API 모델
├── Services/
│   └── APIClient.swift         # REST API 클라이언트
└── Views/
    ├── DashboardView.swift     # 오늘 요약 (메인)
    ├── RoutinesView.swift      # 루틴 목록 + 체크
    ├── HabitsView.swift        # 습관 스트릭 + 기록
    ├── GoalsView.swift         # 목표 진행률
    ├── SettingsView.swift      # 서버 URL 설정
    └── ComplicationViews.swift # 시계 화면 위젯
```

## 푸시 알림
Life-Master에 Pushover 설정이 되어 있으면 Apple Watch에서 직접 알림 수신:
- 루틴 시작 시간 알림
- 습관 기록 리마인더
- 스트릭 위기 경고
- 목표 마감 알림
