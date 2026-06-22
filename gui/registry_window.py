"""
법령 목록 관리 창 — ldb_auth.law_registry (공용 카탈로그) 편집.

per-law 편집(메인 창의 표 탭)과 분리된 '관리자' 화면. 행 추가/수정/삭제로
웹 드롭다운에 뜨는 법령 목록·순서·노출·표시명을 관리한다.
"""
import re
import tkinter as tk
from tkinter import ttk, messagebox

from editor import registry_db

_COLS = ("code", "label", "sort_order", "enabled", "kind")
_HEAD = {"code": "코드", "label": "표시명(빈칸=법명 자동)", "sort_order": "순서", "enabled": "노출", "kind": "종류"}
_WIDTH = {"code": 80, "label": 360, "sort_order": 60, "enabled": 60, "kind": 100}
_CODE_RE = re.compile(r"[a-z0-9_]{1,16}")


class RegistryWindow(tk.Toplevel):
    def __init__(self, master, target: str = "dev"):
        super().__init__(master)
        self.target = target
        self.title(f"법령 목록 관리 — law_registry @ {target}")
        self.geometry("760x500")
        self.transient(master)

        try:
            registry_db.ensure_table(target)  # 없으면 생성(idempotent)
        except Exception as ex:
            messagebox.showerror("연결 실패", f"{registry_db.AUTH_DB} 접속/테이블 준비 실패:\n{ex}", parent=self)

        self._build()
        self._refresh()

    # ---------- UI ----------
    def _build(self):
        top = ttk.Frame(self, padding=6)
        top.pack(fill="both", expand=True)
        self.tree = ttk.Treeview(top, columns=_COLS, show="headings", height=12)
        for c in _COLS:
            self.tree.heading(c, text=_HEAD[c])
            self.tree.column(c, width=_WIDTH[c], anchor=("w" if c == "label" else "center"))
        self.tree.pack(side="left", fill="both", expand=True)
        sb = ttk.Scrollbar(top, orient="vertical", command=self.tree.yview)
        sb.pack(side="left", fill="y")
        self.tree.configure(yscrollcommand=sb.set)
        self.tree.bind("<<TreeviewSelect>>", self._on_select)

        form = ttk.LabelFrame(self, text="추가 / 수정 (코드가 같으면 덮어씀)", padding=8)
        form.pack(fill="x", padx=6, pady=4)
        self.v_code = tk.StringVar()
        self.v_label = tk.StringVar()
        self.v_order = tk.StringVar(value="100")
        self.v_enabled = tk.IntVar(value=1)
        self.v_kind = tk.StringVar(value="law")

        ttk.Label(form, text="코드").grid(row=0, column=0, sticky="e", padx=2, pady=2)
        self.code_cb = ttk.Combobox(form, textvariable=self.v_code, width=14, values=[])
        self.code_cb.grid(row=0, column=1, sticky="w", padx=2)
        ttk.Label(form, text="표시명").grid(row=0, column=2, sticky="e", padx=2)
        ttk.Entry(form, textvariable=self.v_label, width=44).grid(row=0, column=3, columnspan=3, sticky="w", padx=2)

        ttk.Label(form, text="순서").grid(row=1, column=0, sticky="e", padx=2, pady=2)
        ttk.Entry(form, textvariable=self.v_order, width=8).grid(row=1, column=1, sticky="w", padx=2)
        ttk.Checkbutton(form, text="노출(enabled)", variable=self.v_enabled).grid(row=1, column=2, columnspan=2, sticky="w", padx=2)
        ttk.Label(form, text="종류").grid(row=1, column=4, sticky="e", padx=2)
        ttk.Combobox(form, textvariable=self.v_kind, width=12, values=["law", "accounting"]).grid(row=1, column=5, sticky="w", padx=2)

        btns = ttk.Frame(self, padding=6)
        btns.pack(fill="x")
        ttk.Button(btns, text="새로고침", command=self._refresh).pack(side="left")
        ttk.Button(btns, text="추가/수정 저장", command=self._save).pack(side="left", padx=4)
        ttk.Button(btns, text="선택 삭제", command=self._delete).pack(side="left")
        ttk.Button(btns, text="폼 비우기", command=self._clear).pack(side="left", padx=4)
        ttk.Label(btns, text="ⓘ 코드칸 ▼ = 미등록 ldb_* 자동 추천").pack(side="left", padx=12)

    # ---------- 데이터 ----------
    def _refresh(self):
        try:
            rows = registry_db.list_registry(self.target)
        except Exception as ex:
            messagebox.showerror("조회 실패", str(ex), parent=self)
            return
        self.tree.delete(*self.tree.get_children())
        for r in rows:
            self.tree.insert("", "end", iid=r["code"], values=(
                r["code"], r["label"] or "", r["sort_order"],
                "Y" if r["enabled"] else "N", r["kind"],
            ))
        try:
            self.code_cb["values"] = registry_db.unregistered_codes(self.target)
        except Exception:
            self.code_cb["values"] = []

    def _on_select(self, _e=None):
        sel = self.tree.selection()
        if not sel:
            return
        v = self.tree.item(sel[0], "values")
        self.v_code.set(v[0])
        self.v_label.set(v[1])
        self.v_order.set(v[2])
        self.v_enabled.set(1 if v[3] == "Y" else 0)
        self.v_kind.set(v[4])

    def _clear(self):
        self.v_code.set("")
        self.v_label.set("")
        self.v_order.set("100")
        self.v_enabled.set(1)
        self.v_kind.set("law")

    def _confirm_prod(self) -> bool:
        if self.target != "prod":
            return True
        return messagebox.askyesno("운영 변경 주의", "운영(prod) law_registry 를 변경합니다. 계속할까요?", parent=self)

    def _save(self):
        code = self.v_code.get().strip()
        if not _CODE_RE.fullmatch(code):
            messagebox.showwarning("코드", "코드는 영소문자/숫자/_ 1~16자여야 합니다.", parent=self)
            return
        try:
            order = int(self.v_order.get())
        except ValueError:
            messagebox.showwarning("순서", "순서는 정수여야 합니다.", parent=self)
            return
        if not self._confirm_prod():
            return
        try:
            registry_db.upsert(code, self.v_label.get().strip() or None, order,
                               self.v_enabled.get() == 1, self.v_kind.get().strip() or "law", self.target)
            self._refresh()
            self.tree.selection_set(code)
        except Exception as ex:
            messagebox.showerror("저장 실패", str(ex), parent=self)

    def _delete(self):
        sel = self.tree.selection()
        if not sel:
            return
        code = sel[0]
        if not messagebox.askyesno("목록에서 삭제", f"'{code}' 를 목록에서 제거할까요?\n(법령 DB ldb_{code} 는 그대로 둡니다.)", parent=self):
            return
        if not self._confirm_prod():
            return
        try:
            registry_db.delete(code, self.target)
            self._clear()
            self._refresh()
        except Exception as ex:
            messagebox.showerror("삭제 실패", str(ex), parent=self)
