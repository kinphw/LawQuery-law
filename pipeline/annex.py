"""annex: 별표 적재. 별표를 그 단의 조에 연결(id_src).

연결 신호(우선순위):
  1) 별표제목의 '(제N조[의M] … 관련)'  → id_src (법/시행령 표준)
  2) 없으면 같은 단 조문 본문의 '별표 N[의M]' 언급 첫 조 → id_src (행정규칙 표준)
출처: 법/시행령=API 별표목록, 감독규정/세칙=admrul _raw['별표']['별표단위'].
삭제 별표·서식(별표구분≠별표) 제외. id_annex={TIER}_AN{번호}[_{가지}].

annex_url = 법령정보센터 **별표서식 뷰어 링크**(화면 표시; PDF 다운로드 링크 아님):
  법령    : /법령별표서식/(법령명,별표X)
  행정규칙: /행정규칙별표서식/(행정규칙명,발령번호,별표X)
"""
import re
import sys

from fetcher import law_api
from pipeline import load_job, read_artifact, write_artifact

UP = {"a": "A", "e": "E", "s": "S", "r": "R"}
BASE = "https://www.law.go.kr"
_REL = re.compile(r"제(\d+)조(?:의(\d+))?[^)]*관련")   # (제N조[의M] … 관련)


def _source_annexes(src: dict):
    """source → (별표서식뷰어경로, 법령명, 발령번호|None, [별표…])."""
    if src["kind"] == "law":
        if src.get("mst") and src.get("ef_yd"):       # 연혁(구버전)
            t = law_api.get_law_text(mst=src["mst"], ef_yd=src["ef_yd"])
        else:
            t = law_api.get_law_text(src["id"])
        name, pub, path = t["법령명"], None, "법령별표서식"
        items = t["별표목록"]
    else:
        t = law_api.get_admin_rule_text(src["id"])
        info = t["_raw"].get("행정규칙기본정보") or {}
        name, pub, path = t["행정규칙명"], (info.get("발령번호") or ""), "행정규칙별표서식"
        u = t["_raw"].get("별표", {}).get("별표단위", [])
        items = u if isinstance(u, list) else ([u] if u else [])
    out = []
    for b in items:
        gubun = (b.get("별표구분") or "별표")
        if gubun not in ("별표", "별지"):                 # 별표 + 별지서식(둘 다 적재), 기타만 제외
            continue
        title = (b.get("별표제목") or "").strip()
        if not title:
            continue
        out.append({
            "no": int(b.get("별표번호") or 0),
            "ga": int(b.get("별표가지번호") or 0) or None,
            "title": title,
            "form": gubun == "별지",                      # 별지서식 여부
        })
    return path, name, pub, out


def _viewer_url(path: str, name: str, pub, annex_no: str) -> str:
    inner = f"{name},{annex_no}" if pub is None else f"{name},{pub},{annex_no}"
    return f"{BASE}/{path}/({inner})"


def _src_from_body(tier: str, no: int, ga, data: dict, form: bool = False):
    if form:                                              # 별지 제N호[의M]서식
        pat = re.compile(rf"별\s*지\s*제?\s*{no}\s*호" + (rf"\s*의\s*{ga}" if ga else ""))
    else:                                                 # 별표 N[의M]
        pat = re.compile(rf"별\s*표\s*{no}" + (rf"\s*의\s*{ga}" if ga else r"(?!\s*의\s*\d)"))
    for row in data[tier]:
        if pat.search(row.get(f"content_{tier}") or ""):
            return row[f"id_{tier}"]
    return None


def build_annex(code: str) -> list[dict]:
    job = load_job(code)
    data = read_artifact(code, "data.json")
    rows, nolink = [], []
    for tier, src in job["sources"].items():
        path, name, pub, items = _source_annexes(src)
        for b in items:
            m = None if b["form"] else _REL.search(b["title"])   # (제N조 관련)은 별표만
            if m:
                src_id = f"{UP[tier]}{int(m.group(1))}" + (f"_{int(m.group(2))}" if m.group(2) else "")
                if src_id not in {r[f"id_{tier}"] for r in data[tier]}:
                    src_id = _src_from_body(tier, b["no"], b["ga"], data, b["form"])
            else:
                src_id = _src_from_body(tier, b["no"], b["ga"], data, b["form"])
            kind, pfx = ("별지", "F") if b["form"] else ("별표", "AN")
            no = f"{kind}{b['no']}" + (f"의{b['ga']}" if b["ga"] else "")
            aid = f"{UP[tier]}_{pfx}{b['no']}" + (f"_{b['ga']}" if b["ga"] else "")
            rows.append({"origin": tier, "id_annex": aid, "annex_no": no, "id_src": src_id,
                         "annex_name": b["title"], "annex_url": _viewer_url(path, name, pub, no)})
            if not src_id:
                nolink.append(aid)
        n = sum(1 for r in rows if r["origin"] == tier)
        if n:
            print(f"  {tier}: 별표 {n} (미연결 {sum(1 for a in nolink if a.startswith(UP[tier]))})")
    write_artifact(code, "annex.json", rows)
    print(f"저장: jobs/{code}/annex.json  별표 {len(rows)} (미연결 {len(nolink)})")
    return rows


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    build_annex(sys.argv[1] if len(sys.argv) > 1 else "g")
