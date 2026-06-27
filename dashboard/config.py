"""허브 설정 — 경로 + 파사드가 감추는 외부 도구 레지스트리."""
import os
import sys

# LawQuery-law 루트 (dashboard/ 의 부모)
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
INTAKE_DIR = os.path.join(ROOT, "intake")
JOBS_DIR = os.path.join(ROOT, "jobs")
STATIC_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "static")

# c:\projects — 형제 워크트리(frc/sqlhandler)들이 여기 있다
PROJECTS_ROOT = os.path.dirname(ROOT)

# 현재 인터프리터(=동일 가상환경 유지). GUI 런치는 콘솔 없는 pythonw.
PYTHON = sys.executable
_pyw = os.path.join(os.path.dirname(PYTHON), "pythonw.exe")
PYTHONW = _pyw if os.path.exists(_pyw) else PYTHON

HOST = "127.0.0.1"
PORT = 4500

# ── 외부 도구(파사드가 단일 현관 뒤로 감추는 기존 진입점) ──────────────────
# kind: "gui" = 콘솔 없는 별창(tkinter), 허브는 런치만 함(추후 웹으로 흡수 가능)
EXTERNAL_TOOLS = [
    {
        "id": "law-editor",
        "name": "법령 편집기",
        "desc": "이미 적재된 ldb_<code> 를 레코드 단위로 손보는 기존 tkinter GUI.",
        "details": [
            "타깃(dev/prod)·법 DB 선택 → 불러오기 → 표에서 행 추가/수정/삭제(즉시 1레코드 반영)",
            "새 법(엑셀) 벌크 생성 · 검증 · 엑셀 내보내기 · 빈 템플릿",
            "rdb 위임연결 매핑 탭 · '오버라이드 저장'(수동 큐레이션 박제)",
            "'운영 배포' 버튼 = dev → 운영 정확복제",
            "※ Phase 2 에서 허브 웹페이지로 흡수 예정 → 그때 이 타일 제거",
        ],
        "cwd": ROOT,
        "cmd": ["legacy/LawEditor.pyw"],
        "kind": "gui",
    },
    {
        "id": "frc",
        "name": "FRC 크롤러",
        "desc": "금융규제 포털에서 유권해석·비조치의견서를 수집하는 크롤러.",
        "details": [
            "late(최신)·past(과거)·integ(통합) 3가지 수집 모드",
            "list → detail 크롤 → parser/combiner 로 구조화",
            "exporter 로 DB/파일 적재 (해석 DB ldb_i 계열)",
        ],
        "cwd": os.path.join(PROJECTS_ROOT, "LawQuery-frc"),
        "cmd": ["run.py"],
        "kind": "gui",
    },
    {
        "id": "sqlhandler",
        "name": "SQL 핸들러",
        "desc": "DB 가져오기/내보내기·정리 도구 (MySQL & SQLite).",
        "details": [
            "MySQL ↔ xlsx/pkl, SQLite ↔ xlsx/pkl 양방향 변환",
            "DB 연결 관리(공유 커넥션) · 콜레이션/통계 서비스",
            "Table Cleaner — 테이블 비우기/정리",
            "SQLite → base64/wasm 변환 유틸",
        ],
        "cwd": os.path.join(PROJECTS_ROOT, "LawQuery-sqlhandler"),
        "cmd": ["main.pyw"],
        "kind": "gui",
    },
]


def tool(tool_id: str):
    return next((t for t in EXTERNAL_TOOLS if t["id"] == tool_id), None)


def public_tools():
    """프론트 노출용 — 실행 경로(cwd/cmd)는 감추고 메타 + 가용여부만."""
    return [
        {
            "id": t["id"],
            "name": t["name"],
            "desc": t["desc"],
            "details": t.get("details", []),
            "kind": t["kind"],
            "available": os.path.isdir(t["cwd"]),
        }
        for t in EXTERNAL_TOOLS
    ]
