"""인테이크 큐 I/O (intake/<code>.json) — 허브 웹과 NewLaw GUI 가 공유하는 데이터층.

사람이 *아는 것*(약자·단수·명칭·지시)만 담는 요청 파일을 읽고 쓴다.
job.json 의 소스 식별값(법령ID/일련번호)은 Claude 가 채우므로 여기엔 없다.
"""
import json
import os

from . import config

# 단(tier) 정의: 코드 → (한글명, 종류 힌트)
TIERS = [
    ("a", "법 (A)", "law"),
    ("e", "시행령 (E)", "law"),
    ("s", "감독규정 (S)", "admrul"),
    ("r", "시행세칙 (R)", "admrul"),
]


def intake_path(code: str) -> str:
    return os.path.join(config.INTAKE_DIR, f"{code}.json")


def save_intake(data: dict) -> str:
    os.makedirs(config.INTAKE_DIR, exist_ok=True)
    path = intake_path(data["code"])
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    return path


def load_intake(code: str):
    path = intake_path(code)
    if not os.path.exists(path):
        return None
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def load_job(code: str):
    """jobs/<code>/job.json — 이미 구축된 법의 레시피(제목·소스 식별값)."""
    jp = os.path.join(config.JOBS_DIR, code, "job.json")
    if not os.path.exists(jp):
        return None
    with open(jp, encoding="utf-8") as f:
        return json.load(f)


def delete_intake(code: str) -> bool:
    path = intake_path(code)
    if os.path.exists(path):
        os.remove(path)
        return True
    return False


def list_built() -> list:
    """jobs/<code>/job.json 스캔 → 이미 구축된 법."""
    out = []
    if os.path.isdir(config.JOBS_DIR):
        for code in sorted(os.listdir(config.JOBS_DIR)):
            jp = os.path.join(config.JOBS_DIR, code, "job.json")
            if not os.path.exists(jp):
                continue
            try:
                with open(jp, encoding="utf-8") as f:
                    j = json.load(f)
                out.append({"code": j.get("code", code),
                            "title": j.get("title", ""),
                            "status": "구축됨"})
            except Exception:
                out.append({"code": code, "title": "(읽기 실패)", "status": "구축됨"})
    return out


def list_intakes() -> list:
    """intake/<code>.json 스캔 → 인테이크 요청."""
    out = []
    if os.path.isdir(config.INTAKE_DIR):
        for fn in sorted(os.listdir(config.INTAKE_DIR)):
            if not fn.endswith(".json"):
                continue
            try:
                with open(os.path.join(config.INTAKE_DIR, fn), encoding="utf-8") as f:
                    out.append(json.load(f))
            except Exception:
                pass
    return out


def overview() -> list:
    """구축된 법 + 인테이크 대기 합본(약자 기준)."""
    built = {b["code"]: b for b in list_built()}
    intakes = {d.get("code"): d for d in list_intakes()}
    rows = []
    seen = set()
    for code, b in built.items():
        # 구축됐고 인테이크 파일도 있으면 명칭 보강
        d = intakes.get(code)
        if not b.get("title") and d:
            b = {**b, "title": d.get("names", {}).get("a") or ""}
        rows.append(b)
        seen.add(code)
    for code, d in intakes.items():
        if code in seen:
            continue
        title = d.get("names", {}).get("a") or "(미정)"
        rows.append({"code": code, "title": title, "status": "인테이크 대기"})
    rows.sort(key=lambda r: str(r["code"]))
    return rows
