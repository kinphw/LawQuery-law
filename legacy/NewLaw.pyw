"""
NewLaw — 새 법령 **인테이크 폼** (최전선 진입로).

  • 더블클릭 → 작은 GUI 창. 사람이 *아는 것*만 입력:
      약자(code) · 단수(4단/5단) · 신규/갱신 · 단별 정확한 명칭 · 지시메모
  • [저장] → intake/<code>.json 으로 저장.
  • 그 뒤 Claude 에게  "intake/<code>.json 읽고 작업해줘"  라고 말하면
      Claude 가 MCP 로 소스(법령ID/일련번호)를 찾아 jobs/<code>/job.json 을
      작성하고 파이프라인(run → verify)을 돌린다.

왜 GUI 가 job.json 을 직접 안 만드나:
  job.json 의 핵심값(sources.id = law.go.kr 법령ID/일련번호, refers, umbrella)은
  사람이 모르는 값이라 Claude 가 검색·판단으로 채운다. GUI 는 사람이 아는 명칭·약자만 받는다.

콘솔 없음(.pyw). 오류는 대화상자로 표시. 외부 의존성 없음(표준 라이브러리 tkinter 만).
"""
import os
import re
import sys
import json
import datetime
import traceback

# legacy/ 로 이관됨(허브 웹 인테이크로 대체) → intake/·jobs/ 는 부모(프로젝트 루트) 기준
HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
INTAKE_DIR = os.path.join(HERE, "intake")
JOBS_DIR = os.path.join(HERE, "jobs")

# 단(tier) 정의: 코드 → (한글명, 종류 힌트)
TIERS = [
    ("a", "법 (A)", "law"),
    ("e", "시행령 (E)", "law"),
    ("s", "감독규정 (S)", "admrul"),
    ("r", "시행세칙 (R)", "admrul"),
]


# ──────────────────────────────────────────────────────────────────────────
# 데이터 입출력 (GUI 없이도 동작)
# ──────────────────────────────────────────────────────────────────────────
def intake_path(code: str) -> str:
    return os.path.join(INTAKE_DIR, f"{code}.json")


def save_intake(data: dict) -> str:
    os.makedirs(INTAKE_DIR, exist_ok=True)
    path = intake_path(data["code"])
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    return path


def load_intake(code: str) -> dict | None:
    path = intake_path(code)
    if not os.path.exists(path):
        return None
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def list_built() -> list[dict]:
    """jobs/<code>/job.json 스캔 → 이미 구축된 법 목록."""
    out = []
    if os.path.isdir(JOBS_DIR):
        for code in sorted(os.listdir(JOBS_DIR)):
            jp = os.path.join(JOBS_DIR, code, "job.json")
            if os.path.exists(jp):
                try:
                    with open(jp, encoding="utf-8") as f:
                        j = json.load(f)
                    out.append({"code": j.get("code", code),
                                "title": j.get("title", ""),
                                "status": "구축됨"})
                except Exception:
                    out.append({"code": code, "title": "(읽기 실패)", "status": "구축됨"})
    return out


def list_intakes() -> list[dict]:
    """intake/<code>.json 스캔 → 인테이크 요청 목록."""
    out = []
    if os.path.isdir(INTAKE_DIR):
        for fn in sorted(os.listdir(INTAKE_DIR)):
            if not fn.endswith(".json"):
                continue
            try:
                with open(os.path.join(INTAKE_DIR, fn), encoding="utf-8") as f:
                    d = json.load(f)
                out.append(d)
            except Exception:
                pass
    return out


def overview() -> list[dict]:
    """구축된 법 + 인테이크 대기 합본(약자 기준)."""
    built = {b["code"]: b for b in list_built()}
    rows = []
    seen = set()
    for code, b in built.items():
        rows.append(b)
        seen.add(code)
    for d in list_intakes():
        c = d.get("code")
        if c in seen:
            continue
        title = d.get("names", {}).get("a") or "(미정)"
        rows.append({"code": c, "title": title, "status": "인테이크 대기"})
    rows.sort(key=lambda r: str(r["code"]))
    return rows


# ──────────────────────────────────────────────────────────────────────────
# GUI
# ──────────────────────────────────────────────────────────────────────────
def run_gui() -> None:
    import tkinter as tk
    from tkinter import ttk, messagebox

    root = tk.Tk()
    root.title("LawQuery · 새 법령 인테이크")
    root.geometry("640x720")
    try:
        root.call("tk", "scaling", 1.2)
    except Exception:
        pass

    PAD = {"padx": 8, "pady": 4}
    name_vars: dict[str, tk.StringVar] = {}

    # ── 상단 안내 ──────────────────────────────────────────────
    head = ttk.Label(
        root,
        text="사람이 아는 것만 입력 → intake/<약자>.json 저장.\n"
             "이후 Claude 에게 “intake/<약자>.json 읽고 작업해줘” 라고 지시.",
        justify="left", foreground="#444",
    )
    head.pack(anchor="w", padx=12, pady=(10, 2))

    # ── 입력 폼 ────────────────────────────────────────────────
    form = ttk.LabelFrame(root, text="새 법령 / 갱신 요청")
    form.pack(fill="x", padx=12, pady=6)

    # 약자
    ttk.Label(form, text="약자(code)").grid(row=0, column=0, sticky="w", **PAD)
    code_var = tk.StringVar()
    code_entry = ttk.Entry(form, textvariable=code_var, width=12)
    code_entry.grid(row=0, column=1, sticky="w", **PAD)
    ttk.Label(form, text="ldb_<code> 가 됨 · 예: j, y, g (영소문자/숫자)",
              foreground="#888").grid(row=0, column=2, sticky="w", **PAD)

    # 종류
    ttk.Label(form, text="종류").grid(row=1, column=0, sticky="w", **PAD)
    kind_var = tk.StringVar(value="new")
    kf = ttk.Frame(form); kf.grid(row=1, column=1, columnspan=2, sticky="w", **PAD)
    ttk.Radiobutton(kf, text="신규", variable=kind_var, value="new").pack(side="left")
    ttk.Radiobutton(kf, text="갱신(기존 재가동)", variable=kind_var, value="update").pack(side="left", padx=10)

    # 단수
    ttk.Label(form, text="단수").grid(row=2, column=0, sticky="w", **PAD)
    tiers_var = tk.IntVar(value=4)
    tf = ttk.Frame(form); tf.grid(row=2, column=1, columnspan=2, sticky="w", **PAD)
    ttk.Radiobutton(tf, text="4단 (법·시행령·감독규정·세칙)", variable=tiers_var, value=4).pack(side="left")
    ttk.Radiobutton(tf, text="5단 (+ 별표 B)", variable=tiers_var, value=5).pack(side="left", padx=10)

    # 단별 명칭
    ttk.Separator(form, orient="horizontal").grid(row=3, column=0, columnspan=3, sticky="ew", pady=6)
    ttk.Label(form, text="단별 정확한 명칭  (없는 단은 비워두세요)",
              foreground="#444").grid(row=4, column=0, columnspan=3, sticky="w", **PAD)
    for i, (tcode, tlabel, _kind) in enumerate(TIERS):
        ttk.Label(form, text=tlabel).grid(row=5 + i, column=0, sticky="w", **PAD)
        v = tk.StringVar()
        name_vars[tcode] = v
        ttk.Entry(form, textvariable=v, width=46).grid(row=5 + i, column=1, columnspan=2, sticky="w", **PAD)

    # 별표 안내
    ttk.Label(form, text="※ 별표(B)는 문서가 아니라 위 단들 안의 표/서식 → 명칭 입력 불필요. 5단 선택 = 별표 적재 지시.",
              foreground="#888", wraplength=580, justify="left"
              ).grid(row=5 + len(TIERS), column=0, columnspan=3, sticky="w", **PAD)

    # 옵션
    sched_var = tk.BooleanVar(value=False)
    ttk.Checkbutton(form, text="시행예정(미시행 개정) 반영", variable=sched_var
                    ).grid(row=6 + len(TIERS), column=0, columnspan=3, sticky="w", **PAD)

    # 지시메모
    ttk.Label(form, text="지시/메모 (선택)").grid(row=7 + len(TIERS), column=0, sticky="nw", **PAD)
    notes_txt = tk.Text(form, height=4, width=48, wrap="word")
    notes_txt.grid(row=7 + len(TIERS), column=1, columnspan=2, sticky="w", **PAD)

    form.columnconfigure(2, weight=1)

    # ── 버튼 + 상태 ────────────────────────────────────────────
    btns = ttk.Frame(root); btns.pack(fill="x", padx=12, pady=(2, 4))
    status = ttk.Label(root, text="", foreground="#1a7f37")
    status.pack(anchor="w", padx=12)

    def clear_form():
        code_var.set(""); kind_var.set("new"); tiers_var.set(4)
        sched_var.set(False)
        for v in name_vars.values():
            v.set("")
        notes_txt.delete("1.0", "end")
        status.config(text="", foreground="#1a7f37")
        code_entry.focus_set()

    def fill_form(d: dict):
        clear_form()
        code_var.set(d.get("code", ""))
        kind_var.set(d.get("kind", "new"))
        tiers_var.set(int(d.get("tiers", 4)))
        sched_var.set(bool(d.get("options", {}).get("sched", False)))
        for tcode, v in name_vars.items():
            v.set(d.get("names", {}).get(tcode, ""))
        notes_txt.insert("1.0", d.get("notes", ""))

    def do_save():
        code = code_var.get().strip().lower()
        if not re.fullmatch(r"[a-z0-9]{1,16}", code):
            messagebox.showwarning("약자 확인", "약자(code)는 영소문자/숫자 1~16자로 입력하세요. 예: j, y, g")
            return
        names = {tc: name_vars[tc].get().strip() for tc, *_ in TIERS}
        if not names["a"]:
            messagebox.showwarning("명칭 확인", "최소한 법(A)의 정확한 명칭은 입력해야 합니다.")
            return

        built_codes = {b["code"] for b in list_built()}
        kind = kind_var.get()
        if code in built_codes and kind == "new":
            if not messagebox.askyesno(
                "이미 구축된 약자",
                f"'{code}' 는 이미 jobs/{code}/job.json 으로 구축돼 있습니다.\n"
                "갱신(기존 재가동)으로 저장할까요?",
            ):
                return
            kind = "update"; kind_var.set("update")

        if os.path.exists(intake_path(code)):
            if not messagebox.askyesno("덮어쓰기", f"intake/{code}.json 이 이미 있습니다. 덮어쓸까요?"):
                return

        data = {
            "code": code,
            "kind": kind,
            "tiers": tiers_var.get(),
            "names": names,
            "options": {"sched": sched_var.get()},
            "notes": notes_txt.get("1.0", "end").strip(),
            "created": datetime.date.today().isoformat(),
            "_status": "pending",
        }
        try:
            path = save_intake(data)
        except Exception:
            messagebox.showerror("저장 실패", traceback.format_exc())
            return

        rel = os.path.relpath(path, HERE).replace("\\", "/")
        status.config(text=f"저장됨: {rel}  →  Claude 에게  “{rel} 읽고 작업해줘”", foreground="#1a7f37")
        refresh_list()

    ttk.Button(btns, text="저장", command=do_save).pack(side="left")
    ttk.Button(btns, text="폼 비우기", command=clear_form).pack(side="left", padx=6)

    # ── 구축/대기 목록 ─────────────────────────────────────────
    listf = ttk.LabelFrame(root, text="이미 구축된 법 / 인테이크 대기  (더블클릭 = 폼으로 불러오기)")
    listf.pack(fill="both", expand=True, padx=12, pady=(8, 10))

    cols = ("code", "title", "status")
    tree = ttk.Treeview(listf, columns=cols, show="headings", height=8)
    tree.heading("code", text="약자"); tree.column("code", width=70, anchor="center")
    tree.heading("title", text="명칭"); tree.column("title", width=400, anchor="w")
    tree.heading("status", text="상태"); tree.column("status", width=110, anchor="center")
    tree.pack(side="left", fill="both", expand=True, padx=(6, 0), pady=6)
    sb = ttk.Scrollbar(listf, orient="vertical", command=tree.yview)
    sb.pack(side="right", fill="y"); tree.configure(yscrollcommand=sb.set)

    def refresh_list():
        tree.delete(*tree.get_children())
        for r in overview():
            tree.insert("", "end", iid=str(r["code"]),
                        values=(r["code"], r["title"], r["status"]))

    def on_double(_e):
        sel = tree.selection()
        if not sel:
            return
        code = sel[0]
        d = load_intake(code)
        if d:
            fill_form(d)
            status.config(text=f"불러옴: intake/{code}.json", foreground="#0969da")
        else:
            # 구축됐지만 인테이크가 없는 경우 — 갱신 폼 시드
            clear_form()
            code_var.set(code); kind_var.set("update")
            vals = tree.item(code, "values")
            notes_txt.insert("1.0", f"기존 구축법 — jobs/{code}/job.json 존재. 제목: {vals[1]}")
            status.config(text=f"갱신 폼 시드: {code} (인테이크 파일 없음)", foreground="#0969da")

    tree.bind("<Double-1>", on_double)

    ttk.Button(root, text="목록 새로고침", command=refresh_list).pack(anchor="e", padx=12, pady=(0, 10))

    refresh_list()
    clear_form()
    root.mainloop()


def main() -> None:
    try:
        run_gui()
    except Exception:
        # .pyw 는 콘솔이 없으므로 오류를 대화상자로
        try:
            import tkinter.messagebox as mb
            mb.showerror("NewLaw 오류", traceback.format_exc())
        except Exception:
            sys.stderr.write(traceback.format_exc())


if __name__ == "__main__":
    main()
