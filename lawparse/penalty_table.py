"""과태료·과징금/업무정지 부과기준 별표 파서.

시행령 별표의 ASCII 박스표(light ┌┬┐│ / heavy ┏┳┓┃ 혼용) → 행렬 파싱.
  과태료 별표(3열): 위반행위 │근거 법조문 │금액
  업무정지+갈음과징금 별표(4열): 위반행위 │근거 법조문 │업무정지기간 │과징금금액
근거법조 '법 제51조제3항제1호' → 노드 A51_3h_1ho. 멀티라인 셀=한글 줄바꿈(무공백) 연결.
"""
import re

_LAWREF = re.compile(r"제(\d+)조(?:의(\d+))?(?:제(\d+)항)?(?:제(\d+)호)?")
_VERT = re.compile(r"[┃│]")                 # 세로 칸 구분
_HSEP = re.compile(r"[─━]")                 # 가로 구분선
_FLUSH = re.compile(r"[├┠└┗┝┣┌┏╞]")        # 행 경계 시작


def ref_to_id(ref: str) -> str | None:
    """'법 제51조제3항제1호' → 'A51_3h_1ho' (항/호까지). 실패 시 None."""
    m = _LAWREF.search((ref or "").replace(" ", ""))
    if not m:
        return None
    jo, ga, hang, ho = m.groups()
    nid = f"A{jo}" + (f"_{ga}" if ga else "")
    if hang:
        nid += f"_{hang}h"
    if ho:
        nid += f"_{ho}ho"
    return nid


def refs_in(text: str) -> list[str]:
    """본문 속 모든 '제N조[의M][제K항][제L호]' → 노드ID 리스트(순서)."""
    out = []
    for m in re.finditer(r"제\d+조(?:의\d+)?(?:제\d+항)?(?:제\d+호)?", (text or "").replace(" ", "")):
        rid = ref_to_id(m.group(0))
        if rid:
            out.append(rid)
    return out


def parse_box_table(content: str, section: str | None = "개별기준") -> list[list[str]]:
    """박스표 → [[셀…], …]. section 지정 시 그 이후만. 헤더(위반행위 포함)는 제외."""
    if section and section in content:
        content = content[content.index(section):]
    rows, cur, ncol = [], None, None
    for ln in content.split("\n"):
        if _HSEP.search(ln) and not _VERT.search(ln):    # 순수 가로 구분선
            if _FLUSH.search(ln) and cur and any(cur):
                rows.append(cur)
                cur = None
            continue
        if not _VERT.search(ln):                          # 표 밖
            continue
        cells = [p.strip() for p in _VERT.split(ln)[1:-1]]
        if not cells:
            continue
        if ncol is None:
            ncol = len(cells)
        cells = (cells + [""] * ncol)[:ncol]              # 칸수 고정
        if cur is None:
            cur = [""] * ncol
        for i in range(ncol):
            if cells[i]:
                cur[i] += cells[i]                        # 멀티라인 연결(무공백)
    if cur and any(cur):
        rows.append(cur)
    return [r for r in rows if "위반행위" not in r[0]]


def parse_penalty_annex(content: str) -> list[dict]:
    """과태료 부과기준(3열) → penalty_e 행. 금액 콤마 제거."""
    out = []
    for r in parse_box_table(content):
        if len(r) < 3:
            continue
        viol, ref, amt = r[0], r[1], r[2]
        out.append({"content_pe": viol, "item_a_log": ref,
                    "penalty_e_log": amt.replace(",", "").strip(),
                    "item_a_phy": ref_to_id(ref)})
    return out


def parse_suspension_annex(content: str) -> list[list[str]]:
    """업무정지+갈음과징금(4열) → [위반행위, 근거, 업무정지기간, 과징금] 리스트(셀 가공은 호출측)."""
    return [r[:4] for r in parse_box_table(content, section=None) if len(r) >= 4]
