"""
GUI ↔ 엔진 브리지.

편집 모델:
  - 기존 법은 LiveEditor 로 연다 → 각 행이 '__pk' 보유 → 편집은 그 레코드만 즉시 반영.
  - 새 법은 create_law(벌크 임포트)로 생성 후, 같은 코드를 LiveEditor 로 다시 연다.
"""
from common.schema_map import SHEETS
from reader.excel_reader import read_workbook
from validator.validate import validate as _validate
from loader.loader import load as _load
from exporter.db_export import list_law_dbs, write_workbook
from editor import record_db


def list_dbs(target: str):
    return list_law_dbs(target)


def load_excel(path: str):
    return read_workbook(path)  # (data, cols, all_sheets)


def validate(data: dict):
    cols = {s: SHEETS[s][1] for s in data}
    return _validate(data, cols, list(data.keys()))


def create_law(code: str, data: dict, target: str, recreate: bool = True):
    """새 법 벌크 생성(엑셀 → ldb_<code>). 편집은 이후 LiveEditor 로."""
    return _load(code, data, target=target, recreate=recreate)


def write_excel(data: dict, out_path: str):
    return write_workbook(data, out_path)


class LiveEditor:
    """ldb_<code>@target 의 레코드 단위 편집 핸들. 편집=즉시 1 레코드 반영."""

    def __init__(self, code: str, target: str):
        self.code = code
        self.target = target

    @classmethod
    def open(cls, code: str, target: str):
        record_db.ensure_editable(code, target)          # PK 없는 테이블에 _pk 부여
        data = record_db.read_law_editable(code, target)  # 행+__pk 로드
        for s in SHEETS:
            data.setdefault(s, [])
        return cls(code, target), data

    def insert(self, sheet, row):
        return record_db.insert_record(self.code, sheet, row, self.target)

    def update(self, sheet, pk, row):
        return record_db.update_record(self.code, sheet, pk, row, self.target)

    def delete(self, sheet, pk):
        return record_db.delete_record(self.code, sheet, pk, self.target)

    def split_article(self, sheet, pk, level):
        """조 1개를 항/호 자식으로 분리 + rdb 자동재연결 (트랜잭션)."""
        return record_db.split_article_op(self.code, sheet, pk, level, self.target)
