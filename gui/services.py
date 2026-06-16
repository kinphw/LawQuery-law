"""
GUI ↔ 엔진 브리지. reader / validator / loader / exporter 를 재사용한다.
GUI는 이 모듈만 호출하고, 엔진 세부는 모른다.
"""
from common.schema_map import SHEETS
from reader.excel_reader import read_workbook
from validator.validate import validate as _validate
from loader.loader import load as _load
from exporter.db_export import (
    list_law_dbs,
    read_law,
    code_of,
    write_workbook,
)


def _ensure_all_sheets(data: dict) -> dict:
    for sheet in SHEETS:
        data.setdefault(sheet, [])
    return data


def list_dbs(target: str):
    return list_law_dbs(target)


def load_db(code: str, target: str) -> dict:
    return _ensure_all_sheets(read_law(code, target))


def load_excel(path: str):
    data, cols, all_sheets = read_workbook(path)
    return _ensure_all_sheets(data), cols, all_sheets


def validate(data: dict):
    """메모리/DB 데이터 검증. cols=전체, all_sheets=현재 시트들."""
    cols = {s: SHEETS[s][1] for s in data}
    return _validate(data, cols, list(data.keys()))


def save_db(code: str, data: dict, target: str, recreate: bool = False):
    return _load(code, data, target=target, recreate=recreate)


def write_excel(data: dict, out_path: str):
    return write_workbook(data, out_path)
