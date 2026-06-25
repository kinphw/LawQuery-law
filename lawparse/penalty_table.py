"""과태료(·과징금) 부과기준 별표 파서.

시행령 별표의 ASCII 박스표(┌┬┐│├┼┤└┴┘─)를 행으로 파싱.
  개별기준 표: │위반행위 │근거 법조문 │금액 │
  → (위반행위, 근거법조, 금액) ; 근거법조 '법 제51조제3항제1호' → 노드 A51_3h_1ho

법별 표 형태가 다를 수 있어(과태료는 대개 '위반행위|근거법조문|금액' 3열) 3열 박스표 전제.
멀티라인 셀은 줄 연결(한글 줄바꿈=무공백 연결). 헤더행(위반행위 포함)은 제외.
"""
import re

_LAWREF = re.compile(r"제(\d+)조(?:의(\d+))?(?:제(\d+)항)?(?:제(\d+)호)?")


def ref_to_id(ref: str) -> str | None:
    """'법 제51조제3항제1호' → 'A51_3h_1ho' (항/호까지). 매칭 실패 시 None."""
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


def parse_box_table(content: str, ncol: int = 3) -> list[list[str]]:
    """박스표 → [[셀1, 셀2, ...], ...]. '개별기준' 이후만. 헤더/구분선 제외."""
    if "개별기준" in content:
        content = content[content.index("개별기준"):]
    rows, cur = [], None
    for ln in content.split("\n"):
        if any(ch in ln for ch in "┌┬┐├┼┤└┴┘"):       # 구분선
            if ("├" in ln or "└" in ln) and cur and any(cur):
                rows.append(cur)
                cur = None
            continue
        if "│" in ln:                                    # 데이터행
            cells = [p.strip() for p in ln.split("│")[1:-1]]
            if len(cells) != ncol:
                continue
            if cur is None:
                cur = [""] * ncol
            for i in range(ncol):
                if cells[i]:
                    cur[i] += cells[i]                    # 멀티라인 셀 연결(무공백)
    if cur and any(cur):
        rows.append(cur)
    return [r for r in rows if "위반행위" not in r[0]]    # 헤더 제외


def parse_penalty_annex(content: str) -> list[dict]:
    """과태료 부과기준 별표 → penalty_e 행(dict). 금액은 콤마 제거."""
    out = []
    for viol, ref, amt in parse_box_table(content, 3):
        out.append({
            "content_pe": viol,
            "item_a_log": ref,
            "penalty_e_log": amt.replace(",", "").strip(),
            "item_a_phy": ref_to_id(ref),
        })
    return out
