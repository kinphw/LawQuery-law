"""
적재 전 검증. 두 단계:
  errors   → 적재 차단 (구조가 깨짐: 연계 끊김·중복키·필수시트 누락)
  warnings → 적재는 가능하나 확인 권장 (컬럼 누락·미상 시트 등)

핵심은 rdb(연계) dangling 검출 — id_start/id_end 가 실제 노드에 존재해야 한다.
"""
from collections import Counter

from common.schema_map import SHEETS, REQUIRED_SHEETS, NODE_ID_COLUMN


def validate(data, cols, all_sheets):
    errors: list[str] = []
    warnings: list[str] = []

    # 1) 필수 시트
    for s in REQUIRED_SHEETS:
        if s not in all_sheets:
            errors.append(f"필수 시트 누락: '{s}'")

    # 2) 매핑 안 된 시트(오타 의심)
    for s in all_sheets:
        if s not in SHEETS:
            warnings.append(f"알 수 없는 시트(무시됨): '{s}'")

    # 3) 컬럼 누락(없으면 NULL 적재)
    for s, found in cols.items():
        want = SHEETS[s][1]
        missing = [c for c in want if c not in found]
        if missing:
            warnings.append(f"[{s}] 컬럼 누락(NULL 적재): {missing}")

    # 4) 노드 ID 수집(단별)
    node_ids: set = set()
    for tier, idcol in NODE_ID_COLUMN.items():
        ids = [row[idcol] for row in data.get(tier, []) if row.get(idcol)]
        # 4-a) 동일 단 내 중복 ID
        dups = [k for k, n in Counter(ids).items() if n > 1]
        if dups:
            errors.append(f"[{tier}] 중복 ID {sorted(dups)}")
        node_ids.update(ids)

    # 5) rdb dangling — 연계 엣지 양끝이 노드에 존재해야 함
    for i, row in enumerate(data.get("rdb", []), 1):
        for col in ("id_start", "id_end"):
            v = row.get(col)
            if not v:
                errors.append(f"[rdb #{i}] {col} 비어있음")
            elif v not in node_ids:
                # 별표(B*)는 annex 키 규약 확인 필요 → 경고로 완화
                bucket = warnings if str(v).upper().startswith("B") else errors
                bucket.append(f"[rdb #{i}] {col}='{v}' 가 어느 단에도 없음(dangling)")

    # 6) annex.id_src 가 본문 노드를 가리키는지
    for i, row in enumerate(data.get("annex", []), 1):
        src = row.get("id_src")
        if src and src not in node_ids:
            warnings.append(f"[annex #{i}] id_src='{src}' 가 본문 노드에 없음")

    # 7) meta origin a/e/s/r 존재
    metas = {row.get("origin") for row in data.get("meta", [])}
    for need in ("a", "e", "s", "r"):
        if need not in metas:
            warnings.append(f"[meta] origin '{need}' 행 없음")

    return errors, warnings
