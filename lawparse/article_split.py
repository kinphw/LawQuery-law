r"""조 1개 본문 → 항/호 자식 노드 분리 (LawParser ClsSplitSingleArticle 포팅 + ID 부여).

split_article(jo_id, content, level) → (stem, [(child_id, child_text), …])
  level='hang'   : 1단 분리(항, 또는 항 없으면 호) → {jo_id}_{k}h
  level='hangho' : 2단(항 _kh + 항 안의 호 _kh_mho)
단위번호 기반 ID(① → _1h, "3." → _3h)라 삭제 항/호로 번호가 띄어도 정확. ID 규약은 ids.py/CLAUDE.md.
"""
import re

from lawparse import splitter

_HANG = "①②③④⑤⑥⑦⑧⑨⑩⑪⑫⑬⑭⑮"
_HO = re.compile(r"^\s*(\d+)(?:의(\d+))?\.")          # 호번호(+가지호)


def _hang_num(line: str):
    c = line.strip()[:1]
    return _HANG.index(c) + 1 if c and c in _HANG else None


def _ho_num(line: str):
    m = _HO.match(line.strip())
    return int(m.group(1)) if m else None


def _ho_key(line: str):
    """호 ID 키: '6.'→'6', '6의2.'→'6_2' (가지호 구분 — 충돌 방지)."""
    m = _HO.match(line.strip())
    if not m:
        return None
    return m.group(1) + (f"_{m.group(2)}" if m.group(2) else "")


def _unit_num(line: str):
    return _hang_num(line) or _ho_num(line)


def _split_by_ho(hang_item: str):
    """항 덩어리 → (항 stem, [호…])."""
    lines = hang_item.split("\n")
    stem, subs, cur = [lines[0]], [], None
    for l in lines[1:]:
        if _HO.match(l.strip()):
            if cur is not None:
                subs.append(cur)
            cur = l
        elif cur is not None:
            cur += "\n" + l
        else:
            stem.append(l)
    if cur is not None:
        subs.append(cur)
    return "\n".join(stem).rstrip(), subs


def split_article(jo_id: str, content: str, level: str = "hang"):
    stem, items = splitter._split_article(content)   # 항 우선(없으면 호) 1차 분리
    children: list[tuple[str, str]] = []
    for item in items:
        k = _unit_num(item)
        if k is None:
            continue
        cid = f"{jo_id}_{k}h"
        if level == "hang":
            children.append((cid, item.strip()))
        else:  # hangho — 항 안의 호 2단
            hstem, hos = _split_by_ho(item)
            children.append((cid, hstem.strip()))
            for ho in hos:
                key = _ho_key(ho)                       # '6'→_6ho, '6의2'→_6_2ho (가지호)
                children.append((f"{cid}_{key}ho" if key else f"{cid}_x", ho.strip()))
    return stem.strip(), children
