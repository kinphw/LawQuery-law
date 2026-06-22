"""
LawQuery 법령 편집기 (tkinter) — 레코드 단위 편집.

  - 타깃(dev/prod) + 법 DB 선택 → 불러오기 → 표 탭에서 행 추가/편집/삭제 (즉시 DB 반영)
  - 새 법(엑셀): 벌크 생성 → 자동으로 편집 모드 진입
  - 검증 / 엑셀 내보내기
전체 교체 저장 없음. 각 동작이 지정 레코드 하나만 INSERT/UPDATE/DELETE.
"""
import os
import tkinter as tk
from tkinter import ttk, messagebox, filedialog, simpledialog

from common.schema_map import LOAD_ORDER, SHEETS
from gui import services
from gui.grid import TableTab
from exporter.db_export import code_of


class App(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("LawQuery 법령 편집기")
        self.geometry("1150x740")
        self.data = None
        self.code = None
        self.editor = None
        self.tabs = {}

        self._toolbar()
        self.nb = ttk.Notebook(self)
        self.nb.pack(fill="both", expand=True, padx=6, pady=(0, 4))
        self.status = ttk.Label(self, text="준비됨", anchor="w", relief="sunken")
        self.status.pack(fill="x", side="bottom")

        self._refresh_dbs()

    def _toolbar(self):
        bar = ttk.Frame(self, padding=6)
        bar.pack(fill="x")
        ttk.Label(bar, text="타깃").pack(side="left")
        self.target = tk.StringVar(value="dev")
        cb = ttk.Combobox(bar, textvariable=self.target, values=["dev", "prod"],
                          width=6, state="readonly")
        cb.pack(side="left", padx=(2, 12))
        cb.bind("<<ComboboxSelected>>", lambda e: self._refresh_dbs())

        ttk.Label(bar, text="법 DB").pack(side="left")
        self.db_var = tk.StringVar()
        self.db_cb = ttk.Combobox(bar, textvariable=self.db_var, width=18, state="readonly")
        self.db_cb.pack(side="left", padx=2)
        ttk.Button(bar, text="새로고침", command=self._refresh_dbs).pack(side="left", padx=2)
        ttk.Button(bar, text="불러오기", command=self.load_db).pack(side="left", padx=2)

        ttk.Separator(bar, orient="vertical").pack(side="left", fill="y", padx=8)
        ttk.Button(bar, text="빈 템플릿", command=self.make_template).pack(side="left", padx=2)
        ttk.Button(bar, text="새 법(엑셀)", command=self.import_excel).pack(side="left", padx=2)
        ttk.Button(bar, text="검증", command=self.do_validate).pack(side="left", padx=2)
        ttk.Button(bar, text="엑셀 내보내기", command=self.export_excel).pack(side="left", padx=2)

        ttk.Separator(bar, orient="vertical").pack(side="left", fill="y", padx=8)
        ttk.Button(bar, text="법령 목록 관리", command=self.open_registry).pack(side="left", padx=2)

    def open_registry(self):
        """ldb_auth.law_registry(법령 카탈로그) 관리 창. per-law 편집과 분리된 관리자 영역."""
        from gui.registry_window import RegistryWindow
        RegistryWindow(self, self.target.get())

    def make_template(self):
        out = filedialog.asksaveasfilename(
            defaultextension=".xlsx", initialfile="template_law.xlsx",
            filetypes=[("Excel", "*.xlsx")],
        )
        if not out:
            return
        try:
            from template.make_template import build
            build(out)
            self.set_status(f"빈 템플릿 생성: {out}")
            if messagebox.askyesno("템플릿 생성", f"생성됨:\n{out}\n\n엑셀로 열까요?"):
                os.startfile(out)
        except Exception as ex:
            messagebox.showerror("템플릿 생성 실패", str(ex))

    def set_status(self, msg):
        self.status.config(text=msg)
        self.update_idletasks()

    def _refresh_dbs(self):
        try:
            dbs = services.list_dbs(self.target.get())
            self.db_cb["values"] = dbs
            if dbs and self.db_var.get() not in dbs:
                self.db_var.set(dbs[0])
            self.set_status(f"법 DB {len(dbs)}개 ({self.target.get()})")
        except Exception as ex:
            self.set_status(f"DB 목록 오류: {ex}")

    def _build_tabs(self, title):
        for t in list(self.nb.tabs()):
            self.nb.forget(t)
        self.tabs = {}
        for sheet in LOAD_ORDER:
            cols = SHEETS[sheet][1]
            tab = TableTab(self.nb, sheet, cols, self.data[sheet], self.editor,
                           on_status=self.set_status)
            n = len(self.data[sheet])
            self.nb.add(tab, text=f"{sheet} ({n})" if n else sheet)
            self.tabs[sheet] = tab
        # rdb 매핑 점검 탭(하위규정 조문별 상위 위임 현황·편집) — 로드된 법에 묶임
        try:
            from gui.rdb_map_tab import RdbMapTab
            self.nb.add(RdbMapTab(self.nb, self.code, self.target.get()), text="🔗 rdb 점검")
        except Exception as ex:
            self.set_status(f"rdb 점검 탭 로드 실패: {ex}")
        self.title(f"LawQuery 법령 편집기 — {title}")

    # ---------- 동작 ----------
    def _open_live(self, code, title):
        if self.target.get() == "prod":
            if not messagebox.askyesno(
                "운영 편집 주의",
                f"운영(prod) DB ldb_{code} 를 직접 편집합니다.\n"
                "모든 변경이 즉시 반영됩니다. 계속할까요?",
            ):
                return False
        self.set_status(f"여는 중: ldb_{code} …")
        self.editor, self.data = services.LiveEditor.open(code, self.target.get())
        self.code = code
        self._build_tabs(title)
        self.set_status(f"편집 중: ldb_{code} @ {self.target.get()} (변경 즉시 반영)")
        return True

    def load_db(self):
        db = self.db_var.get()
        if not db:
            return
        try:
            self._open_live(code_of(db), db)
        except Exception as ex:
            messagebox.showerror("불러오기 실패", str(ex))

    def import_excel(self):
        path = filedialog.askopenfilename(filetypes=[("Excel", "*.xlsx")])
        if not path:
            return
        code = simpledialog.askstring("법 코드", "새 법 코드(예: c) → ldb_<코드>:", parent=self)
        if not code:
            return
        code = code.strip()
        try:
            data, _c, _a = services.load_excel(path)
            errors, warnings = services.validate(data)
            if errors:
                _report(self, errors, warnings)
                messagebox.showerror("생성 차단", "검증 오류를 해결한 엑셀로 다시 시도하세요.")
                return
            if not messagebox.askyesno(
                "새 법 생성",
                f"ldb_{code} @ {self.target.get()} 를 생성합니다.\n"
                "(같은 이름이 있으면 전체 교체) 계속할까요?",
            ):
                return
            self.set_status(f"생성 중: ldb_{code} …")
            services.create_law(code, data, self.target.get(), recreate=True)
            self._refresh_dbs()
            self.db_var.set(f"ldb_{code}")
            # 생성 직후 편집 모드로 진입
            self._open_live(code, f"ldb_{code} (신규)")
        except Exception as ex:
            messagebox.showerror("새 법 생성 실패", str(ex))

    def do_validate(self):
        if self.data is None:
            messagebox.showinfo("검증", "먼저 법을 불러오세요.")
            return
        errors, warnings = services.validate(self.data)
        _report(self, errors, warnings)

    def export_excel(self):
        if self.data is None:
            return
        out = filedialog.asksaveasfilename(
            defaultextension=".xlsx",
            initialfile=f"ldb_{self.code or 'law'}.xlsx",
            filetypes=[("Excel", "*.xlsx")],
        )
        if not out:
            return
        try:
            services.write_excel(self.data, out)
            self.set_status(f"엑셀 저장: {out}")
        except Exception as ex:
            messagebox.showerror("내보내기 실패", str(ex))


def _report(master, errors, warnings):
    win = tk.Toplevel(master)
    win.title("검증 결과")
    win.geometry("680x420")
    txt = tk.Text(win, wrap="word")
    txt.pack(fill="both", expand=True)
    if not errors and not warnings:
        txt.insert("end", "✅ 검증 통과 (오류·경고 없음)\n")
    if errors:
        txt.insert("end", f"❌ 오류 {len(errors)}건:\n")
        for e in errors:
            txt.insert("end", f"  - {e}\n")
        txt.insert("end", "\n")
    if warnings:
        txt.insert("end", f"⚠️ 경고 {len(warnings)}건:\n")
        for w in warnings:
            txt.insert("end", f"  - {w}\n")
    txt.config(state="disabled")


def main():
    App().mainloop()


if __name__ == "__main__":
    main()
