"""수동 큐레이션 오버라이드 (전 테이블) — 자동 산출물 위에 사람의 편집 델타를 재적용.

개념(= Kustomize base+overlay / git rebase):
  자동 산출물(data/rdb/annex/ref/penalty.json) = 결정론 베이스.
  overrides.json = 사람 델타(테이블별 add/remove/modify).  적재 = 베이스 + 델타.
  capture = 라이브 DB(=db_export.read_law) ⊖ 베이스 → overrides.json 박제.
규정 갱신(--force) 후에도 델타 재적용 → 큐레이션 영속. 안정 ID(A37/S17, id_annex…)가 가능케 함.

테이블 식별:
  키드(meta/a/e/s/r/annex)  : 키 컬럼으로 add/remove/**modify**(내용 수정 보존).
  키리스(rdb/ref/penalty*)  : 행 전체(id 제외)로 add/remove.
rdb add 는 엔드포인트 노드 검증(갱신으로 사라지면 스킵+경고 = rebase 충돌).
편집은 GUI 편집기('오버라이드 저장') 또는 `python -m pipeline.overrides <code>` 로 박제.
"""
import json
import sys

from common.schema_map import SHEETS, AUTO_ID_SHEETS
from pipeline import job_dir, read_artifact, write_artifact

KEY = {"meta": "origin", "a": "id_a", "e": "id_e", "s": "id_s", "r": "id_r", "annex": "id_annex"}


def _cmp(x):
    return None if x is None else str(x)


def _ident(row, cols):
    return tuple(_cmp(row.get(c)) for c in cols)


def auto_rows(code: str, sheet: str) -> list[dict]:
    """해당 테이블의 자동 산출물(베이스) 행."""
    if sheet in ("meta", "a", "e", "s", "r"):
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


def load_overrides(code: str) -> dict:
    p = job_dir(code) / "overrides.json"
    return json.loads(p.read_text(encoding="utf-8")) if p.exists() else {}


# ───────── capture: 라이브 ⊖ 베이스 ─────────
def _diff_sheet(sheet: str, auto: list, live: list) -> dict:
    cols = SHEETS[sheet][1]
    key = KEY.get(sheet)
    if key:
        cmp_cols = [c for c in cols if c not in (key, "id")]
        idc = [c for c in cols if c != "id"]
        a = {r.get(key): r for r in auto if r.get(key) is not None}
        l = {r.get(key): r for r in live if r.get(key) is not None}
        add = [l[k] for k in l if k not in a]
        remove = [k for k in a if k not in l]
        modify = {}
        for k in a.keys() & l.keys():
            ch = {c: l[k].get(c) for c in cmp_cols if _cmp(l[k].get(c)) != _cmp(a[k].get(c))}
            if ch:
                modify[str(k)] = ch
        # 키 없는 행(장/절 제목 등, id=NULL) — 전체 행 식별로 add/remove
        a_null = {_ident(r, idc): r for r in auto if r.get(key) is None}
        l_null = {_ident(r, idc): r for r in live if r.get(key) is None}
        add += [{c: l_null[i].get(c) for c in idc} for i in l_null if i not in a_null]
        out = {"add": add, "remove": remove, "modify": modify}
        rrows = [{c: a_null[i].get(c) for c in idc} for i in a_null if i not in l_null]
        if rrows:
            out["remove_rows"] = rrows
        return out
    idc = [c for c in cols if c != "id"]          # 자동 id 는 식별·저장에서 제외
    aset = {_ident(r, idc) for r in auto}
    lset = {_ident(r, idc) for r in live}
    pick = lambda r: {c: r.get(c) for c in idc}
    return {"add": [pick(r) for r in live if _ident(r, idc) not in aset],
            "remove": [pick(r) for r in auto if _ident(r, idc) not in lset]}


def _empty(ov: dict) -> bool:
    return not any(ov.get(k) for k in ("add", "remove", "modify"))


def capture(code: str, target: str = "dev", log=print) -> dict:
    from exporter.db_export import read_law
    live = read_law(code, target)
    out = {}
    for sheet in SHEETS:
        ov = _diff_sheet(sheet, auto_rows(code, sheet), live.get(sheet, []))
        if not _empty(ov):
            out[sheet] = ov
    write_artifact(code, "overrides.json", out)
    summary = ", ".join(
        f"{s}(+{len(o.get('add', []))}/-{len(o.get('remove', []))}/~{len(o.get('modify', {}))})"
        for s, o in out.items()) or "변경 없음"
    log(f"[capture] overrides.json — {summary}")
    return out


# ───────── apply: 베이스 + 델타 ─────────
def apply_overrides(sheet: str, auto: list, sheet_ov: dict | None,
                    valid_nodes: set | None = None, log=print) -> list[dict]:
    cols = SHEETS[sheet][1]
    key = KEY.get(sheet)
    if not sheet_ov:
        rows = [dict(r) for r in auto]
    elif key:
        idc = [c for c in cols if c != "id"]
        by = {r.get(key): dict(r) for r in auto if r.get(key) is not None}
        null_rows = [dict(r) for r in auto if r.get(key) is None]
        for k in sheet_ov.get("remove", []):
            by.pop(k, None)
        rem_n = {_ident(r, idc) for r in sheet_ov.get("remove_rows", [])}
        if rem_n:
            null_rows = [r for r in null_rows if _ident(r, idc) not in rem_n]
        skip = 0
        for k, ch in sheet_ov.get("modify", {}).items():
            if k in by:
                by[k].update(ch)
            else:
                skip += 1
        for r in sheet_ov.get("add", []):
            if r.get(key) is not None:
                by[r.get(key)] = dict(r)
            else:
                null_rows.append(dict(r))         # 장/절 제목 등 키없는 행
        if skip:
            log(f"[overrides:{sheet}] ⚠ modify 대상 {skip}건 부재(갱신 소멸) 스킵")
        rows = list(by.values()) + null_rows
    else:
        idc = [c for c in cols if c != "id"]
        rem = {_ident(r, idc) for r in sheet_ov.get("remove", [])}
        rows = [dict(r) for r in auto if _ident(r, idc) not in rem]
        rows += [dict(r) for r in sheet_ov.get("add", [])]

    if sheet == "rdb" and valid_nodes is not None:        # rdb 엔드포인트 검증
        kept = [r for r in rows if r["id_start"] in valid_nodes and r["id_end"] in valid_nodes]
        if len(kept) != len(rows):
            log(f"[overrides:rdb] ⚠ 노드 부재 엣지 {len(rows) - len(kept)}건 스킵(갱신 충돌)")
        rows = kept
    if sheet in AUTO_ID_SHEETS:                           # id 비워서 loader가 1..N 재부여
        for r in rows:
            r["id"] = None
    return rows


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    capture(sys.argv[1] if len(sys.argv) > 1 else "g")
