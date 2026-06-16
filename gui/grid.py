"""
편집 가능한 표 위젯 (레코드 단위 즉시 반영).
  TableTab : Treeview + 추가/편집/삭제. 각 동작이 editor(LiveEditor)를 통해
             지정 레코드 하나만 INSERT/UPDATE/DELETE 한다. (전체 교체 아님)
  RowForm  : 컬럼별 입력칸(긴 텍스트=멀티라인). '__pk'는 화면에 안 보임.
"""
import tkinter as tk
from tkinter import ttk, messagebox

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
    def __init__(self, master, sheet, columns, rows, editor, on_status=None):
        super().__init__(master)
        self.sheet = sheet
        self.columns = columns
        self.rows = rows          # data[sheet] 참조 (각 행에 __pk 포함)
        self.editor = editor      # LiveEditor
        self.on_status = on_status or (lambda m: None)

        bar = ttk.Frame(self)
        bar.pack(fill="x", pady=3)
        ttk.Button(bar, text="＋ 추가", command=self.add).pack(side="left", padx=2)
        ttk.Button(bar, text="✎ 편집", command=self.edit).pack(side="left", padx=2)
        ttk.Button(bar, text="🗑 삭제", command=self.delete).pack(side="left", padx=2)
        ttk.Label(bar, text="변경은 즉시 DB 반영").pack(side="left", padx=10)
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

    # ----- 레코드 단위 동작(즉시 반영) -----
    def add(self):
        RowForm(self, f"[{self.sheet}] 행 추가", self.columns, {}, self._on_add)

    def _on_add(self, row):
        try:
            pk = self.editor.insert(self.sheet, row)
        except Exception as ex:
            messagebox.showerror("추가 실패", str(ex))
            return
        row["__pk"] = pk
        self.rows.append(row)
        self.refresh()
        self.on_status(f"[{self.sheet}] 1건 추가 (pk={pk})")

    def edit(self):
        idx = self._selected()
        if idx is None:
            messagebox.showinfo("편집", "행을 선택하세요.")
            return
        RowForm(self, f"[{self.sheet}] 행 편집", self.columns, self.rows[idx],
                lambda r: self._on_edit(idx, r))

    def _on_edit(self, idx, row):
        pk = self.rows[idx].get("__pk")
        try:
            self.editor.update(self.sheet, pk, row)
        except Exception as ex:
            messagebox.showerror("수정 실패", str(ex))
            return
        row["__pk"] = pk
        self.rows[idx] = row
        self.refresh()
        self.on_status(f"[{self.sheet}] 1건 수정 (pk={pk})")

    def delete(self):
        idx = self._selected()
        if idx is None:
            messagebox.showinfo("삭제", "행을 선택하세요.")
            return
        pk = self.rows[idx].get("__pk")
        if not messagebox.askyesno("삭제", "선택한 행을 DB에서 삭제할까요?"):
            return
        try:
            self.editor.delete(self.sheet, pk)
        except Exception as ex:
            messagebox.showerror("삭제 실패", str(ex))
            return
        del self.rows[idx]
        self.refresh()
        self.on_status(f"[{self.sheet}] 1건 삭제 (pk={pk})")
