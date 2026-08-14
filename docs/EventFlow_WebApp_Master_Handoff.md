# EventFlow 웹앱 전환 종합 인수인계서

> 작성 기준일: 2026-08-13  
> 데스크톱 사실 갱신: 2026-08-14 (EventFlow 0.3.29 / schema v8, 웹 아키텍처는 유지)  
> 기준 데스크톱 버전: EventFlow 0.3.29  
> 기준 DB 스키마: SQLite v8  
> 기준 검증: `111 passed`  
> 새 웹 저장소: `https://github.com/armsyuda/EventFlow-web.git` (Private)  
> 기존 데스크톱 저장소: `https://github.com/armsyuda/EventFlow.git`  
> 권장 새 작업 폴더: `C:\Work\02_EventFlow_Web`

## 1. 이 문서의 목적

이 문서는 새 Codex 프로젝트가 기존 EventFlow 데스크톱 앱의 기능과 업무 규칙을 빠뜨리지 않고 웹/PWA로 재구현하고, Supabase 로그인·회사별 데이터 분리·실시간 협업을 연결한 뒤 Cloudflare Workers에 배포할 수 있도록 만든 단일 기준 문서다.

새 웹앱은 기존 데스크톱 앱을 덮어쓰거나 같은 저장소에 섞지 않는다. 데스크톱 앱은 당분간 그대로 유지하고, 웹앱은 별도 저장소와 별도 작업 폴더에서 개발한다.

이 문서에서 다음 표현을 구분한다.

- **현재 구현**: v0.3.29 데스크톱 앱에서 실제로 동작하고 자동검사로 확인된 기능
- **웹 구현 계약**: 기존 기능을 웹으로 옮길 때 반드시 지켜야 할 동작
- **신규 협업 기능**: 로그인, 회사별 권한, 실시간 동기화처럼 데스크톱 앱에는 아직 없는 기능
- **1차 제외**: 이번 웹앱 범위에서 의도적으로 구현하지 않는 기능

## 2. 확정된 범위와 제외 범위

### 2.1 반드시 포함할 범위

- 이메일 기반 로그인, 로그아웃, 비밀번호 재설정
- 개인별 계정과 회사 워크스페이스 소속
- 회사별 데이터 완전 분리
- 회사 관리자·PM·일반 작업자·조회자 권한
- 행사 생성·수정·삭제와 행사 선택
- 기본항목 또는 이전 행사에서 체크리스트 생성
- 행사 체크리스트의 모든 현재 편집 기능
- 담당자(PM), 업체, 업체담당자 관계 검증
- 대시보드와 지연·7일 이내 마감 집계
- 월간 달력과 완료·마감연장 동작
- 공급가·VAT·예산 비교 정산
- 기본 항목 관리
- 업체·소속 담당자·프리랜서 관리
- PDF 및 Excel 내보내기
- 회사 데이터 백업·복원
- 여러 사용자의 실시간 변경 반영
- 변경 이력과 안전한 되돌리기
- PC·태블릿 반응형 UI와 홈 화면 설치형 PWA
- Supabase 서버 연동과 RLS 보안
- Cloudflare Workers 무료 호스팅과 Git 자동 배포

### 2.2 이번 1차 웹앱에서 명시적으로 제외

- **사진 촬영, 이미지 업로드, 이미지 갤러리**
- 모든 종류의 파일 첨부와 Supabase Storage 버킷
- 댓글과 사용자 멘션
- 이메일·문자·카카오톡·Slack 알림
- 앱스토어 및 플레이스토어 네이티브 앱
- 결제와 구독 과금
- 완전한 오프라인 편집 및 충돌 병합
- 기존 데스크톱 앱과 웹앱의 양방향 실시간 동기화

사진 기능은 나중에 별도 단계로 추가한다. 1차 DB 마이그레이션에 `attachments`, `photos`, `storage_path` 같은 임시 열을 만들지 않는다.

## 3. 현재 외부 서비스 상태

### 3.1 GitHub

- 데스크톱: `armsyuda/EventFlow`
  - Windows 앱과 공개 Release 자동 업데이트에 사용한다.
  - `v*` 태그가 생성되면 `.github/workflows/windows-release.yml`이 `03_Program`을 테스트·빌드·Release한다.
- 웹앱: `armsyuda/EventFlow-web`
  - 비공개 저장소다.
  - 이 문서 작성 시점에는 실행 가능한 웹앱 파일과 첫 커밋이 없다.
  - 웹앱 작업은 이 저장소에서만 한다.

### 3.2 Cloudflare

- `EventFlow-web` 비공개 GitHub 저장소와 Cloudflare Git 통합 연결은 완료됐다.
- Cloudflare 화면에서 `main`, 루트 `/`, 배포 명령 `npx wrangler deploy`로 프로젝트가 생성됐다.
- 첫 빌드는 저장소에 가져올 커밋이 없어 `Cloning repository → Failed: error occurred while fetching repository`에서 실패했다.
- 저장소를 공개로 바꿀 필요가 없다. 첫 웹앱 커밋을 `main`에 push한 뒤 다시 빌드하면 된다.
- 현재 화면 형태는 전통적인 Pages 출력 디렉터리 방식보다 **Cloudflare Workers + Workers Assets Git 배포**에 가깝다. 공식 SvelteKit Workers 구성을 사용한다.

### 3.3 Supabase

- 프로젝트명: `JMT Event Flow`
- 리전: `ap-northeast-2`
- 프로젝트 URL: `https://pzyujbmqvmbfeolfwyyu.supabase.co`
- 공개용 Publishable Key는 소스와 문서에 저장하지 않는다.
- 이메일 인증은 활성화되어 있다.
- 2026-08-13 확인 당시 `public` 스키마의 앱 테이블은 아직 없다.
- 데스크톱 앱에는 환경변수 기반 연결 검사만 있다. 로그인 UI, 원격 테이블, 원격 CRUD, 실시간 동기화는 아직 구현되지 않았다.
- 연결 검사 파일:
  - `03_Program/src/event_checklist/supabase_connection.py`
  - `03_Program/tools/check_supabase_connection.py`
  - `03_Program/.env.example`

## 4. 제품 정의와 현재 사용자 흐름

EventFlow(이벤트 플로우, 약칭 이플)는 행사별 준비업무, 일정, 담당자·업체와 예산 정산을 관리하는 프로그램이다.

현재 데스크톱의 핵심 흐름은 다음과 같다.

1. 앱은 행사 미선택 대시보드로 시작한다.
2. 사용자가 새 행사를 만들거나 기존 행사를 선택한다.
3. 새 행사는 120개 기본 항목 또는 이전 행사의 선택 항목으로 체크리스트를 만든다.
4. 모든 새 업무의 시작일과 마감일은 비어 있다.
5. 체크리스트에서 상태, 날짜, PM, 업체와 업체담당자를 직접 입력한다.
6. 날짜가 모두 입력된 미완료 업무는 달력에 기간 막대로 표시된다.
7. 정산 화면에서 수량·단가·VAT를 관리하고 행사 예산과 비교한다.
8. PDF/Excel로 출력하고 백업을 보관한다.

웹앱에서도 위 흐름을 유지하되 로그인 후 사용자의 회사 워크스페이스를 먼저 결정한다.

## 5. 현재 데스크톱 기술 구조

- Python 3.11+
- PySide6 Qt Widgets
- SQLite + WAL
- openpyxl Excel 출력
- PySide6 벡터 PDF 출력
- pytest
- PyInstaller onedir
- Inno Setup 설치 파일
- GitHub Release 기반 인앱 자동 업데이트

주요 코드 위치:

```text
03_Program/
  src/event_checklist/
    app.py                 시작, 스플래시, DB 초기화
    config.py              사용자 데이터·백업·업데이트 경로
    database.py            SQLite 스키마 v8, 마이그레이션, undo/redo
    services.py            행사·업무·달력·정산 업무규칙
    backup.py              자동/수동 백업과 복원
    export.py              Excel 출력
    pdf_export.py          PDF 출력
    supabase_connection.py Supabase 최소 연결 검사만 제공
    update_service.py      GitHub Release 조회·다운로드·롤백 업데이트
    install_service.py     Windows 고정 설치와 바로가기
    choices.py             현재 데이터 기반 분류·단위 선택 목록
    units.py               공통 단위와 기본 단위 추론
    theme.py               색상·타이포·QSS
    ui/                    전체 화면과 대화상자
    resources/
      master_items.json    120개 기본 업무
  tests/                   현재 111개 자동검사
```

현재 로컬 데이터:

```text
프로그램: %LOCALAPPDATA%\Programs\EventFlow\EventFlow.exe
DB:       %LOCALAPPDATA%\EventCheckList\data\event_checklist.db
백업:     %LOCALAPPDATA%\EventCheckList\backups
이력:     %LOCALAPPDATA%\EventCheckList\history
업데이트: %LOCALAPPDATA%\EventCheckList\updates
```

## 6. 화면 및 기능 전수 목록

### 6.1 공통 셸

현재 메뉴:

- 대시보드
- 체크리스트
- 달력
- 정산내역
- 설정

현재 공통 동작:

- 행사 미선택 시 체크리스트·달력·정산내역 비활성화
- 선택된 행사명을 상단에 표시
- 212px 좌측 메뉴 접기/펼치기
- Ctrl+Z 되돌리기, Ctrl+Y 다시 실행
- 최대 50단계 로컬 변경 이력
- `저장` 버튼으로 전체 수동 백업
- 변경이 있을 때 10분마다 자동 백업, 최근 자동 백업 10개 유지
- 사용자 수동 백업은 자동 삭제하지 않음
- 설정 화면 진입 시 최신 기본항목·연락처 다시 조회
- 모든 표는 한 번 클릭으로 선택, 더블클릭으로 편집
- 표 열 너비 수동 드래그, 열 이동, `열 너비 맞춤`

웹 대응:

- PC에서는 좌측 내비게이션을 유지한다.
- 태블릿에서는 접히는 사이드 시트 또는 하단/상단 내비게이션으로 바꿀 수 있다.
- 웹의 새 버전은 Cloudflare 배포로 공급한다. Windows 인앱 업데이트 UI는 복제하지 않고, PWA 새 버전 감지 시 `새 버전이 있습니다 · 새로고침`을 표시한다.

### 6.2 로그인 및 회사 선택 — 신규 기능

현재 데스크톱에는 로그인 기능이 전혀 없다.

웹 구현 계약:

1. 사용자는 **개인 이메일 계정**으로 로그인한다.
2. 회사가 하나면 로그인 직후 해당 회사 워크스페이스로 진입한다.
3. 여러 회사에 초대된 사용자는 회사 선택 화면을 거친다.
4. 회사 공용 아이디 하나를 여러 사람이 공유하지 않는다. 변경자 추적을 위해 반드시 개인 계정을 사용한다.
5. 초기 가입은 자유가입이 아닌 **초대 기반**을 기본으로 한다.
6. 초대 메일 → 비밀번호 설정 → 이메일 확인 → 로그인 → 회사 진입 순서다.
7. 로그인 화면은 이메일, 비밀번호, 로그인, 비밀번호 찾기만 우선 제공한다.
8. 로그아웃 시 Supabase 세션을 종료하고 로컬 캐시의 민감 데이터를 지운다.
9. 비밀번호 재설정 링크의 리다이렉트 URL은 실제 Cloudflare 운영 도메인과 미리보기 도메인을 구분해 등록한다.

### 6.3 대시보드

행사 미선택 화면:

- `이벤트 플로우`
- `+ 새 행사`
- 행사 목록
- 각 행사 카드에 행사명, 준비 시작일, 최종 행사일, 진행률
- 행사 카드를 클릭하거나 키보드 Enter/Space로 선택

행사 선택 화면:

- 행사명과 기간
- 행사 정보 수정
- 행사 삭제
- 다른 행사 선택
- KPI: 관리 대상, 완료, 진행중, 미착수, 지연
- 전체 진행률과 완료/관리대상 개수
- `지연 · 7일 이내 마감` 최대 12개, 마감일 순

집계 규칙:

- 관리 대상 = `required=1`이며 상태가 `해당없음`이 아닌 활성 업무
- 진행률 = 완료 / 관리 대상
- 지연 = 완료·해당없음이 아니고 마감일이 오늘보다 이전인 업무
- 날짜 미입력 업무는 지연·임박 목록에 나오지 않음
- 제외 업무는 모든 집계에서 제외

### 6.4 행사 생성·수정·삭제

행사 필드:

- 행사명: 필수
- 준비 시작일: 필수
- 최종 행사일: 선택, 시작일보다 빠를 수 없음
- 장소
- 주최/주관
- 예산
- 예산 VAT 기준: 미선택/부가세 포함/부가세 별도
- PM 업체
- 참여 업체 다중 선택
- 참여 프리랜서 다중 선택

새 행사 체크리스트 생성 방식 A — 기본항목:

- 기본 120개가 분류 트리로 표시됨
- 전체/대분류/중분류/개별 항목 선택
- 적어도 1개 항목 필요
- 기본항목의 이름·세부내용·수량·단위·기준단가·VAT·기본 업체·기본 담당을 행사 업무 스냅샷으로 복사
- 시작일·마감일은 `NULL`
- 상태는 `미착수`
- 기본 업체·담당 때문에 필요한 업체/프리랜서는 행사 참여자에 자동 포함

새 행사 체크리스트 생성 방식 B — 이전 행사:

- 기준 행사 선택
- `항목만 가져오기` 또는 `항목과 정산 가져오기`
- 원본 행사에서 제외 처리된 항목은 표시·복사하지 않음
- 기본항목 기반 항목과 직접 추가 항목 모두 복사 가능
- 분류, 항목명, 세부내용, 단위 유지
- 수량 1, 상태 미착수, 날짜·PM·업체·업체담당자 미지정
- 항목만 가져오기: 단가 0원
- 항목과 정산 가져오기: 단가와 VAT 구분 보존
- 다른 행사 소속 ID나 제외된 ID를 요청에 섞어도 서버에서 거부

수정 규칙:

- 행사 날짜를 바꿔도 기존 업무 날짜는 변경하지 않음
- PM 업체를 바꾸면 새 PM 업체 소속이 아닌 기존 업무의 PM 담당자를 미지정으로 정리
- 업무에 이미 지정된 업체·담당자는 행사 참여자 목록에서 임의로 제거하지 않음

삭제 규칙:

- 행사 삭제는 확인이 필요함
- 행사와 그 업무·참여 관계가 함께 삭제됨
- 웹에서는 OWNER/ADMIN만 삭제 가능하게 하고, 기본은 즉시 물리삭제보다 휴지통/soft delete 후 보존기간 삭제를 권장

### 6.5 체크리스트

상단 기능:

- 항목·세부내용·메모 검색
- 상태 필터
- 대분류 필터
- 기본항목에서 항목 가져오기
- 행사 정보 수정
- 열 너비 맞춤
- 선택 행 담당 지정
- 직접 항목 추가
- 선택 항목 제외
- 제외 항목 보기/복원
- PDF 내보내기
- 현재 항목 수 표시

표 열과 편집 가능 여부:

| 열 | 동작 |
|---|---|
| 순서 | 표시 전용 |
| 대분류 | 표시 전용, 같은 그룹 세로 병합 |
| 중분류 | 표시 전용, 같은 대분류 안에서 세로 병합 |
| 항목 | 더블클릭 텍스트 편집, 빈 값 금지 |
| 세부내용 | 더블클릭 텍스트 편집 |
| 상태 | 6개 상태 선택 |
| 작업 시작일 | 달력 선택 또는 날짜 비우기 |
| 마감일 | 달력 선택 또는 날짜 비우기 |
| 담당자(PM) | 행사 PM 업체 소속 담당자만 선택 |
| 업체 | 전체 등록 업체 중 선택 |
| 업체담당자 | 선택한 업체 소속 담당자만 선택 |
| 업체담당자 전화번호 | 담당자에서 자동 표시, 직접 편집 불가 |

상태:

- 미착수
- 진행중
- 확인요청
- 완료
- 보류
- 해당없음

완료 규칙:

- 상태가 완료가 되면 `completed_at` 기록
- 완료가 아닌 상태로 바꾸면 `completed_at` 제거
- 달력의 완료 처리/취소도 같은 상태 변경을 사용
- 해당없음은 진행률과 정산에서 제외

날짜 규칙:

- 새 업무 날짜는 비어 있음
- 한쪽 날짜만 입력하는 것은 허용되지만 달력에는 두 날짜가 모두 있어야 표시
- 시작일은 마감일보다 늦을 수 없음
- 행사 날짜와 자동 연동하지 않음
- `미입력` 상태로 되돌릴 수 있음

담당 관계 규칙:

- PM 담당자는 행사 `pm_vendor_id` 업체 소속 사람만 허용
- 업체담당자는 업무의 선택 업체 소속 사람만 허용
- 업체 변경 시 기존 업체담당자가 새 업체 소속이 아니면 미지정으로 전환
- 담당자 표시 라벨은 `이름 · 직책 · 역할`, 빈 값은 생략
- 동명이인은 고유 ID로 구분

다중 일괄 지정:

- 셀이 하나라도 선택된 모든 행을 대상으로 함
- 담당자(PM), 업체, 업체담당자를 각각 `변경 안 함`/`미지정`/값 선택
- 한 DB 트랜잭션으로 전부 적용
- 업체 변경만 선택하면 기존 업체담당자를 기본적으로 미지정 처리
- PM과 업체담당자의 소속 검증 실패 시 전체 작업을 롤백

분류 정렬:

- 기존 최초 `sort_order`를 기준으로 대분류와 중분류를 인접하게 유지
- 나중에 추가한 항목도 해당 분류 안에 배치
- 대분류/중분류 병합이 여러 덩어리로 갈라지지 않아야 함

직접 항목 추가 필드:

- 대분류, 중분류, 항목명 필수
- 세부내용
- 작업 시작일·마감일 선택
- 수량, 단위
- 행사 단가(공급가)
- VAT 10%/면세
- `master_item_id=NULL`

기본항목 가져오기:

- 현재 행사에 없는 기본항목 또는 제외된 기본항목만 표시
- 새 항목은 기본값으로 생성
- 이전에 제외한 동일 기본항목은 새 레코드를 만들지 않고 기존 기록을 복원
- 복원 시 기존 상태·메모·가격 같은 행사 기록을 유지하고 제외 표시만 해제
- 한 행사에 같은 기본항목을 중복 생성하지 않음

제외/복원:

- 제외는 삭제가 아니며 기존 상태·날짜·금액·메모를 보존
- 현재 UI는 제외 사유를 새로 묻지 않고 빈 문자열로 유지할 수 있음
- 제외 보기에서는 일괄 담당 지정 비활성화
- 복원하면 원래 체크리스트로 돌아옴
- 제외 업무는 대시보드, 달력, 정산, 일반 출력에서 제외

태블릿 대응:

- 12열 표를 그대로 축소하지 않는다.
- 기본 목록은 항목명·상태·마감일·담당을 보여주는 카드/압축 행으로 제공한다.
- 항목을 누르면 세부내용, 날짜, PM, 업체, 업체담당자를 편집하는 하단 시트 또는 전체화면 패널을 연다.
- 다중 선택 모드에서 일괄 지정·제외를 제공한다.

### 6.6 달력

- 행사별 월간 7열×6주 타임라인
- 이전 달, 다음 달, 오늘로 가기
- 현재 월 표시
- 우측 일정 목록 표시/숨기기와 설정 저장
- 날짜 선택
- PDF 내보내기
- 대분류 저채도 색상:
  - 시스템: 파랑 계열
  - 시설: 초록 계열
  - 행사: 주황/살구 계열
  - 홍보: 보라 계열
  - 운영: 황갈색 계열

달력 표시 조건:

- 제외되지 않음
- 상태가 완료·해당없음이 아님
- 시작일과 마감일이 모두 있음
- 조회 월과 기간이 겹침

달력 막대:

- 여러 날 기간은 연속 주간 막대로 연결
- 업무명을 표시
- 겹침은 동적 lane으로 분리
- 공간 초과는 `+N개 더보기`
- 완료 처리하면 기간 막대에서 사라짐

선택 날짜 목록:

- 선택 날짜가 업무 기간 안에 포함되는 모든 항목
- 완료 항목도 목록에는 나오며 마지막에 정렬
- 지연 미완료 우선, 이후 마감일 순
- 업무명, 분류, 기간, 상태
- 완료 처리/완료 취소
- 오늘 마감인 미완료 업무에는 `내일까지`, `모레까지`, `날짜 선택` 제공
- 마감 연장 시 시작일보다 앞선 날짜는 거부

### 6.7 정산내역

상단 기능:

- 행사 설명
- 입력 예산
- 예산 VAT 기준: 미선택/포함/별도
- KPI: 입력 예산, 공급가 합계, VAT, VAT 포함 합계, 잔액/부족
- 수량·단가 미입력 경고 개수
- 선택 행 담당 지정
- 열 너비 맞춤
- PDF 내보내기

정산 표:

| 열 | 편집 |
|---|---|
| 대분류 | 표시 전용, 병합 |
| 중분류 | 표시 전용, 병합 |
| 항목 | 텍스트 편집 |
| 수량 | 숫자 편집 |
| 단위 | 선택 또는 직접 입력 |
| 행사 단가 | 공급가 기준 원 단위 정수 |
| 공급가 | 계산 |
| VAT 구분 | 10%/면세 |
| VAT | 계산 |
| 합계 | 계산 |
| 업체 | 선택 |
| 메모 | 텍스트 편집 |

계산 규칙:

- 공급가 = 수량 × 행사 단가
- 원 단위 `ROUND_HALF_UP`
- 과세 VAT = 공급가 × 10%, 원 단위 `ROUND_HALF_UP`
- 면세 VAT = 0
- 합계 = 공급가 + VAT
- 대분류별 소계와 전체 합계
- 각 대분류의 중분류 `기타`는 마지막 정렬
- 제외 및 해당없음 업무는 정산에서 제외
- 수량 또는 단가가 비어 있으면 0으로 계산하되 경고 표시

예산 비교:

- 예산 포함: VAT 포함 전체 합계와 비교
- 예산 별도: 공급가 합계와 비교
- VAT 기준 미선택: 임의 비교하지 않고 `VAT 기준 선택 필요`
- 예산 미입력: `예산 미입력`
- 차액은 남음/부족/일치로 표시
- 정산 화면의 입력 예산과 행사 정보의 예산은 같은 필드

### 6.8 설정 > 기본 항목

현재 기본 항목은 120개다.

| 대분류 | 수 | 중분류 |
|---|---:|---|
| 시스템 | 14 | 무대, 소스 |
| 시설 | 26 | 기반, 렌탈, 기타 |
| 행사 | 24 | 연출, 개막식, 공연, 경연, 참여·체험, 전시, 먹거리, 판매, 부대행사 |
| 홍보 | 21 | 공통, 온라인, 인쇄, 옥외, 기타 |
| 운영 | 35 | 행정, 인력, 비품/물품, 환경정리, 기타, 기록 |

초기 원본 118개에 `카메라다이`, `콘솔다이`를 추가했다. 오염값 `81`과 `#NAME?`는 포함하지 않는다.

기본 항목 필드:

- 순서
- 대분류
- 중분류
- 항목
- 세부내용
- 수량
- 단위
- 기준 단가(공급가)
- VAT 10%/면세
- 기본 업체
- 기본 담당

기능:

- 분류·항목·세부내용 검색
- 항목 추가
- 선택 수정
- 선택 삭제
- 표 직접 편집
- 단위·VAT·업체·담당 선택 편집
- 대분류/중분류 그룹명 변경 시 같은 그룹 전체에 반영
- 기본항목 변경은 이미 만든 행사 업무에 소급하지 않음
- 기본항목 삭제도 기존 행사 스냅샷을 삭제하지 않음
- 일정 규칙/D-Day/오프셋은 없음
- DB의 `active` 열은 현재 UI에서 사용 여부를 제어하지 않는 레거시 열이므로 웹 설계에서 의존하지 않음

초기 연락처 seed:

- PERSON 9개: 총괄, 기획, 무대/시스템, 시설, 홍보, 운영, 행정, 안전, 기록
- VENDOR 1개: `(업체 미정)`

웹에서는 이 seed를 회사 생성 시 선택적으로 복사하되, 회사별로 독립된 기본항목과 연락처가 되도록 한다.

### 6.9 설정 > 업체·담당자

업체별 담당자 탭:

- 업체 추가/삭제
- 업체 필드: 업체명, 업종
- 업체를 선택하면 소속 담당자 목록 표시
- 소속 담당자 추가
- 담당자 필드: 이름, 직책, 연락처, 역할
- 셀 더블클릭 편집

프리랜서 탭:

- 프리랜서 추가/삭제
- 이름, 직책, 연락처, 역할
- 프리랜서는 소속 업체가 없음

관계 규칙:

- 업체와 사람은 ID로 구분하며 이름 중복 허용
- 사람은 하나의 업체에 소속되거나 프리랜서
- 업체 삭제 시 소속 사람은 삭제되지 않고 회사 소속이 해제되는 현재 FK 규칙을 웹에서도 명시적으로 결정해야 함. 권장 웹 동작은 삭제 전 영향 안내 후 프리랜서로 전환 또는 함께 비활성화 중 선택
- 연락처는 주소록 레코드이며 로그인 계정과 동일하지 않음
- 로그인 가능한 사람은 `people.auth_user_id`로 선택적으로 연결

### 6.10 설정 > 데이터 관리

현재 기능:

- 데이터 저장 위치 표시
- 지금 백업
- 백업에서 복원
- Excel 내보내기
- 앱 정보와 버전/설치 위치
- 업데이트 설명

웹 대응:

- 로컬 DB 경로와 Windows 설치 위치는 표시하지 않음
- 회사 데이터 JSON 백업 다운로드
- 회사 데이터 백업 복원은 OWNER만 가능
- 복원 전에 서버가 현재 회사 데이터의 안전 백업을 자동 생성
- Supabase 무료 플랜에는 프로젝트 자동 백업이 포함되지 않으므로 앱 수준 백업을 생략하지 않음
- 복원은 반드시 회사 범위에 한정하고 다른 회사 데이터를 건드리지 않음
- 앱 정보에는 웹 버전, 마지막 배포 시각, Supabase 연결 상태를 표시

### 6.11 PDF 내보내기

공통:

- 체크리스트, 정산내역, 달력 지원
- A4/A3
- 가로/세로
- 연한 회색 헤더, 오렌지 분류/소계, 상태 색상
- 행사명, 기간, 출력 시각, 요약, 페이지 번호
- 긴 행사명 자동 축소/최대 2줄
- 같은 파일명이면 덮어쓰지 않는 방향

체크리스트 PDF:

- 전체 또는 대분류 선택
- 대·중분류 시각적 그룹
- A4 세로는 날짜·PM과 업체·담당·전화번호를 2단으로 압축
- 세부내용만 좌측 정렬, 나머지는 중앙 정렬

달력 PDF:

- 현재 표시 월
- 전체/대분류/중분류 선택
- 우측 일정 목록 없이 6주 달력만 출력
- 일정 겹침이 페이지 lane을 넘으면 같은 달력을 다음 페이지로 반복하여 누락 없이 출력

정산 PDF:

- 대분류 소계와 전체 합계
- 행사금액 VAT 기준, 비교 대상, 잔액/부족 명시
- A4 세로는 세부내용을 항목 오른쪽에 배치

기본 파일명:

```text
종류_행사명_분류명_YYYYMMDD_A4세로.pdf
```

### 6.12 Excel 내보내기

- 행사 선택
- 체크리스트 또는 정산내역 중 하나만 선택
- A4/A3, 가로/세로
- 체크리스트: 전체/대분류/중분류
- 정산: 전체
- PDF와 같은 압축 행사 헤더와 시각 스타일
- 체크리스트 대·중분류 셀 병합
- 정산 대분류 소계, 전체 합계와 Excel 수식
- 긴 세부내용 및 2단 셀에 맞춘 행 높이
- 인쇄 영역, 너비 1페이지, 반복 제목행, 여백, 페이지 번호
- 기본 파일명은 PDF 규칙과 동일하되 `.xlsx`

웹 구현 시 브라우저가 동일 이름 파일에 자체 순번을 붙일 수 있으므로 파일 시스템 존재 여부를 직접 검사하는 데스크톱 로직은 그대로 복제하지 않아도 된다. 원본 파일을 자동 덮어쓰지 않는 사용자 경험은 유지한다.

## 7. 현재 SQLite 데이터 모델

현재 스키마 버전은 8이다.

### `events`

- `id`
- `name`
- `start_date`
- `end_date`
- `location`
- `organizer`
- `budget`
- `budget_tax_mode`: INCLUDED/EXCLUDED/UNSET
- `pm_vendor_id`
- `created_at`, `updated_at`

### `master_items`

- `id`
- `major`, `minor`, `name`, `detail`
- `priority`: 상/중/하 — 현재 주요 화면에서 직접 사용하지 않지만 데이터 보존
- `quantity`, `unit`
- `base_unit_price`
- `default_vat_type`: TAXABLE/EXEMPT
- `default_vendor_id`, `default_assignee_id`
- `sort_order`
- `active` — 현재 UI 비사용 레거시

### `contacts`

- `id`
- `kind`: PERSON/VENDOR
- `name`
- `phone`
- `job_title`
- `role_note`: 사람은 역할, 업체는 업종
- `company_id`: PERSON이 속한 VENDOR 연락처 ID
- `created_at`

### `event_tasks`

- `id`, `event_id`, `master_item_id`
- `major`, `minor`, `name`, `detail`
- `required`
- `status`
- `priority`
- `quantity`, `unit`
- `assignee_id`: 업체담당자 또는 프리랜서 연락처
- `pm_assignee_id`: PM 업체 소속 담당자
- `vendor_id`
- `planned_start`, `due_date`
- `cost`: 레거시 필드, 현재 계산은 `unit_price` 사용
- `unit_price`
- `vat_type`
- `is_removed`, `removed_reason`
- `note`
- `completed_at`
- `sort_order`
- `created_at`, `updated_at`

제약:

- 상태 6종만 허용
- 시작일이 마감일보다 늦을 수 없음
- 같은 행사에 같은 `master_item_id`는 하나만 허용

### `event_vendors`

- `event_id`, `vendor_id` 복합 PK

### `event_freelancers`

- `event_id`, `person_id` 복합 PK

### `settings`

- `key`, `value`
- 현재 주요 값: `calendar_list_visible`, 과거 자동백업일 등

### `schema_info`

- SQLite 마이그레이션 버전

## 8. 웹 목표 기술 구조

권장 스택:

- SvelteKit + TypeScript
- `@sveltejs/adapter-cloudflare`
- Cloudflare Workers + Workers Assets
- Supabase Auth
- Supabase Postgres
- Supabase Realtime
- PWA manifest + service worker
- Vitest 단위검사
- Playwright PC/태블릿 E2E
- 접근성 검사

구조:

```text
사용자 PC/태블릿 PWA
  ├─ Cloudflare Workers: SvelteKit 화면·SSR·정적 자산
  └─ Supabase
      ├─ Auth: 개인 이메일 로그인
      ├─ Postgres: 회사·행사·업무·정산
      ├─ RLS: 회사/행사/역할별 권한
      └─ Realtime: 다른 사용자의 변경 알림
```

Cloudflare D1/R2/KV는 1차에서 사용하지 않는다. 업무 데이터의 단일 기준은 Supabase Postgres다.

## 9. 회사별 로그인과 권한 설계

### 9.1 핵심 원칙

- 회사별 공용 로그인 계정을 만들지 않는다.
- 개인 `auth.users.id`와 회사 소속을 다대다 관계로 저장한다.
- 연락처 사람 레코드와 로그인 사용자는 별개이며 필요할 때 연결한다.
- 권한 판단에 사용자가 수정 가능한 `user_metadata`를 사용하지 않는다.
- 테이블 접근은 JWT 인증만으로 허용하지 않고 반드시 회사/행사 멤버십 RLS 조건을 함께 검사한다.

### 9.2 회사 역할

| 역할 | 권한 |
|---|---|
| OWNER | 회사 설정, 사용자 초대/권한, 모든 행사·정산·백업·복원·삭제 |
| ADMIN | 사용자 관리, 기본항목·연락처, 모든 행사·정산, 내보내기 |
| PM | 행사 생성·수정, 체크리스트·달력·정산 운영, 내보내기 |
| MEMBER | 허용된 행사 조회, 체크리스트·달력 편집 |
| VIEWER | 허용된 데이터 조회와 출력만 가능 |

### 9.3 외부 업체 사용자

1차에서 업체·담당자 주소록은 로그인 계정이 아니다. 외부 업체 사용자 로그인이 필요해지면 `event_members`에 `VENDOR` 역할로 초대한다.

VENDOR 역할 기본 제한:

- 초대된 행사만 조회
- 자신 또는 자기 업체에 배정된 업무만 조회·상태/메모 수정
- 회사 전체 기본항목·연락처·예산·정산 합계는 볼 수 없음
- 행사 삭제, 담당자 권한 변경, 백업/복원 불가

### 9.4 초대 흐름

1. OWNER/ADMIN이 이메일, 이름, 회사 역할을 입력한다.
2. 서버 전용 함수가 요청자의 권한을 다시 확인한다.
3. Supabase Auth 초대 메일을 보낸다.
4. `organization_invitations`에 만료시간과 상태를 저장한다.
5. 사용자가 링크를 열어 비밀번호와 이름을 확정한다.
6. 초대를 한 번만 소비해 `organization_members`를 만든다.
7. 이미 가입한 이메일이면 기존 사용자에게 회사 멤버십만 추가한다.

관리자 초대 API에 필요한 secret/service-role은 브라우저에 넣지 않는다. Supabase Edge Function 또는 검증된 Cloudflare 서버 엔드포인트의 secret으로만 사용한다.

## 10. 권장 Supabase 웹 스키마

웹에서는 모든 주요 PK를 UUID로 사용한다. 기존 SQLite ID는 마이그레이션 추적용 `legacy_id`로만 보존한다.

### 인증·회사

#### `profiles`

- `user_id uuid PK references auth.users`
- `display_name`
- `phone`
- `created_at`, `updated_at`

#### `organizations`

- `id uuid PK`
- `name`
- `slug`
- `status`: ACTIVE/ARCHIVED
- `created_by`
- `created_at`, `updated_at`

#### `organization_members`

- `organization_id`
- `user_id`
- `role`: OWNER/ADMIN/PM/MEMBER/VIEWER
- `status`: ACTIVE/SUSPENDED
- `invited_by`, `joined_at`
- 복합 unique `(organization_id, user_id)`

#### `organization_invitations`

- `id`, `organization_id`, `email`, `role`
- `token_hash`
- `expires_at`, `accepted_at`, `invited_by`, `created_at`

#### `user_preferences`

- `user_id`
- `last_organization_id`
- `calendar_list_visible`
- 기타 사용자별 UI 설정

### 주소록

SQLite의 self-reference `contacts`보다 목적을 명확히 하기 위해 웹은 분리 테이블을 권장한다.

#### `vendors`

- `id`, `organization_id`
- `name`
- `industry`
- `is_active`
- `legacy_id`
- `created_at`, `updated_at`

#### `people`

- `id`, `organization_id`
- `vendor_id nullable` — null이면 프리랜서
- `auth_user_id nullable` — 로그인 사용자와 연결할 때만 사용
- `name`, `job_title`, `phone`, `role_note`
- `is_active`
- `legacy_id`
- `created_at`, `updated_at`

### 기본항목·행사

#### `master_items`

- `id`, `organization_id`, `legacy_id`
- `major`, `minor`, `name`, `detail`
- `priority`
- `quantity numeric`, `unit`
- `base_unit_price bigint`
- `default_vat_type`
- `default_vendor_id`, `default_assignee_id`
- `sort_order`
- `is_active`
- `created_at`, `updated_at`, `updated_by`

#### `events`

- `id`, `organization_id`, `legacy_id`
- `name`, `start_date`, `end_date`
- `location`, `organizer`
- `budget bigint nullable`
- `budget_tax_mode`
- `pm_vendor_id`
- `deleted_at nullable`
- `created_at`, `updated_at`, `created_by`, `updated_by`

#### `event_members`

- `event_id`, `user_id`
- `role`: MANAGER/EDITOR/VIEWER/VENDOR
- `vendor_id nullable`
- `created_at`, `created_by`
- 복합 unique `(event_id, user_id)`

#### `event_vendors`

- `event_id`, `vendor_id`
- 복합 PK

#### `event_freelancers`

- `event_id`, `person_id`
- 복합 PK

#### `event_tasks`

- `id`, `organization_id`, `event_id`, `legacy_id`
- `master_item_id nullable`
- `major`, `minor`, `name`, `detail`
- `required`, `status`, `priority`
- `quantity numeric`, `unit`
- `pm_assignee_id`, `vendor_id`, `assignee_id`
- `planned_start`, `due_date`
- `unit_price bigint nullable`
- `vat_type`
- `is_removed`, `removed_reason`
- `note`
- `completed_at`
- `sort_order`
- `row_version bigint default 1`
- `created_at`, `updated_at`, `created_by`, `updated_by`

`cost` 레거시 열은 웹에 만들지 않는다.

### 이력·백업

#### `activity_logs`

- `id`, `organization_id`, `event_id nullable`
- `actor_user_id`
- `entity_type`, `entity_id`
- `action`
- `before_data jsonb`, `after_data jsonb`
- `created_at`

#### `organization_backups`

- `id`, `organization_id`
- `schema_version`
- `payload jsonb` 또는 안전한 외부 백업 위치
- `created_by`, `created_at`
- `kind`: MANUAL/PRE_RESTORE

사진/첨부 테이블은 만들지 않는다.

## 11. RLS와 보안 계약

### 11.1 공통

- `public`에 노출되는 모든 테이블에 RLS 활성화
- `anon`은 앱 데이터 SELECT/INSERT/UPDATE/DELETE 모두 금지
- `authenticated`도 멤버십 조건 없이 접근 금지
- 모든 테이블의 `organization_id`가 현재 사용자의 활성 멤버십과 일치해야 함
- event 범위 데이터는 organization 권한 또는 `event_members` 권한을 추가 확인
- UPDATE 정책은 `USING`과 `WITH CHECK` 둘 다 작성
- 뷰는 `security_invoker=true`
- `service_role`/secret 키는 클라이언트·GitHub·문서에 저장 금지

### 11.2 권한 예시

- 조직 멤버: 자신이 속한 조직 기본 정보 조회
- OWNER/ADMIN: 조직 멤버와 기본항목·주소록 관리
- PM: 조직 행사 생성·수정, 운영 데이터 편집
- MEMBER: 자신에게 허용된 행사 업무 편집
- VIEWER: SELECT만 가능
- VENDOR: 지정 행사와 배정 업무의 제한된 열만 접근. 비용 열이 API 응답에 포함되지 않도록 전용 보안 뷰/RPC를 고려

### 11.3 서버 함수

초대, 회사 전체 복원처럼 권한 상승이 필요한 작업만 서버 함수로 둔다.

- 요청 JWT의 `auth.uid()` 확인
- DB에서 OWNER/ADMIN 멤버십을 직접 확인
- 요청의 `organization_id`를 신뢰하지 않고 멤버십과 대조
- `SECURITY DEFINER`가 꼭 필요하면 비노출 스키마에 두고 `PUBLIC` 실행 권한 철회
- 구현 후 Supabase DB advisors와 실제 비권한 계정 테스트 필수

## 12. 실시간 협업·동시 편집·되돌리기

### 12.1 실시간 반영

- 초기 소규모 시험은 `Postgres Changes`로 시작 가능
- 운영 확장 시 Supabase가 권장하는 private Broadcast + DB trigger로 전환
- 최소 구독 대상: `events`, `event_tasks`, `vendors`, `people`, `master_items`
- 이벤트 수신 시 전체 페이지를 무조건 다시 불러오기보다 해당 레코드와 집계를 갱신
- 연결 끊김/재연결 상태를 화면에 표시

### 12.2 충돌 제어

- `event_tasks.row_version`을 업데이트할 때 기존 버전을 조건으로 사용
- 성공하면 버전 +1
- 다른 사용자가 먼저 수정해 조건이 맞지 않으면 덮어쓰지 않고 최신 값과 내 입력을 비교하는 충돌 안내 표시
- 상태 체크처럼 단순한 값은 최신 서버 값을 다시 보여주고 재시도를 선택하게 함

### 12.3 Undo/Redo 대응

데스크톱의 전체 SQLite 스냅샷 50단계를 여러 사용자가 공유하는 서버에 그대로 적용하면 다른 사람 변경까지 되돌릴 위험이 있다.

웹 구현 계약:

- 모든 변경을 `activity_logs`에 기록
- 현재 사용자 세션의 최근 작업만 역변경 가능
- 역변경 전에 대상 `row_version`이 당시와 같은지 확인
- 다른 사용자가 이후 수정했으면 Undo를 막고 충돌 안내
- 회사 전체 복원은 Undo가 아니라 OWNER 전용 백업 복원으로 처리

## 13. 기존 SQLite 데이터 이전

### 13.1 원칙

- 실제 `%LOCALAPPDATA%\EventCheckList` 데이터를 직접 수정하지 않는다.
- 원본 DB를 먼저 별도 백업한다.
- 마이그레이션은 복사본에서 수행한다.
- 회사 한 곳을 먼저 생성하고 모든 기존 데이터를 해당 `organization_id` 아래로 가져온다.
- integer ID → UUID 매핑표를 유지한다.
- 반복 실행해도 중복되지 않는 idempotent importer를 사용한다.
- 기존 행사 업무 스냅샷을 기본항목으로 다시 생성하지 않는다.

### 13.2 이전 순서

1. organizations
2. vendors
3. people와 업체 소속
4. master_items
5. events
6. event_vendors/event_freelancers
7. event_tasks
8. 사용자 계정과 people 연결

### 13.3 보존해야 할 값

- 모든 행사와 날짜
- 모든 체크리스트 항목과 직접 추가 항목
- 상태, 완료시각, 날짜, 메모
- PM 업체·PM 담당자
- 업체·업체담당자·전화번호 관계
- 수량·단위·단가·VAT
- 제외 여부·제외 사유
- 분류·정렬 순서
- 기본항목 스냅샷 관계

### 13.4 이전 검증

- 테이블별 행 수 전후 비교
- 모든 FK 유효성
- 행사별 관리대상/완료/진행률/지연 개수 비교
- 행사별 공급가/VAT/합계/잔액 비교
- `master_item_id` 중복 없음
- 시작일 > 마감일 없음
- 업체담당자 소속 불일치 목록 0건 또는 명시적 예외 목록
- 제외·해당없음이 집계에서 빠지는지 확인

## 14. 디자인·반응형·접근성

현재 시각 방향:

- 당근 SEED의 의미 토큰 원칙만 참고하고 고유 브랜드 자산은 사용하지 않음
- 브랜드 주황 `#F25B24`
- 눌림 `#D84B18`
- 약한 브랜드 배경 `#FFF0E8`
- 완료 초록, 확인/임박 노랑, 지연/삭제 빨강, 진행 파랑
- Segoe UI, Malgun Gothic 계열
- 화면 제목 26px/700, 섹션 18px/700, 본문 14px
- 밝은 테마 우선
- 색상만으로 상태를 전달하지 않고 텍스트·아이콘 병행

웹 반응형 기준:

- 데스크톱: 1280px 이상에서 현재 정보 밀도 유지
- 태블릿 가로: 체크리스트 핵심 열 + 세부 편집 패널
- 태블릿 세로: 카드 목록 + 전체화면 편집 패널
- 터치 대상 최소 44×44px
- hover에만 의존하지 않음
- 키보드 Tab/Shift+Tab, Enter, Space, Escape 지원
- 명확한 focus 표시
- WCAG AA 수준 대비 목표

## 15. Cloudflare Workers 배포 계약

### 15.1 초기 프로젝트

공식 Cloudflare SvelteKit 방식:

```text
npm create cloudflare@latest -- eventflow-web --framework=svelte
```

기존 빈 저장소를 사용하므로 생성 결과를 임시 폴더에서 만든 뒤 저장소 루트로 옮긴다. 현재 데스크톱 저장소 안에 중첩 clone하지 않는다.

필수 파일 예:

```text
package.json
package-lock.json
src/
static/
svelte.config.js
vite.config.ts
wrangler.jsonc
.gitignore
README.md
docs/codex-context.md
```

- Svelte adapter는 Cloudflare adapter 사용
- dependency 버전 고정 및 lockfile 커밋
- `npm run dev`, `npm run build`, `npm run check`, `npm test` 정의
- Cloudflare CI 배포 명령은 프로젝트 package script와 일치시킴

### 15.2 환경변수

브라우저 공개 가능:

```text
PUBLIC_SUPABASE_URL
PUBLIC_SUPABASE_PUBLISHABLE_KEY
```

절대 공개 금지:

```text
SUPABASE_SERVICE_ROLE_KEY
SUPABASE_SECRET_KEY
DATABASE_PASSWORD
초대 토큰 signing secret
```

- `.env`, `.dev.vars`는 Git 제외
- `.env.example`에는 값 없이 변수명만 기록
- Cloudflare Preview와 Production 환경변수를 각각 설정
- Supabase Auth Redirect URLs에 실제 `workers.dev` 주소와 최종 사용자 도메인을 등록

### 15.3 배포 흐름

1. 로컬 build/check/test 성공
2. `main` push
3. Cloudflare가 비공개 저장소 clone
4. 의존성 설치
5. SvelteKit build
6. Wrangler deploy
7. `*.workers.dev` 배포 URL 확인
8. 로그인 redirect, 새로고침, 직접 URL 접근, PWA 설치 확인

첫 실행 가능한 커밋이 올라가기 전에는 Cloudflare `Retry build`를 반복하지 않는다.

## 16. PWA 계약

- 앱 이름: 이벤트 플로우
- 짧은 이름: 이플
- 아이콘: 기존 EventFlow 주황 아이콘을 웹용 192/512px로 변환 가능
- `display: standalone`
- 시작 URL과 scope 명시
- 배경/테마 색상 설정
- 태블릿 홈 화면 설치 안내
- 앱 셸과 정적 자산 캐시
- 로그인 후 민감 API 응답을 service worker cache에 무제한 저장하지 않음
- 1차에서는 오프라인 조회·편집을 보장하지 않음
- 네트워크 단절 시 저장 실패를 성공처럼 표시하지 않고 재시도 안내

## 17. 백업·복원 설계

### 백업

- OWNER가 회사 데이터 전체 JSON 백업 요청
- 서버가 RLS를 우회하기 전에 OWNER 권한 재검증
- 현재 스키마 버전, 생성시각, organization ID, 레코드 수 포함
- 다른 회사 데이터 제외
- 민감 인증 정보와 비밀번호 제외
- 다운로드 파일과 서버 보관본 중 최소 하나 제공

### 복원

- OWNER만 가능
- 대상 회사와 백업 회사 일치 검증
- 지원 스키마 버전 검증
- 복원 직전 `PRE_RESTORE` 안전 백업 생성
- 단일 트랜잭션 또는 실패 시 전체 롤백
- 복원 후 행 수·FK·집계 검증
- 모든 접속자에게 데이터 새로고침 안내

## 18. 구현 단계

### 단계 0 — 저장소와 기준선

- `EventFlow-web` clone
- SvelteKit/Cloudflare 프로젝트 생성
- README, AGENTS, `docs/codex-context.md` 생성
- CI build/check/test
- 임시 첫 화면 배포

### 단계 1 — Supabase 기반

- 로컬 Supabase CLI 환경
- 마이그레이션 파일
- 조직·멤버·profile 스키마
- Auth 이메일 로그인/비밀번호 재설정
- invite-only 가입
- RLS 테스트

### 단계 2 — 주소록과 기본항목

- 업체·사람 분리 스키마
- 프리랜서
- 120개 seed
- 회사별 기본항목 CRUD

### 단계 3 — 행사와 체크리스트

- 행사 CRUD
- 기본항목/이전 행사 생성
- 체크리스트 검색·필터·편집
- 일괄 담당, 제외/복원, 직접 추가
- 태블릿 카드 UI

### 단계 4 — 대시보드·달력·정산

- 정확한 집계
- 월간 타임라인과 날짜 카드 동작
- ROUND_HALF_UP VAT 정산
- 실시간 반영과 충돌 처리

### 단계 5 — 출력·백업·PWA

- PDF/Excel
- 회사 백업·복원
- PWA 설치와 업데이트 안내
- PC/태블릿 전체 흐름 검증

### 단계 6 — 기존 데이터 이전과 운영 전환

- SQLite 복사본 importer
- dry-run 보고서
- 실제 이전
- 데스크톱과 웹 결과 비교
- 사용자 승인 후 운영

## 19. 필수 자동검사

### 데이터·규칙

- 120개 seed와 5개 대분류
- 행사 스냅샷 불변성
- 이전 행사 복사 두 방식
- 제거된/다른 행사 항목 복사 거부
- 새 업무 날짜 null
- 날짜 순서 검증
- 진행률에서 해당없음/제외 제외
- PM 업체 소속 검증
- 업체담당자 소속 검증
- 일괄 지정 전체 롤백
- VAT ROUND_HALF_UP
- 예산 포함/별도/미선택 비교
- 기타 중분류 마지막 정렬
- 분류 연속 정렬

### 인증·RLS

- 비로그인 사용자는 앱 데이터 0건
- A회사 사용자가 B회사 모든 테이블 접근 불가
- VIEWER 변경 불가
- MEMBER 회사 설정 불가
- VENDOR 비용·다른 업체 업무 접근 불가
- 초대 토큰 재사용 불가
- 정지된 멤버 접근 불가
- service role이 브라우저 bundle에 없음

### 협업

- 두 클라이언트에서 상태 변경 실시간 반영
- row_version 충돌 시 조용히 덮어쓰지 않음
- 다른 사용자 후속 변경이 있으면 Undo 차단

### UI/E2E

- 로그인→회사 선택→행사 선택→업무 완료
- 새 행사와 120개 선택
- 체크리스트 검색/필터/직접추가/제외/복원
- 달력 완료·오늘 마감 연장
- 정산 입력과 합계
- PDF/Excel 생성
- 백업→변경→복원
- 태블릿 가로/세로
- PWA 설치 가능
- 직접 URL 새로고침 404 없음

## 20. 현재 검증 기준선

현재 데스크톱 소스에서 다음 명령이 통과했다.

```powershell
cd C:\Work\02_EventCheckList\03_Program
.\.venv\Scripts\python.exe -m pytest -q
```

결과:

```text
111 passed
```

웹 구현 중 업무규칙이 모호하면 먼저 다음을 기준으로 확인한다.

1. `03_Program/tests/`
2. `03_Program/src/event_checklist/services.py`
3. 각 `ui/*_page.py`
4. `docs/codex-context.md`
5. 이 문서

초기 기획 문서 `02_Planning`에는 자동 일정, CSV, 사용 여부 등 현재 코드와 다른 과거 설명이 있으므로 최신 기능 판단의 단독 근거로 사용하지 않는다.

## 21. 새 Codex 프로젝트 시작 지시문

아래 문구와 이 파일을 새 프로젝트에 전달한다.

```text
EventFlow 웹/PWA를 새로 구현한다.

웹 저장소:
https://github.com/armsyuda/EventFlow-web.git

기존 데스크톱 참고 경로:
C:\Work\02_EventCheckList
기존 프로젝트는 읽기 전용으로 참고하고 수정하지 않는다.

반드시 docs/EventFlow_WebApp_Master_Handoff.md를 전체 읽고,
현재 구현과 웹 구현 계약을 구분해서 따른다.

기술 방향:
- SvelteKit + TypeScript
- Cloudflare Workers
- Supabase Auth/Postgres/RLS/Realtime
- 회사별 개인 계정 로그인
- PC/태블릿 PWA

사진·이미지·파일 첨부 기능은 이번 범위에서 제외한다.
service role/secret 키는 클라이언트와 Git에 넣지 않는다.

먼저 단계 0~1의 상세 작업계획, 스키마, RLS, 화면 구조를 검토하고
기존 기능 누락 여부를 확인한 뒤 구현한다.
```

## 22. 공식 참고 링크

- Supabase Auth: <https://supabase.com/docs/guides/auth>
- Supabase Password Auth: <https://supabase.com/docs/guides/auth/passwords>
- Supabase RLS: <https://supabase.com/docs/guides/database/postgres/row-level-security>
- Supabase Realtime: <https://supabase.com/docs/guides/realtime>
- Supabase Realtime 변경 구독: <https://supabase.com/docs/guides/realtime/subscribing-to-database-changes>
- Cloudflare SvelteKit Workers: <https://developers.cloudflare.com/workers/framework-guides/web-apps/sveltekit/>
- Cloudflare Git 통합: <https://developers.cloudflare.com/pages/configuration/git-integration/>

## 23. 금지사항과 주의사항

- 기존 데스크톱 저장소에 웹앱을 추가하지 않는다.
- 기존 사용자 SQLite DB를 초기화하거나 덮어쓰지 않는다.
- 기존 행사 업무를 기본항목에서 다시 생성해 사용자 스냅샷을 잃지 않는다.
- 회사/사용자 권한을 이름이나 이메일 문자열만으로 판단하지 않는다.
- `TO authenticated`만으로 RLS를 끝내지 않는다.
- `user_metadata`를 권한 근거로 쓰지 않는다.
- service-role/secret을 브라우저 환경변수에 넣지 않는다.
- 같은 이름의 업체·담당자를 중복 데이터로 단정하지 않는다.
- 업체를 바꾼 뒤 다른 업체 담당자를 그대로 남기지 않는다.
- 해당없음·제외 항목을 진행률과 정산에 포함하지 않는다.
- 수량·VAT 계산을 부동소수점 단순 반올림으로 처리하지 않는다.
- 사진/첨부 기능을 선행 구현하지 않는다.
- UI를 PC 12열 표 그대로 태블릿에 축소하지 않는다.

