"""
LawQuery 법령 엑셀 → DB 적재 파이프라인 CLI.

  python run.py template -o template_law.xlsx
  python run.py ingest --law c --excel data/foo.xlsx                 # dry-run(검증만)
  python run.py ingest --law c --excel data/foo.xlsx --apply         # dev(localhost) 적재
  python run.py ingest --law c --excel data/foo.xlsx --apply --target prod --recreate
"""
import argparse
import re
import sys

# Windows 콘솔(cp949)에서도 한글·이모지 출력되도록 UTF-8 강제
for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8")
    except Exception:
        pass

from reader.excel_reader import read_workbook
from validator.validate import validate
from loader.loader import load
from common.db import describe_target
from common.schema_map import SHEETS, LOAD_ORDER

LAW_RE = re.compile(r"[a-z0-9_]{1,16}")


def _summary(data):
    print("\n── 읽은 시트 ──")
    for s in LOAD_ORDER:
        if s in data:
            print(f"  {s:10s} {len(data[s]):>5d} 행")


def cmd_template(args):
    from template.make_template import build
    print(f"✅ 템플릿 생성: {build(args.out)}")


def cmd_ingest(args):
    if not LAW_RE.fullmatch(args.law):
        sys.exit("❌ --law 는 영소문자/숫자/_ 1~16자여야 합니다.")

    print(f"📖 읽는 중: {args.excel}")
    data, cols, all_sheets = read_workbook(args.excel)
    _summary(data)

    errors, warnings = validate(data, cols, all_sheets)
    if warnings:
        print("\n⚠️  경고:")
        for w in warnings:
            print(f"  - {w}")
    if errors:
        print("\n❌ 오류(적재 차단):")
        for e in errors:
            print(f"  - {e}")
        sys.exit(1)
    print("\n✅ 검증 통과 (오류 0)")

    if not args.apply:
        print("\n[dry-run] 적재하지 않음. 실제 적재하려면 --apply 추가.")
        print(f"          타깃 예정: {args.target} ({describe_target(args.target)}) → ldb_{args.law}")
        return

    tag = " [recreate]" if args.recreate else ""
    print(f"\n🚀 적재 → ldb_{args.law} @ {args.target} ({describe_target(args.target)}){tag}")
    dbname, counts = load(args.law, data, target=args.target, recreate=args.recreate)
    print(f"✅ 완료: {dbname}")
    for s, n in counts.items():
        print(f"    {SHEETS[s][0]:14s} {n:>5d} 행")


def cmd_export(args):
    if not LAW_RE.fullmatch(args.law):
        sys.exit("❌ --law 는 영소문자/숫자/_ 1~16자여야 합니다.")
    from exporter.db_export import export_to_excel
    out, data = export_to_excel(args.law, args.out, target=args.target)
    print(f"✅ export: ldb_{args.law} ({args.target}) → {out}")
    for s in LOAD_ORDER:
        if data.get(s):
            print(f"    {s:10s} {len(data[s]):>5d} 행")


def cmd_gui(_args):
    from gui.app import main as gui_main
    gui_main()


def main():
    ap = argparse.ArgumentParser(description="LawQuery 법령 엑셀 → DB 적재 파이프라인")
    sub = ap.add_subparsers(dest="cmd", required=True)

    t = sub.add_parser("template", help="빈 엑셀 템플릿 생성")
    t.add_argument("-o", "--out", default="template_law.xlsx")
    t.set_defaults(func=cmd_template)

    g = sub.add_parser("ingest", help="엑셀 검증·적재")
    g.add_argument("--law", required=True, help="법 코드(예: c) → ldb_<코드>")
    g.add_argument("--excel", required=True, help="입력 엑셀 경로")
    g.add_argument("--apply", action="store_true", help="실제 적재(기본은 dry-run 검증만)")
    g.add_argument("--target", choices=["dev", "prod"], default="dev")
    g.add_argument("--recreate", action="store_true", help="기존 ldb_<코드> DROP 후 재생성")
    g.set_defaults(func=cmd_ingest)

    e = sub.add_parser("export", help="기존 법 DB → 엑셀(템플릿 형식)")
    e.add_argument("--law", required=True, help="법 코드(예: j)")
    e.add_argument("-o", "--out", default=None, help="출력 엑셀 경로(기본: ldb_<코드>.xlsx)")
    e.add_argument("--target", choices=["dev", "prod"], default="dev")
    e.set_defaults(func=cmd_export)

    u = sub.add_parser("gui", help="데스크톱 GUI 실행 (법 선택·표 편집·저장·가져오기)")
    u.set_defaults(func=cmd_gui)

    args = ap.parse_args()
    if getattr(args, "cmd", None) == "export" and not args.out:
        args.out = f"ldb_{args.law}.xlsx"
    args.func(args)


if __name__ == "__main__":
    main()
