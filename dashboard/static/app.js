"use strict";

// ── helpers ───────────────────────────────────────────────
const $ = (sel, el = document) => el.querySelector(sel);
const view = $("#view");
const esc = (s) => String(s ?? "").replace(/[&<>"]/g, (c) =>
  ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c]));

async function api(path, opts) {
  const res = await fetch(path, opts);
  const ct = res.headers.get("content-type") || "";
  const body = ct.includes("json") ? await res.json() : await res.text();
  if (!res.ok) throw new Error(body?.detail || body || res.statusText);
  return body;
}

let toastTimer;
function toast(msg, kind = "") {
  const t = $("#toast");
  t.textContent = msg;
  t.className = "toast show " + kind;
  clearTimeout(toastTimer);
  toastTimer = setTimeout(() => (t.className = "toast"), 2600);
}

function copy(text) {
  navigator.clipboard.writeText(text).then(
    () => toast("복사됨", "ok"),
    () => toast("복사 실패", "err"));
}

const statusTag = (s) =>
  s === "구축됨" ? '<span class="tag built">구축됨</span>'
  : '<span class="tag pending">인테이크 대기</span>';

// ── SSE 로그 실행 ─────────────────────────────────────────
let activeES = null;
function runStream(url, logEl, btns, onDone) {
  if (activeES) { activeES.close(); activeES = null; }
  logEl.innerHTML = "";
  const append = (html) => { logEl.insertAdjacentHTML("beforeend", html); logEl.scrollTop = logEl.scrollHeight; };
  btns.forEach((b) => (b.disabled = true));
  const es = new EventSource(url);
  activeES = es;
  es.onmessage = (ev) => {
    let m; try { m = JSON.parse(ev.data); } catch { return; }
    if (m.type === "start") append(`<div class="meta">$ ${esc(m.cmd)}</div>`);
    else if (m.type === "log") append(esc(m.line) + "\n");
    else if (m.type === "end") {
      const ok = m.code === 0;
      append(`<div class="${ok ? "end-ok" : "end-fail"}">── 종료 (code ${m.code})${m.error ? " · " + esc(m.error) : ""} ──</div>`);
      es.close(); activeES = null;
      btns.forEach((b) => (b.disabled = false));
      toast(ok ? "완료" : "실패 (로그 확인)", ok ? "ok" : "err");
      if (onDone) { try { onDone(ok); } catch (e) { /* noop */ } }
    }
  };
  es.onerror = () => {
    append(`<div class="err">── 연결 끊김 ──</div>`);
    es.close(); activeES = null;
    btns.forEach((b) => (b.disabled = false));
  };
}

// ── 홈 ────────────────────────────────────────────────────
async function renderHome() {
  view.innerHTML = `<h1>대시보드</h1><p class="page-sub">법령 현황과 개발/운영 비교.</p>
    <div id="home-body" class="muted"><span class="spinner"></span> 불러오는 중…</div>`;
  let rows, tools, dev;
  try {
    [rows, tools, dev] = await Promise.all([
      api("/api/intake/list"), api("/api/tools"), api("/api/status/laws?target=dev"),
    ]);
  } catch (e) { $("#home-body").innerHTML = `<p class="empty">${esc(e.message)}</p>`; return; }
  const built = rows.filter((r) => r.status === "구축됨");
  const pending = rows.filter((r) => r.status !== "구축됨");
  $("#home-body").innerHTML = `
    <div class="cards">
      <div class="card"><div class="stat"><div><div class="num">${built.length}</div><div class="lbl">구축된 법</div></div></div></div>
      <div class="card"><div class="stat"><div><div class="num">${pending.length}</div><div class="lbl">인테이크 대기</div></div></div></div>
      <div class="card"><div class="stat"><div><div class="num">${tools.filter((t) => t.available).length}</div><div class="lbl">연결된 도구</div></div></div></div>
    </div>
    <div class="row" style="align-items:center;justify-content:space-between;margin:26px 0 12px">
      <h2 style="margin:0">개발 / 운영 법령 현황 <span class="muted" style="font-size:13px;font-weight:400">— 단별 법령명·시행일자</span></h2>
      <button class="btn btn-sm" id="load-prod">운영(prod) 불러와 비교</button>
    </div>
    <div class="panel" style="padding:0;overflow:hidden"><div id="law-status"></div></div>`;

  let prod = null;
  const draw = () => { $("#law-status").innerHTML = lawTable(dev.laws, prod && prod.laws); };
  draw();
  $("#load-prod").onclick = async () => {
    const b = $("#load-prod");
    b.disabled = true; b.innerHTML = '<span class="spinner"></span> 운영 접속 중…';
    try {
      prod = await api("/api/status/laws?target=prod");
      draw(); b.textContent = "운영 새로고침"; toast("운영 현황 불러옴", "ok");
    } catch (e) { toast(e.message, "err"); b.textContent = "운영(prod) 다시 시도"; }
    finally { b.disabled = false; }
  };
}

// dev/prod 법령 현황표 (prodLaws 가 있으면 시행일 비교 열 추가)
const TIER_RANK = { a: 0, e: 1, s: 2, r: 3, b: 4 };
function gapText(devEff, prodEff) {
  const da = Date.parse(devEff), dp = Date.parse(prodEff);
  if (isNaN(da) || isNaN(dp)) return "";
  const days = Math.round((da - dp) / 86400000);
  if (days <= 0) return "";
  if (days < 60) return ` ${days}일`;
  const mo = Math.round(days / 30.44);
  return mo < 24 ? ` ${mo}개월` : ` ${(days / 365.25).toFixed(1)}년`;
}
// 상태는 '운영에 그 단이 존재하는가'로 판정 (시행일 파싱 실패 ≠ 미배포)
function statusCell(d, p, prodLoaded) {
  if (!prodLoaded) return "";
  if (!p) return '<span class="tag st-missing">미배포</span>';
  if (!d) return '<span class="tag">개발없음</span>';
  if (d.eff && p.eff) {
    if (d.eff === p.eff) return '<span class="tag st-ok">최신</span>';
    if (d.eff > p.eff) return `<span class="tag st-behind" title="개발 ${d.eff} ↔ 운영 ${p.eff}">운영 지체${gapText(d.eff, p.eff)}</span>`;
    return '<span class="tag st-warn">개발 지체</span>';
  }
  return '<span class="tag">배포됨</span>';
}
function lawTable(devLaws, prodLaws) {
  const prodLoaded = !!prodLaws;
  const byCode = new Map();
  const add = (laws, key) => (laws || []).forEach((l) => {
    if (!byCode.has(l.code)) byCode.set(l.code, { code: l.code });
    byCode.get(l.code)[key] = l;
  });
  add(devLaws, "dev"); add(prodLaws, "prod");
  const codes = [...byCode.keys()].sort();
  if (!codes.length) return `<div class="empty">배포된 법 DB 없음</div>`;

  let body = "";
  for (const code of codes) {
    const ent = byCode.get(code);
    const tmap = new Map();
    const fill = (law, key) => (law ? law.tiers : []).forEach((t) => {
      if (!tmap.has(t.tier)) tmap.set(t.tier, { tier: t.tier });
      tmap.get(t.tier)[key] = t;
    });
    fill(ent.dev, "dev"); fill(ent.prod, "prod");
    const tiers = [...tmap.values()].sort((a, b) => (TIER_RANK[a.tier] ?? 9) - (TIER_RANK[b.tier] ?? 9));
    tiers.forEach((t, i) => {
      const d = t.dev, p = t.prod;
      const ref = d || p;
      const devEff = d ? (d.eff || "—") : '<span class="muted">없음</span>';
      const prodCells = prodLoaded
        ? `<td class="code">${p ? (p.eff || '<span class="muted">시행일?</span>') : '<span class="muted">없음</span>'}</td>
           <td>${statusCell(d, p, true)}</td>`
        : "";
      body += `<tr>
        ${i === 0 ? `<td class="code" rowspan="${tiers.length}">${esc(code)}</td>` : ""}
        <td>${esc(ref.label || t.tier)}</td>
        <td>${esc(ref.name || "")}</td>
        <td class="code">${devEff}</td>
        ${prodCells}
      </tr>`;
    });
  }
  return `<table><thead><tr>
    <th>법</th><th>단</th><th>법령명</th><th>개발 시행</th>
    ${prodLoaded ? "<th>운영 시행</th><th>상태</th>" : ""}
  </tr></thead><tbody>${body}</tbody></table>`;
}

// ── 법령 인테이크 ─────────────────────────────────────────
let META;
async function renderIntake(params) {
  if (!META) META = await api("/api/intake/meta");
  view.innerHTML = `
    <h1>법령 인테이크</h1>
    <p class="page-sub">새 법 작업의 <b>주문서</b>. 사람이 <b>아는 것</b>만 적고 Claude 에게 넘기는 곳.</p>
    <div class="help">
      <b>신규 법은 여기서 인테이크만 만들면 됩니다 — 파이프라인을 직접 돌릴 필요 없습니다.</b>
      <ol>
        <li>아래에 <b>아는 것만</b> 입력 — 약자·단수·단별 명칭·지시. (법령ID 같은 건 몰라도 됨)</li>
        <li><b>저장</b> → 뜨는 <code>intake/&lt;약자&gt;.json 읽고 작업해줘</code> 를 <b>복사해 Claude 에게 전달</b>.</li>
        <li>그러면 <b>Claude 가</b> 법령ID 검색 → <code>job.json</code> 작성 → 파이프라인(dry-run → 적재 → verify) → 연결 보정까지 <b>대신 수행</b>합니다.</li>
        <li><b>이미 구축된 법</b>(아래 목록의 "구축됨")은 행을 클릭하면 단별 법령명·시행일 상세가 뜹니다. 재적재·운영배포는 <a href="#/pipeline">파이프라인</a> 탭.</li>
      </ol>
    </div>
    <div class="panel">
      <div class="row">
        <div class="field" style="max-width:220px">
          <label>약자 (code)<span class="hint">ldb_&lt;code&gt; · 예: j, y, g</span></label>
          <input type="text" id="f-code" placeholder="g" autocomplete="off">
        </div>
        <div class="field">
          <label>종류</label>
          <div class="radios" style="padding-top:8px">
            <label><input type="radio" name="kind" value="new" checked> 신규</label>
            <label><input type="radio" name="kind" value="update"> 갱신(기존 재가동)</label>
          </div>
        </div>
        <div class="field">
          <label>단수</label>
          <div class="radios" style="padding-top:8px">
            <label><input type="radio" name="tiers" value="4" checked> 4단</label>
            <label><input type="radio" name="tiers" value="5"> 5단(+별표 B)</label>
          </div>
        </div>
      </div>
      <div class="field">
        <label>단별 정확한 명칭<span class="hint">없는 단은 비워두세요 · 왼쪽 단 종류명도 수정 가능(예: s·r 둘 다 감독규정)</span></label>
        <div id="tier-names-rows"></div>
      </div>
      <div class="field">
        <label class="checkbox"><input type="checkbox" id="f-sched"> 시행예정(미시행 개정) 반영</label>
      </div>
      <div class="field">
        <label>지시 / 메모 <span class="hint">(선택)</span></label>
        <textarea id="f-notes" placeholder="예: 감독규정 별표 과태료 표 파싱 필요"></textarea>
      </div>
      <div class="btn-row">
        <button class="btn btn-primary" id="f-save">저장</button>
        <button class="btn" id="f-clear">폼 비우기</button>
        <span id="f-loaded" class="muted"></span>
      </div>
      <div id="f-handoff"></div>
      <div id="f-detail"></div>
    </div>

    <h2>구축된 법 / 인테이크 대기 <span class="muted" style="font-size:13px;font-weight:400">— 행 클릭 = 폼으로 불러오기</span></h2>
    <div class="panel" style="padding:0;overflow:hidden"><div id="intake-list"></div></div>`;

  const codeEl = $("#f-code");
  const tierEl = (c) => $(`#tier-names-rows [data-tier="${c}"]`);
  const currentTiers = () =>
    META.tiersByRank[document.querySelector('[name=tiers]:checked').value] || META.tiersByRank["4"];
  // 단수(4/5)에 맞춰 명칭 칸을 다시 렌더 — 슬롯 의미가 시프트하므로 라벨 기본값도 바뀜.
  // 정확한 명칭(data-tier) 입력값은 슬롯 코드 기준으로 보존(전환 시 데이터 손실 방지).
  // 단 종류명(data-label)은 단수 기본값으로 재설정(슬롯 의미가 단수따라 달라 보존이 오히려 오류) — setForm 이 저장값으로 덮음.
  const renderTierRows = () => {
    const cur = {};
    document.querySelectorAll('#tier-names-rows [data-tier]').forEach((el) => (cur[el.dataset.tier] = el.value));
    $("#tier-names-rows").innerHTML = currentTiers().map((t) => `
      <div style="display:flex;align-items:center;gap:8px;margin-bottom:8px">
        <input type="text" data-label="${t.code}" value="${esc(t.label)}" title="단 종류명 — 수정 가능 (예: s·r 둘 다 감독규정)"
               style="width:92px;color:var(--muted);text-align:right">
        <span class="muted" style="width:22px;font-size:12px">(${t.code.toUpperCase()})</span>
        <input type="text" data-tier="${t.code}" style="flex:1" placeholder="${t.code === "a" ? "○○법 (필수)" : ""}">
      </div>`).join("");
    currentTiers().forEach((t) => { if (cur[t.code]) tierEl(t.code).value = cur[t.code]; });
  };
  const setForm = (d) => {
    codeEl.value = d.code || "";
    document.querySelectorAll('[name=kind]').forEach((r) => (r.checked = r.value === (d.kind || "new")));
    document.querySelectorAll('[name=tiers]').forEach((r) => (r.checked = r.value === String(d.tiers || 4)));
    renderTierRows();
    const names = d.names || {};
    document.querySelectorAll('#tier-names-rows [data-tier]').forEach((el) => (el.value = names[el.dataset.tier] || ""));
    const labels = d.labels || {};  // 저장된 단 종류명만 덮고, 없으면 단수 기본값(이미 렌더됨) 유지
    document.querySelectorAll('#tier-names-rows [data-label]').forEach((el) => { if (labels[el.dataset.label]) el.value = labels[el.dataset.label]; });
    $("#f-sched").checked = !!(d.options || {}).sched;
    $("#f-notes").value = d.notes || "";
  };
  const clearForm = () => { setForm({}); $("#f-loaded").textContent = ""; $("#f-handoff").innerHTML = ""; $("#f-detail").innerHTML = ""; codeEl.focus(); };
  document.querySelectorAll('[name=tiers]').forEach((r) => (r.onchange = renderTierRows));
  renderTierRows();

  // 이미 구축된 법 — 읽기용 상세 카드. 정식 법령명·시행일은 db_meta(meta), 소스 ID·별칭은 job.json.
  // 슬롯(a/e/s/r/b) 의미가 법마다 달라(예: y 는 s=시행규칙) 단 라벨은 위치(N단)+슬롯.
  const jobDetail = (code, job, meta) => {
    const src = job.sources || {};
    const metaBy = {};
    (meta || []).forEach((t) => { metaBy[t.tier] = t; });
    const rows = ["a", "e", "s", "r", "b"].filter((k) => src[k]).map((k, i) => {
      const s = src[k];
      const m = metaBy[k] || {};
      const name = m.name || s.short || "";          // 정식 법령명(db_meta) 우선, 없으면 short
      return `<tr><td>${i + 1}단 <span class="muted">(${k.toUpperCase()})</span></td>
        <td>${esc(name)}</td><td class="code">${esc(m.eff || "—")}</td><td>${esc(s.kind || "")}</td>
        <td class="code">${esc(s.id || "")}</td><td class="muted">${esc((s.refers || []).join(", "))}</td></tr>`;
    }).join("");
    return `<div class="panel" style="margin-top:14px">
      <div class="btn-row" style="justify-content:space-between;margin-bottom:6px">
        <b>${esc(job.title || code)}</b><span class="tag built">구축됨</span></div>
      <p class="muted" style="margin:0 0 12px">법령명·시행일 = 개발 DB(db_meta) 기준. refers 는 인용 별칭(본문에서 상위를 부르는 약칭).
        갱신은 파이프라인에서 재실행하거나 위 폼에서 약자 <b>${esc(code)}</b> 로 새 인테이크를 작성하세요.</p>
      <table><thead><tr><th>단</th><th>법령명</th><th>시행일</th><th>kind</th><th>법령ID/일련번호</th><th>refers(별칭)</th></tr></thead>
        <tbody>${rows}</tbody></table>
      <div class="btn-row" style="margin-top:12px">
        <a class="btn btn-sm" href="#/pipeline?code=${esc(code)}">파이프라인 ▸</a></div>
    </div>`;
  };

  $("#f-clear").onclick = clearForm;
  $("#f-save").onclick = async () => {
    const names = {}; document.querySelectorAll('#tier-names-rows [data-tier]').forEach((el) => (names[el.dataset.tier] = el.value.trim()));
    const labels = {}; document.querySelectorAll('#tier-names-rows [data-label]').forEach((el) => (labels[el.dataset.label] = el.value.trim()));
    const payload = {
      code: codeEl.value.trim().toLowerCase(),
      kind: document.querySelector('[name=kind]:checked').value,
      tiers: Number(document.querySelector('[name=tiers]:checked').value),
      names,
      labels,
      options: { sched: $("#f-sched").checked },
      notes: $("#f-notes").value.trim(),
    };
    try {
      const r = await api("/api/intake", {
        method: "POST", headers: { "content-type": "application/json" },
        body: JSON.stringify(payload),
      });
      toast("저장됨: " + r.path, "ok");
      $("#f-handoff").innerHTML = `<div class="handoff">
        <code>${esc(r.handoff)}</code>
        <button class="btn btn-sm" id="f-copy">복사</button>
        <a class="btn btn-sm" href="#/pipeline?code=${esc(payload.code)}">파이프라인 ▸</a></div>`;
      $("#f-copy").onclick = () => copy(r.handoff);
      loadList();
    } catch (e) { toast(e.message, "err"); }
  };

  async function loadList() {
    const rows = await api("/api/intake/list");
    $("#intake-list").innerHTML = rows.length ? `<table><thead><tr><th>약자</th><th>명칭</th><th>상태</th><th></th></tr></thead><tbody>
      ${rows.map((r) => `<tr data-code="${esc(r.code)}" style="cursor:pointer">
        <td class="code">${esc(r.code)}</td><td>${esc(r.title)}</td><td>${statusTag(r.status)}</td>
        <td style="text-align:right">${r.status === "구축됨" ? "" : `<button class="btn btn-sm btn-del" data-del="${esc(r.code)}">삭제</button>`}</td>
      </tr>`).join("")}</tbody></table>` : `<div class="empty">아직 없음</div>`;

    $("#intake-list").querySelectorAll("tr[data-code]").forEach((tr) => {
      tr.onclick = async (e) => {
        if (e.target.dataset.del) return;
        const code = tr.dataset.code;
        try {
          const d = await api("/api/intake/" + code);
          if (d._built) {
            $("#f-detail").innerHTML = jobDetail(code, d.job, d.meta);
            $("#f-handoff").innerHTML = "";
            $("#f-loaded").textContent = "구축됨: " + code + " (job.json)";
          } else {
            setForm(d);
            $("#f-handoff").innerHTML = ""; $("#f-detail").innerHTML = "";
            $("#f-loaded").textContent = "불러옴: intake/" + code + ".json";
          }
          window.scrollTo({ top: 0, behavior: "smooth" });
        } catch (err) { toast(err.message, "err"); }
      };
    });
    $("#intake-list").querySelectorAll("[data-del]").forEach((b) => {
      b.onclick = async (e) => {
        e.stopPropagation();
        if (!confirm(`intake/${b.dataset.del}.json 삭제할까요?`)) return;
        await api("/api/intake/" + b.dataset.del, { method: "DELETE" });
        toast("삭제됨", "ok"); loadList();
      };
    });
  }

  await loadList();
  if (params.code) {
    try { setForm(await api("/api/intake/" + params.code)); $("#f-loaded").textContent = "불러옴: " + params.code; }
    catch { codeEl.value = params.code; }
  } else clearForm();
}

// ── 파이프라인 ────────────────────────────────────────────
async function renderPipeline(params) {
  const rows = await api("/api/intake/list");
  const devMap = {};
  try {
    const ds = await api("/api/status/laws?target=dev");
    (ds.laws || []).forEach((l) => { devMap[l.code] = l; });
  } catch (e) { /* dev 상태 못 읽어도 파이프라인은 진행 */ }
  view.innerHTML = `
    <h1>파이프라인</h1>
    <p class="page-sub">법 하나를 적재·검증·배포하는 곳. 터미널 대신 버튼으로.</p>
    <div class="help">
      <b>이 탭은 <span style="color:var(--accent)">이미 구축된 법(job.json 있음)</span>의 재적재·검증·배포용 — 판단이 필요 없는 반복 작업을 터미널 없이.</b>
      <ul>
        <li><b>신규 법 최초 구축은 여기가 아닙니다.</b> <a href="#/intake">인테이크</a>만 만들어 Claude 에게 핸드오프하면, Claude 가 법령ID 검색 → job.json 작성 → 적재·verify·보정까지 수행합니다.</li>
        <li>여기서 직접 하는 일: <b>개정 반영 재적재 · 부분 갱신(--only) · verify · 운영 배포</b>. (운영 배포는 사람 결정)</li>
      </ul>
      <b style="display:block;margin-top:12px">버튼 — 위 <span style="color:var(--accent)">법(code)</span> 먼저 고르고, 보통 ①→④ 순서</b>
      <ol>
        <li><b>Dry-run</b> — 실제 적재 없이 빌드+검증만(미리보기). 새 법이나 큰 변경 전 안전 확인용.</li>
        <li><b>적재 (dev)</b> — 개발 DB <code>ldb_&lt;code&gt;</code> 에 실제 반영. 이미 있는 DB를 갈아엎으려면 <b>--force</b> 체크.</li>
        <li><b>verify</b> — 적재 후 연결 무결성(고아 0 등) 확인.</li>
        <li><b>운영 배포(복제)</b> — 개발에서 다듬은 DB를 운영으로 그대로 복제. <span style="color:var(--amber)">⚠ 운영 DROP+재생성</span>.</li>
      </ol>
      <p class="muted" style="margin:8px 0 0"><b>--only</b> = 특정 단계만 갱신(예: <code>annex</code> → 별표만, <code>annex,ref</code> 복수). 비우면 전체 실행. 로그는 아래에 실시간 표시.</p>
    </div>
    <div class="panel">
      <div class="row" style="align-items:flex-end">
        <div class="field" style="max-width:260px">
          <label>법 (code)</label>
          <select id="p-code">
            <option value="">— 선택 —</option>
            ${rows.map((r) => `<option value="${esc(r.code)}">${esc(r.code)} · ${esc(r.title)} (${esc(r.status)})</option>`).join("")}
          </select>
        </div>
        <div class="field" style="max-width:200px">
          <label>--only <span class="hint">(선택)</span></label>
          <input type="text" id="p-only" placeholder="annex,ref" autocomplete="off">
        </div>
        <div class="field">
          <label class="checkbox" title="기존 ldb_<code> 가 있으면 DROP+재생성 (수동보정은 overrides 로 재적용)"><input type="checkbox" id="p-force"> --force (기존 재생성)</label>
        </div>
      </div>
      <div class="btn-row">
        <button class="btn" id="b-dry">Dry-run</button>
        <button class="btn btn-green" id="b-apply">적재 (dev)</button>
        <button class="btn" id="b-verify">verify</button>
        <span style="flex:1"></span>
        <button class="btn btn-amber" id="b-replicate" title="dev → 운영 정확복제 (mysqldump | mysql, SSH 터널)">운영 배포 (복제)</button>
      </div>
    </div>
    <div id="p-info"></div>
    <div class="log" id="p-log"><span class="meta">code 선택 후 작업 버튼을 누르세요.</span></div>`;

  const codeSel = $("#p-code");
  if (params.code) codeSel.value = params.code;

  // 선택 피드백 — 고른 법의 개발 상태를 바로 보여주고, '운영과 비교'로 배포 전 차이 확인
  const showSel = () => {
    const c = codeSel.value;
    if (!c) { $("#p-info").innerHTML = ""; return; }
    const dl = devMap[c];
    $("#p-info").innerHTML = `<div class="panel">
      <div class="btn-row" style="justify-content:space-between;margin-bottom:8px">
        <b>선택: <span class="code">${esc(c)}</span>${dl ? "" : ' <span class="muted">— 개발 DB 없음</span>'}</b>
        <button class="btn btn-sm" id="p-cmp"${dl ? "" : " disabled"}>운영과 비교 (배포 전 확인)</button>
      </div>
      <div id="p-cmp-body">${dl ? lawTable([dl], null) : '<div class="empty">개발 DB가 없습니다 — 먼저 적재(dev) 하세요.</div>'}</div>
    </div>`;
    const cmp = $("#p-cmp");
    if (cmp) cmp.onclick = async () => {
      cmp.disabled = true; cmp.innerHTML = '<span class="spinner"></span> 운영 확인 중…';
      try {
        const prod = await api("/api/status/laws?target=prod");
        const pl = (prod.laws || []).find((l) => l.code === c);
        $("#p-cmp-body").innerHTML = lawTable(dl ? [dl] : [], pl ? [pl] : []);
        cmp.textContent = "운영 다시 확인";
      } catch (e) { toast(e.message, "err"); cmp.textContent = "운영 확인 재시도"; }
      finally { cmp.disabled = false; }
    };
  };
  codeSel.onchange = showSel;
  showSel();
  const logEl = $("#p-log");
  const allBtns = ["#b-dry", "#b-apply", "#b-verify", "#b-replicate"].map((s) => $(s));
  const need = () => { const c = codeSel.value; if (!c) { toast("code 를 선택하세요", "err"); } return c; };
  const only = () => { const v = $("#p-only").value.trim(); return v ? `&only=${encodeURIComponent(v)}` : ""; };
  const force = () => ($("#p-force").checked ? "&force=true" : "");

  $("#b-dry").onclick = () => { const c = need(); if (c) runStream(`/api/pipeline/run?code=${c}${only()}`, logEl, allBtns); };
  $("#b-apply").onclick = () => {
    const c = need(); if (!c) return;
    const f = $("#p-force").checked;
    if (!confirm(`ldb_${c} 에 적재(dev)합니다${f ? " · --force(기존 DROP+재생성)" : ""}. 진행할까요?`)) return;
    runStream(`/api/pipeline/run?code=${c}&apply=true${force()}${only()}`, logEl, allBtns);
  };
  $("#b-verify").onclick = () => { const c = need(); if (c) runStream(`/api/pipeline/verify?code=${c}`, logEl, allBtns); };
  $("#b-replicate").onclick = () => {
    const c = need(); if (!c) return;
    if (!confirm(`⚠ 운영 배포\n\ndev 의 ldb_${c} 를 운영 DB로 정확복제합니다(운영 기존 DROP+CREATE).\n계속할까요?`)) return;
    runStream(`/api/pipeline/replicate?code=${c}`, logEl, allBtns);
  };
}

// ── 도구 (파사드 런치) ────────────────────────────────────
async function renderTools() {
  view.innerHTML = `<h1>도구</h1><p class="page-sub">기존 GUI 도구를 단일 현관에서 실행. (추후 웹페이지로 흡수 예정)</p>
    <div id="tools-body" class="muted"><span class="spinner"></span> 불러오는 중…</div>`;
  const tools = await api("/api/tools");
  $("#tools-body").innerHTML = `<div class="cards cards-wide">${tools.map((t) => `
    <div class="card">
      <h3>${esc(t.name)}</h3>
      <p>${esc(t.desc)}</p>
      ${(t.details && t.details.length)
        ? `<ul class="tool-details">${t.details.map((d) => `<li>${esc(d)}</li>`).join("")}</ul>`
        : ""}
      ${t.available
        ? `<button class="btn btn-primary launch" data-id="${esc(t.id)}">실행 ▸</button>`
        : `<span class="tag">경로 없음</span>`}
    </div>`).join("")}</div>`;
  $("#tools-body").querySelectorAll(".launch").forEach((b) => {
    b.onclick = async () => {
      b.disabled = true; b.textContent = "실행 중…";
      try { await api(`/api/tools/${b.dataset.id}/launch`, { method: "POST" }); toast("창을 띄웠습니다", "ok"); }
      catch (e) { toast(e.message, "err"); }
      finally { b.disabled = false; b.textContent = "실행 ▸"; }
    };
  });
}

// ── 노출 레지스트리 (dev/prod) ────────────────────────────
async function renderRegistry(params) {
  const target = params.target === "prod" ? "prod" : "dev";
  view.innerHTML = `
    <h1>노출 레지스트리</h1>
    <p class="page-sub">사용자에게 보이는 법령 목록·순서·표시명 관리 (<code>ldb_auth.law_registry</code>). 새 법 = DB 배포 + 여기 1행 등록.</p>
    <div class="seg">
      <a href="#/registry?target=dev" class="seg-btn ${target === "dev" ? "on" : ""}">개발 (dev)</a>
      <a href="#/registry?target=prod" class="seg-btn ${target === "prod" ? "on" : ""}">운영 (prod)</a>
    </div>
    ${target === "prod" ? `<div class="help" style="border-left-color:var(--amber)"><b style="color:var(--amber)">⚠ 운영(prod) 레지스트리</b> — 저장/삭제가 사용자 노출에 즉시 반영됩니다(확인창 표시).</div>` : ""}
    <div id="reg-body" class="muted"><span class="spinner"></span> 불러오는 중…</div>`;

  async function load() {
    let data;
    try { data = await api(`/api/registry?target=${target}`); }
    catch (e) { $("#reg-body").innerHTML = `<p class="empty">${esc(e.message)}</p>`; return; }
    const rows = data.rows || [], unreg = data.unregistered || [];
    $("#reg-body").innerHTML = `
      <div class="panel">
        <div class="row" style="align-items:flex-end">
          <div class="field" style="max-width:160px"><label>코드</label>
            <input type="text" id="r-code" list="r-unreg" autocomplete="off" placeholder="g">
            <datalist id="r-unreg">${unreg.map((c) => `<option value="${esc(c)}">미등록 ldb_${esc(c)}</option>`).join("")}</datalist>
          </div>
          <div class="field"><label>표시명 <span class="hint">빈칸=법명 자동</span></label><input type="text" id="r-label"></div>
          <div class="field" style="max-width:90px"><label>순서</label><input type="text" id="r-order" value="100"></div>
          <div class="field" style="max-width:140px"><label>종류</label>
            <select id="r-kind"><option value="law">law</option><option value="accounting">accounting</option></select></div>
          <div class="field" style="max-width:110px"><label>노출</label><label class="checkbox" style="padding-top:9px"><input type="checkbox" id="r-enabled" checked> 노출</label></div>
        </div>
        <div class="btn-row">
          <button class="btn btn-primary" id="r-save">추가 / 수정 저장</button>
          <button class="btn" id="r-clear">폼 비우기</button>
          ${unreg.length ? `<span class="muted">미등록 DB: ${unreg.map(esc).join(", ")} — 코드칸 ▼ 에서 선택</span>` : ""}
        </div>
      </div>
      <div class="panel" style="padding:0;overflow:hidden">
        ${rows.length ? `<table><thead><tr><th>코드</th><th>표시명</th><th>순서</th><th>노출</th><th>종류</th><th></th></tr></thead><tbody>
          ${rows.map((r) => `<tr data-code="${esc(r.code)}" style="cursor:pointer">
            <td class="code">${esc(r.code)}</td><td>${r.label ? esc(r.label) : '<span class="muted">(법명 자동)</span>'}</td>
            <td>${r.sort_order}</td><td>${r.enabled ? '<span class="tag st-ok">노출</span>' : '<span class="tag st-missing">숨김</span>'}</td>
            <td>${esc(r.kind)}</td>
            <td style="text-align:right"><button class="btn btn-sm" data-del="${esc(r.code)}">삭제</button></td>
          </tr>`).join("")}
        </tbody></table>` : `<div class="empty">등록된 법령 없음</div>`}
      </div>`;

    const set = (r) => {
      $("#r-code").value = r.code || "";
      $("#r-label").value = r.label || "";
      $("#r-order").value = r.sort_order ?? 100;
      $("#r-kind").value = r.kind || "law";
      $("#r-enabled").checked = !(r.enabled === 0 || r.enabled === false);
    };
    const clear = () => { set({ sort_order: 100, enabled: true, kind: "law" }); $("#r-code").focus(); };
    $("#r-clear").onclick = clear;

    $("#reg-body").querySelectorAll("tr[data-code]").forEach((tr) => {
      tr.onclick = (e) => {
        if (e.target.dataset.del) return;
        const r = rows.find((x) => x.code === tr.dataset.code);
        if (r) { set(r); window.scrollTo({ top: 0, behavior: "smooth" }); }
      };
    });
    $("#reg-body").querySelectorAll("[data-del]").forEach((b) => {
      b.onclick = async (e) => {
        e.stopPropagation();
        if (!confirm(`${target === "prod" ? "운영(prod) " : ""}레지스트리에서 '${b.dataset.del}' 제거할까요? (법령 DB 는 그대로)`)) return;
        try { await api(`/api/registry/${b.dataset.del}?target=${target}`, { method: "DELETE" }); toast("삭제됨", "ok"); load(); }
        catch (err) { toast(err.message, "err"); }
      };
    });
    $("#r-save").onclick = async () => {
      const code = $("#r-code").value.trim().toLowerCase();
      if (!code) { toast("코드를 입력하세요", "err"); return; }
      if (target === "prod" && !confirm(`운영(prod) 레지스트리에 '${code}' 저장합니다. 사용자 노출에 즉시 반영됩니다. 계속할까요?`)) return;
      const payload = {
        code, label: $("#r-label").value.trim(),
        sort_order: Number($("#r-order").value) || 100,
        enabled: $("#r-enabled").checked, kind: $("#r-kind").value,
      };
      try {
        await api(`/api/registry?target=${target}`, {
          method: "POST", headers: { "content-type": "application/json" }, body: JSON.stringify(payload),
        });
        toast("저장됨", "ok"); load();
      } catch (err) { toast(err.message, "err"); }
    };
  }
  await load();
}

// ── 해외법령 이관 (dev/prod 비교 + 법 단위 복제) ───────────
// 국내 ldb_<code> 와 달리 해외법령은 단일 fin_law_db 안에 모든 나라 법이 공존 →
// DB 통째 덤프가 아니라 선택 code 한 건만 교체(다른 나라 법 무해).
const JURIS_LABEL = { eu: "🇪🇺 EU", us: "🇺🇸 미국", jp: "🇯🇵 일본", hk: "🇭🇰 홍콩", sg: "🇸🇬 싱가포르", other: "기타" };
const JURIS_RANK = { eu: 0, us: 1, jp: 2, hk: 3, sg: 4, other: 5 };

function koRate(l) {
  if (!l || !l.provision_count) return '<span class="muted">—</span>';
  const pct = Math.round((l.ko_count / l.provision_count) * 100);
  return `${l.ko_count}/${l.provision_count} <span class="muted">(${pct}%)</span>`;
}
// 상태는 dev/prod 지문(조문수·번역수·내용 CRC) 일치 여부로 판정
function foreignStatus(d, p, prodLoaded) {
  if (!prodLoaded) return "";
  if (!p) return '<span class="tag st-missing">미배포</span>';
  if (!d) return '<span class="tag st-warn">운영만 있음</span>';
  const same = d.provision_count === p.provision_count && d.ko_count === p.ko_count && d.content_sig === p.content_sig;
  if (same) return '<span class="tag st-ok">최신</span>';
  const bits = [];
  if (d.provision_count !== p.provision_count) bits.push(`조문 ${p.provision_count}→${d.provision_count}`);
  if (d.ko_count !== p.ko_count) bits.push(`번역 ${p.ko_count}→${d.ko_count}`);
  if (!bits.length) bits.push("본문 갱신");
  return `<span class="tag st-behind" title="개발 ↔ 운영 지문 불일치">운영 지체</span> <span class="muted" style="font-size:12px">${esc(bits.join(" · "))}</span>`;
}
function foreignTable(devLaws, prodLaws) {
  const prodLoaded = !!prodLaws;
  const byCode = new Map();
  const add = (laws, key) => (laws || []).forEach((l) => {
    if (!byCode.has(l.code)) byCode.set(l.code, { code: l.code });
    byCode.get(l.code)[key] = l;
  });
  add(devLaws, "dev"); add(prodLaws, "prod");
  const entries = [...byCode.values()];
  if (!entries.length) return `<div class="empty">해외법령 없음</div>`;
  const meta = (e) => e.dev || e.prod;
  entries.sort((a, b) => {
    const ja = JURIS_RANK[meta(a).jurisdiction] ?? 9, jb = JURIS_RANK[meta(b).jurisdiction] ?? 9;
    return ja - jb || a.code.localeCompare(b.code);
  });
  const colspan = prodLoaded ? 6 : 4;
  let body = "", curJuris = null;
  for (const e of entries) {
    const m = meta(e), d = e.dev, p = e.prod;
    if (m.jurisdiction !== curJuris) {
      curJuris = m.jurisdiction;
      body += `<tr><td colspan="${colspan}" style="background:rgba(255,255,255,.03);font-weight:600;padding:6px 12px">${esc(JURIS_LABEL[curJuris] || curJuris)}</td></tr>`;
    }
    const title = `${esc(m.title_ko || m.code)}${m.abbrev ? ` <span class="muted">(${esc(m.abbrev)})</span>` : ""}`;
    const prodCells = prodLoaded
      ? `<td class="code">${p ? koRate(p) : '<span class="muted">없음</span>'}</td>
         <td>${foreignStatus(d, p, true)}</td>` : "";
    body += `<tr>
      <td class="code">${esc(e.code)}</td>
      <td>${title}</td>
      <td class="code">${d ? koRate(d) : '<span class="muted">없음</span>'}</td>
      ${prodCells}
      <td style="text-align:right">${d ? `<button class="btn btn-sm btn-amber" data-xfer="${esc(e.code)}" title="이 법 한 건만 운영으로 복제">이관 ▸</button>` : ""}</td>
    </tr>`;
  }
  return `<table><thead><tr>
    <th>code</th><th>법령명</th><th>개발 번역</th>
    ${prodLoaded ? "<th>운영 번역</th><th>상태</th>" : ""}
    <th></th>
  </tr></thead><tbody>${body}</tbody></table>`;
}

// 이관 전 미리보기 패널 — dev↔prod 조(article) 단위 신규/변경/삭제
function previewPanel(d) {
  const artLine = (g, label, color) => g.count
    ? `<div style="margin-top:6px"><b style="color:${color}">${label} ${g.count}개</b>${g.count ? ":" : ""}
         <span class="muted code" style="font-size:12px">${g.sample.map(esc).join(", ")}${g.more ? ` …외 ${g.more}` : ""}</span></div>`
    : "";
  const head = d.dev_exists
    ? (d.prod_exists ? "운영에 이미 있음 — <b>변경분만</b> 반영" : '<b style="color:var(--amber)">운영 미배포</b> — 전체 신규 적재')
    : '<b style="color:var(--amber)">개발에 없음</b> — 이관 불가';
  const nochange = d.dev_exists && d.prod_exists && (d.added.count + d.changed.count + d.removed.count === 0);
  return `<div class="panel" style="border-left:3px solid var(--amber)">
    <div class="btn-row" style="justify-content:space-between;margin-bottom:8px">
      <b>이관 미리보기 · <span class="code">${esc(d.code)}</span></b>
      <span class="muted">${head}</span>
    </div>
    <table><tbody>
      <tr><td style="width:120px">조문(seg)</td><td class="code">운영 ${d.prod_segs} → 개발 ${d.dev_segs}</td></tr>
      <tr><td>번역(seg)</td><td class="code">운영 ${d.prod_ko} → 개발 ${d.dev_ko}</td></tr>
      <tr><td>조(article)</td><td class="code">운영 ${d.prod_articles} → 개발 ${d.dev_articles}</td></tr>
    </tbody></table>
    ${artLine(d.added, "신규 조", "var(--accent)")}
    ${artLine(d.changed, "변경 조", "var(--amber)")}
    ${artLine(d.removed, "삭제 조", "var(--muted)")}
    ${nochange ? `<p class="muted" style="margin:8px 0 0">개발과 운영이 동일합니다(이관해도 변화 없음).</p>` : ""}
    <div class="btn-row" style="margin-top:12px">
      <button class="btn btn-amber" id="pv-go"${d.dev_exists ? "" : " disabled"}>이 내용으로 이관 ▸</button>
      <button class="btn" id="pv-cancel">취소</button>
    </div>
  </div>`;
}

async function renderForeign() {
  view.innerHTML = `
    <h1>해외법령 이관</h1>
    <p class="page-sub">단일 <code>fin_law_db</code> 안의 법(code)별로 개발→운영 복제. <b>선택한 법만 교체</b>되고 다른 나라 법은 그대로입니다.</p>
    <div class="help">
      <b>국내(ldb_&lt;code&gt;)와 구조가 달라 이관 방식이 다릅니다.</b>
      <ul>
        <li>국내는 1법=1DB라 DB 통째 복제하지만, 해외는 모든 나라 법이 <code>fin_law_db</code> 한 곳에 행으로 공존합니다.</li>
        <li>그래서 <b>선택 code 한 건의 law + law_provision(원문·번역)만</b> 트랜잭션으로 갈아끼웁니다(다른 법 무해).</li>
        <li>메모(<code>foreign_memo</code>)는 논리키 기반이라 이관과 무관하게 보존됩니다.</li>
        <li><b>운영 불러와 비교</b> → 법별 <b>이관 ▸</b>(미리보기 후 실행), 또는 <b>지체 일괄 이관</b>으로 다른 법을 한 번에.</li>
      </ul>
    </div>
    <div class="row" style="align-items:center;justify-content:space-between;margin:18px 0 12px">
      <h2 style="margin:0">개발 / 운영 해외법령 현황 <span class="muted" style="font-size:13px;font-weight:400">— 법별 번역 커버리지·내용 지문 비교</span></h2>
      <div class="btn-row" style="margin:0">
        <button class="btn btn-sm" id="load-prod-f">운영(prod) 불러와 비교</button>
        <button class="btn btn-sm btn-amber" id="xfer-stale" disabled title="미배포·운영지체 법을 한 번에 이관">지체 일괄 이관</button>
      </div>
    </div>
    <div class="panel" style="padding:0;overflow:hidden"><div id="foreign-status" class="muted" style="padding:18px"><span class="spinner"></span> 개발 현황 불러오는 중…</div></div>
    <div id="f-preview" style="margin-top:14px"></div>
    <div class="log" id="f-log" style="margin-top:16px"><span class="meta">법별 '이관 ▸' 버튼을 누르면 여기에 실시간 로그가 표시됩니다.</span></div>`;

  let dev, prod = null;
  try { dev = await api("/api/foreign/status?target=dev"); }
  catch (e) { $("#foreign-status").innerHTML = `<p class="empty" style="padding:18px">${esc(e.message)}</p>`; return; }

  const logEl = $("#f-log");
  const refreshProd = async () => { try { prod = await api("/api/foreign/status?target=prod"); } catch (e) { /* keep stale */ } };
  // dev 와 운영 지문이 다른(미배포 포함) code 목록 — 일괄 이관 대상
  const staleCodes = () => {
    if (!prod) return [];
    const pmap = new Map((prod.laws || []).map((l) => [l.code, l]));
    return (dev.laws || []).filter((d) => {
      const p = pmap.get(d.code);
      return !p || d.provision_count !== p.provision_count || d.ko_count !== p.ko_count || d.content_sig !== p.content_sig;
    }).map((d) => d.code);
  };

  // 단건 이관 전 미리보기 → 확인 → 실행
  async function showPreview(code) {
    const pv = $("#f-preview");
    pv.innerHTML = `<div class="panel"><span class="spinner"></span> '${esc(code)}' 미리보기(운영과 비교) 중…</div>`;
    pv.scrollIntoView({ behavior: "smooth", block: "nearest" });
    let d;
    try { d = await api(`/api/foreign/preview?code=${encodeURIComponent(code)}`); }
    catch (e) { pv.innerHTML = `<div class="panel"><p class="empty">${esc(e.message)}</p></div>`; return; }
    pv.innerHTML = previewPanel(d);
    $("#pv-cancel").onclick = () => { pv.innerHTML = ""; };
    $("#pv-go").onclick = () => {
      if (!confirm(`'${code}' 를 운영 fin_law_db 로 이관합니다(해당 법만 교체). 계속할까요?`)) return;
      const host = $("#foreign-status");
      const btns = [...host.querySelectorAll("[data-xfer]"), $("#load-prod-f"), $("#xfer-stale"), $("#pv-go"), $("#pv-cancel")];
      runStream(`/api/foreign/replicate?code=${encodeURIComponent(code)}`, logEl, btns, async (ok) => {
        if (ok) { pv.innerHTML = ""; if (prod) { await refreshProd(); draw(); } }
      });
    };
  }

  const draw = () => {
    const host = $("#foreign-status");
    host.className = ""; host.style.padding = "0";
    host.innerHTML = foreignTable(dev.laws, prod && prod.laws);
    host.querySelectorAll("[data-xfer]").forEach((b) => { b.onclick = () => showPreview(b.dataset.xfer); });

    // 일괄 이관 버튼 상태 갱신
    const sb = $("#xfer-stale");
    const stale = staleCodes();
    if (!prod) { sb.disabled = true; sb.textContent = "지체 일괄 이관"; }
    else { sb.disabled = stale.length === 0; sb.textContent = stale.length ? `지체 일괄 이관 (${stale.length})` : "전부 최신 ✓"; }
    sb.onclick = () => {
      if (!stale.length) return;
      if (!confirm(`운영과 다른 ${stale.length}개 법을 일괄 이관합니다:\n\n${stale.join(", ")}\n\n각 법은 독립 트랜잭션(일부 실패해도 성공분 보존)입니다. 계속할까요?`)) return;
      $("#f-preview").innerHTML = "";
      const btns = [...host.querySelectorAll("[data-xfer]"), $("#load-prod-f"), sb];
      runStream(`/api/foreign/replicate-bulk?codes=${encodeURIComponent(stale.join(","))}`, logEl, btns, async (ok) => {
        if (ok) { await refreshProd(); draw(); }
      });
    };
  };
  draw();

  $("#load-prod-f").onclick = async () => {
    const b = $("#load-prod-f");
    b.disabled = true; b.innerHTML = '<span class="spinner"></span> 운영 접속 중…';
    try { await refreshProd(); if (!prod) throw new Error("운영 현황을 불러오지 못했습니다"); draw(); b.textContent = "운영 새로고침"; toast("운영 해외법령 불러옴", "ok"); }
    catch (e) { toast(e.message, "err"); b.textContent = "운영(prod) 다시 시도"; }
    finally { b.disabled = false; }
  };
}

// ── router ────────────────────────────────────────────────
const ROUTES = { "/": renderHome, "/intake": renderIntake, "/pipeline": renderPipeline, "/registry": renderRegistry, "/foreign": renderForeign, "/tools": renderTools };

function parseHash() {
  const raw = (location.hash || "#/").slice(1);
  const [path, qs] = raw.split("?");
  const params = Object.fromEntries(new URLSearchParams(qs || ""));
  return { path: path || "/", params };
}

async function route() {
  if (activeES) { activeES.close(); activeES = null; }
  const { path, params } = parseHash();
  document.querySelectorAll("#nav a").forEach((a) =>
    a.classList.toggle("active", a.dataset.route === path));
  const fn = ROUTES[path] || renderHome;
  try { await fn(params); }
  catch (e) { view.innerHTML = `<h1>오류</h1><p class="empty">${esc(e.message)}</p>`; }
}

window.addEventListener("hashchange", route);
window.addEventListener("DOMContentLoaded", route);

$("#shutdown-btn").onclick = async () => {
  if (!confirm("허브 서버를 종료할까요? (이 탭은 닫으면 됩니다)")) return;
  try { await api("/api/shutdown", { method: "POST" }); } catch {}
  document.body.innerHTML = '<div style="padding:60px;text-align:center;color:#9aa3b2;font-family:sans-serif">허브를 종료했습니다. 이 탭을 닫으세요.</div>';
};
