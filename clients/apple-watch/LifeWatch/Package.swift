// swift-tools-version: 5.9
// LifeWatch - UFS Life-Master Apple Watch Client
// Xcode에서 열어서 빌드하세요.
//
// 프로젝트 설정:
//   - Target: watchOS 10.0+
//   - Language: Swift 5.9
//   - UI: SwiftUI
//   - Bundle ID: com.ufs.lifewatch
//
// Xcode 프로젝트 생성 방법:
//   1. Xcode > New Project > watchOS > App
//   2. Product Name: LifeWatch
//   3. Bundle Identifier: com.ufs.lifewatch
//   4. 이 디렉토리의 Swift 파일들을 프로젝트에 추가
//
// 또는 이 Package.swift로 SPM 기반으로 사용:

import PackageDescription

let package = Package(
    name: "LifeWatch",
    platforms: [
        .watchOS(.v10)
    ],
    targets: [
        .executableTarget(
            name: "LifeWatch",
            path: "LifeWatch WatchKit App"
        )
    ]
)
