# dashboard/ — LawQuery 허브 (단일 현관 / 파사드)

산발돼 있던 진입점(NewLaw 인테이크 폼, LawEditor, FRC 크롤러, SQL 핸들러)을
**하나의 로컬 웹 대시보드**로 모은다. 일부는 웹페이지로 흡수하고, 아직 흡수 안 한
기존 GUI 는 "도구" 탭에서 런치(파사드)한다.

```
Dashboard.pyw  (더블클릭)
   └─ uvicorn 기동 → http://127.0.0.1:4500  (브라우저 자동 오픈)
        ├─ 홈           구축된 법 / 대기 현황
        ├─ 법령 인테이크  intake/<code>.json CRUD  (NewLaw 폼 흡수)  → "Claude 핸드오프" 복사
        ├─ 파이프라인    run(dry/apply/force/only) · verify · 운영복제 — 실시간 SSE 로그
        └─ 도구          frc · sqlhandler · (기존)법령편집기 런치
```

## 실행
```bash
pip install fastapi uvicorn        # 최초 1회 (requirements.txt 에 포함)
# 일반 사용:
Dashboard.pyw  더블클릭
# 콘솔 디버그(로그 보임):
python -m dashboard
```
포트 4500. 종료는 우하단 **'허브 종료'** 버튼.

## 구조
```
Dashboard.pyw            런처(uvicorn + 브라우저)
dashboard/
  server.py              FastAPI 앱(라우터 등록 + 정적 SPA + /api/shutdown)
  config.py              경로 + 외부 도구 레지스트리(EXTERNAL_TOOLS)
  intake_store.py        intake/<code>.json I/O (NewLaw 와 공유하는 데이터층)
  proc.py                서브프로세스: SSE 로그 스트림 / 분리 런치
  routers/intake.py      /api/intake/*   (CRUD)
  routers/pipeline.py    /api/pipeline/* (run·verify·replicate, SSE)
  routers/tools.py       /api/tools/*    (외부 GUI 런치)
  static/                index.html · style.css · app.js (빌드 불필요 바닐라 SPA)
```

## 설계 메모
- **로직 재사용**: 무거운 로직(파싱·적재·복제)은 `pipeline.*` / `common.replicate` 그대로,
  허브는 그 위 얇은 웹층. 파이프라인은 CLI 를 서브프로세스로 호출해 로그를 SSE 로 흘린다.
- **운영 적재 = 복제**: `run --prod` 가 아니라 `common.replicate` (CLAUDE.md 원칙). 강한 확인창.
- **새 도구 추가**: `config.EXTERNAL_TOOLS` 에 한 줄. 프론트 코드 수정 0.
- **후속(Phase 2)**: LawEditor 의 레코드 그리드·rdb 매핑·레지스트리 관리를 웹페이지로 흡수
  (`LiveEditor` 를 `/api/editor/*` 로 노출) → "도구"의 법령편집기 런치 타일 제거.
```
```
