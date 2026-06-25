r"""
법령 본문 분리 (LawParser VBA 포팅).

split_body(text) → 유닛 리스트:
  {'type':'title',   'title':'제1장 총칙'}
  {'type':'article', 'jo':2, 'ga':None, 'head':'제2조(정의)',
                     'stem':'제2조(정의) …도입부', 'items':[' 1. …', ' 2. …']}

- 조간분리: 줄 맨 앞 헤더 `제N조(…)` / `제N조의M(…)` / `제N조 삭제<…>` / `제N장` / `제N절`.
  (조는 괄호 또는 '삭제<…>' 필수 — 본문 중 "제N조" 인용 오매칭 방지)
- 조내분리: 항(①~⑮) 우선, 없으면 호(`^\d+(의\d+)*\.`). 목(가.~하.)은 호 안에 유지.
"""
import re

_HEADER = re.compile(
    r'^제(\d+)조(?:의(\d+))?(\([^)]*\)|\s*삭\s*제(?:\s*<[^>]+>)?)'   # g1=조 g2=가지 g3=괄호/삭제(날짜 선택)
    r'|^제(\d+)(장|절)',                                       # g4=번호 g5=장|절
    re.M,
)
_HANG = re.compile(r'^[①-⑮]')
_HO = re.compile(r'^\d+(?:의\d+)*\.')


def _norm(text: str) -> str:
    text = text.replace('\r\n', '\n').replace('\r', '\n')
    # 빈 줄(연속 개행) 1개로 축소 (VBA CleanUpLineFeed)
    while '\n\n' in text:
        text = text.replace('\n\n', '\n')
    return text


_HANG_CH = '①②③④⑤⑥⑦⑧⑨⑩⑪⑫⑬⑭⑮'
# 법령 목 번호 순환: 가~하 → 거~허 → 고~호 → 구~후 (초성 14 × 중성 ㅏㅓㅗㅜ)
_MOK_SEQ = ('가나다라마바사아자차카타파하'
            '거너더러머버서어저처커터퍼허'
            '고노도로모보소오조초코토포호'
            '구누두루무부수우주추쿠투푸후')


def format_admin_body(text: str) -> str:
    """행정규칙 본문(API가 조 단위로 주며 항/호/목이 한 줄에 붙어 옴) → 항/호/목 앞 개행 삽입.

    법/시행령은 구조화 API라 이미 분리됨. 이 함수는 admrul 문자열 전용.
    날짜 등 <…> 보호 후 항(①)·호(N.)·목(가.) 마커 앞에 개행. 목은 가→나→다 시퀀스로만 분리(문장끝 '~다.' 오삽입 방지).
    """
    return '\n'.join(_format_admin_line(ln) for ln in _norm(text).split('\n'))


def _format_admin_line(line: str) -> str:
    if not re.match(r'제\d+조', line):     # 장/절 등은 그대로
        return line
    holds: list[str] = []
    s = re.sub(r'<[^>]*>', lambda m: holds.append(m.group(0)) or f'\x01{len(holds)-1}\x02', line)
    s = re.sub(rf'([{_HANG_CH}])', r'\n\1', s)                                   # 항 ①
    s = re.sub(r'(?<!\d)(\d{1,2}(?:의\d+)*\.)(?=\s|["\'(《「가-힣])', r'\n\1', s)   # 호 N.
    s = _split_mok(s)                                                            # 목 가.
    for i, h in enumerate(holds):
        s = s.replace(f'\x01{i}\x02', h)
    return re.sub(r'\n[ \t]+', '\n', s).strip('\n')


def _split_mok(s: str) -> str:
    """가.나.다… 시퀀스 런만 분리. 마커 사이 '①'/개행 만나면 런 종료."""
    res, pos = [], 0
    while True:
        m = re.search(r'(?<![가-힣])가\.', s[pos:])     # 런 시작 가.(앞이 한글이 아님)
        if not m:
            res.append(s[pos:]); break
        st = pos + m.start()
        res.append(s[pos:st])
        j, k = 0, st
        while k < len(s):
            if j < len(_MOK_SEQ) and s[k] == _MOK_SEQ[j] and k + 1 < len(s) and s[k + 1] == '.':
                res.append('\n' + s[k] + '.'); k += 2; j += 1
            elif s[k] in _HANG_CH or s[k] == '\n':
                break
            else:
                res.append(s[k]); k += 1
        pos = k
    return ''.join(res)


def split_body(text: str) -> list[dict]:
    text = _norm(text)
    matches = list(_HEADER.finditer(text))
    units: list[dict] = []
    for i, m in enumerate(matches):
        end = matches[i + 1].start() if i + 1 < len(matches) else len(text)
        chunk = text[m.start():end].strip('\n')
        if m.group(5):  # 장/절
            units.append({'type': 'title', 'title': chunk.split('\n', 1)[0].strip()})
            continue
        jo = int(m.group(1))
        ga = int(m.group(2)) if m.group(2) else None
        stem, items = _split_article(chunk)
        units.append({'type': 'article', 'jo': jo, 'ga': ga,
                      'head': m.group(0).strip(), 'stem': stem, 'items': items})
    return units


def _split_article(chunk: str) -> tuple[str, list[str]]:
    """조 본문 → (stem, [항/호 item…]). 항 있으면 항기준, 없으면 호기준."""
    lines = chunk.split('\n')
    body = lines[1:]  # 0번째 = '제N조(…) …' 헤더줄(stem 시작)
    has_hang = any(_HANG.match(l.strip()) for l in body)
    trig = _HANG if has_hang else _HO
    if not any(trig.match(l.strip()) for l in body):
        return chunk.strip(), []

    stem_lines = [lines[0]]
    items: list[str] = []
    cur: list[str] = []
    started = False
    for l in body:
        if trig.match(l.strip()):
            if started:
                items.append('\n'.join(cur).rstrip())
            started = True
            cur = [_indent(l)]
        elif started:
            cur.append(_indent(l))
        else:
            stem_lines.append(l)
    if cur:
        items.append('\n'.join(cur).rstrip())
    return '\n'.join(stem_lines).strip(), items


def _indent(line: str) -> str:
    t = line.strip()
    if _HANG.match(t):
        return t
    if _HO.match(t):
        return ' ' + t
    return line
