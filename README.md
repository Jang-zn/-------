# Jira/Confluence Work History Scraper

개인의 업무 이력 정리를 위한 Jira 이슈 및 Confluence 문서 스크래핑 도구입니다.

## ⚠️ 주의사항

이 도구는 개인의 업무 이력 정리를 위한 목적으로 설계되었습니다.

- **회사의 데이터 보안 정책을 확인하고 준수하십시오.**
- 수집된 데이터에 기밀 정보가 포함되어 있을 수 있으니 관리에 주의하십시오.
- 본인의 업무 이력만 수집하며, 타인의 데이터는 수집하지 않습니다.
- API 토큰을 안전하게 보관하고 절대 공유하지 마십시오.

## 기능

### Jira 수집 기능
- ✅ 본인이 담당자(assignee) 또는 보고자(reporter)인 이슈 수집
- ✅ 이슈 상세 정보 (30개 필드)
- ✅ 코멘트 정보 (본인 작성 코멘트만)
- ✅ 에픽 및 스프린트 정보
- ✅ 링크된 이슈, 컴포넌트, 라벨 등

### Confluence 수집 기능
- ✅ 본인이 작성한 페이지 수집
- ✅ 페이지 상세 정보 (17개 필드)
- ✅ HTML 본문 파싱 및 텍스트 추출
- ✅ 버전 이력, 라벨, 상위 페이지 정보

### 기타 기능
- ✅ CSV 파일로 출력 (Excel 호환)
- ✅ 월별/프로젝트별 통계 생성
- ✅ Rate limiting 및 재시도 로직
- ✅ 체크포인트 기능 (중단 후 재개 가능)
- ✅ 진행률 표시

## 요구사항

- Python 3.10 이상
- Atlassian Cloud 계정 및 API Token

## 설치

### 1. 저장소 클론 또는 다운로드

```bash
cd "지라 스크래핑"
```

### 2. 가상 환경 생성 및 활성화

```bash
python3 -m venv venv
source venv/bin/activate  # macOS/Linux
# 또는
venv\Scripts\activate  # Windows
```

### 3. 의존성 설치

```bash
pip install -e .
```

개발 도구도 함께 설치하려면:

```bash
pip install -e ".[dev]"
```

## 설정

### 1. API Token 발급

1. Atlassian 계정 설정으로 이동: https://id.atlassian.com/manage-profile/security/api-tokens
2. "Create API token" 클릭
3. 토큰 이름 입력 (예: "Work History Scraper")
4. 생성된 토큰 복사 (한 번만 표시됨!)

### 2. 환경 변수 설정

`.env.example` 파일을 복사하여 `.env` 파일 생성:

```bash
cp .env.example .env
```

`.env` 파일을 편집하여 인증 정보 입력:

```env
ATLASSIAN_EMAIL=your-email@example.com
ATLASSIAN_API_TOKEN=your-api-token-here
```

### 3. 설정 파일 편집

`config/config.yaml` 파일을 편집하여 스크래핑 설정 구성:

```yaml
server:
  jira_base_url: "https://yourcompany.atlassian.net"
  confluence_base_url: "https://yourcompany.atlassian.net/wiki"

user:
  account_id: "your-account-id"  # Jira 프로필 URL에서 확인
  display_name: "홍길동"
```

#### Account ID 확인 방법

**방법 1: API를 통한 확인 (가장 정확)**

`.env` 파일을 먼저 설정한 후:

```bash
python -m src validate
```

실행하면 로그에 Account ID가 표시됩니다.

**방법 2: Jira 이슈에서 확인**

1. Jira에서 본인이 담당자인 아무 이슈나 열기
2. 브라우저 개발자 도구 열기 (F12)
3. Network 탭에서 API 호출 확인
4. `/rest/api/2/issue/{issue-key}` 응답에서 `fields.assignee.accountId` 찾기

**방법 3: Jira 사용자 검색**

1. Jira에서 검색창에 `assignee = currentUser()` 입력
2. 아무 이슈나 클릭
3. 담당자 필드에 마우스 올리면 Account ID가 툴팁으로 표시될 수 있음

**방법 4: 임시로 빈 값 사용**

일단 `account_id`를 임시로 `"unknown"`으로 설정하고:
- `validate` 명령어를 실행하면 로그에 실제 Account ID가 출력됩니다
- 그 값을 `config.yaml`에 업데이트하세요

## 사용법

### 연결 테스트

설정이 올바른지 확인:

```bash
cd "/Users/jang/projects/utils/지라 스크래핑"
source venv/bin/activate  # 가상 환경 활성화
python -m src validate
```

### 데이터 수집

**⚠️ 중요: 모든 명령어는 반드시 가상 환경을 활성화한 상태에서 실행하세요!**

```bash
cd "/Users/jang/projects/utils/지라 스크래핑"
source venv/bin/activate  # 가상 환경 활성화 (필수!)
```

#### 전체 수집 (Jira + Confluence)

```bash
python -m src scrape -s all
# 또는
python -m src scrape  # source 기본값이 all
```

#### Jira만 수집

```bash
python -m src scrape -s jira
```

#### Confluence만 수집

```bash
python -m src scrape -s confluence
```

#### 특정 프로젝트만 수집

```bash
python -m src scrape -p PROJ1,PROJ2
```

#### 특정 기간만 수집

```bash
python -m src scrape -f 2024-01-01 -t 2024-12-31
```

#### 건수만 확인 (Dry Run)

```bash
python -m src scrape --dry-run
```

#### 중단된 수집 재개

```bash
python -m src scrape --resume
```

### 출력 파일

수집 완료 후 `output/` 디렉토리에 CSV 파일이 생성됩니다:

- `work_history_jira_issues_{timestamp}.csv` - Jira 이슈 목록
- `work_history_confluence_pages_{timestamp}.csv` - Confluence 페이지 목록
- `work_history_work_summary_{timestamp}.csv` - 월별/프로젝트별 통계

## CSV 컬럼 설명

### Jira CSV (30개 컬럼)

| 컬럼 | 설명 |
|------|------|
| issue_key | 이슈 키 (예: PROJ-123) |
| project_key | 프로젝트 키 |
| project_name | 프로젝트 이름 |
| issue_type | 이슈 유형 (Story, Bug 등) |
| summary | 이슈 제목 |
| description | 이슈 설명 |
| status | 현재 상태 |
| priority | 우선순위 |
| assignee | 담당자 |
| reporter | 보고자 |
| created_date | 생성일 |
| updated_date | 수정일 |
| resolved_date | 해결일 |
| epic_name | 에픽 이름 |
| sprint_name | 스프린트 이름 |
| comments_count | 전체 코멘트 수 |
| my_comments_count | 본인 코멘트 수 |
| ... | (총 30개) |

### Confluence CSV (17개 컬럼)

| 컬럼 | 설명 |
|------|------|
| page_id | 페이지 ID |
| space_key | 스페이스 키 |
| space_name | 스페이스 이름 |
| title | 페이지 제목 |
| content_plain | 본문 (텍스트) |
| author | 작성자 |
| created_date | 작성일 |
| last_modified_date | 최종 수정일 |
| version_count | 버전 수 |
| ... | (총 17개) |

## 문제 해결

### 인증 실패

```
AuthenticationError: Failed to authenticate with Jira API
```

**해결 방법:**
1. `.env` 파일의 이메일과 API 토큰 확인
2. API 토큰이 만료되지 않았는지 확인
3. `python -m src.main validate` 명령어로 연결 테스트

### Rate Limit 오류

```
RateLimitError: Rate limit exceeded
```

**해결 방법:**
1. `config/config.yaml`에서 `rate_limit_per_second` 값을 낮춤 (예: 2 또는 1)
2. 잠시 대기 후 `--resume` 옵션으로 재개

### 설정 오류

```
ConfigValidationError: Configuration validation failed
```

**해결 방법:**
1. `config/config.yaml` 파일의 YAML 문법 확인
2. 날짜 형식이 `YYYY-MM-DD`인지 확인
3. URL이 올바른지 확인 (trailing slash 없음)

## 로그 파일

실행 로그는 `logs/` 디렉토리에 저장됩니다:

- 파일명: `scraper_YYYYMMDD_HHMMSS.log`
- 상세한 디버그 정보 포함
- 문제 발생 시 로그 파일 확인

## 개발

### 테스트 실행

```bash
pytest
```

### 코드 포맷팅

```bash
black src/
```

### Linting

```bash
ruff check src/
```

## 라이선스

MIT License

## 기여

이슈 및 풀 리퀘스트는 환영합니다!
