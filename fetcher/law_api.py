"""
국가법령정보센터 OPEN API 클라이언트.
sentinel/law-mcp 의 LawApiClient.ts 를 Python 으로 포팅.

- 법·시행령: lawService.do?target=eflaw → 조/항/호/목 구조화
- 감독규정·세칙(행정규칙): lawService.do?target=admrul → 조문내용(문자열, 항/호는 splitter로)
- 체계도(상하위법): lawService.do?target=lsStmd
- .env 의 LAW_OC 필요. docs/law-api.md 참조.
"""
import os
import time
from pathlib import Path

import requests
from dotenv import load_dotenv

load_dotenv(Path(__file__).resolve().parent.parent / ".env")

BASE = "http://www.law.go.kr/DRF"
_RETRYABLE = {429, 500, 502, 503, 504}


def _oc() -> str:
    oc = os.getenv("LAW_OC")
    if not oc:
        raise RuntimeError("LAW_OC 환경변수가 설정되지 않았습니다(.env).")
    return oc


def _get(path: str, params: dict, retries: int = 3) -> dict:
    q = {"OC": _oc(), "type": "JSON", **params}
    last = None
    for i in range(retries + 1):
        try:
            r = requests.get(f"{BASE}/{path}", params=q, timeout=20)
            if r.status_code in _RETRYABLE and i < retries:
                time.sleep(1.0 * (i + 1))
                continue
            r.raise_for_status()
            return r.json()
        except requests.RequestException as e:
            last = e
            if i == retries:
                break
            time.sleep(1.0 * (i + 1))
    raise last


def _arr(v):
    if v is None:
        return []
    return v if isinstance(v, list) else [v]


def _flat(c):
    """조문내용이 string | string[][] 둘 다 올 수 있음 → 문자열."""
    if isinstance(c, list):
        out = []
        for x in c:
            out.extend(x) if isinstance(x, list) else out.append(x)
        return "\n".join(str(s) for s in out)
    return c or ""


# ───────── 검색(법·시행령) ─────────
def search_law(query: str) -> list[dict]:
    data = _get("lawSearch.do", {"target": "eflaw", "query": query, "nw": 3})
    items = _arr((data.get("LawSearch") or {}).get("law"))
    return [
        {"법령ID": l.get("법령ID"), "법령명": l.get("법령명한글"),
         "법령구분": l.get("법령구분명"), "시행일자": l.get("시행일자"),
         "소관부처": l.get("소관부처명")}
        for l in items if l.get("현행연혁코드") == "현행"
    ]


# ───────── 본문(법·시행령) — 조/항/호/목 구조화 ─────────
def _parse_article(raw: dict) -> dict:
    return {
        "조문번호": int(raw.get("조문번호")),
        "조문가지번호": int(raw["조문가지번호"]) if raw.get("조문가지번호") else None,
        "조제목": raw.get("조문제목") or "",
        "조문시행일자": str(raw.get("조문시행일자") or ""),   # 시행예정 식별용(미래일=예정)
        "조문내용": _flat(raw.get("조문내용")),
        "항목록": [
            {"항번호": h.get("항번호") or "", "항내용": _flat(h.get("항내용")),
             "호목록": [
                 {"호번호": ho.get("호번호") or "", "호내용": _flat(ho.get("호내용")),
                  "목목록": [{"목번호": m.get("목번호") or "", "목내용": _flat(m.get("목내용"))}
                            for m in _arr(ho.get("목"))]}
                 for ho in _arr(h.get("호"))]}
            for h in _arr(raw.get("항"))
        ],
    }


def get_law_text(law_id: str = None, mst: str = None, ef_yd: str = None) -> dict:
    """ID=현행. MST+efYd=특정 시행일 연혁 버전(구버전 조회)."""
    if mst and ef_yd:
        params = {"target": "eflaw", "MST": str(mst), "efYd": str(ef_yd)}
    else:
        params = {"target": "eflaw", "ID": law_id}
    raw = _get("lawService.do", params)
    data = raw.get("법령")
    if not data:
        raise RuntimeError(f"법령 본문을 찾을 수 없습니다({params}).")
    info = data.get("기본정보") or {}
    arts = [_parse_article(j)
            for j in _arr((data.get("조문") or {}).get("조문단위"))
            if j.get("조문여부") == "조문"]
    return {
        "법령명": info.get("법령명_한글") or "",
        "법령ID": info.get("법령ID") or law_id,
        "시행일자": info.get("시행일자") or "",
        "공포정보": info,
        "조문목록": arts,
        "별표목록": _arr((data.get("별표") or {}).get("별표단위")),
        "_raw": data,
    }


# ───────── 시행예정 버전 탐색 ─────────
def find_sched_version(law_name: str):
    """법령명으로 시행예정(미시행 개정) 버전 → (MST, 시행일자) 또는 None. nw=2=시행예정."""
    data = _get("lawSearch.do", {"target": "eflaw", "query": law_name, "nw": "2", "display": "50"})
    for r in _arr((data.get("LawSearch") or {}).get("law")):
        if str(r.get("법령명한글")) == law_name and str(r.get("현행연혁코드")) == "시행예정":
            return str(r.get("법령일련번호")), str(r.get("시행일자"))
    return None


# ───────── 체계도(상하위법) ─────────
def _tier(t):
    info = (t or {}).get("기본정보") or {}
    if not info.get("법령ID"):
        return None
    return {"법령ID": info.get("법령ID"), "법령명": info.get("법령명") or "",
            "시행일자": info.get("시행일자") or "", "행정규칙": t.get("행정규칙")}


def get_law_hierarchy(law_id: str) -> dict:
    raw = _get("lawService.do", {"target": "lsStmd", "ID": law_id})
    data = raw.get("법령체계도")
    if not data:
        raise RuntimeError(f"법령ID {law_id} 체계도를 찾을 수 없습니다.")
    base = data.get("기본정보") or {}
    law = (data.get("상하위법") or {}).get("법률")
    return {
        "법령명": base.get("법령명") or "",
        "법률": _tier(law),
        "시행령": _tier((law or {}).get("시행령")),
        "시행규칙": _tier(((law or {}).get("시행령") or {}).get("시행규칙")),
        "_raw": data,
    }


# ───────── 행정규칙(감독규정·세칙) ─────────
def search_admin_rule(query: str) -> list[dict]:
    data = _get("lawSearch.do", {"target": "admrul", "query": query})
    items = _arr((data.get("AdmRulSearch") or {}).get("admrul"))
    out = []
    for r in items:
        if (r.get("현행연혁구분") or "현행") != "현행":
            continue
        sn = str(r.get("행정규칙일련번호") or "")
        if sn:
            out.append({"행정규칙일련번호": sn, "행정규칙명": str(r.get("행정규칙명") or ""),
                        "행정규칙종류": str(r.get("행정규칙종류") or ""),
                        "시행일자": str(r.get("시행일자") or "")})
    return out


def get_admin_rule_text(serial_no: str) -> dict:
    raw = _get("lawService.do", {"target": "admrul", "ID": serial_no})
    svc = raw.get("AdmRulService")
    if not svc:
        raise RuntimeError(f"행정규칙 {serial_no} 본문을 찾을 수 없습니다.")
    info = svc.get("행정규칙기본정보") or {}
    body = svc.get("조문내용")
    body = "\n".join(body) if isinstance(body, list) else (body if isinstance(body, str) else "")
    return {
        "행정규칙명": info.get("행정규칙명") or "",
        "행정규칙일련번호": info.get("행정규칙일련번호") or serial_no,
        "시행일자": info.get("시행일자") or "",
        "조문내용": body,
        "_raw": svc,
    }
