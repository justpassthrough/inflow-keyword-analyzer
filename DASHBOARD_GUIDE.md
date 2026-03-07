# 유입 키워드 분석기 — 대시보드 기술 가이드

> 작성일: 2026-03-07
> 이 문서를 Claude Code에게 주면 대시보드를 디버깅/수정할 수 있습니다.

---

## 1. 프로젝트 개요

네이버 블로그 유입분석 엑셀에서 **"검색 수요는 있는데 전용 글이 없는 키워드"**를 자동으로 찾아내는 도구.

- **레포**: https://github.com/justpassthrough/inflow-keyword-analyzer
- **대시보드**: https://justpassthrough.github.io/inflow-keyword-analyzer/
- **로컬 클론 위치**: `C:\Users\Andy\inflow-keyword-analyzer\`

---

## 2. 파일 구조

```
inflow-keyword-analyzer/
├── docs/
│   └── index.html              ← 대시보드 (GitHub Pages, 단일 HTML)
├── scripts/
│   └── update_posts.py         ← RSS + 모바일 스크래핑으로 글 목록 수집
├── data/
│   ├── config.json             ← 설정 (blog_id, 임계값, 검색 소스 목록)
│   ├── inflow_history.json     ← 유입 키워드 히스토리 (GitHub API로 자동 저장)
│   └── my_posts.json           ← 블로그 글 목록 (Actions + 스크래핑으로 자동 생성)
├── .github/workflows/
│   └── daily_update.yml        ← 매일 KST 08:00 글 목록 자동 갱신
├── requirements.txt
└── SPEC_유입키워드분석기_v1.md  ← 원본 설계 스펙
```

---

## 3. 기술 스택

| 구성요소 | 기술 | 비고 |
|---|---|---|
| 대시보드 | HTML + CSS + Vanilla JS | 단일 파일, 프레임워크 없음 |
| 엑셀 파싱 | SheetJS (xlsx.js) | CDN 로드 |
| GitHub 연동 | GitHub REST API + raw.githubusercontent.com | fetch() + PAT |
| 글 목록 수집 | Python (requests + BeautifulSoup + feedparser) | GitHub Actions에서 실행 |
| 배포 | GitHub Pages | docs/index.html |
| 자동화 | GitHub Actions | daily_update.yml, 매일 KST 08:00 |

---

## 4. 데이터 흐름

```
[사용자]
  │ 네이버 블로그 관리자 → 유입분석 → 일간 → 엑셀 다운로드
  │
  ▼
[대시보드 (index.html)]
  │ 1. SheetJS로 엑셀 파싱 → 날짜 + 키워드 + 비율 추출
  │ 2. inflowHistory에 머지 (같은 날짜는 덮어쓰기)
  │ 3. GitHub API로 inflow_history.json 저장 (PUT, sha 필요)
  │ 4. 키워드 정규화 → 그룹핑
  │ 5. 연속 등장 감지
  │ 6. my_posts.json과 매칭 → 갭/부분커버/완전커버 분류
  │ 7. 우선순위 점수 계산
  │ 8. 결과 렌더링
  │
  ▼
[GitHub]
  ├── data/inflow_history.json  ← 대시보드가 읽고 씀 (GitHub API)
  └── data/my_posts.json        ← Actions가 매일 갱신, 대시보드가 읽기만

[GitHub Actions — daily_update.yml]
  │ 매일 KST 08:00 실행
  │ scripts/update_posts.py 실행
  │ RSS 파싱 → 모바일 스크래핑 → my_posts.json 업데이트 → 커밋+푸시
```

---

## 5. 핵심 알고리즘 상세

### 5-1. 엑셀 파싱 (parseExcel 함수)

**네이버 유입분석 엑셀 구조:**
- Row 4 (index 3): 날짜 추출 — `"2026.03.06. 일간"` → `"2026-03-06"`
- Row 5 (index 4): `"전체"` vs `"검색 유입"` 분기
- Row 8 (index 7): 헤더
- Row 9+ (index 8+): 데이터

**"전체" 선택 시:**
- 컬럼 A: 유입경로 (None이면 이전 경로 계속)
- 컬럼 C: 상세유입경로 (= 키워드)
- 컬럼 D: 비율

**"검색 유입" 선택 시:**
- 컬럼 A: 키워드
- 컬럼 C: 유입경로
- 컬럼 D: 비율

**필터링:**
- 검색 관련 유입경로만 수집: `SEARCH_SOURCES` 배열에 정의
- URL 형태 (`https://`) 제외
- "기타" 제외
- 비율 0 이하 제외

### 5-2. 키워드 정규화 + 그룹핑 (groupKeywords 함수)

1. **정규화**: 공백 제거 + 소문자 변환
2. **포함 관계 그룹핑** (Union-Find):
   - 짧은 쪽 >= 4글자
   - 길이 차이 <= 5
   - 긴 쪽이 짧은 쪽을 포함
3. **편집거리 그룹핑**: Levenshtein 거리 <= 2 → 같은 그룹 (오타 보정)
4. **대표 키워드**: 그룹 내 가장 높은 비율을 가진 원본 형태

**주의사항:**
- 이전에 포함 관계 체크가 너무 과도하여 "마운자로"가 모든 변형을 흡수하는 버그가 있었음
- 현재는 짧은 쪽 4글자 이상 + 길이 차이 5 이하 조건으로 제한

### 5-3. 연속 등장 감지 (calcConsecutive 함수)

- 날짜를 역순 정렬 후 연속 일수 카운트
- 하루라도 빠지면 연속 리셋
- 연속 기간의 평균 비율 계산

### 5-4. 글 매칭 (matchKeywordToPosts 함수)

**매칭 우선순위:**
1. **수동 매핑** (manualMappings) — localStorage에 저장, 최우선
2. **제목 60%+ 매칭** → "완전 커버"
3. **본문 100% + 제목 1개+ 매칭** → "완전 커버" 승격
4. **본문 40%+ 매칭** → "부분 커버"
5. **그 외** → "갭 키워드"

**단어 매칭 방식 (wordSimilar 함수):**
- 정확히 같음
- 포함 관계 (`includes`)
- 공통 접두사 2자 이상 & 60%+ 일치 (예: "경구약" ↔ "경구형")

**붙어있는 키워드 처리 (splitBlob 함수):**
- 6글자+ 단일 단어 → 글 목록의 어휘(vocab)로 분리 시도
- 예: "순수알부민함량비교" → "알부민" + "함량" + "비교" 발견
- vocab은 my_posts.json의 제목 + body_keywords에서 구축

**핵심 단어 추출 (extractCoreWords 함수):**
- 한글/영문/숫자만 남기고 공백으로 분리
- 조사 제거: 은/는/이/가/을/를/의/에/에서/으로/과/와/도/만/하고/하면/하는
- 1글자 이하 제거

### 5-5. 우선순위 점수

```
Priority Score = 연속등장일수 × 평균유입비율(%) × 갭배수

갭배수:
  - 전용 글 없음 = ×3
  - 부분 커버 = ×1.5
  - 완전 커버 = ×0.3
```

### 5-6. 분류 기준

| 분류 | 조건 |
|---|---|
| 즉시 작성 | 5일+ 연속 AND 커버되지 않음 |
| 작성 고려 | 3~4일 연속 AND 커버되지 않음 |
| 모니터링 | 2일 연속 AND 커버되지 않음 |
| 이미 커버됨 | matchStatus === 'covered' |
| 표시 안 함 | 1일만 등장 (노이즈) |

---

## 6. GitHub API 연동

### 데이터 로드 (loadFromGitHub)
- **히스토리 sha**: `GET /repos/{owner}/{repo}/contents/data/inflow_history.json` (Contents API)
- **히스토리 데이터**: `https://raw.githubusercontent.com/{owner}/{repo}/main/data/inflow_history.json` (raw, base64 디코딩 문제 회피)
- **글 목록**: 동일하게 raw URL로 로드

**base64 디코딩 대신 raw URL을 쓰는 이유:**
- GitHub Contents API는 파일을 base64로 반환
- 한글 JSON을 `atob()` → `decodeURIComponent(escape())` 하면 깨지는 경우 있음
- raw.githubusercontent.com은 UTF-8 JSON을 직접 반환하므로 안전

### 데이터 저장 (ghPut)
- `PUT /repos/{owner}/{repo}/contents/{path}`
- sha가 없으면 먼저 GET으로 현재 sha를 가져옴
- content는 `btoa(unescape(encodeURIComponent(JSON.stringify(...))))`로 인코딩

### PAT 관리
- localStorage `github_pat` 키에 저장
- Classic PAT 사용 (Fine-grained는 레포 권한 설정 필요)
- 필요 scope: `repo`

---

## 7. 글 목록 수집 (update_posts.py)

### 동작 방식
1. RSS 피드 파싱: `https://rss.blog.naver.com/biopharmblog.xml`
2. 기존 `my_posts.json` 로드
3. URL 기준 중복 체크 → 새 글만 추가
4. 각 글의 모바일 URL로 스크래핑 시도 (2초 딜레이)
5. 본문에서 핵심 키워드 추출 → `body_keywords`
6. 스크래핑 실패 시 RSS 요약으로 폴백

### 모바일 스크래핑
- URL 변환: `blog.naver.com` → `m.blog.naver.com`
- User-Agent: 모바일 Safari
- 본문 영역: `.se-main-container` 또는 `#postViewArea`

### body_keywords 추출
- 한글 2글자+ / 영문숫자 2글자+ 추출
- 조사 제거
- 중복 제거, 최대 50개

### Windows 인코딩 주의
- `sys.stdout` UTF-8 강제 설정 (cp949 에러 방지)

---

## 8. 저장소 위치 정리

| 데이터 | 저장 위치 | 비고 |
|---|---|---|
| inflow_history.json | GitHub repo (API로 읽기/쓰기) | 대시보드에서 자동 관리 |
| my_posts.json | GitHub repo (Actions가 갱신) | 대시보드는 읽기만 |
| GitHub PAT | 브라우저 localStorage | `github_pat` 키 |
| 수동 매핑 | 브라우저 localStorage | `manual_mappings` 키, JSON |
| config.json | GitHub repo | 현재 대시보드에서 직접 사용 안 함 (하드코딩) |

---

## 9. 알려진 한계 및 해결된 이슈

### 해결된 이슈
1. **base64 한글 디코딩 실패** → raw.githubusercontent.com으로 변경
2. **GitHub PUT 404** → sha 자동 조회 추가, Classic PAT 필요
3. **키워드 과도 그룹핑** → 포함 관계 조건 강화 (짧은 쪽 4자+, 길이 차이 5 이하)
4. **매칭 우선순위** → covered가 항상 partial보다 우선, 본문 100%+제목1+ → 커버 승격
5. **붙어있는 키워드 오매칭** → 8자+ 긴 단어에서 부분 포함 비활성화 + vocab 기반 분리
6. **유사어 미매칭** → 공통 접두사 60%+ 기반 fuzzy matching

### 알려진 한계
1. **의미 기반 매칭 불가**: "경구약" = "먹는"은 알 수 없음 (해결: 수동 매핑으로 보완)
2. **붙어있는 키워드 분리**: vocab에 없는 단어는 분리 못 함
3. **RSS 제한**: 네이버 RSS는 최근 글만 제공 (전체 글 목록 아님)
4. **스크래핑 차단**: 네이버가 차단하면 RSS 요약만 사용 (body_keywords 정확도 하락)
5. **config.json 미사용**: 현재 설정값이 index.html에 하드코딩됨

---

## 10. 디버깅 가이드

### 엑셀 파싱 안 될 때
1. 브라우저 F12 → Console 확인
2. 엑셀 파일을 Python openpyxl로 열어서 Row 4~9 구조 확인
3. `parseExcel` 함수의 Row 인덱스가 실제 구조와 맞는지 확인

### GitHub 저장 실패
1. Console에서 `GitHub PUT failed: {status} {error}` 확인
2. 404 → PAT 권한 또는 sha 문제. Classic PAT인지 확인
3. 409 → sha 충돌. 페이지 새로고침 후 재시도
4. 422 → content 인코딩 문제

### 키워드 매칭 디버깅
1. `matchKeywordToPosts` 함수에 console.log 추가
2. 확인할 것: `kwWords`, `titleWords`, `bodyKw`, `titleMatches`, `titleRatio`, `allRatio`
3. `buildVocab` → `splitBlob` 순서로 붙어있는 키워드 분리 과정 확인

### 글 목록 로드 실패
1. Console에서 `Posts loaded: N posts` 확인
2. 안 뜨면 raw URL 직접 접속해서 JSON 확인
3. `my_posts.json`이 없으면 `python scripts/update_posts.py` 로컬 실행

### GitHub Actions 실패
1. GitHub repo → Actions 탭에서 로그 확인
2. 보통 원인: pip 설치 실패, 스크래핑 차단, git push 권한

---

## 11. 주요 함수 위치 (index.html 내)

| 함수 | 역할 |
|---|---|
| `parseExcel(rows)` | 엑셀 행 배열 → {date, keywords[]} |
| `groupKeywords(allKeywordsByDate)` | 정규화 + Union-Find 그룹핑 |
| `calcConsecutive(dateRatios)` | 연속 등장일수 + 평균비율 |
| `buildVocab(posts)` | 글 목록에서 어휘 사전 구축 |
| `splitBlob(blob, vocab)` | 붙어있는 키워드 분리 |
| `wordSimilar(w, tw)` | 유사 단어 판정 (포함/접두사) |
| `matchKeywordToPosts(keyword, posts)` | 키워드-글 매칭 (수동>제목>본문) |
| `analyze()` | 전체 분석 파이프라인 |
| `ghFetch(path)` / `ghFetchRaw(path)` | GitHub에서 데이터 로드 |
| `ghPut(path, content, sha)` | GitHub에 데이터 저장 |
| `loadFromGitHub()` / `saveToGitHub()` | 초기 로드 / 엑셀 업로드 후 저장 |
| `renderAll()` | 전체 UI 렌더링 |
| `renderCard(item)` | 키워드 카드 HTML 생성 |
| `showMapModal(keyword)` / `saveMapping()` | 수동 매핑 UI |
