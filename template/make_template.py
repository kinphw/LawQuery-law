"""
빈 엑셀 템플릿 생성. 시트 1개 = 테이블 1개, 첫 행은 헤더(적재 컬럼).
핵심 시트엔 ldb_j 실제 데이터를 발췌한 예시행을 넣어 형식을 보여준다.
"""
from openpyxl import Workbook

from common.schema_map import SHEETS, LOAD_ORDER

# ldb_j 발췌 예시행 (형식 안내용 — 실제 채울 땐 지우고 작성)
EXAMPLES = {
    "meta": [
        {"origin": "a", "full_name": "전자금융거래법\n[시행 2025. 12. 16.]", "short_name": "법률"},
        {"origin": "e", "full_name": "전자금융거래법 시행령\n[시행 2024. 12. 27.]", "short_name": "시행령"},
        {"origin": "s", "full_name": "전자금융감독규정\n[시행 2025. 2. 5.]", "short_name": "감독규정"},
        {"origin": "r", "full_name": "전자금융감독규정시행세칙\n[시행 2025. 2. 5.]", "short_name": "시행세칙"},
    ],
    "a": [
        {"seq": 1, "id_aa": None, "id_a": None, "title_a": "제1장 총칙", "content_a": "제1장 총칙"},   # 장/절 제목행: id_a 비움
        {"seq": 2, "id_aa": "A1", "id_a": "A1", "title_a": "제1조(목적)", "content_a": "제1조(목적) 이 법은 ..."},
        {"seq": 3, "id_aa": "A2", "id_a": "A2", "title_a": "제2조(정의)", "content_a": "제2조(정의) 이 법에서 ..."},
        {"seq": 4, "id_aa": "A2", "id_a": "A2_1h", "title_a": "제2조(정의)", "content_a": " 1. “전자금융거래”라 함은 ..."},  # 항/호
        {"seq": 5, "id_aa": "A3", "id_a": "A3", "title_a": "제3조", "content_a": "제3조 ..."},
    ],
    "e": [
        {"seq": 1, "id_e": "E1", "content_e": "제1조(목적) ..."},
        {"seq": 2, "id_e": "E2", "content_e": "제2조 ..."},
    ],
    "s": [{"seq": 1, "id_s": "S1", "content_s": "제1조 ..."}],
    "r": [{"seq": 1, "id_r": "R1", "content_r": "제1조 ..."}],
    "annex": [
        {"origin": "a", "id_annex": "A_B1", "annex_no": "별표 1", "id_src": "A3",
         "annex_name": "별표 예시명", "annex_url": "https://..."},
    ],
    "ref": [{"id": 1, "id_origin": "A2", "ref_type": "...", "ref_target": "...", "ref_content": "..."}],
    "rdb": [
        {"id": 1, "id_start": "A1", "id_end": "E1"},
        {"id": 2, "id_start": "A2", "id_end": "E2"},
        {"id": 3, "id_start": "A3", "id_end": "S1"},  # 중간단(시행령) 건너뛰고 감독규정으로 직접
    ],
}


def build(out_path: str) -> str:
    wb = Workbook()
    wb.remove(wb.active)
    for sheet in LOAD_ORDER:
        _table, cols = SHEETS[sheet]
        ws = wb.create_sheet(title=sheet)
        ws.append(cols)
        for ex in EXAMPLES.get(sheet, []):
            ws.append([ex.get(c) for c in cols])
        ws.freeze_panes = "A2"
    wb.save(out_path)
    return out_path
