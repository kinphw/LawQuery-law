"""수동 큐레이션 오버라이드 (typed) — 자동 베이스 위에 구조/연결/내용 델타를 재적용.

세 종류(신규추출·현행화 동일하게 적용, 차이는 베이스 버전뿐):
  splits  : {조ID: 'hang'|'hangho'}  — 어느 조를 항/호로 분리. **현행 본문을 재분리**(내용 저장 안 함).
  links   : rdb/ref/annex/penalty* 델타(add/remove/modify) — 연결·매핑 큐레이션.
  content : {sheet:{nodeID:{col:val}}} — 명시적 내용 하드코딩만(자동 포맷/버전 노이즈는 안 담음).

핵심: splits가 내용을 **베이스에서 재생성**하므로, 현행화 시 내용은 현행·구조는 큐레이션 유지.
캡처=라이브 DB ⊖ 베이스. 적용 시 splits→재분리, links→델타, content→강제.
"""
import json
import re
import sys

from common.schema_map import SHEETS, AUTO_ID_SHEETS
from pipeline import job_dir, read_artifact, write_artifact

KEY = {"meta": "origin", "a": "id_a", "e": "id_e", "s": "id_s", "r": "id_r", "annex": "id_annex"}
CONTENT_TIERS = ("a", "e", "s", "r")
LINK_SHEETS = ("annex", "ref", "rdb", "penalty", "penalty_a", "penalty_e")  # 델타로 carry
_CHILD = re.compile(r"^([AESR]\d+(?:_\d+)?)_(\d+)h(?:_(\d+)ho)?$")


def _cmp(x):
    return None if x is None else str(x)


def _ident(row, cols):
    return tuple(_cmp(row.get(c)) for c in cols)


def auto_rows(code, sheet):
    if sheet in CONTENT_TIERS + ("meta",):
        return read_artifact(code, "data.json").get(sheet, [])
    if sheet == "annex":
        return read_artifact(code, "annex.json")
    if sheet == "ref":
        return read_artifact(code, "ref.json")
    if sheet == "rdb":
        return [{"id_start": e["id_start"], "id_end": e["id_end"]}
                for e in read_artifact(code, "rdb.json")["edges"]]
    if sheet in ("penalty", "penalty_a", "penalty_e"):
        return read_artifact(code, "penalty.json").get(sheet, [])
    return []


def load_overrides(code):
    p = job_dir(code) / "overrides.json"
    return json.loads(p.read_text(encoding="utf-8")) if p.exists() else {}


# ───────── splits 감지 ─────────
def detect_splits(live: dict) -> dict:
    """라이브 a/e/s/r 에서 항/호 자식 가진 조 → {조ID: level}."""
    splits = {}
    for t in CONTENT_TIERS:
        for r in live.get(t, []):
            m = _CHILD.match(str(r.get(f"id_{t}") or ""))
            if m:
                jo = m.group(1)
                if m.group(3) or splits.get(jo) == "hangho":
                    splits[jo] = "hangho"
                else:
                    splits.setdefault(jo, "hang")
    return splits


# ───────── 델타(키드/키리스 테이블) ─────────
def _diff_sheet(sheet, auto, live):
    cols = SHEETS[sheet][1]
    key = KEY.get(sheet)
    if key:
        cmp_cols = [c for c in cols if c not in (key, "id")]
        a = {r.get(key): r for r in auto if r.get(key) is not None}
        l = {r.get(key): r for r in live if r.get(key) is not None}
        add = [l[k] for k in l if k not in a]
        remove = [k for k in a if k not in l]
        modify = {}
        for k in a.keys() & l.keys():
            ch = {c: l[k].get(c) for c in cmp_cols if _cmp(l[k].get(c)) != _cmp(a[k].get(c))}
            if ch:
                modify[str(k)] = ch
        return {"add": add, "remove": remove, "modify": modify}
    idc = [c for c in cols if c != "id"]
    aset = {_ident(r, idc) for r in auto}
    lset = {_ident(r, idc) for r in live}
    pick = lambda r: {c: r.get(c) for c in idc}
    return {"add": [pick(r) for r in live if _ident(r, idc) not in aset],
            "remove": [pick(r) for r in auto if _ident(r, idc) not in lset]}


def _empty(ov):
    return not any(ov.get(k) for k in ("add", "remove", "modify"))


def apply_delta(sheet, auto, ov, valid_nodes=None, log=print):
    """키드/키리스 테이블 델타 적용(annex/ref/rdb/penalty*/meta)."""
    cols = SHEETS[sheet][1]
    key = KEY.get(sheet)
    if not ov:
        rows = [dict(r) for r in auto]
    elif key:
        idc = [c for c in cols if c != "id"]
        by = {r.get(key): dict(r) for r in auto if r.get(key) is not None}
        nulls = [dict(r) for r in auto if r.get(key) is None]
        for k in ov.get("remove", []):
            by.pop(k, None)
        for k, ch in ov.get("modify", {}).items():
            if k in by:
                by[k].update(ch)
        for r in ov.get("add", []):
            (by.__setitem__(r.get(key), dict(r)) if r.get(key) is not None else nulls.append(dict(r)))
        rows = list(by.values()) + nulls
    else:
        idc = [c for c in cols if c != "id"]
        rem = {_ident(r, idc) for r in ov.get("remove", [])}
        rows = [dict(r) for r in auto if _ident(r, idc) not in rem] + \
               [dict(r) for r in ov.get("add", [])]
    if sheet == "rdb" and valid_nodes is not None:
        kept = [r for r in rows if r["id_start"] in valid_nodes and r["id_end"] in valid_nodes]
        if len(kept) != len(rows):
            log(f"[overrides:rdb] ⚠ 노드부재 엣지 {len(rows)-len(kept)}건 스킵(갱신 충돌)")
        rows = kept
    if sheet in AUTO_ID_SHEETS:
        for r in rows:
            r["id"] = None
    return rows


# ───────── content 단(a/e/s/r): splits 재분리 + 내용 하드코딩 ─────────
def apply_content_tier(tier, base_rows, splits, content_ov, log=print):
    from lawparse.article_split import split_article
    rows, nsplit = [], 0
    for r in base_rows:
        rid = r.get(f"id_{tier}")
        if rid in splits and r.get(f"content_{tier}"):
            stem, children = split_article(rid, r[f"content_{tier}"], splits[rid])
            pr = dict(r); pr[f"content_{tier}"] = stem
            rows.append(pr)
            for cid, ctext in children:
                cr = {"seq": None, f"id_{tier}": cid, f"content_{tier}": ctext,
                      f"content_{tier}_sched": None, "sched_date": None}
                if tier == "a":
                    cr["id_aa"] = r.get("id_aa") or rid
                    cr["title_a"] = r.get("title_a")
                rows.append(cr)
            nsplit += 1
        else:
            rows.append(dict(r))
    for nid, ch in (content_ov.get(tier, {}) or {}).items():     # 명시적 하드코딩
        for row in rows:
            if row.get(f"id_{tier}") == nid:
                row.update(ch)
    for i, row in enumerate(rows, 1):                            # 재seq
        row["seq"] = i
    if nsplit:
        log(f"[overrides:{tier}] 재분리 {nsplit}조")
    return rows


# ───────── capture / 적재 데이터 구성 ─────────
def capture(code, target="dev", log=print):
    from exporter.db_export import read_law
    live = read_law(code, target)
    out = {}
    splits = detect_splits(live)
    if splits:
        out["splits"] = splits
    for sheet in LINK_SHEETS:                                    # 연결·매핑 델타
        ov = _diff_sheet(sheet, auto_rows(code, sheet), live.get(sheet, []))
        if not _empty(ov):
            out[sheet] = ov
    # content(a/e/s/r 내용 하드코딩)는 자동캡처 안 함(포맷/버전 노이즈 배제) — 명시적 추가 전용
    out.setdefault("content", {})
    write_artifact(code, "overrides.json", out)
    summ = f"splits {len(splits)}조, " + ", ".join(
        f"{s}(+{len(out[s].get('add',[]))}/-{len(out[s].get('remove',[]))}/~{len(out[s].get('modify',{}))})"
        for s in LINK_SHEETS if s in out)
    log(f"[capture] overrides.json(typed) — {summ}")
    return out


def build_load_data(code, sheets, log=print):
    """선택 sheet들의 적재 행 구성: a/e/s/r=splits재분리, 나머지=델타. valid_nodes로 rdb검증."""
    ov = load_overrides(code)
    splits = ov.get("splits", {})
    content = ov.get("content", {})
    # 최종 a/e/s/r (재분리 반영) — valid_nodes 산정 + 적재용
    tiers = {t: apply_content_tier(t, auto_rows(code, t), splits, content, log)
             for t in CONTENT_TIERS}
    # 시행예정 부착(splits 후 노드에). 분리된 조 stem은 제외 → 변경된 항/호 노드만 받음.
    sp = job_dir(code) / "sched.json"
    if sp.exists():
        sched = json.loads(sp.read_text(encoding="utf-8"))
        ns = 0
        for t in CONTENT_TIERS:
            for row in tiers[t]:
                nid = row.get(f"id_{t}")
                if nid and nid in sched and nid not in splits:
                    row[f"content_{t}_sched"], row["sched_date"] = sched[nid]
                    ns += 1
        if ns:
            log(f"[sched] 시행예정 {ns}노드 부착")
    valid = {r[f"id_{t}"] for t in CONTENT_TIERS for r in tiers[t] if r.get(f"id_{t}")}
    out = {}
    for sheet in sheets:
        if sheet in CONTENT_TIERS:
            out[sheet] = tiers[sheet]
        elif sheet == "meta":
            out[sheet] = apply_delta(sheet, auto_rows(code, sheet), ov.get(sheet), log=log)
        else:
            out[sheet] = apply_delta(sheet, auto_rows(code, sheet), ov.get(sheet),
                                     valid_nodes=valid, log=log)
    return out


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    capture(sys.argv[1] if len(sys.argv) > 1 else "g")
