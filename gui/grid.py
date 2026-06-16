"""
편집 가능한 표 위젯.
  TableTab : Treeview(목록) + 추가/편집/삭제. 행은 모달 폼(RowForm)으로 편집.
  RowForm  : 컬럼별 입력칸. 긴 텍스트 컬럼은 멀티라인.
backing list(rows)는 외부 data[sheet] 의 참조라 편집이 곧 모델에 반영된다.
"""
import tkinter as tk
from tkinter import ttk, messagebox

# 멀티라인 입력으로 띄울 긴 텍스트 컬럼
LONG_COLS = {
    "content_a", "content_e", "content_s", "content_r",
    "content_a_sched", "content_e_sched", "content_s_sched", "content_r_sched",
    "full_name", "title_a", "ref_content", "ref_target", "annex_url", "annex_name",
    "content_pa", "penalty_a_phy", "penalty_a_log", "penalty_e_log",
    "item_a_phy", "item_a_log", "content_pe", "category",
}


def _disp(v, width=70):
    if v is None:
        return ""
    s = str(v).replace("\n", "⏎")
    return s if len(s) <= width else s[: width - 1] + "…"


class RowForm(tk.Toplevel):
    def __init__(self, master, title, columns, row, on_ok):
        super().__init__(master)
        self.title(title)
        self.columns = columns
        self.on_ok = on_ok
        self.widgets = {}
        self.transient(master)
        self.grab_set()

        frm = ttk.Frame(self, padding=10)
        frm.pack(fill="both", expand=True)
        for i, c in enumerate(columns):
            ttk.Label(frm, text=c).grid(row=i, column=0, sticky="nw", padx=4, pady=2)
            val = "" if row.get(c) is None else str(row.get(c))
            if c in LONG_COLS:
                w = tk.Text(frm, width=72, height=4, wrap="word")
                w.insert("1.0", val)
            else:
                w = ttk.Entry(frm, width=72)
                w.insert(0, val)
            w.grid(row=i, column=1, sticky="we", padx=4, pady=2)
            self.widgets[c] = w
        frm.columnconfigure(1, weight=1)

        btns = ttk.Frame(frm)
        btns.grid(row=len(columns), column=0, columnspan=2, pady=(10, 0))
        ttk.Button(btns, text="확인", command=self._ok).pack(side="left", padx=4)
        ttk.Button(btns, text="취소", command=self.destroy).pack(side="left", padx=4)
        self.bind("<Escape>", lambda e: self.destroy())

    def _value(self, c):
        w = self.widgets[c]
        s = w.get("1.0", "end-1c") if isinstance(w, tk.Text) else w.get()
        s = s.strip()
        return s if s else None

    def _ok(self):
        self.on_ok({c: self._value(c) for c in self.columns})
        self.destroy()


class TableTab(ttk.Frame):
    def __init__(self, master, sheet, columns, rows):
        super().__init__(master)
        self.sheet = sheet
        self.columns = columns
        self.rows = rows  # 외부 data[sheet] 참조

        bar = ttk.Frame(self)
        bar.pack(fill="x", pady=3)
        ttk.Button(bar, text="＋ 추가", command=self.add).pack(side="left", padx=2)
        ttk.Button(bar, text="✎ 편집", command=self.edit).pack(side="left", padx=2)
        ttk.Button(bar, text="🗑 삭제", command=self.delete).pack(side="left", padx=2)
        self.count_lbl = ttk.Label(bar, text="")
        self.count_lbl.pack(side="right", padx=6)

        wrap = ttk.Frame(self)
        wrap.pack(fill="both", expand=True)
        self.tree = ttk.Treeview(wrap, columns=columns, show="headings", selectmode="browse")
        for c in columns:
            self.tree.heading(c, text=c)
            self.tree.column(c, width=max(60, min(300, len(c) * 13)), anchor="w")
        ysb = ttk.Scrollbar(wrap, orient="vertical", command=self.tree.yview)
        xsb = ttk.Scrollbar(wrap, orient="horizontal", command=self.tree.xview)
        self.tree.configure(yscrollcommand=ysb.set, xscrollcommand=xsb.set)
        self.tree.grid(row=0, column=0, sticky="nsew")
        ysb.grid(row=0, column=1, sticky="ns")
        xsb.grid(row=1, column=0, sticky="ew")
        wrap.rowconfigure(0, weight=1)
        wrap.columnconfigure(0, weight=1)
        self.tree.bind("<Double-1>", lambda e: self.edit())
        self.refresh()

    def refresh(self):
        self.tree.delete(*self.tree.get_children())
        for i, row in enumerate(self.rows):
            self.tree.insert("", "end", iid=str(i),
                             values=[_disp(row.get(c)) for c in self.columns])
        self.count_lbl.config(text=f"{len(self.rows)} 행")

    def _selected(self):
        sel = self.tree.selection()
        return int(sel[0]) if sel else None

    def add(self):
        RowForm(self, f"[{self.sheet}] 행 추가", self.columns, {},
                lambda r: (self.rows.append(r), self.refresh()))

    def edit(self):
        idx = self._selected()
        if idx is None:
            messagebox.showinfo("편집", "행을 선택하세요.")
            return
        RowForm(self, f"[{self.sheet}] 행 편집", self.columns, self.rows[idx],
                lambda r: (self.rows.__setitem__(idx, r), self.refresh()))

    def delete(self):
        idx = self._selected()
        if idx is None:
            messagebox.showinfo("삭제", "행을 선택하세요.")
            return
        if messagebox.askyesno("삭제", "선택한 행을 삭제할까요?"):
            del self.rows[idx]
            self.refresh()
