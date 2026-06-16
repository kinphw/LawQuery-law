"""
엑셀 → 파이썬 자료구조.

매핑(schema_map.SHEETS)된 시트·컬럼만 추출한다.
- 빈 셀 → None
- 정수형 float("1.0") → int(1)  (엑셀 숫자셀 보정)
- 좌우 공백 제거, 빈 문자열 → None
- 전부 빈 행은 스킵
"""
import pandas as pd

from common.schema_map import SHEETS


def _clean(v):
    if v is None:
        return None
    if isinstance(v, float):
        if pd.isna(v):
            return None
        if v.is_integer():
            return int(v)
        return v
    if isinstance(v, str):
        v = v.strip()
        return v or None
    return v


def read_workbook(path):
    """returns (data, cols, all_sheets)
    data: {sheet: [ {col: value}, ... ]}
    cols: {sheet: [실제 엑셀 컬럼...]}  (검증용)
    all_sheets: 엑셀의 모든 시트명
    """
    xl = pd.ExcelFile(path)
    all_sheets = list(xl.sheet_names)
    data, cols = {}, {}

    for sheet, (_table, want) in SHEETS.items():
        if sheet not in all_sheets:
            continue
        df = xl.parse(sheet)
        cols[sheet] = [str(c) for c in df.columns]
        rows = []
        for _, r in df.iterrows():
            row = {c: (_clean(r[c]) if c in df.columns else None) for c in want}
            if any(v is not None for v in row.values()):
                rows.append(row)
        data[sheet] = rows

    return data, cols, all_sheets
