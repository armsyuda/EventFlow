# SEED 기반 데스크톱 디자인 가이드

## 적용 원칙

SEED React 컴포넌트를 직접 사용하지 않고 공식 디자인 토큰의 의미와 사용 원칙을 PySide6 스타일로 변환한다. 당근 로고·서비스명·고유 브랜드 자산은 사용하지 않는다.

참고: <https://seed-design.io/foundations/design-token>, <https://seed-design.io/foundations/color>, <https://seed-design.io/foundations/layout>, <https://seed-design.io/foundations/inclusive-design>

## 의미 기반 색상

| 토큰 | 용도 |
|---|---|
| `bg.basement` | 앱 전체 배경 |
| `bg.layer` | 카드·표·입력 표면 |
| `fg.neutral` | 기본 텍스트 |
| `fg.muted` | 설명·보조 텍스트 |
| `brand.solid` | 가장 중요한 동작·선택 상태 |
| `positive` | 완료·성공 |
| `warning` | 임박·확인 필요 |
| `critical` | 지연·오류·삭제 |
| `informative` | 진행 중·안내 |

색상만으로 상태를 전달하지 않고 텍스트·아이콘·D-Day를 함께 표시한다. MVP는 밝은 테마만 제공하되 모든 스타일은 의미 토큰을 참조한다.

## 타이포그래피

- 글꼴: `Segoe UI`, `Malgun Gothic`, sans-serif
- 화면 제목: 26px/700
- 섹션 제목: 18px/700
- 본문·입력: 14px/400~500
- 보조·배지: 12~13px/500~700

## 간격과 레이아웃

- 화면 바깥 여백 32px, 큰 영역 간격 24px
- 카드 내부 16~20px, 입력·버튼 사이 8~12px
- 버튼 높이 44px, 작은 아이콘 버튼도 클릭 영역 최소 32px
- 표 행 높이 40~44px
- 기본 화면은 Middle Density, 체크리스트 표만 정보 밀도를 높인다.

## 공통 컴포넌트

- Primary Button: 행사 생성·저장처럼 화면의 주 동작 하나에 사용
- Secondary Button: 내보내기·필터 초기화
- Checkbox: 완료와 항목 선택
- Select: 상태·담당·업체
- Badge: 상태 및 D-Day
- Side Navigation: 현재 위치를 배경과 왼쪽 강조선으로 함께 표시
- Dialog: 생성·수정·확인
- Snackbar/Message: 저장·백업·내보내기 결과

## 접근성

- 읽기 텍스트와 배경은 높은 대비를 유지한다.
- 비활성 상태도 읽을 수 있는 대비를 유지한다.
- 키보드 포커스 테두리를 제거하지 않는다.
- 아이콘 단독 버튼에는 접근 가능한 설명을 지정한다.
- 100%, 125%, 150% Windows 배율에서 확인한다.
