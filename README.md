# LawQuery-law

법령 적재 파이프라인. law.go.kr OPEN API 로 법령을 받아 **조 단위 + 연계(rdb)·별표·참조·벌칙**까지
새 DB(`ldb_<코드>`)로 적재한다. 백엔드는 `?law=<코드>` → `ldb_<코드>` 자동 라우팅(코드 수정 0).

> **운용 모델**: 님이 *무엇을* 할지 지시 → **Claude Code 가 오케스트레이션**(소스 검색·명령 실행·의미 판단).
> 상세 절차·설계는 [CLAUDE.md](CLAUDE.md). 이 문서는 **지시·명령 치트시트**.

---

## ① Claude 에게 지시하는 법 (자연어 → Claude 가 실행)

| 이렇게 말하면 | Claude 가 하는 일 |
|---|---|
| **"○○법 추가해줘 (코드 X, N단)"** | MCP로 소스 검색 → `jobs/X/job.json` 작성 → `run X`(dry) 검토 → `run X --apply` → `verify X` → 무인용 rdb 등 판단보정 제안 |
| **"별표만 다시 가져와"** (참조/벌칙도) | `run X --only=annex --apply` (해당 테이블만, rdb 큐레이션 안전) |
| **"규정 개정됐어, 갱신해줘"** | `run X --apply --force` (전체 재생성 + **내 오버라이드 자동 재적용**) |
| **"내 수정 저장해줘"** | `python -m pipeline.overrides X` (= GUI '오버라이드 저장') |
| **"트리·연결 검증해줘"** | `python -m pipeline.verify X` (연결성·dangling) |
| **"운영에 배포해줘"** | `python -m common.replicate X` (개발 DB asis 정확복제) + 레지스트리 안내 |

> 판단이 필요한 곳은 **2군데뿐**(소스 식별·무인용 rdb 의미연결), 나머지는 명령. 그래서 위임이 안전.

## ② 직접 칠 때 — 명령 레퍼런스

```bash
# 신규 법 (예: 코드 g)
python -m pipeline.run g                 # dry-run: build→qa→rdb→annex→ref→penalty (적재 X)
python -m pipeline.run g --apply         # dev 적재 (최초). 이미 있으면 거부(수동편집 보호)
python -m pipeline.run g --apply --force # 규정 개정 — 전체 재생성 + 오버라이드 재적용
python -m pipeline.run g --only=annex --apply      # 일부만: 별표만 갱신(안전)
python -m pipeline.run g --only=annex,ref --apply  # 복수 단계
python -m pipeline.verify g              # 연결성·부가 무결성
python -m pipeline.overrides g           # 수동수정 → overrides.json 박제(capture)
python -m common.replicate g             # 개발 ldb_g → 운영 정확복제(SSH 터널)

# GUI 편집기 (사람용 — 수동 보정·검증·배포 버튼)
LawEditor.pyw   (더블클릭)   또는   python run.py gui
```

## ③ 오버라이드 워크플로 (수동수정이 규정 갱신에도 살아남음)

자동 산출물(`rdb/data/…json`) = 베이스, `overrides.json` = 내 델타. **적재 = 베이스 + 델타** (= git rebase).

```
편집:  GUI 편집기에서 rdb 연결·본문 등 수정  →  [오버라이드 저장] 버튼
         → 라이브 DB ⊖ 자동 = 델타(add/remove/modify, 전 테이블)가 jobs/<코드>/overrides.json 에 박제
갱신:  run <코드> --apply --force  →  자동 재생성 후 델타 자동 재적용 → 내 큐레이션 생존
배포:  common.replicate <코드>     →  운영 정확복제
```
- **반드시 GUI 편집기/capture 경유** — 안정 ID(A37/S17, id_annex…)라 델타가 갱신을 건너뛰어 유효.
- 갱신으로 가리키던 조가 사라지면 **스킵+경고**(= rebase 충돌). `overrides.json` 은 **git 추적**(큐레이션=소스).

## 설치

```bash
copy .env.example .env     # MYSQL_*(dev/prod)·SSH_*(운영 터널)·LAW_OC 채우기
pip install -r requirements.txt
```

## 구조 / 스키마

| 경로 | 역할 |
|---|---|
| `pipeline/` | API 파이프라인: build·qa·rdb·annex·ref·penalty·run·verify·overrides |
| `jobs/<코드>/job.json` | per-law **레시피**(소스ID·refers·umbrella) — git 추적 |
| `jobs/<코드>/overrides.json` | 수동 **큐레이션** 델타 — git 추적 (산출물 json은 ignore) |
| `fetcher/law_api.py` | law.go.kr OPEN API(법/시행령=구조화, 행정규칙=문자열) |
| `lawparse/` | splitter(조/항/호·개행)·ids(ID 규약) |
| `loader/loader.py` | CREATE DB → DDL → TRUNCATE+INSERT (recreate=전체 DROP) |
| `common/{db,schema_map,replicate}.py` | 연결·시트매핑·운영복제 |
| `exporter/db_export.py` | DB → 행 dict (capture·GUI 불러오기) |
| `gui/` · `LawEditor.pyw` | tkinter 편집기(수동 보정·검증·운영배포·오버라이드 저장) |
| `mcp/law-mcp/` | 법령 fetcher MCP (Claude 가 소스 검색·내용 판독) |

**11 테이블**: `meta` · `a/e/s/r`(본문) · `annex`(별표) · `ref`(참조) · `rdb`(연계 엣지 id_start→id_end) · `penalty*`(벌칙).
**ID 규약**: 법/시행령/감독규정/세칙 = `A1`·`E1`·`S1`·`R1`, 가지조문 `_2`, (항/호 분리 시 `_kh`). 별표 `id_annex`, `id_src`=붙는 노드.

> 노출: 적재 후 `ldb_auth.law_registry` 에 1행(GUI '법령 목록 관리') → `/api/law/list` 가 잡음.
> 레지스트리는 별도 DB라 `replicate` 에 안 딸려옴(운영 노출은 따로).

---

### 기타 (엑셀/txt 수동 경로 — 보조)

```bash
python run.py template -o template_law.xlsx       # 빈 템플릿
python run.py ingest --law c --excel data/foo.xlsx --apply --recreate   # 엑셀 적재
python run.py export --law j -o ldb_j.xlsx         # DB → 엑셀
```
