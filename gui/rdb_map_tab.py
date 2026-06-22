"""
rdb 매핑 점검 탭 — 하위규정 조문별로 상위규정 위임(rdb) 현황을 보고 직접 추가/수정/삭제.

좌: 선택 하위 단(e/s/r/b)의 조문(id+본문). 미매핑 행은 노란 배지.
우: 선택 조문(id_end)을 받는 rdb 엣지(상위 id + 본문) + 추가(픽커/직접입력)·수정·삭제.
현재 메인 에디터에 로드된 법(code)·타깃에 묶인다.
"""
import tkinter as tk
from tkinter import ttk, messagebox

from editor import rdb_map_db


def _snip(s, n=90):
    t = " ".join(str(s or "").split())
    return (t[:n] + "…") if len(t) > n else t


class RdbMapTab(ttk.Frame):
    def __init__(self, master, code, target):
        super().__init__(master, padding=6)
        self.code = code
        self.target = target
        self.levels = []
        self.cur_id = None  # 선택된 하위 조문 id(id_end)

        try:
            rdb_map_db.ensure_pk(code, target)
            self.levels = rdb_map_db.levels(code, target)
        except Exception as ex:
            messagebox.showerror("rdb 점검 초기화 실패", str(ex), parent=self)

        self._build()
        if self.levels:
            self.v_level.set("e" if "e" in self.levels else self.levels[-1])
            self._load_lower()

    # ---------- UI ----------
    def _build(self):
        bar = ttk.Frame(self)
        bar.pack(fill="x", pady=(0, 4))
        ttk.Label(bar, text="하위 단").pack(side="left")
        self.v_level = tk.StringVar()
        cb = ttk.Combobox(bar, textvariable=self.v_level, width=6, state="readonly", values=self.levels)
        cb.pack(side="left", padx=4)
        cb.bind("<<ComboboxSelected>>", lambda e: self._load_lower())
        ttk.Button(bar, text="새로고침", command=self._load_lower).pack(side="left")
        self.v_unmapped = tk.IntVar(value=0)
        ttk.Checkbutton(bar, text="미매핑만 보기", variable=self.v_unmapped, command=self._load_lower).pack(side="left", padx=8)
        self.lbl_count = ttk.Label(bar, text="")
        self.lbl_count.pack(side="left", padx=8)

        # 하단 변경 로그(실제 DB 반영 시에만 기록)
        logf = ttk.LabelFrame(self, text="변경 로그 (실제 DB 반영 시 기록)", padding=2)
        logf.pack(side="bottom", fill="x")
        self.log = tk.Text(logf, height=5, wrap="none", state="disabled",
                           background="#f7f7f7", font=("Consolas", 9))
        self.log.pack(side="left", fill="both", expand=True)
        logsb = ttk.Scrollbar(logf, orient="vertical", command=self.log.yview)
        logsb.pack(side="left", fill="y")
        self.log.configure(yscrollcommand=logsb.set)
        ttk.Button(logf, text="지우기", command=self._clear_log).pack(side="left", padx=2)

        paned = ttk.Panedwindow(self, orient="horizontal")
        paned.pack(fill="both", expand=True)

        # 좌: 하위 조문
        left = ttk.Frame(paned)
        self.left = ttk.Treeview(left, columns=("id", "content"), show="headings")
        self.left.heading("id", text="id")
        self.left.column("id", width=100, anchor="w")
        self.left.heading("content", text="하위규정 본문")
        self.left.column("content", width=440, anchor="w")
        self.left.tag_configure("unmapped", background="#fff3cd")
        self.left.pack(side="left", fill="both", expand=True)
        lsb = ttk.Scrollbar(left, orient="vertical", command=self.left.yview)
        lsb.pack(side="left", fill="y")
        self.left.configure(yscrollcommand=lsb.set)
        self.left.bind("<<TreeviewSelect>>", self._on_pick_lower)
        paned.add(left, weight=1)

        # 우: 상위 매핑 현황 + 편집
        right = ttk.Frame(paned)
        self.lbl_sel = ttk.Label(right, text="상위규정 매핑 — 왼쪽에서 하위 조문을 선택하세요")
        self.lbl_sel.pack(anchor="w")
        self.right = ttk.Treeview(right, columns=("id_start", "content"), show="headings", height=10)
        self.right.heading("id_start", text="상위 id")
        self.right.column("id_start", width=100, anchor="w")
        self.right.heading("content", text="상위규정 본문")
        self.right.column("content", width=360, anchor="w")
        self.right.pack(fill="both", expand=True)

        rb = ttk.Frame(right)
        rb.pack(fill="x", pady=2)
        ttk.Button(rb, text="선택 매핑 수정", command=self._edit).pack(side="left")
        ttk.Button(rb, text="선택 매핑 삭제", command=self._delete).pack(side="left", padx=4)

        addf = ttk.LabelFrame(right, text="상위규정 추가 (검색 픽커 또는 id 직접 입력)", padding=6)
        addf.pack(fill="x", pady=4)
        ttk.Label(addf, text="상위 id").grid(row=0, column=0, padx=2)
        self.v_start = tk.StringVar()
        ttk.Entry(addf, textvariable=self.v_start, width=16).grid(row=0, column=1, padx=2)
        ttk.Button(addf, text="검색…", command=self._open_picker).grid(row=0, column=2, padx=2)
        ttk.Button(addf, text="추가", command=self._add).grid(row=0, column=3, padx=6)
        paned.add(right, weight=1)

    # ---------- 데이터 ----------
    def _load_lower(self):
        lv = self.v_level.get()
        if not lv:
            return
        try:
            rows = rdb_map_db.lower_rows(self.code, lv, self.target)
            mapped = rdb_map_db.mapped_id_ends(self.code, self.target)
        except Exception as ex:
            messagebox.showerror("조회 실패", str(ex), parent=self)
            return
        only_un = self.v_unmapped.get() == 1
        self.left.delete(*self.left.get_children())
        shown = unmapped_n = 0
        for r in rows:
            un = r["id"] not in mapped
            if un:
                unmapped_n += 1
            if only_un and not un:
                continue
            try:
                self.left.insert("", "end", iid=r["id"],
                                 values=(r["id"], _snip(r["content"])),
                                 tags=("unmapped",) if un else ())
                shown += 1
            except tk.TclError:
                pass  # 중복 id 방어
        self.lbl_count.config(text=f"표시 {shown}행 · 미매핑 {unmapped_n}")
        self.right.delete(*self.right.get_children())
        self.lbl_sel.config(text="상위규정 매핑 — 왼쪽에서 하위 조문을 선택하세요")
        self.cur_id = None

    def _on_pick_lower(self, _e=None):
        sel = self.left.selection()
        if not sel:
            return
        self.cur_id = sel[0]
        self.lbl_sel.config(text=f"상위규정 매핑 — '{self.cur_id}' 에 위임한 상위규정")
        self._load_upstream()

    def _load_upstream(self):
        self.right.delete(*self.right.get_children())
        if not self.cur_id:
            return
        try:
            ups = rdb_map_db.upstream(self.code, self.cur_id, self.levels, self.target)
        except Exception as ex:
            messagebox.showerror("조회 실패", str(ex), parent=self)
            return
        for u in ups:
            self.right.insert("", "end", iid=str(u["pk"]),
                              values=(u["id_start"], _snip(u["content"] or "(상위 본문 없음 — dangling?)")))
        if not ups:
            self.right.insert("", "end", values=("(없음)", "rdb 매핑 없음 — 미매핑 조문"))

    def _refresh_keep(self):
        cur = self.cur_id
        self._load_lower()
        if cur and self.left.exists(cur):
            self.left.selection_set(cur)
            self.left.see(cur)
            self.cur_id = cur
            self._load_upstream()

    def _log(self, msg):
        self.log.configure(state="normal")
        self.log.insert("end", msg + "\n")
        self.log.see("end")
        lines = int(self.log.index("end-1c").split(".")[0])
        if lines > 300:  # 너무 길어지면 오래된 줄 정리
            self.log.delete("1.0", f"{lines - 300}.0")
        self.log.configure(state="disabled")

    def _clear_log(self):
        self.log.configure(state="normal")
        self.log.delete("1.0", "end")
        self.log.configure(state="disabled")

    def _confirm_prod(self):
        if self.target != "prod":
            return True
        return messagebox.askyesno("운영 변경 주의", "운영(prod) rdb 를 변경합니다. 계속할까요?", parent=self)

    def _selected_pk(self):
        sel = self.right.selection()
        if not sel or not sel[0].isdigit():
            return None
        return int(sel[0])

    # ---------- 편집 ----------
    def _add(self):
        if not self.cur_id:
            messagebox.showinfo("추가", "왼쪽에서 하위 조문을 먼저 선택하세요.", parent=self)
            return
        start = self.v_start.get().strip()
        if not start:
            return
        if not self._confirm_prod():
            return
        end = self.cur_id
        try:
            pk = rdb_map_db.add_edge(self.code, start, end, self.target)
        except ValueError as ve:
            messagebox.showwarning("검증", str(ve), parent=self)
            return
        except Exception as ex:
            messagebox.showerror("추가 실패", str(ex), parent=self)
            return
        self._log(f"✔ 추가 반영  {start} → {end}   (rdb INSERT, _pk={pk})")
        self.v_start.set("")
        self._refresh_keep()

    def _edit(self):
        pk = self._selected_pk()
        if pk is None:
            return
        cur_start = self.right.item(self.right.selection()[0], "values")[0]
        dlg = _IdInputDialog(
            self, self.code, self.target, self.levels,
            title="상위 매핑 수정",
            prompt=f"'{self.cur_id}' 의 상위규정 id  (직접 입력 또는 [검색…]):",
            initial=cur_start,
        )
        self.wait_window(dlg)
        new = dlg.result
        if not new:
            return
        new = new.strip()
        if new == cur_start or not self._confirm_prod():
            return
        try:
            n = rdb_map_db.update_start(self.code, pk, new, self.cur_id, self.target)
        except ValueError as ve:
            messagebox.showwarning("검증", str(ve), parent=self)
            return
        except Exception as ex:
            messagebox.showerror("수정 실패", str(ex), parent=self)
            return
        if n:
            self._log(f"✔ 수정 반영  {self.cur_id} 의 상위  {cur_start} → {new}   (rdb UPDATE _pk={pk}, {n}행)")
        else:
            self._log(f"· 변경 없음  (_pk={pk})")
        self._refresh_keep()

    def _delete(self):
        pk = self._selected_pk()
        if pk is None:
            return
        if not messagebox.askyesno("삭제", "이 상위 매핑(rdb 엣지)을 삭제할까요?", parent=self):
            return
        if not self._confirm_prod():
            return
        start_val = self.right.item(self.right.selection()[0], "values")[0]
        try:
            n = rdb_map_db.delete_edge(self.code, pk, self.target)
        except Exception as ex:
            messagebox.showerror("삭제 실패", str(ex), parent=self)
            return
        if n:
            self._log(f"✔ 삭제 반영  {start_val} → {self.cur_id}   (rdb DELETE _pk={pk}, {n}행)")
        else:
            self._log(f"· 이미 없음  (_pk={pk})")
        self._refresh_keep()

    def _open_picker(self):
        _PickerDialog(self, self.code, self.target, self.levels,
                      on_pick=lambda idv: self.v_start.set(idv))


class _PickerDialog(tk.Toplevel):
    """상위규정 본문 검색 → 더블클릭/선택으로 id 반환."""

    def __init__(self, master, code, target, levels, on_pick):
        super().__init__(master)
        self.code = code
        self.target = target
        self.on_pick = on_pick
        self.title("상위규정 검색")
        self.geometry("640x440")
        self.transient(master)

        bar = ttk.Frame(self, padding=6)
        bar.pack(fill="x")
        ttk.Label(bar, text="단").pack(side="left")
        self.v_lv = tk.StringVar(value=(levels[0] if levels else "a"))
        ttk.Combobox(bar, textvariable=self.v_lv, values=levels, width=6, state="readonly").pack(side="left", padx=4)
        ttk.Label(bar, text="검색어").pack(side="left")
        self.v_q = tk.StringVar()
        ent = ttk.Entry(bar, textvariable=self.v_q, width=30)
        ent.pack(side="left", padx=4)
        ent.bind("<Return>", lambda e: self._search())
        ttk.Button(bar, text="검색", command=self._search).pack(side="left")

        self.tree = ttk.Treeview(self, columns=("id", "content"), show="headings")
        self.tree.heading("id", text="id")
        self.tree.column("id", width=100, anchor="w")
        self.tree.heading("content", text="본문")
        self.tree.column("content", width=500, anchor="w")
        self.tree.pack(fill="both", expand=True, padx=6, pady=4)
        self.tree.bind("<Double-1>", lambda e: self._choose())
        ttk.Button(self, text="이 조문 선택", command=self._choose).pack(pady=4)
        ent.focus_set()

    def _search(self):
        try:
            rows = rdb_map_db.search_upper(self.code, self.v_lv.get(), self.v_q.get().strip(), self.target)
        except Exception as ex:
            messagebox.showerror("검색 실패", str(ex), parent=self)
            return
        self.tree.delete(*self.tree.get_children())
        for r in rows:
            try:
                self.tree.insert("", "end", iid=r["id"], values=(r["id"], _snip(r["content"], 110)))
            except tk.TclError:
                pass

    def _choose(self):
        sel = self.tree.selection()
        if not sel:
            return
        self.on_pick(sel[0])
        self.destroy()


class _IdInputDialog(tk.Toplevel):
    """상위 id 입력 — 직접 입력 + [검색…] 픽커 겸용. result = 확정 id(취소 시 None)."""

    def __init__(self, master, code, target, levels, title, prompt, initial=""):
        super().__init__(master)
        self.title(title)
        self.transient(master)
        self.code = code
        self.target = target
        self.levels = levels
        self.result = None

        frm = ttk.Frame(self, padding=10)
        frm.pack(fill="both", expand=True)
        ttk.Label(frm, text=prompt).grid(row=0, column=0, columnspan=2, sticky="w", pady=(0, 6))
        self.v = tk.StringVar(value=initial)
        ent = ttk.Entry(frm, textvariable=self.v, width=26)
        ent.grid(row=1, column=0, sticky="w")
        ttk.Button(frm, text="검색…", command=self._pick).grid(row=1, column=1, padx=4)
        btns = ttk.Frame(frm)
        btns.grid(row=2, column=0, columnspan=2, sticky="e", pady=(12, 0))
        ttk.Button(btns, text="확인", command=self._ok).pack(side="left")
        ttk.Button(btns, text="취소", command=self.destroy).pack(side="left", padx=4)
        ent.focus_set()
        ent.bind("<Return>", lambda e: self._ok())

    def _pick(self):
        # 직접입력 칸을 검색 결과로 채운다(추가 박스의 검색과 동일 동작).
        _PickerDialog(self, self.code, self.target, self.levels, on_pick=lambda idv: self.v.set(idv))

    def _ok(self):
        v = self.v.get().strip()
        if v:
            self.result = v
        self.destroy()
