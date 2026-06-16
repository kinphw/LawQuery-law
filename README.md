# LawQuery-law

LawQuery 법령 적재 파이프라인. 엑셀(시트=테이블)로 파싱된 법령·연계매핑을
검증 후 새 법령 DB(`ldb_<코드>`)로 적재한다. (LawQuery-frc 의 자매 파이프라인)

## 워크플로

```
엑셀 채움 → dry-run(검증) → --apply(로컬 ldb_<x>) → 트리 렌더 확인 → --apply --target prod
```

## 설치

```bash
copy .env.example .env        # MYSQL_* 채우기 (dev=localhost, prod=192.168.0.7)
pip install -r requirements.txt
```

## 사용법

```bash
# 1) 빈 템플릿 생성 (시트=테이블, ldb_j 예시행 포함)
python run.py template -o template_law.xlsx

# 2) 검증만 (dry-run) — dangling 연계·중복 ID·누락을 적재 전에 잡음
python run.py ingest --law c --excel data/foo.xlsx

# 3) 실제 적재 (기본 dev=localhost). --recreate 면 ldb_c 를 DROP 후 재생성
python run.py ingest --law c --excel data/foo.xlsx --apply --recreate

# 4) 운영 적재
python run.py ingest --law c --excel data/foo.xlsx --apply --target prod --recreate

# 5) 기존 법 DB → 엑셀로 내보내기 (수정용)
python run.py export --law j -o ldb_j.xlsx

# 6) GUI (법 선택·표 편집·연계 편집·검증·저장 + 새 법 가져오기)
python run.py gui
```

### GUI

`python run.py gui` → 데스크톱 편집기(tkinter). 타깃(dev/prod)·법 DB 선택 → **불러오기** →
탭(a/e/s/r/annex/ref/rdb/meta/penalty)에서 행 추가·편집·삭제 → **검증** → **저장(DB)**.
새 법은 **새 법(엑셀)** 으로 가져와 편집 후 저장. 편집 엔진은 CLI와 동일(reader/validator/loader).

> 적재는 매번 TRUNCATE 후 재적재(idempotent). `--law` 코드가 곧 DB명(`ldb_<코드>`)이며
> 백엔드는 `?law=<코드>`로 자동 라우팅된다(코드 수정 불필요). 새 법 노출은 프론트 법 선택 UI만 추가.

## 구조

| 경로 | 역할 |
|---|---|
| `run.py` | CLI (template / ingest / export / gui) |
| `common/schema_map.py` | 시트↔테이블 매핑 **단일 출처** |
| `common/db.py` | MySQL 연결 (dev/prod) |
| `schema/ddl.sql` | `ldb_<x>` 표준 스키마 (11테이블) |
| `reader/excel_reader.py` | 엑셀 → 행 dict (NULL·숫자 보정) |
| `validator/validate.py` | dangling rdb·중복 ID·누락 검증 |
| `loader/loader.py` | CREATE DB → DDL → TRUNCATE+INSERT (트랜잭션) |
| `exporter/db_export.py` | 기존 법 DB → 행 dict / 엑셀 (GUI·export 공용) |
| `template/make_template.py` | 빈 엑셀 템플릿 + 예시행 |
| `gui/` | tkinter 편집기 (app / grid / services) |

## 적재 대상 스키마 (ldb_j 기준)

| 시트/테이블 | 역할 | 핵심 컬럼 |
|---|---|---|
| `meta` / db_meta | 법령명(단별) | origin(a/e/s/r), full_name, short_name |
| `a` / db_a | 법(Act) | seq, id_aa(조묶음), **id_a(노드ID)**, title_a, content_a |
| `e`·`s`·`r` / db_e·s·r | 시행령·감독규정·세칙 | seq, id_e/s/r, content_* |
| `annex` / db_annex | 별표(B단) | origin, id_annex, id_src(붙는노드) |
| `ref` / db_ref | 참조 | id_origin, ref_type, ref_target, ref_content |
| **`rdb` / rdb** | **연계 엣지** | **id_start → id_end** |
| `penalty*` / db_penalty* | 벌칙(선택) | — |

### ID 규약 (중요 — rdb가 이 ID를 참조)

- 법: `A1`, 항/호 분리 시 `A2_1h`. `id_aa`=조 묶음(`A2`), 장/절 제목행은 `id_a` 비움
- 시행령/감독규정/세칙: `E1`, `S1`, `R1` (가지조문 `_2` 등)
- 별표: db_annex 의 `id_annex`(B*), `id_src`=붙는 본문 노드
- **rdb**: 상위 노드 → 다음으로 *존재하는* 하위 노드로 직접 연결(중간단 없으면 건너뜀, 가상노드는 백엔드가 자동 생성)
