"""
LawQuery 법령 DB 스키마 매핑 (단일 출처 of truth).

엑셀 시트명 → (테이블명, 적재 컬럼 목록).
적재 컬럼은 AUTO_INCREMENT PK(_pk / db_annex.id / db_meta._pk)는 제외한다.
reader / validator / loader / template 이 전부 이 매핑만 참조한다.
"""

# 시트명: (테이블명, 적재할 컬럼 순서)
SHEETS: dict[str, tuple[str, list[str]]] = {
    "meta":      ("db_meta",      ["origin", "full_name", "short_name", "track"]),  # track: 멀티트랙 r/b 구분(단일=NULL)
    "track":     ("db_track",     ["track_code", "label", "sort_order"]),           # 행정규칙 병렬 트랙 목록(토글)
    "a":         ("db_a",         ["seq", "id_aa", "id_a", "title_a", "content_a", "content_a_sched", "sched_date"]),
    "e":         ("db_e",         ["seq", "id_e", "content_e", "content_e_sched", "sched_date"]),
    "s":         ("db_s",         ["seq", "id_s", "content_s", "content_s_sched", "sched_date"]),
    "r":         ("db_r",         ["seq", "id_r", "content_r", "content_r_sched", "sched_date"]),
    "b":         ("db_b",         ["seq", "id_b", "content_b", "content_b_sched", "sched_date"]),  # 5단째(시행규칙 등 추가 단). 4단 법은 미사용(빈 테이블).
    "annex":     ("db_annex",     ["origin", "id_annex", "annex_no", "id_src", "annex_name", "annex_url"]),
    "ref":       ("db_ref",       ["id", "id_origin", "ref_type", "ref_target", "ref_content"]),
    "rdb":       ("rdb",          ["id", "id_start", "id_end", "track"]),  # track: 트랙별 r/b 엣지(공유 a/e/s=NULL)
    "penalty":   ("db_penalty",   ["id", "penalty_a_phy", "penalty_a_log"]),
    "penalty_a": ("db_penalty_a", ["id", "category", "item_a_phy", "item_a_log", "content_pa", "penalty_a_phy", "id_a"]),
    "penalty_e": ("db_penalty_e", ["id", "content_pe", "item_a_log", "penalty_e_log", "item_a_phy"]),
    "rdb_hl":    ("db_rdb_hl",    ["id", "up_id", "down_id"]),  # 인용 정밀 강조쌍(상위 항/호 ↔ 하위 항/호)
}

# 필수 시트(없으면 적재 불가) / 선택 시트(벌칙)
REQUIRED_SHEETS = ["meta", "a", "e", "s", "r", "annex", "ref", "rdb"]
OPTIONAL_SHEETS = ["penalty", "penalty_a", "penalty_e"]

# 각 본문 단의 "노드 ID" 컬럼 — 연계(rdb) 검증과 트리 식별의 기준.
#   db_a 는 id_a(세부, 예: A2_3h)가 노드 키. id_aa(조 묶음)는 표시용.
NODE_ID_COLUMN = {"a": "id_a", "e": "id_e", "s": "id_s", "r": "id_r", "b": "id_b", "annex": "id_annex"}

# id 컬럼이 실키가 아니라 단순 순번인 테이블(없으면 1..N 자동부여)
AUTO_ID_SHEETS = ["ref", "rdb", "penalty", "penalty_a", "penalty_e", "rdb_hl"]

# 적재 순서(부모 단을 먼저). meta/track → 본문 → 별표/참조/연계 → 벌칙
LOAD_ORDER = ["meta", "track", "a", "e", "s", "r", "b", "annex", "ref", "rdb", "rdb_hl", "penalty", "penalty_a", "penalty_e"]

# 레코드 단위 편집용 PK 컬럼(시트별). 에디터가 이 키로 UPDATE/DELETE 한다.
PK_COLUMN = {
    "meta": "_pk", "a": "_pk", "e": "_pk", "s": "_pk", "r": "_pk", "b": "_pk",
    "annex": "id",
    "ref": "_pk", "rdb": "_pk",
    "penalty": "_pk", "penalty_a": "_pk", "penalty_e": "_pk",
}

# 원래 PK가 없어 편집용 surrogate _pk 를 붙여야 하는 테이블(편집 진입 시 자동 ALTER)
NEEDS_SURROGATE_PK = ["ref", "rdb", "penalty", "penalty_a", "penalty_e"]
