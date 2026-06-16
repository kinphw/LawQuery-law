"""
LawQuery 법령 편집기 (tkinter).

  - 타깃(dev/prod) + 법 DB 선택 → 불러오기 → 표 탭에서 편집
  - 새 법(엑셀) 가져오기 / 검증 / 엑셀로 내보내기 / 저장(DB)
편집 엔진은 CLI와 동일(reader/validator/loader/exporter). gui.services 만 호출.
"""
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
        self.data = None     # 현재 편집 중인 법 데이터
        self.code = None     # 현재 법 코드
        self.tabs = {}

        self._toolbar()
        self.nb = ttk.Notebook(self)
        self.nb.pack(fill="both", expand=True, padx=6, pady=(0, 4))
        self.status = ttk.Label(self, text="준비됨", anchor="w", relief="sunken")
        self.status.pack(fill="x", side="bottom")

        self._refresh_dbs()

    # ---------- UI ----------
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
        ttk.Button(bar, text="새 법(엑셀)", command=self.import_excel).pack(side="left", padx=2)
        ttk.Button(bar, text="검증", command=self.do_validate).pack(side="left", padx=2)
        ttk.Button(bar, text="엑셀 내보내기", command=self.export_excel).pack(side="left", padx=2)
        ttk.Button(bar, text="💾 저장(DB)", command=self.save_db).pack(side="left", padx=2)

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
            tab = TableTab(self.nb, sheet, cols, self.data[sheet])
            n = len(self.data[sheet])
            self.nb.add(tab, text=f"{sheet} ({n})" if n else sheet)
            self.tabs[sheet] = tab
        self.title(f"LawQuery 법령 편집기 — {title}")

    # ---------- 동작 ----------
    def load_db(self):
        db = self.db_var.get()
        if not db:
            return
        self.code = code_of(db)
        try:
            self.set_status(f"불러오는 중: {db} …")
            self.data = services.load_db(self.code, self.target.get())
            self._build_tabs(db)
            self.set_status(f"불러옴: {db}")
        except Exception as ex:
            messagebox.showerror("불러오기 실패", str(ex))

    def import_excel(self):
        path = filedialog.askopenfilename(filetypes=[("Excel", "*.xlsx")])
        if not path:
            return
        code = simpledialog.askstring("법 코드", "새 법 코드(예: c) → ldb_<코드>:", parent=self)
        if not code:
            return
        try:
            self.data, _c, _a = services.load_excel(path)
            self.code = code.strip()
            self._build_tabs(f"(엑셀) → ldb_{self.code}")
            self.set_status(f"엑셀 로드: {path}")
        except Exception as ex:
            messagebox.showerror("엑셀 로드 실패", str(ex))

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

    def save_db(self):
        if self.data is None or not self.code:
            messagebox.showinfo("저장", "먼저 법을 불러오세요.")
            return
        errors, warnings = services.validate(self.data)
        if errors:
            _report(self, errors, warnings)
            messagebox.showerror("저장 차단", "검증 오류를 먼저 해결하세요.")
            return
        tgt = self.target.get()
        if not messagebox.askyesno(
            "저장 확인",
            f"ldb_{self.code} @ {tgt} 에 저장합니다.\n"
            "기존 데이터는 전체 교체(TRUNCATE 후 재적재)됩니다.\n계속할까요?",
        ):
            return
        try:
            self.set_status("저장 중 …")
            dbname, counts = services.save_db(self.code, self.data, tgt)
            total = sum(counts.values())
            self.set_status(f"저장 완료: {dbname} ({total} 행)")
            messagebox.showinfo("완료", f"{dbname} 저장 완료 ({total} 행).")
            self._refresh_dbs()
        except Exception as ex:
            messagebox.showerror("저장 실패", str(ex))


def _report(master, errors, warnings):
    win = tk.Toplevel(master)
    win.title("검증 결과")
    win.geometry("680x420")
    txt = tk.Text(win, wrap="word")
    txt.pack(fill="both", expand=True)
    if not errors and not warnings:
        txt.insert("end", "✅ 검증 통과 (오류·경고 없음)\n")
    if errors:
        txt.insert("end", f"❌ 오류 {len(errors)}건 (저장 차단):\n")
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
