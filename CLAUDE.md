# CLAUDE.md — LawQuery-law

LawQuery 법령 적재 파이프라인 + GUI 편집기. 새 법령을 파싱·검증해 DB(`ldb_<코드>`)로 적재하고
GUI에서 레코드 단위로 편집한다. 입력 경로 2가지:
1. **API 파이프라인(권장)** — law.go.kr OPEN API 로 구조화 데이터 적재. → 아래 ★ 섹션
2. **txt/엑셀(수동)** — 본문 txt나 엑셀 파싱. GUI 편집·소량 보정용.

## 통합 원칙 (★ 핵심)
모든 입력 리더는 **동일한 `data` dict** 를 만든다 → validator/loader/editor/GUI 가 그대로 재사용.
```
data = { "meta":[...], "a":[...], "e":[...], "s":[...], "r":[...],
         "annex":[...], "ref":[...], "rdb":[...], "penalty*":[...] }
```
- `pipeline/build.py`      : API → data  (권장, `lawparse/*`+`fetcher/law_api.py`)
- `reader/excel_reader.py` : 엑셀 → data
- `reader/txt_reader.py`   : txt 본문 → data  (`lawparse/*` 가 분리·ID·rdb 담당)

## ★ 새 법령 추가 — API 파이프라인 (권장 경로)

law.go.kr OPEN API 로 조/항/호 **구조화 데이터**를 받아 결정론적으로 적재(txt 파싱보다 정확).
재사용 모듈 `pipeline/` + per-law 레시피 `jobs/<코드>/job.json`. 첫 실전: `ldb_g`(금융위설치법 4단).

### 데이터 출처 (중요)
- 파이프라인은 `fetcher/law_api.py`(API JSON **직결**) 사용. 법/시행령=구조화 조/항/호, 감독규정/세칙=문자열→`lawparse/splitter`.
- **MCP `mcp__law__*` 는 포맷된 텍스트 반환** → 기계 재파싱엔 부적합. MCP는 Claude가 **소스 식별(검색)·내용 읽고 의미 판단**할 때 쓴다. 적재 데이터는 law_api.py.
- `.env` 의 `LAW_OC` 필요.

### 절차 (Claude 수행)
1. **소스 식별**: `mcp__law__search_law`(법·시행령) / `mcp__law__search_admin_rule`(감독규정·세칙) → 법령ID·일련번호.
2. **레시피**: `jobs/<코드>/job.json` 작성(스키마 아래).
3. **dry-run**: `python -m pipeline.run <코드>` → build→qa→rdb→annex→ref→penalty(적재 안 함). `jobs/<코드>/*.json` 산출물 검토.
4. **적재(dev)**: `python -m pipeline.run <코드> --apply` → `python -m pipeline.verify <코드>`(연결성·부가테이블 dangling 0 확인).
5. **검토·보정**: `LawEditor.pyw` GUI로 트리·별표·참조·벌칙 확인 → 의미적 부분만 수동 보정(아래).
6. **운영 적재**: `python -m pipeline.run <코드> --apply --prod`.
7. **노출**: `ldb_auth.law_registry` 에 `(code, sort_order, kind)` 1행(enabled=1) — GUI "법령 목록 관리" 또는 `LawQuery/db/law_registry.sql`. → `/api/law/list` 가 잡아 `?law=<코드>` 렌더(백엔드 코드 수정 0).

### job.json 스키마
```jsonc
{
  "code": "g",
  "sources": {
    "a": { "kind": "law",    "id": "000552",        "short": "법률" },
    "e": { "kind": "law",    "id": "003072",        "short": "시행령",   "parent": "a",
           "refers": ["「금융위원회의 설치 등에 관한 법률」", "법"] },
    "s": { "kind": "admrul", "id": "2100000272518", "short": "감독규정", "parent": "a",
           "refers": ["금융위설치법", "「금융위원회의 설치 등에 관한 법률」"] },
    "r": { "kind": "admrul", "id": "2200000106255", "short": "시행세칙", "parent": "s",
           "refers": ["규정", "「금융기관검사및제재에관한규정」"] }
  },
  "umbrella": { "e": "A27", "s": "A37", "r": "S8" }
}
```
- `sources.<tier>`: `kind`(law=법/시행령, admrul=행정규칙) + `id`(법령ID|일련번호) + `short`(db_meta 표시) + `parent`(인용 상위단) + `refers`(하위가 상위를 부르는 별칭 — rdb/ref 정규식을 여기서 자동생성).
- `umbrella.<tier>`: 무인용 조의 블록 시드 앵커(문서순 직전 정밀앵커가 없을 때 매달 상위조). 산출물(`data.json`/`rdb.json`/…)은 .gitignore, `job.json`만 추적.

### 단계별 — 결정론 vs 판단
| 단계 | 산출 | 성격 |
|---|---|---|
| build | data.json (조 단위 노드+ID+meta) | 결정론 |
| qa | 원문 조헤더 ↔ 데이터 대조(누락·흡수 게이트) | 결정론 |
| rdb | 정밀(특정조 명시인용)+엄브렐러(무인용=직전앵커 상속) | 정밀=결정론 / 엄브렐러=근사 |
| annex | 별표→조("(제N조 관련)" 또는 본문 "별표 N") | 결정론 |
| ref | 외부법(text)+family 내부(db_*) | 결정론 |
| penalty | 벌칙/과태료 조 → "…위반" 대상 조 추출 | 본문형=결정론 |
| load / verify | ldb_<코드> 적재 · 무결성 | 결정론 |

### 판단(사람/Claude 보정) 지점 — 본질적 비결정론
정보가 본문에 없어 규칙으로 100%가 안 되는 **3곳만** 판단계층, 나머지는 `run --apply` 한 줄로 재현:
- **rdb 엄브렐러**: 무인용 조는 위임근거가 본문에 없어 근사연결 → GUI에서 부모 조정.
- **ref 외부전문**: 외부법 조 전문 임베드(ldb_j 방식)는 MCP fetch 필요 — 기본은 인용 헤더만. 필요시 enrich.
- **penalty 과태료 별표표**: 과태료 금액이 시행령 별표(반정형 표)로 정의되면 표 파싱 필요(전자금융 케이스). g처럼 본문형이면 자동.

### 수동 큐레이션 오버라이드 (전 테이블, = Kustomize base+overlay / git rebase)
사람 편집(rdb 연결·본문 수정 등)을 **규정 갱신과 무관하게 영속**시키는 레이어. `pipeline/overrides.py`:
- 자동 산출물(data/rdb/annex/ref/penalty.json) = 결정론 베이스, `overrides.json` = 사람 델타(**테이블별** add/remove/modify). **적재 = 베이스 + 델타**(전 테이블).
- **테이블 식별**: 키드(meta/a/e/s/r/annex)=키 컬럼으로 add/remove/**modify**(내용수정 보존). 키리스(rdb/ref/penalty\*)=행 전체(id 제외)로 add/remove.
- **capture**: GUI '오버라이드 저장'(또는 `python -m pipeline.overrides <code>`) → `db_export.read_law`(라이브) ⊖ 베이스 → overrides.json 박제.
- **재적용**: `run --apply`(특히 `--force`) 적재 시 `apply_overrides`가 전 테이블 자동 재적용 → 큐레이션 생존. **안정 ID(A37/S17, id_annex…)가 가능케 함**(순번ID면 불가).
- **충돌**: rdb add 엔드포인트 등이 갱신으로 사라지면 스킵+경고(= rebase 충돌). overrides.json 은 **git 추적**(큐레이션=소스). 편집은 GUI 편집기/capture 경유(Workbench 직접수정도 잡히나 기록 누락 위험).
- 검증: g 의 rdb 3건 + 본문수정(S2 content) 1건이 `--force` 후 모두 생존 확인.

### 부분 실행 (`--only`) — 일부 단계·테이블만 갱신
- `run <code> --only=annex --apply` → annex 단계만 재생성 + **db_annex 만** TRUNCATE+INSERT(recreate 안 함). **rdb 큐레이션 등 다른 테이블 안 건드림** → 가드 불필요·안전.
- 단계: `build·rdb·annex·ref·penalty` (콤마 복수: `--only=annex,ref`). `data.json`(노드 베이스)이 먼저 있어야 함(없으면 전체 run 선행).
- 용도: "감독규정에 별표 추가됨 → `--only=annex`로 별표만 새로고침" 처럼 **파생 테이블만** 갱신.
- vs 전체 `--force`: **규정 개정**(조번호 이동 등 구조 변화)은 전체 `--apply --force`가 맞음(rdb 재평가 + overrides 재적용). `--only`는 파생 테이블 새로고침용. 부분은 recreate=False라 가드·DROP 없음.

### 조 단위 기본 / splitter 실측 교정
- 현재 파이프라인은 **조 단위**(항/호는 조 본문에 병합, `items=[]`). 항/호 분리는 향후 옵션(`ids.py` `_kh` 지원). 미세조정은 GUI.
- 행정규칙 splitter 교정 완료: 가지조문 `제N조의M`(조 뒤 가지), 삭제조 `제N조 삭 제 <날짜>`(삭/제 공백). QA가 원문 조헤더와 대조해 누락·흡수 즉시 검출.
- **행정규칙 본문 개행**: admrul API는 조문을 **조 단위 문자열**로 주며 항/호/목이 한 줄에 붙어 옴(법/시행령은 구조화라 무관). `splitter.format_admin_body()`가 항(①)·호(N.)·목(가.) 앞에 개행 삽입. 목은 가~하→거~허→고~호 순환 시퀀스로만 분리(문장끝 "~다." 오삽입 방지), `<개정 …>` 날짜 보호. `build._admin_articles`에서 적용.
- **별표 URL**: PDF다운로드 링크(flDownload) 아님 → 법령정보센터 **뷰어 링크**(인라인 표시): 법령 `/법령별표서식/(법령명,별표X)`, 행정규칙 `/행정규칙별표서식/(행정규칙명,발령번호,별표X)`. 발령번호=`행정규칙기본정보.발령번호`(이름+별표번호로 해석되므로 placeholder여도 동작).

## 운영 배포 (개발 → 운영 **정확복제**)

> 파이프라인 재실행이 아니라, **세션·GUI로 다듬은 개발 ldb_<code> asis 를 운영으로 그대로 복제**한다.
> (운영에서 `run --prod` 하면 API 재호출·수동보정 유실 → 쓰지 말 것. 운영 이관은 복제로.)
>
> **수동편집 보호 가드**: `run --apply` 는 DROP+재적재라 GUI 수정(rdb 보정·항/호)을 덮어쓴다.
> 그래서 `ldb_<code>` 가 이미 존재하면 **기본 거부** → 규정 개정 등 의도적 재생성만 `--apply --force`.
> 신규 법(미존재)은 그대로 진행. (파이프라인 자체는 유지 — 갱신은 가능, 사고성 덮어쓰기만 차단)

- **방식**: `mysqldump(dev) | mysql(prod)` 파이프 — 스키마·데이터·콜레이션(uca1400)·PK·surrogate `_pk` 전부 그대로(`--add-drop-database`로 운영 DROP+CREATE).
- **전송**: 운영 MySQL은 localhost 바인딩(3306 직접 미도달) → **SSH 터널**(paramiko/sshtunnel) 경유. `common/replicate.py` 가 `.env` 의 `SSH_HOST/USER/PASSWORD` 로 터널을 열고 파이프.
- **진입점**:
  - GUI: 편집기 툴바 **'운영 배포'** 버튼 → 선택 DB의 개발본을 운영으로 복제(확인창 + 스레드 실행).
  - CLI: `python -m common.replicate <code>`
- **.env**: `MYSQL_*`(dev) + `MYSQL_*_PROD`(운영 MySQL 자격) + `SSH_*`(운영 SSH). `pip install paramiko sshtunnel` 필요.
- **레지스트리는 별도**: `ldb_auth.law_registry` 노출 행은 이 복제에 안 딸려옴 → GUI '법령 목록 관리'(target=prod)로 따로 추가.

> 운영 3306이 직접 닿는 환경이면 `SSH_HOST` 비우고 `MYSQL_HOST_PROD` 직접 연결도 됨(터널 생략).

## txt 입력 규약
- 폴더 `txt_in/` (또는 `txt_in/<코드>/`) 에 단별 txt: `a.txt`(법) `e.txt`(시행령) `s.txt`(감독규정) `r.txt`(시행세칙). **있는 단만.**
- 각 txt 첫머리 법령정보센터 헤더(법령명·[시행…]·[법률 제…호…]) → `db_meta.full_name`.
- 인코딩 자동(utf-8 / utf-8-sig / cp949). 본문 txt는 git 제외(`txt_in/**/*.txt`).

## ID 규약 (rdb 가 이 ID 참조 — 절대기준, ldb_j 실측)
| 단위 | id | 비고 |
|---|---|---|
| 장/절 | (id 없음) | **db_a 만** title 행. e/s/r 은 장/절 미저장 |
| 제N조 | `{T}N` (A2,E2,S2,R2) | T = A/E/S/R |
| 제N조의M (가지조문) | `{T}N_M` (A6_2) | **h 없음** |
| 제N조 k번째 항/호 | `{T}N_kh` (A2_3h) | **h 있음**, k=순번 |
| 가지조문의 항/호 | `{T}N_M_kh` | |
- `id_aa`(db_a 전용) = 그 조의 stem id(A2). 항/호 행도 같은 id_aa·title_a 공유.
- 항/호 분리: a·e·s 는 분리, r 은 조+가지조문만(ldb_j curation). 신규 법은 항/호 있으면 분리.

## 파싱 (`lawparse/`, LawParser(VBA) 포팅)
- `splitter.py`  : 조간분리(`^제N조(...)`) + 조내분리(항 `①~⑮` / 호 `^\d+(의\d+)*\.` / 목 `가.~하.`은 호 안에 유지)
- `ids.py`       : 분리 유닛 → 단별 행(+ID, seq)
- `meta_parse.py`: 헤더 → db_meta
- `rdb_extract.py`(Phase 2): 본문 인용("법/영/규정 제N조…") → rdb 후보 엣지(위임·따라 시그널)

## 실행 (단일 진입점: `LawEditor.pyw`)
- GUI: `LawEditor.pyw` 더블클릭 (인자 없음 → GUI, 콘솔 없음)
- CLI: `python LawEditor.pyw {template|ingest|export|gui}` (예정: `ingest-txt`, GUI "새 법(txt)")
- `run.py` 는 CLI 구현 모듈 — `LawEditor.pyw` 가 인자 있으면 위임. (`python run.py …` 도 back-compat 동작)

## DB 규약
- `--law <code>` = DB명 `ldb_<code>`. 백엔드가 `?law=<code>` → `ldb_<code>` 자동 라우팅(코드 수정 0).
- collation `utf8mb4_uca1400_ai_ci`. PK 없던 rdb/ref/penalty 는 편집 시 surrogate `_pk` 자동 부여.
- 별표(b)는 본문 txt 밖 → v1 범위 외(db_annex 별도).

## 환경
- 로컬 MariaDB(dev=localhost root/genius), 운영 192.168.0.7. `.env`(`common/db.py` 가 프로젝트 루트에서 로드).
- Windows 콘솔(cp949): `run.py` 가 stdout UTF-8 강제. `.pyw`는 콘솔 없음.
