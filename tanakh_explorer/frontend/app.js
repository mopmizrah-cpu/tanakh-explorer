/* חוקר התנ״ך — web interface (vanilla JS, no build step). */
"use strict";

let META = null;

// ---------------------------------------------------------------- utilities
const $ = (sel, el = document) => el.querySelector(sel);
const esc = (s) => String(s ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));

function h(tag, attrs = {}, ...children) {
  const el = document.createElement(tag);
  for (const [k, v] of Object.entries(attrs || {})) {
    if (v === null || v === undefined || v === false) continue;
    if (k === "class") el.className = v;
    else if (k === "html") el.innerHTML = v;
    else if (k.startsWith("on")) el.addEventListener(k.slice(2), v);
    else el.setAttribute(k, v === true ? "" : v);
  }
  for (const c of children.flat()) {
    if (c === null || c === undefined || c === false) continue;
    el.append(c instanceof Node ? c : document.createTextNode(String(c)));
  }
  return el;
}

const store = {
  get(k, d) { try { const v = localStorage.getItem("te:" + k); return v === null ? d : JSON.parse(v); } catch { return d; } },
  set(k, v) { try { localStorage.setItem("te:" + k, JSON.stringify(v)); } catch { /* storage unavailable */ } },
};

function globals() {
  return { layer: { kq: $("#g-kq").value, maqaf: $("#g-maqaf").value }, finals: $("#g-finals").value };
}

async function api(path, body, method) {
  const opt = body === undefined ? { method: method || "GET" } : {
    method: method || "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body),
  };
  const r = await fetch(path, opt);
  let data;
  try { data = await r.json(); } catch { data = { error: `שגיאת שרת (${r.status})` }; }
  if (!r.ok) throw new Error(data.error || data.detail || `שגיאה ${r.status}`);
  return data;
}

function field(label, input, cls = "") {
  return h("label", { class: "field " + cls }, h("span", {}, label), input);
}
function textInput(id, placeholder = "", value = "", heb = true) {
  return h("input", { id, type: "text", class: heb ? "heb" : "", placeholder, value, dir: "rtl", autocomplete: "off" });
}
function numInput(id, value, min) {
  return h("input", { id, type: "number", value, min: min ?? "" });
}
function selectEl(id, options, value) {
  const s = h("select", { id });
  for (const [v, label] of options) s.append(h("option", { value: v, selected: v === value }, label));
  return s;
}
function checkbox(id, label, checked = false) {
  return h("label", { class: "check" }, h("input", { id, type: "checkbox", checked }), label);
}
function parseList(s) {
  return String(s || "").split(/[,\s]+/).filter(Boolean).map((x) => parseInt(x, 10)).filter((x) => !Number.isNaN(x));
}
function card(title, ...children) {
  return h("div", { class: "card" }, title ? h("h3", {}, title) : null, ...children);
}
function loading(el, msg = "מחפש…") { el.innerHTML = ""; el.append(h("div", { class: "loading" }, msg)); }
function showError(el, e) { el.innerHTML = ""; el.append(h("div", { class: "card err" }, "שגיאה: " + e.message)); }

// ---------------------------------------------------------------- scope picker
class ScopePicker {
  constructor() {
    this.el = h("div", { class: "scope-items" });
    this.items = [];
    this.add("all");
    this.root = card("בחר תחום", this.el,
      h("div", { class: "actions" }, h("button", { class: "btn small secondary", type: "button", onclick: () => this.add("books") }, "+ הוסף תחום")),
      h("div", { class: "hint" }, "ברירת המחדל: כל התנ״ך. תחומים אחדים מצטרפים; התאמה אינה חוצה בין שני תחומים נפרדים."));
  }
  add(type) {
    const row = h("div", { class: "scope-item" });
    const typeSel = selectEl("", [["all", "כל התנ״ך"], ["section", "תורה / נביאים / כתובים"], ["group", "ספר (24 הספרים)"],
      ["books", "ספרים (חלוקת הדפוס)"], ["parasha", "פרשת שבוע"], ["masoretic", "פרשה פתוחה/סתומה"],
      ["chapters", "טווח פרקים"], ["verses", "טווח פסוקים"]], type);
    const body = h("span", { class: "row" });
    const rm = h("button", { class: "btn small secondary", type: "button", onclick: () => { row.remove(); this.items = this.items.filter((i) => i.row !== row); } }, "הסר");
    const item = { row, typeSel, body };
    typeSel.addEventListener("change", () => this.fill(item));
    row.append(typeSel, body, rm);
    this.el.append(row);
    this.items.push(item);
    this.fill(item);
  }
  bookSelect(multiple) {
    const s = h("select", multiple ? { multiple: true, size: 6 } : {});
    for (const b of META.books) s.append(h("option", { value: b.osis }, b.he));
    return s;
  }
  fill(item) {
    const t = item.typeSel.value;
    item.body.innerHTML = "";
    item.get = () => ({ type: "all" });
    if (t === "section") {
      const s = selectEl("", META.sections.map((x) => [x.id, x.he]));
      item.body.append(s);
      item.get = () => ({ type: "section", value: s.value });
    } else if (t === "group") {
      const s = selectEl("", META.groups_24.map((g) => [g, g]));
      item.body.append(s);
      item.get = () => ({ type: "group", value: s.value });
    } else if (t === "books") {
      const s = this.bookSelect(true);
      s.options[0].selected = true;
      item.body.append(s, h("span", { class: "hint" }, "Ctrl לבחירה מרובה"));
      item.get = () => ({ type: "books", value: [...s.selectedOptions].map((o) => o.value) });
    } else if (t === "parasha") {
      const s = selectEl("", META.parashot.map((p) => [p.name, p.name]));
      item.body.append(s);
      item.get = () => ({ type: "parasha", value: s.value });
    } else if (t === "masoretic") {
      const b = this.bookSelect(false);
      const n = numInput("", 1, 1);
      const info = h("span", { class: "hint" });
      const upd = () => { const bk = META.books.find((x) => x.osis === b.value); info.textContent = `(1–${bk.masoretic_sections})`; };
      b.addEventListener("change", upd); upd();
      item.body.append(b, h("span", {}, "פרשה מס׳"), n, info);
      item.get = () => ({ type: "masoretic", book: b.value, number: parseInt(n.value, 10) });
    } else if (t === "chapters") {
      const b = this.bookSelect(false), f = numInput("", 1, 1), to = numInput("", 1, 1);
      item.body.append(b, h("span", {}, "מפרק"), f, h("span", {}, "עד"), to);
      item.get = () => ({ type: "chapters", book: b.value, from: +f.value, to: +to.value });
    } else if (t === "verses") {
      const f = h("input", { type: "text", value: "Gen.1.1", dir: "ltr", size: 12 });
      const to = h("input", { type: "text", value: "Gen.2.3", dir: "ltr", size: 12 });
      item.body.append(h("span", {}, "מ־"), f, h("span", {}, "עד"), to, h("span", { class: "hint" }, "בתבנית Gen.1.1"));
      item.get = () => ({ type: "verses", from: f.value.trim(), to: to.value.trim() });
    }
  }
  value() { return { items: this.items.map((i) => i.get()) }; }
}

// ---------------------------------------------------------------- results
function wordHTML(w) {
  const t = w.text;
  let out = "", pos = 0;
  const spans = [...(w.hl || [])].sort((a, b) => a[0] - b[0]);
  for (const [s, e] of spans) {
    if (s < pos) continue;
    out += esc(t.slice(pos, s)) + "<mark>" + esc(t.slice(s, e)) + "</mark>";
    pos = e;
  }
  out += esc(t.slice(pos));
  return w.mark ? `<span class="wmark">${out}</span>` : out;
}

function verseEl(block) {
  if (block.more) return h("div", { class: "hint" }, `ועוד ${block.more} פסוקים…`);
  const parts = block.words.map((w, i) => wordHTML(w) + (i < block.words.length - 1 ? (w.maqaf ? "־" : " ") : ""));
  return h("div", { class: "verse", html: `<span class="vref">${esc(block.ref.ref_he)}</span>${parts.join("")}` });
}

function resultEl(r, i) {
  const ref = r.from && r.to && r.from.osis !== r.to.osis ? `${r.from.ref_he} – ${r.to.ref_he}` : (r.from ? r.from.ref_he : "");
  const head = h("div", { class: "head" }, h("span", { class: "badge" }, "#" + i), h("span", { class: "ref" }, ref),
    r.found ? h("span", { class: "found" }, r.found) : null,
    r.value !== undefined && r.value !== null ? h("span", { class: "badge" }, "ערך: " + r.value) : null,
    r.skips ? h("span", { class: "badge" }, "דילוגים: " + r.skips.join(", ")) : null);
  const box = h("div", { class: "result" }, head, ...(r.display || []).map(verseEl));
  if (r.steps && r.steps.length) {
    box.append(h("details", { class: "calc" }, h("summary", {}, "הצג כיצד חושבה התוצאה"),
      h("ol", { class: "steps" }, ...r.steps.map((s) => h("li", {}, s)))));
  }
  return box;
}

function settingsLine(s) {
  if (!s) return null;
  const bits = [s.layer_he, "תחום: " + s.scope_he];
  if (s.finals) bits.push(s.finals === "exact" ? "סופיות: מדויק" : "סופיות: ם=מ");
  if (s.skip_definition) bits.push(s.skip_definition);
  if (s.match_he) bits.push("התאמה: " + s.match_he);
  return h("div", { class: "hint" }, bits.filter(Boolean).join(" · "));
}

function exportLinks(res) {
  if (!res.history_id) return null;
  return h("span", { class: "row" },
    h("a", { href: `/api/history/${res.history_id}/export?format=csv`, class: "btn small secondary" }, "ייצוא CSV"),
    h("a", { href: `/api/history/${res.history_id}/export?format=json`, class: "btn small secondary" }, "ייצוא JSON"));
}

function renderResults(el, res, rerun, extraHead) {
  el.innerHTML = "";
  const limit = res.settings && res.settings.limit ? res.settings.limit : 100;
  const shown = (res.results || []).length;
  const head = h("div", { class: "summary" },
    h("span", { class: "total" }, `${(res.total ?? 0).toLocaleString("he-IL")} תוצאות`),
    res.elapsed_ms !== undefined ? h("span", { class: "hint" }, `${res.elapsed_ms} מ״ש`) : null,
    res.total_reverse ? h("span", { class: "badge" }, `קדימה ${res.total_forward} · הפוך ${res.total_reverse}`) : null,
    exportLinks(res));
  const c = card(null, head, settingsLine(res.settings), extraHead || null);
  if (!shown) c.append(h("div", { class: "hint" }, res.total ? "אין תוצאות בעמוד זה." : "לא נמצאו התאמות בתחום שנבחר."));
  (res.results || []).forEach((r, i) => c.append(resultEl(r, (res._offset || 0) + i + 1)));
  if (rerun && res.total > shown) {
    const off = res._offset || 0;
    c.append(h("div", { class: "pager" },
      h("button", { class: "btn small secondary", disabled: off === 0, onclick: () => rerun(Math.max(0, off - res._limit)) }, "הקודם"),
      h("span", { class: "hint" }, `${off + 1}–${off + shown} מתוך ${res.total.toLocaleString("he-IL")}`),
      h("button", { class: "btn small secondary", disabled: off + shown >= res.total, onclick: () => rerun(off + res._limit) }, "הבא")));
  }
  el.append(c);
}

async function runSearch(el, path, buildReq, extraHead) {
  const go = async (offset = 0) => {
    loading(el);
    try {
      const req = { ...globals(), ...buildReq(), offset, limit: 50 };
      const res = await api(path, req);
      res._offset = offset; res._limit = 50;
      renderResults(el, res, go, typeof extraHead === "function" ? extraHead(res) : extraHead);
    } catch (e) { showError(el, e); }
  };
  await go(0);
}

function queryAnalysisEl(q) {
  if (!q || !q.length) return null;
  return h("div", { class: "analysis" }, ...q.map((u) =>
    h("div", { class: "lbox" }, h("div", { class: "g" }, u.letter), h("div", { class: "v" }, u.vowels_he), h("div", { class: "v" }, "ערך " + u.value))));
}

// ---------------------------------------------------------------- permutation search
function anagramBox() {
  return h("div", { class: "row" }, checkbox("x-anagram", "חפש בכל סידורי האותיות (קומבינטוריקה)"),
    checkbox("x-orig", "כולל הסדר המקורי", true));
}
function anagramOn() { const c = $("#x-anagram"); return c && c.checked; }

function runAnagram(out, buildReq, exactSearch) {
  runSearch(out, "/api/search/anagram", () => ({ ...buildReq(), include_original: $("#x-orig").checked }), (res) => {
    const tbl = h("table", { class: "grid perm-table" }, h("tr", {}, h("th", {}, "סידור"), h("th", {}, "הופעות"), h("th", {}, "")));
    for (const a of res.arrangements) {
      tbl.append(h("tr", { class: a.original ? "sel" : "" },
        h("td", { class: "l" }, a.display + (a.original ? " (מקורי)" : "")), h("td", {}, a.count),
        h("td", {}, a.count ? h("button", { class: "btn small secondary", onclick: () => exactSearch(a.arrangement) }, "הצג רק סידור זה") : "")));
    }
    const note = res.arrangements_listed_all
      ? `${res.arrangements_total} סידורים אפשריים, מתוכם ${res.arrangements_found} נמצאו`
      : `${res.arrangements_total.toLocaleString("he-IL")} סידורים אפשריים — מוצגים ${res.arrangements_found} הסידורים שנמצאו`;
    return h("div", {}, h("div", { class: "summary" }, h("span", { class: "badge pass" }, "נבדקו כל הסידורים"), h("span", { class: "hint" }, note),
      h("span", { class: "hint" }, "אותיות סופיות נחשבות כרגילות (ם = מ)")), h("div", { class: "scroll", style: "max-height:320px" }, tbl));
  });
}

// ---------------------------------------------------------------- pages
const PAGES = [];
function page(id, title, lead, render) { PAGES.push({ id, title, lead, render }); }

function skipsField(id, def = "1") {
  return field("דילוג (מספר אחד = קבוע; רשימה = משתנה, למשל 5,10,5)", h("input", { id, type: "text", value: def, dir: "ltr" }));
}
function boundarySelect(id, withWord) {
  const opts = [["none", "מותר לחצות גבולות"], ["verse", "בתוך פסוק אחד"], ["chapter", "בתוך פרק אחד"], ["book", "בתוך ספר אחד"]];
  if (withWord) opts.splice(1, 0, ["word", "בתוך מילה אחת"]);
  return field("גבולות", selectEl(id, opts, "none"));
}

// 1 — acrostics
page("acrostic", "חיפוש ראשי תיבות", "ראשי מילים, סופי מילים, חיפוש מעורב, מילה שלמה, רצף אותיות וביטוי.", (root) => {
  const scope = new ScopePicker();
  const mode = selectEl("a-mode", [["first", "ראשי מילים"], ["last", "סופי מילים"], ["mixed", "מעורב — ראש/סוף לכל אות"],
    ["word", "מילה שלמה"], ["sequence", "רצף אותיות (גם בין מילים)"], ["phrase", "ביטוי (מילים שלמות ברצף)"]], "first");
  const q = textInput("a-q", "למשל: שלום", "שלום");
  const mixedBox = h("div", { class: "row" });
  const updMixed = () => {
    mixedBox.innerHTML = "";
    if (mode.value !== "mixed") return;
    const letters = [...q.value].filter((c) => c >= "א" && c <= "ת");
    letters.forEach((c, i) => mixedBox.append(field(c, selectEl("a-sel-" + i, [["first", "ראש מילה"], ["last", "סוף מילה"]], "first"))));
  };
  mode.addEventListener("change", updMixed); q.addEventListener("input", updMixed);
  const out = h("div");
  root.append(card("שאילתה",
    h("div", { class: "row" }, field("מילת חיפוש", q, "wide"), field("סוג חיפוש", mode), skipsField("a-skips"),
      boundarySelect("a-bound", true), field("קבוצות אותיות", selectEl("a-groups", [["", "ללא"], ["articulation", "חילופי מוצאות הפה (אחה״ע…)"]], ""))),
    mixedBox,
    h("div", { class: "row" }, checkbox("a-rev", "חפש גם בכיוון הפוך")), anagramBox(),
    h("div", { class: "actions" }, h("button", { class: "btn", onclick: () => go() }, "חפש"))), scope.root, out);
  const go = () => {
    const m = mode.value;
    if (anagramOn()) {
      const sm = { first: "heads", last: "tails", word: "word", sequence: "sequence" }[m];
      if (!sm) { showError(out, new Error("חיפוש בכל סידורי האותיות זמין לראשי מילים, סופי מילים, מילה שלמה ורצף אותיות")); return; }
      const base = () => ({ query: q.value, search_mode: sm, skips: parseList($("#a-skips").value), boundary: $("#a-bound").value, scope: scope.value() });
      runAnagram(out, base, (arr) => runSearch(out, "/api/search/mode", () => ({ ...base(), query: arr })));
      return;
    }
    if (m === "phrase") {
      return runSearch(out, "/api/search/phrase", () => ({ query: q.value, skips: parseList($("#a-skips").value), boundary: $("#a-bound").value, scope: scope.value() }));
    }
    runSearch(out, "/api/search/letters", () => {
      const letters = [...q.value].filter((c) => c >= "א" && c <= "ת");
      const req = { query: q.value, skips: parseList($("#a-skips").value), boundary: $("#a-bound").value, reverse: $("#a-rev").checked,
        letter_groups: $("#a-groups").value || null, scope: scope.value() };
      if (m === "word") Object.assign(req, { unit: "letters", whole_word: true });
      else if (m === "sequence") Object.assign(req, { unit: "letters" });
      else if (m === "mixed") Object.assign(req, { unit: "words", selector: "mixed", selectors: letters.map((_, i) => $("#a-sel-" + i).value) });
      else Object.assign(req, { unit: "words", selector: m });
      return req;
    });
  };
});

// 2 — verse acrostics
page("verses", "חיפוש פסוקים", "ראשי פסוקים וסופי פסוקים, ברצף או בדילוג.", (root) => {
  const scope = new ScopePicker();
  const q = textInput("v-q", "", "שלום");
  const sel = selectEl("v-sel", [["first", "ראשי פסוקים"], ["last", "סופי פסוקים"], ["mixed", "מעורב"]], "first");
  const mixedBox = h("div", { class: "row" });
  const upd = () => {
    mixedBox.innerHTML = "";
    if (sel.value !== "mixed") return;
    [...q.value].filter((c) => c >= "א" && c <= "ת").forEach((c, i) =>
      mixedBox.append(field(c, selectEl("v-sel-" + i, [["first", "ראש פסוק"], ["last", "סוף פסוק"]], "first"))));
  };
  sel.addEventListener("change", upd); q.addEventListener("input", upd);
  const out = h("div");
  root.append(card("שאילתה", h("div", { class: "row" }, field("מילת חיפוש", q, "wide"), field("סוג", sel), skipsField("v-skips"),
    boundarySelect("v-bound"), checkbox("v-rev", "גם בכיוון הפוך")), mixedBox, anagramBox(),
    h("div", { class: "actions" }, h("button", { class: "btn", onclick: () => go() }, "חפש"))), scope.root, out);
  const go = () => {
    if (anagramOn()) {
      const sm = { first: "verse_heads", last: "verse_tails" }[sel.value];
      if (!sm) { showError(out, new Error("חיפוש בכל סידורי האותיות זמין לראשי פסוקים או לסופי פסוקים")); return; }
      const base = () => ({ query: q.value, search_mode: sm, skips: parseList($("#v-skips").value), boundary: $("#v-bound").value, scope: scope.value() });
      runAnagram(out, base, (arr) => runSearch(out, "/api/search/letters", () => ({ ...base(), query: arr, unit: "verses", selector: sel.value })));
      return;
    }
    goPlain();
  };
  const goPlain = () => runSearch(out, "/api/search/letters", () => {
    const letters = [...q.value].filter((c) => c >= "א" && c <= "ת");
    const r = { query: q.value, unit: "verses", selector: sel.value, skips: parseList($("#v-skips").value),
      boundary: $("#v-bound").value, reverse: $("#v-rev").checked, scope: scope.value() };
    if (sel.value === "mixed") r.selectors = letters.map((_, i) => $("#v-sel-" + i).value);
    return r;
  });
});

// 3 — skips and exhaustive scans
page("skips", "חיפוש דילוגים", "דילוג קבוע, דילוג משתנה, דילוג מנקודת התחלה, וסריקה מקיפה של כל אפשרויות הדילוג.", (root) => {
  const scope = new ScopePicker();
  const q = textInput("s-q", "", "שלום");
  const unit = selectEl("s-unit", [["words", "מילים"], ["verses", "פסוקים"], ["letters", "אותיות (דילוג אותיות)"]], "words");
  const sel = selectEl("s-sel", [["first", "אות ראשונה"], ["last", "אות אחרונה"]], "first");
  const anchor = selectEl("s-anchor", [["", "ללא — כל נקודת התחלה"], ["scope", "מתחילת התחום"], ["verse", "מתחילת כל פסוק"], ["chapter", "מתחילת כל פרק"]], "");
  const out = h("div");
  const scanOut = h("div");
  root.append(card("דילוג מוגדר", h("div", { class: "row" }, field("מילת חיפוש", q, "wide"), field("יחידות", unit), field("מכל יחידה", sel),
    skipsField("s-skips", "5,10,5"), boundarySelect("s-bound", true)),
    h("div", { class: "row" }, field("נקודת התחלה", anchor), field("דילוג מנקודת ההתחלה לאות הראשונה", numInput("s-askip", 0, 0)),
      checkbox("s-rev", "גם בכיוון הפוך")),
    h("div", { class: "hint" }, "הגדרה: דילוג d פירושו שהיחידות שנבחרו מרוחקות d מקומות זו מזו (d=1 = יחידות סמוכות). דוגמה: 5,10,5 עם נקודת התחלה ודילוג פתיחה 6."),
    h("div", { class: "actions" }, h("button", { class: "btn", onclick: () => go() }, "חפש"))),
  card("חפש בכל אפשרויות הדילוג",
    h("div", { class: "row" }, field("דילוג מינימלי", numInput("s-min", 1, 1)), field("דילוג מקסימלי", numInput("s-max", 100, 1)),
      field("סוג", selectEl("s-var", [["const", "דילוג קבוע (כל ערך בטווח)"], ["var", "דילוגים משתנים (כל צירוף)"]], "const")),
      checkbox("s-scan-rev", "גם בכיוון הפוך")),
    h("div", { class: "actions" }, h("button", { class: "btn secondary", onclick: () => estimate() }, "הצג היקף הסריקה"),
      h("button", { class: "btn", onclick: () => startScan() }, "חפש בכל אפשרויות הדילוג")), scanOut),
  scope.root, out);
  const base = () => ({ ...globals(), query: q.value, unit: unit.value, selector: sel.value, boundary: $("#s-bound").value, scope: scope.value() });
  const go = () => runSearch(out, "/api/search/letters", () => ({ ...base(), skips: parseList($("#s-skips").value),
    anchor: anchor.value || null, anchor_skip: +$("#s-askip").value, reverse: $("#s-rev").checked }));
  const scanReq = () => ({ ...base(), skip_min: +$("#s-min").value, skip_max: +$("#s-max").value, variable: $("#s-var").value === "var",
    reverse: $("#s-scan-rev").checked, limit: 200 });
  async function estimate() {
    try {
      const e = await api("/api/scan/estimate", scanReq());
      scanOut.innerHTML = ""; scanOut.append(h("div", { class: "hint" }, e.explanation));
    } catch (err) { showError(scanOut, err); }
  }
  async function startScan() {
    try {
      const e = await api("/api/scan/estimate", scanReq());
      const { job_id } = await api("/api/scan/start", scanReq());
      watchJob(job_id, scanOut, e.explanation);
    } catch (err) { showError(scanOut, err); }
  }
});

function watchJob(jid, el, note) {
  el.innerHTML = "";
  const bar = h("div", { class: "progress" }, h("div"));
  const status = h("span", { class: "hint" }, "ממתין…");
  const cancelBtn = h("button", { class: "btn small secondary", onclick: () => api(`/api/jobs/${jid}/cancel`, {}) }, "בטל");
  const resumeBtn = h("button", { class: "btn small secondary", style: "display:none", onclick: async () => { await api(`/api/jobs/${jid}/resume`, {}); poll(); } }, "המשך");
  const res = h("div");
  el.append(note ? h("div", { class: "hint" }, note) : null, h("div", { class: "row" }, bar, status, cancelBtn, resumeBtn), res);
  const label = { queued: "בתור", running: "רץ", done: "הושלם", cancelled: "בוטל (ניתן להמשיך)", interrupted: "נקטע (ניתן להמשיך)", error: "שגיאה" };
  async function poll() {
    const j = await api(`/api/jobs/${jid}`);
    bar.firstChild.style.width = Math.round((j.progress || 0) * 100) + "%";
    status.textContent = `${label[j.status] || j.status} · ${Math.round((j.progress || 0) * 100)}%` + (j.error ? " · " + j.error : "");
    resumeBtn.style.display = ["cancelled", "interrupted", "error"].includes(j.status) ? "" : "none";
    cancelBtn.style.display = ["queued", "running"].includes(j.status) ? "" : "none";
    if (["queued", "running"].includes(j.status)) { setTimeout(poll, 700); return; }
    renderJobResult(res, j);
  }
  poll();
}

function renderJobResult(el, j) {
  el.innerHTML = "";
  const r = j.result || {};
  const complete = r.complete ? h("span", { class: "badge pass" }, "סריקה מלאה של הטווח שהוגדר") : h("span", { class: "badge warn" }, "הסריקה לא הושלמה — התוצאות חלקיות");
  if (j.kind === "constant_scan") {
    const rows = r.rows || [];
    const tbl = h("table", { class: "grid" }, h("tr", {}, h("th", {}, "דילוג"), h("th", {}, "כיוון"), h("th", {}, "התאמות"), h("th", {}, "דוגמה")));
    for (const row of rows) {
      const ex = row.results && row.results[0];
      tbl.append(h("tr", {}, h("td", {}, row.skip), h("td", {}, row.direction === "reverse" ? "הפוך" : "קדימה"), h("td", {}, row.count),
        h("td", {}, ex ? `${ex.from.ref_he} – ${ex.to.ref_he}` : "")));
    }
    el.append(h("div", { class: "summary" }, h("span", { class: "total" }, `${r.total ?? 0} התאמות`), complete,
      h("span", { class: "hint" }, `נבדקו ${r.skips_checked ?? "?"} מתוך ${r.skips_requested ?? "?"} ערכי דילוג`)), h("div", { class: "scroll" }, tbl));
    const all = rows.flatMap((x) => x.results || []).slice(0, 30);
    all.forEach((x, i) => el.append(resultEl(x, i + 1)));
  } else {
    el.append(h("div", { class: "summary" }, h("span", { class: "total" }, `${r.total ?? r.total_so_far ?? 0} התאמות`), complete));
    (r.results || []).forEach((x, i) => el.append(resultEl(x, i + 1)));
  }
}

// 4 — niqqud search
page("niqqud", "חיפוש ניקוד", "הזינו מילה מנוקדת; המערכת מנתחת את חתימת הניקוד ומחפשת אותה לפי שיוך התנועות לאותיות.", (root) => {
  const scope = new ScopePicker();
  const q = textInput("n-q", "מילה מנוקדת", "שָׁלוֹם");
  const kind = selectEl("n-kind", [["heads", "ניקוד בראשי מילים"], ["tails", "ניקוד בסופי מילים"], ["vheads", "ניקוד בראשי פסוקים"],
    ["vtails", "ניקוד בסופי פסוקים"], ["inverse", "ראשי כל המילים בפסוק — התאמה חלקית"], ["inverse_full", "ראשי כל המילים בפסוק — התאמה מלאה"],
    ["word", "מילה שלמה בעלת אותה חתימת ניקוד"], ["letters", "רצף אותיות בכל מקום"]], "heads");
  const match = selectEl("n-match", [["niqqud", "רק הניקוד, ללא תלות באותיות"], ["letters_niqqud", "אותיות וניקוד יחד"],
    ["value", "ערכי ניקוד לפי הסדר"], ["letters_value", "אותיות + ערכי ניקוד"]], "niqqud");
  const anal = h("div");
  const out = h("div");
  const analyze = async () => {
    try {
      const r = await api("/api/calc/letters", { query: q.value });
      anal.innerHTML = "";
      for (const w of r.words) {
        anal.append(h("div", { class: "analysis" }, ...w.letters.map((l) => h("div", { class: "lbox" },
          h("div", { class: "g" }, l.pointed), h("div", { class: "v" }, l.vowels_he.join(" + ")), h("div", { class: "v" }, "ערך " + l.niqqud_value)))),
        h("div", { class: "hint" }, `סכום ניקוד: ${w.niqqud_sum} · גימטריה רגילה: ${w.gematria_sum}`));
      }
    } catch (e) { showError(anal, e); }
  };
  q.addEventListener("change", analyze);
  root.append(card("שאילתה", h("div", { class: "row" }, field("מילה מנוקדת", q, "wide"), field("סוג חיפוש", kind), field("סוג התאמה", match),
    skipsField("n-skips"), boundarySelect("n-bound")),
    h("div", { class: "row" }, checkbox("n-qq", "קמץ קטן = קמץ בהשוואה", true)), anal,
    h("div", { class: "hint" }, "ההשוואה היא לפי שיוך כל תנועה לאות שלה. סגול וקובוץ אינם זהים גם כששניהם שווים 30, אלא אם נבחרה התאמה לפי ערכים. מומלץ לבחור ״קרי״ בהגדרות העליונות, משום שהכתיב אינו מנוקד."),
    h("div", { class: "actions" }, h("button", { class: "btn", onclick: () => go() }, "חפש"))), scope.root, out);
  analyze();
  const go = () => runSearch(out, "/api/search/niqqud", () => {
    const k = kind.value;
    const r = { query: q.value, match: match.value, merge_qamats_qatan: $("#n-qq").checked, skips: parseList($("#n-skips").value),
      boundary: $("#n-bound").value, scope: scope.value() };
    const map = { heads: ["words", "first"], tails: ["words", "last"], vheads: ["verses", "first"], vtails: ["verses", "last"],
      inverse: ["words", "first"], inverse_full: ["words", "first"], word: ["letters", "first"], letters: ["letters", "first"] };
    [r.unit, r.selector] = map[k];
    if (k === "inverse") r.boundary = "verse";
    if (k === "inverse_full") { r.boundary = "verse"; r.full_verse = true; r.skips = [1]; }
    if (k === "word") r.whole_word = true;
    return r;
  }, (res) => queryAnalysisEl(res.query_analysis));
});

// 5 — niqqud gematria
page("niqqud_sum", "גימטריית ניקוד", "חיפוש לפי הסכום המספרי של הניקוד לפי טבלת החוקר, בנפרד לגימטריית ניקוד ולגימטריית אותיות.", (root) => {
  const scope = new ScopePicker();
  const q = textInput("ns-q", "מילה מנוקדת", "שָׁלוֹם");
  const kind = selectEl("ns-kind", [["word", "מילים שסכום הניקוד שלהן שווה"], ["heads", "רצף ראשי מילים"], ["tails", "רצף סופי מילים"],
    ["verse_heads", "רצף ראשי פסוקים"], ["verse_tails", "רצף סופי פסוקים"], ["in_verse:verse_total", "בפסוק: סכום הפסוק כולו"],
    ["in_verse:run", "בפסוק: רצף מילים בתוך הפסוק"], ["in_verse:single_word", "בפסוק: מילה אחת"],
    ["in_verse:word_heads", "בפסוק: סכום ראשי כל המילים"], ["in_verse:word_tails", "בפסוק: סכום סופי כל המילים"]], "word");
  const compare = selectEl("ns-cmp", [["niqqud", "גימטריית ניקוד מול גימטריית ניקוד"], ["letters", "גימטריית ניקוד מול גימטריית אותיות"]], "niqqud");
  const source = selectEl("ns-src", [["niqqud", "ערך הניקוד של השאילתה"], ["letters", "גימטריית האותיות של השאילתה (חיפוש הפוך)"]], "niqqud");
  const out = h("div");
  root.append(card("שאילתה", h("div", { class: "row" }, field("מילה מנוקדת", q, "wide"), field("או ערך מספרי ישיר", numInput("ns-target", "")),
    field("מקור הערך", source), field("סוג חיפוש", kind), field("השוואה בתנ״ך", compare)),
    h("div", { class: "row" }, field("אורך הרצף (ברירת מחדל: מספר האותיות)", numInput("ns-len", "")), skipsField("ns-skips"), boundarySelect("ns-bound")),
    h("div", { class: "hint" }, "טבלה: פתח 6 · קמץ 16 · צירי 20 · סגול 30 · שווא 20 · חולם 10 · חיריק 10 · קובוץ 30 · שורוק 10 · חטף פתח 26 · חטף קמץ 36 · חטף סגול 50. טבלה ייעודית של החוקר, לא שיטה מסורתית."),
    h("div", { class: "actions" }, h("button", { class: "btn", onclick: () => go() }, "חפש"))), scope.root, out);
  const go = async () => {
    let target = $("#ns-target").value;
    if (!target && source.value === "letters") {
      const v = await api("/api/calc/gematria", { query: q.value, method: "standard" });
      target = v[0].value;
    }
    runSearch(out, "/api/search/niqqud-sum", () => {
      const [k, sub] = kind.value.split(":");
      const r = { query: q.value, target: target || null, compare: compare.value, skips: parseList($("#ns-skips").value),
        boundary: $("#ns-bound").value, scope: scope.value(), length: $("#ns-len").value ? +$("#ns-len").value : null };
      if (k === "tails") { r.kind = "heads"; r.selector = "last"; }
      else if (k === "verse_tails") { r.kind = "verse_heads"; r.selector = "last"; }
      else r.kind = k;
      if (sub) r.sub = sub;
      return r;
    }, (res) => h("div", {}, h("div", { class: "summary" }, h("span", { class: "badge" }, res.comparison), h("span", { class: "badge" }, "ערך מבוקש: " + res.target)),
      queryAnalysisEl(res.query_analysis)));
  };
});

// 6 — all gematria
function methodParamsEl(m, prefix) {
  const box = h("span", { class: "row" });
  for (const p of m.params || []) {
    const id = `${prefix}-${p.name}`;
    let inp;
    if (p.kind === "choice") inp = selectEl(id, p.choices.map((c) => [c.value, c.label]), p.default);
    else if (p.kind === "int") inp = numInput(id, p.default, p.min);
    else if (p.kind === "bool") inp = h("input", { id, type: "checkbox", checked: p.default });
    else inp = h("input", { id, type: "text", value: JSON.stringify(p.default), dir: "ltr" });
    box.append(field(p.label_he, inp));
  }
  return box;
}
function readParams(m, prefix) {
  const out = {};
  for (const p of m.params || []) {
    const el = $(`#${prefix}-${p.name}`);
    if (!el) continue;
    if (p.kind === "int") out[p.name] = +el.value;
    else if (p.kind === "bool") out[p.name] = el.checked;
    else if (p.kind === "json") { try { out[p.name] = JSON.parse(el.value || "{}"); } catch { throw new Error("ערך JSON לא תקין ב" + p.label_he); } }
    else out[p.name] = el.value;
  }
  return out;
}
const CAT_HE = { traditional: "מסורתית", mathematical: "מתמטית", niqqud: "ניקוד (טבלת החוקר)", custom: "מותאמת אישית" };

page("gematria", "כל סוגי הגימטריה", "מחשבון מפורט לכל השיטות, חיפוש לפי ערך או מספר, וסריקה בכל השיטות.", (root) => {
  const scope = new ScopePicker();
  const q = textInput("g-q", "מילה או ביטוי", "שָׁלוֹם");
  const methods = META.gematria_methods;
  const msel = selectEl("g-method", methods.map((m) => [m.id, `${m.name_he} — ${CAT_HE[m.category]}`]), "standard");
  const pbox = h("div");
  const info = h("div", { class: "hint" });
  const upd = () => {
    const m = methods.find((x) => x.id === msel.value);
    pbox.innerHTML = ""; pbox.append(methodParamsEl(m, "gp"));
    info.innerHTML = `<b>נוסחה:</b> ${esc(m.formula_he)}<br><b>מקור:</b> ${esc(m.source_he)}<br><b>אותיות סופיות:</b> ${esc(m.finals_he)}`;
  };
  msel.addEventListener("change", upd);
  const span = selectEl("g-span", [["words", "מילים / רצף מילים"], ["verse", "פסוק שלם"]], "words");
  const out = h("div");
  const calcOut = h("div");
  root.append(card("שאילתה ושיטה", h("div", { class: "row" }, field("מילה או ביטוי", q, "wide"), field("או מספר ישיר", numInput("g-target", "")), field("שיטה", msel)),
    pbox, info,
    h("div", { class: "row" }, field("חיפוש ב", span), field("מספר מילים מ־", numInput("g-nmin", 1, 1)), field("עד", numInput("g-nmax", 1, 1)),
      checkbox("g-cross", "מותר לחצות בין פסוקים")),
    h("div", { class: "actions" }, h("button", { class: "btn secondary", onclick: () => calc() }, "חשב בשיטה זו"),
      h("button", { class: "btn", onclick: () => go() }, "חפש בתנ״ך"),
      h("button", { class: "btn", onclick: () => all() }, "חיפוש בכל סוגי הגימטריה")), calcOut),
  card("שיטה מותאמת אישית", h("div", { class: "hint" }, "הגדירו ערך לכל אחת מ־22 האותיות (ואופציונלית לסופיות). השיטה תסווג כ״מותאמת אישית״ ולא כמסורתית."),
    h("div", { class: "row" }, field("מזהה (אותיות לטיניות)", h("input", { id: "c-slug", type: "text", dir: "ltr", value: "my_method" })),
      field("שם", h("input", { id: "c-name", type: "text", value: "השיטה שלי" })),
      field("ערכים (JSON)", h("textarea", { id: "c-vals", rows: 2, dir: "ltr", cols: 60 }, JSON.stringify(Object.fromEntries([..."אבגדהוזחטיכלמנסעפצקרשת"].map((c, i) => [c, i + 1])))), "wide")),
    h("div", { class: "actions" }, h("button", { class: "btn secondary", onclick: () => addCustom() }, "הוסף שיטה"))),
  scope.root, out);
  upd();
  const curParams = () => readParams(methods.find((x) => x.id === msel.value), "gp");
  async function calc() {
    try {
      const r = await api("/api/calc/gematria", { query: q.value, methods: [msel.value], params: { [msel.value]: curParams() } });
      calcOut.innerHTML = "";
      calcOut.append(h("div", { class: "summary" }, h("span", { class: "total" }, `${r[0].name_he}: ${r[0].value}`)),
        h("ol", { class: "steps" }, ...r[0].steps.map((s) => h("li", {}, s))));
    } catch (e) { showError(calcOut, e); }
  }
  const go = () => runSearch(out, "/api/search/gematria", () => ({ query: q.value, target: $("#g-target").value || null, method: msel.value,
    params: curParams(), span: span.value, n_min: +$("#g-nmin").value, n_max: +$("#g-nmax").value, cross_verses: $("#g-cross").checked, scope: scope.value() }),
  (res) => res.query_calculation ? h("div", { class: "hint" }, `ערך השאילתה: ${res.target} · ` + res.query_calculation.steps.join(" · ")) : h("div", { class: "hint" }, `ערך מבוקש: ${res.target}`));
  async function all() {
    loading(out, "מחשב את כל השיטות…");
    try {
      const r = await api("/api/search/gematria-all", { ...globals(), query: q.value, n_max: +$("#g-nmax").value, scope: scope.value() });
      out.innerHTML = "";
      const tbl = h("table", { class: "grid" }, h("tr", {}, h("th", {}, "שיטה"), h("th", {}, "קטגוריה"), h("th", {}, "ערך השאילתה"), h("th", {}, "מספר התאמות"), h("th", {}, "")));
      for (const row of r.rows) {
        tbl.append(h("tr", {}, h("td", {}, row.name_he), h("td", {}, CAT_HE[row.category]), h("td", {}, row.value), h("td", {}, row.total),
          h("td", {}, h("button", { class: "btn small secondary", onclick: () => { msel.value = row.method; upd(); $("#g-target").value = ""; go(); } }, "הצג תוצאות"))));
      }
      out.append(card(null, h("div", { class: "summary" }, h("span", { class: "total" }, `${r.methods_checked} שיטות נבדקו`),
        h("span", { class: "badge pass" }, "סריקה מלאה של השיטות שנבחרו"), exportLinks(r), h("span", { class: "hint" }, `${r.elapsed_ms} מ״ש`)),
      h("div", { class: "hint" }, `ספירת התאמות למילים בודדות${+$("#g-nmax").value > 1 ? " ולרצפים של עד " + $("#g-nmax").value + " מילים (בתוך פסוק)" : ""}.`), tbl));
    } catch (e) { showError(out, e); }
  }
  async function addCustom() {
    try {
      const m = await api("/api/custom-methods", { slug: $("#c-slug").value, name_he: $("#c-name").value, values: JSON.parse($("#c-vals").value) });
      META.gematria_methods.push(m);
      msel.append(h("option", { value: m.id }, `${m.name_he} — ${CAT_HE[m.category]}`));
      msel.value = m.id; upd();
    } catch (e) { alert(e.message); }
  }
});

// 7 — letter transformations
const SEARCH_MODES = [["word", "מילה שלמה"], ["sequence", "רצף אותיות"], ["heads", "ראשי תיבות"], ["tails", "סופי תיבות"], ["verse_heads", "ראשי פסוקים"], ["verse_tails", "סופי פסוקים"]];
page("transform", "חילופי אותיות", "א״ת ב״ש, אלב״ם, אכ״ב י״, אטב״ח, אח״ס בט״ע, אי״ק בכ״ר, הזזות ועוד — מחוברים לחיפוש בתנ״ך.", (root) => {
  const scope = new ScopePicker();
  const q = textInput("t-q", "", "בבל");
  const ts = META.transformations;
  const tsel = selectEl("t-id", ts.map((t) => [t.id, t.name_he]), "atbash");
  const pbox = h("div"), info = h("div", { class: "hint" }), outTxt = h("div");
  const upd = () => {
    const t = ts.find((x) => x.id === tsel.value);
    pbox.innerHTML = ""; pbox.append(methodParamsEl(t, "tp"));
    info.innerHTML = `${esc(t.description_he)}<br><b>מקור:</b> ${esc(t.source_he)}${t.involution ? "<br>החלפה הדדית: הפעלה כפולה מחזירה את המקור." : ""}`;
  };
  tsel.addEventListener("change", upd);
  const out = h("div");
  root.append(card("חילוף", h("div", { class: "row" }, field("מילה", q, "wide"), field("שיטה", tsel), field("חיפוש התוצאה בתנ״ך", selectEl("t-mode", SEARCH_MODES, "word")),
    skipsField("t-skips")), pbox, info,
    h("div", { class: "actions" }, h("button", { class: "btn secondary", onclick: () => show() }, "הצג חילוף וטבלה"), h("button", { class: "btn", onclick: () => go() }, "חפש בתנ״ך"),
      h("button", { class: "btn secondary", onclick: () => shifts() }, "בדוק את כל ההזזות"),
      h("button", { class: "btn", onclick: () => all() }, "חפש בכל שיטות חילופי האותיות"),
      h("button", { class: "btn", onclick: () => allCombined() }, "חפש בכל הגימטריות והחילופים")), outTxt,
    h("div", { class: "hint" }, "מוצאות הפה (ספר יצירה): " + META.articulation_groups.map((g) => `${g.name_he}: ${g.letters}`).join(" · ") + " — זמין כ״קבוצות אותיות״ בעמוד ראשי התיבות.")),
  scope.root, out);
  upd();
  const params = () => readParams(ts.find((x) => x.id === tsel.value), "tp");
  async function show() {
    try {
      const r = await api("/api/calc/transform", { query: q.value, transformation: tsel.value, params: params() });
      outTxt.innerHTML = "";
      const tbl = h("table", { class: "grid" }, h("tr", {}, ...r.table.map((x) => h("th", {}, x.from))), h("tr", {}, ...r.table.map((x) => h("td", { class: "l" }, x.to))));
      outTxt.append(h("div", { class: "summary" }, h("span", { class: "found verse" }, `${r.input} ← ${r.output}`)), h("div", { class: "scroll" }, tbl));
    } catch (e) { showError(outTxt, e); }
  }
  const go = () => runSearch(out, "/api/search/transform", () => ({ query: q.value, transformation: tsel.value, transform_params: params(),
    search_mode: $("#t-mode").value, skips: parseList($("#t-skips").value), scope: scope.value() }),
  (res) => h("div", { class: "hint" }, `${res.transformation.name_he}: ${res.transformation.input} ← ${res.transformation.output}`));
  async function shifts() {
    try {
      const r = await api("/api/calc/shifts", { query: q.value });
      outTxt.innerHTML = "";
      const tbl = h("table", { class: "grid" }, h("tr", {}, h("th", {}, "הזזה"), h("th", {}, "תוצאה")));
      r.forEach((x) => tbl.append(h("tr", {}, h("td", {}, x.n), h("td", { class: "l" }, x.output))));
      outTxt.append(h("div", { class: "hint" }, "22 מצבי ההזזה המחזורית (0 = ללא שינוי); הסופיות נשארות כפי שהן."), tbl);
    } catch (e) { showError(outTxt, e); }
  }
  async function all() {
    loading(out, "בודק את כל השיטות…");
    try {
      const r = await api("/api/search/transform-all", { ...globals(), query: q.value, search_mode: $("#t-mode").value, skips: parseList($("#t-skips").value), scope: scope.value() });
      out.innerHTML = "";
      const tbl = h("table", { class: "grid" }, h("tr", {}, h("th", {}, "שיטה"), h("th", {}, "תוצאת החילוף"), h("th", {}, "התאמות (" + r.search_mode_he + ")")));
      r.rows.forEach((x) => tbl.append(h("tr", {}, h("td", {}, x.name_he), h("td", { class: "l" }, x.output), h("td", {}, x.count))));
      out.append(card(null, h("div", { class: "summary" }, h("span", { class: "total" }, `${r.variants_checked} חילופים נבדקו`), h("span", { class: "badge pass" }, "סריקה מלאה"), exportLinks(r)), tbl));
    } catch (e) { showError(out, e); }
  }
  async function allCombined() {
    loading(out, "מחשב את כל הצירופים…");
    try {
      const r = await api("/api/search/all-combined", { ...globals(), query: q.value, scope: scope.value() });
      out.innerHTML = "";
      const tbl = h("table", { class: "grid" }, h("tr", {}, h("th", {}, "חילוף"), h("th", {}, "טקסט"), h("th", {}, "שיטת גימטריה"), h("th", {}, "ערך"), h("th", {}, "מילים בעלות ערך זה")));
      r.rows.forEach((x) => tbl.append(h("tr", {}, h("td", {}, x.transformation_he), h("td", { class: "l" }, x.text), h("td", {}, x.method_he), h("td", {}, x.value), h("td", {}, x.count))));
      out.append(card(null, h("div", { class: "summary" }, h("span", { class: "total" }, r.scope_note), h("span", { class: "badge pass" }, "כל הצירופים נבדקו"), exportLinks(r)), h("div", { class: "scroll" }, tbl)));
    } catch (e) { showError(out, e); }
  }
});

// 8 — advanced search builder
const OPS = {
  transform: { he: "חילוף אותיות", in: "text", out: "text" },
  heads: { he: "חילוץ ראשי תיבות", in: "text", out: "text" },
  tails: { he: "חילוץ סופי תיבות", in: "text", out: "text" },
  gematria: { he: "חישוב גימטריה", in: "text", out: "number" },
  add_niqqud: { he: "גימטריית ניקוד", in: "text", out: "number" },
  arith: { he: "פעולה חשבונית", in: "number", out: "number" },
  search_text: { he: "חיפוש טקסט בתנ״ך", in: "text", out: "matches" },
  search_niqqud: { he: "חיפוש ניקוד בתנ״ך", in: "text", out: "matches" },
  search_value: { he: "חיפוש ערך גימטרי בתנ״ך", in: "number", out: "matches" },
};
const TYPE_HE = { text: "טקסט", number: "מספר", matches: "התאמות" };

page("builder", "בניית חיפוש משולב", "הרכבת חיפוש מכמה שלבים. לכל שלב סוג קלט וסוג פלט; שלבים שאינם תואמים נדחים עם הסבר.", (root) => {
  const scope = new ScopePicker();
  const q = textInput("b-q", "", "שָׁלוֹם");
  const list = h("div", { class: "steps-builder" });
  const errs = h("div", { class: "err" });
  const out = h("div");
  let steps = [
    { op: "transform", transformation: "atbash" },
    { op: "gematria", method: "kidmi", include_niqqud: false },
    { op: "search_value", method: "standard", n_min: 1, n_max: 1 },
  ];
  const opSel = selectEl("b-add", Object.entries(OPS).map(([k, v]) => [k, `${v.he} (${TYPE_HE[v.in]} → ${TYPE_HE[v.out]})`]), "transform");
  function stepEditor(st, i) {
    const box = h("div", { class: "step" }, h("span", { class: "n" }, i + 1), h("b", {}, OPS[st.op].he),
      h("span", { class: "type-chip" }, `${TYPE_HE[OPS[st.op].in]} → ${TYPE_HE[OPS[st.op].out]}`));
    const set = (k) => (e) => { st[k] = e.target.type === "checkbox" ? e.target.checked : (e.target.type === "number" ? +e.target.value : e.target.value); validate(); };
    if (st.op === "transform") {
      const s = selectEl("", META.transformations.map((t) => [t.id, t.name_he]), st.transformation); s.addEventListener("change", set("transformation"));
      box.append(field("שיטה", s));
    }
    if (st.op === "gematria" || st.op === "search_value") {
      const s = selectEl("", META.gematria_methods.map((m) => [m.id, m.name_he]), st.method || "standard"); s.addEventListener("change", set("method"));
      box.append(field(st.op === "gematria" ? "שיטת חישוב" : "שיטת החיפוש בתנ״ך", s));
    }
    if (st.op === "gematria") {
      const c = h("input", { type: "checkbox", checked: st.include_niqqud }); c.addEventListener("change", set("include_niqqud"));
      box.append(h("label", { class: "check" }, c, "הוסף גימטריית ניקוד"));
    }
    if (st.op === "search_value") {
      const a = numInput("", st.n_min || 1, 1), b = numInput("", st.n_max || 1, 1);
      a.addEventListener("change", set("n_min")); b.addEventListener("change", set("n_max"));
      box.append(field("מילים מ־", a), field("עד", b));
    }
    if (st.op === "arith") {
      const o = selectEl("", [["+", "+"], ["*", "×"]], st.operator || "+"); o.addEventListener("change", set("operator"));
      const v = numInput("", st.value || 0); v.addEventListener("change", set("value"));
      box.append(field("פעולה", o), field("ערך", v));
    }
    if (st.op === "search_text") {
      const m = selectEl("", SEARCH_MODES, st.search_mode || "heads"); m.addEventListener("change", set("search_mode"));
      st.search_mode = st.search_mode || "heads";
      const sk = h("input", { type: "text", value: (st.skips || [1]).join(","), dir: "ltr" });
      sk.addEventListener("change", (e) => { st.skips = parseList(e.target.value); });
      box.append(field("סוג", m), field("דילוג", sk));
    }
    if (st.op === "search_niqqud") {
      st.unit = st.unit || "words"; st.match = st.match || "niqqud";
      const m = selectEl("", [["niqqud", "ניקוד בלבד"], ["letters_niqqud", "אותיות וניקוד"], ["value", "ערכי ניקוד"]], st.match); m.addEventListener("change", set("match"));
      const u = selectEl("", [["words", "ראשי מילים"], ["verses", "ראשי פסוקים"], ["letters", "אותיות"]], st.unit); u.addEventListener("change", set("unit"));
      box.append(field("התאמה", m), field("יחידות", u));
    }
    box.append(h("button", { class: "btn small secondary", onclick: () => { steps.splice(i, 1); draw(); } }, "הסר"),
      i > 0 ? h("button", { class: "btn small secondary", onclick: () => { [steps[i - 1], steps[i]] = [steps[i], steps[i - 1]]; draw(); } }, "↑") : null);
    return box;
  }
  function draw() { list.innerHTML = ""; steps.forEach((s, i) => list.append(stepEditor(s, i))); validate(); }
  async function validate() {
    const r = await api("/api/pipeline/validate", { steps });
    errs.innerHTML = ""; r.errors.forEach((e) => errs.append(h("div", {}, e)));
  }
  root.append(card("שלבי החיפוש", h("div", { class: "row" }, field("שלב 1: קלט (מילה מנוקדת)", q, "wide")), list, errs,
    h("div", { class: "row" }, field("הוסף שלב", opSel), h("button", { class: "btn small secondary", onclick: () => { steps.push({ op: opSel.value }); draw(); } }, "הוסף")),
    h("div", { class: "actions" }, h("button", { class: "btn", onclick: () => run() }, "הפעל חיפוש"))), scope.root, out);
  draw();
  async function run() {
    loading(out);
    try {
      const res = await api("/api/search/pipeline", { ...globals(), query: q.value, steps, scope: scope.value(), limit: 50 });
      out.innerHTML = "";
      if (!res.ok) { out.append(card(null, ...res.errors.map((e) => h("div", { class: "err" }, e)))); return; }
      const trace = card("מעקב השלבים (ניתן לשחזור)", h("ol", { class: "steps" }, ...res.trace.map((t) =>
        h("li", {}, `${t.op_he}${t.detail ? " (" + t.detail + ")" : ""}: ${t.output}` + (t.calc ? " — " + t.calc.join(" · ") : "")))));
      out.append(trace);
      if (res.result) { const r = h("div"); out.append(r); res.result.history_id = res.history_id; renderResults(r, res.result); }
    } catch (e) { showError(out, e); }
  }
});

// 9 — letter & niqqud analysis
page("stats", "ניתוח אותיות וניקוד", "טבלת אותיות × תנועות לכל תחום; לחיצה על תא מציגה את המופעים ואת ההתפלגות.", (root) => {
  const scope = new ScopePicker();
  const scopeB = new ScopePicker();
  const pos = selectEl("st-pos", [["any", "כל מיקום"], ["first", "אות ראשונה במילה"], ["middle", "אמצע מילה"], ["last", "אות אחרונה במילה"]], "any");
  const out = h("div"), detail = h("div"), sumOut = h("div");
  root.append(card("הגדרות", h("div", { class: "row" }, field("מיקום במילה", pos), checkbox("st-fin", "הפרד אותיות סופיות")),
    h("div", { class: "hint" }, "ניתוח הניקוד מתבצע לפי הנוסח שנבחר למעלה. מומלץ ״קרי״, משום שהכתיב אינו מנוקד."),
    h("div", { class: "actions" }, h("button", { class: "btn", onclick: () => go() }, "חשב טבלה"), h("button", { class: "btn secondary", onclick: () => summary() }, "סיכום התחום"),
      h("button", { class: "btn secondary", onclick: () => cmp() }, "השווה לתחום ב׳"))),
  scope.root, h("details", {}, h("summary", {}, "תחום ב׳ להשוואה"), scopeB.root), sumOut, out, detail);
  const base = () => ({ layer: globals().layer, scope: scope.value(), position: pos.value, separate_finals: $("#st-fin").checked });
  async function go() {
    loading(out, "מחשב…");
    try {
      const r = await api("/api/stats/table", base());
      out.innerHTML = "";
      const cols = r.columns;
      const tbl = h("table", { class: "grid" }, h("tr", {}, h("th", {}, "אות"), h("th", {}, "סה״כ"), ...cols.map((c) => h("th", {}, c.name_he)),
        h("th", {}, "סכום ניקוד"), h("th", {}, "סכום גימטריה"), h("th", {}, "משולב")));
      for (const row of r.rows) {
        if (!row.total) continue;
        const tr = h("tr", {}, h("td", { class: "l" }, row.letter), h("td", {}, row.total));
        for (const c of cols) {
          const n = row.cells[c.id];
          tr.append(h("td", { class: n ? "click" : "", title: c.name_he, onclick: n ? () => cell(row.letter, c.id, c.name_he) : null }, n || ""));
        }
        tr.append(h("td", {}, row.niqqud_sum), h("td", {}, row.gematria_sum), h("td", {}, row.combined_sum));
        tbl.append(tr);
      }
      const freq = cols.map((c) => `${c.name_he}: ${(r.frequency[c.id] * 100).toFixed(2)}%`).join(" · ");
      out.append(card(`${r.settings.scope_he} · ${r.settings.position_he}`, h("div", { class: "summary" },
        h("span", { class: "total" }, `${r.total_letters.toLocaleString("he-IL")} אותיות`), h("span", { class: "badge" }, "סכום ניקוד " + r.niqqud_sum.toLocaleString("he-IL")),
        h("span", { class: "badge" }, "סכום גימטריה " + r.gematria_sum.toLocaleString("he-IL")), h("span", { class: "badge" }, "משולב " + r.combined_sum.toLocaleString("he-IL"))),
      h("div", { class: "hint" }, "שכיחות: " + freq), h("div", { class: "scroll" }, tbl)));
    } catch (e) { showError(out, e); }
  }
  async function cell(letter, column, colHe) {
    loading(detail);
    try {
      const req = { ...base(), letter, column, limit: 30 };
      const [occ, byBook, byPos] = await Promise.all([api("/api/stats/cell", req), api("/api/stats/distribution", { ...req, by: "book" }),
        api("/api/stats/distribution", { ...req, by: "position" })]);
      detail.innerHTML = "";
      const bt = h("table", { class: "grid" }, h("tr", {}, h("th", {}, "ספר"), h("th", {}, "מופעים"), h("th", {}, "מתוך אותיות"), h("th", {}, "שיעור")));
      byBook.rows.forEach((x) => bt.append(h("tr", {}, h("td", {}, x.label), h("td", {}, x.count), h("td", {}, x.of_letters), h("td", {}, (x.rate * 100).toFixed(3) + "%"))));
      const pt = h("table", { class: "grid" }, h("tr", {}, ...byPos.rows.map((x) => h("th", {}, x.label))), h("tr", {}, ...byPos.rows.map((x) => h("td", {}, x.count))));
      const c = card(`${letter} עם ${colHe}: ${occ.total.toLocaleString("he-IL")} מופעים`, h("div", { class: "split" }, h("div", { class: "scroll" }, bt), h("div", {}, h("h3", {}, "לפי מיקום במילה"), pt)));
      occ.results.forEach((x, i) => c.append(h("div", { class: "result" }, h("div", { class: "head" }, h("span", { class: "badge" }, "#" + (i + 1)), h("span", { class: "ref" }, x.ref.ref_he)), ...x.display.map(verseEl))));
      if (occ.total > occ.results.length) c.append(h("div", { class: "hint" }, `מוצגים ${occ.results.length} הראשונים מתוך ${occ.total}.`));
      detail.append(c);
      detail.scrollIntoView({ behavior: "smooth" });
    } catch (e) { showError(detail, e); }
  }
  async function summary() {
    try {
      const s = await api("/api/stats/summary", { layer: globals().layer, scope: scope.value() });
      sumOut.innerHTML = "";
      sumOut.append(card("סיכום: " + s.scope_he, h("div", { class: "summary" }, ...[["פסוקים", s.verses], ["פרקים", s.chapters], ["מילים", s.words], ["אותיות", s.letters],
        ["סכום גימטריה", s.gematria_sum], ["סכום ניקוד", s.niqqud_sum], ["אותיות גדולות", s.large_letters], ["אותיות קטנות", s.small_letters], ["אותיות תלויות", s.hung_letters], ["אותיות מנוקדות (נקודות על אותיות)", s.dotted_letters]]
        .map(([k, v]) => h("span", { class: "badge" }, `${k}: ${Number(v).toLocaleString("he-IL")}`))),
      h("div", { class: "hint" }, Object.entries(s.letter_counts).map(([k, v]) => `${k}: ${v.toLocaleString("he-IL")}`).join(" · "))));
    } catch (e) { showError(sumOut, e); }
  }
  async function cmp() {
    loading(out, "משווה…");
    try {
      const r = await api("/api/stats/compare", { layer: globals().layer, scope_a: scope.value(), scope_b: scopeB.value(), position: pos.value });
      out.innerHTML = "";
      const cols = r.columns.filter((c) => r.rows.some((x) => x.cells[c.id].a || x.cells[c.id].b));
      const tbl = h("table", { class: "grid" }, h("tr", {}, h("th", {}, "אות"), ...cols.map((c) => h("th", {}, c.name_he))));
      for (const row of r.rows) {
        if (!row.total_a && !row.total_b) continue;
        tbl.append(h("tr", {}, h("td", { class: "l" }, row.letter), ...cols.map((c) => {
          const x = row.cells[c.id];
          return h("td", { title: `א׳: ${x.a} · ב׳: ${x.b}` }, `${(x.share_a * 100).toFixed(1)}% / ${(x.share_b * 100).toFixed(1)}%`);
        })));
      }
      out.append(card(`השוואה: א׳ = ${r.scope_a} (${r.totals.a.toLocaleString("he-IL")} אותיות) · ב׳ = ${r.scope_b} (${r.totals.b.toLocaleString("he-IL")})`,
        h("div", { class: "hint" }, "בכל תא: שיעור המופעים של התנועה מתוך מופעי האות — בתחום א׳ / בתחום ב׳."), h("div", { class: "scroll" }, tbl)));
    } catch (e) { showError(out, e); }
  }
});

// 10 — reader
page("reader", "קורא תנ״ך", "הצגת התנ״ך כולו: ניקוד, טעמים, קרי וכתיב, פרשות פתוחות וסתומות ואותיות מיוחדות. לחיצה על מילה מציגה ניתוח אותיות.", (root) => {
  const book = selectEl("r-book", META.books.map((b) => [b.osis, b.he]), store.get("reader-book", "Gen"));
  const chap = numInput("r-chap", store.get("reader-chap", 1), 1);
  const kqmode = selectEl("r-kq", [["both", "כתיב וקרי"], ["ketiv", "כתיב בלבד"], ["qere", "קרי בלבד"]], "both");
  const out = h("div", { class: "reader" }), panel = h("div");
  root.append(card(null, h("div", { class: "row" }, field("ספר", book), field("פרק", chap), field("קרי וכתיב", kqmode),
    h("button", { class: "btn small secondary", onclick: () => { chap.value = Math.max(1, +chap.value - 1); go(); } }, "פרק קודם"),
    h("button", { class: "btn small secondary", onclick: () => { chap.value = +chap.value + 1; go(); } }, "פרק הבא"),
    h("button", { class: "btn", onclick: () => go() }, "הצג")),
  h("div", { class: "hint" }, "צבעים: כתיב בחום (בסוגריים עגולים), קרי בכחול (בסוגריים מרובעים). {פ} = פרשה פתוחה, {ס} = פרשה סתומה. הסימונים אינם חלק מהטקסט ואינם נספרים.")), panel, out);
  book.addEventListener("change", () => { chap.value = 1; go(); });
  kqmode.addEventListener("change", () => go());
  const markEl = (m) => `<span class="pmark" title="${esc(m.kind_he)}">${m.marker.startsWith("pe") ? "{פ}" : "{ס}"}</span>`;
  const SLH_HE = { large: "אות גדולה", small: "אות קטנה", hung: "אות תלויה" };
  function atomHTML(a) {
    // one unit = a letter with all of its marks, so a styled letter keeps its niqqud
    const units = [];
    for (const ch of a.text) {
      if ((ch >= "א" && ch <= "ת") || !units.length) units.push(ch);
      else units[units.length - 1] += ch;
    }
    return units.map((u, i) => {
      const kind = a.slh[String(i)];
      return kind ? `<span class="${kind}" title="${SLH_HE[kind]}">${esc(u)}</span>` : esc(u);
    }).join("");
  }
  async function go() {
    store.set("reader-book", book.value); store.set("reader-chap", +chap.value);
    loading(out, "טוען…");
    try {
      const r = await api(`/api/reader/${book.value}/${chap.value}`);
      out.innerHTML = "";
      const c = card(`${r.book_he} פרק ${r.chapter} (מתוך ${r.chapters})`);
      for (const v of r.verses) {
        let html = v.markers_before.map(markEl).join("") + `<span class="vref">${esc(v.ref.ref_he.split(" ").pop())}</span>`;
        v.atoms.forEach((a, i) => {
          if (a.marker) html += markEl({ marker: a.marker, kind_he: a.marker.startsWith("pe") ? "פתוחה" : "סתומה" });
          const mode = kqmode.value;
          if ((a.role === "k" && mode === "qere") || (a.role === "q" && mode === "ketiv")) return;
          let w = `<span class="w" data-t="${esc(a.text)}">${atomHTML(a)}</span>`;
          if (a.role === "k") w = `<span class="ketiv" title="כתיב">(${w})</span>`;
          if (a.role === "q") w = `<span class="qere" title="קרי">[${w}]</span>`;
          html += w;
          if (a.after.includes("paseq")) html += " ׀";
          if (a.after.includes("legarmeih")) html += " ׀";
          if (a.after.includes("sof_pasuq")) html += "׃";
          html += a.maqaf ? "־" : " ";
        });
        html += v.markers_end.map(markEl).join("");
        const div = h("div", { class: "verse", html });
        if (v.notes.length) div.append(h("div", { class: "hint" }, "הערות מסורה: " + v.notes.join(" · ")));
        c.append(div);
      }
      out.append(c);
      out.querySelectorAll(".w").forEach((el) => el.addEventListener("click", () => analyze(el.dataset.t)));
    } catch (e) { showError(out, e); }
  }
  async function analyze(text) {
    try {
      const r = await api("/api/calc/letters", { query: text });
      panel.innerHTML = "";
      const w = r.words[0];
      panel.append(card(`ניתוח המילה ${w.word}`, h("div", { class: "analysis" }, ...w.letters.map((l) => h("div", { class: "lbox", title: l.marks.map((m) => `${m.cp} ${m.kind}`).join("\n") },
        h("div", { class: "g" }, l.pointed), h("div", { class: "v" }, l.vowels_he.join(" + ")), h("div", { class: "v" }, `ניקוד ${l.niqqud_value} · גימטריה ${l.gematria}`),
        h("div", { class: "v" }, `תגין (לפי הכלל): ${l.tagin}`)))),
      h("div", { class: "hint" }, `סכום ניקוד ${w.niqqud_sum} · גימטריה ${w.gematria_sum} · ${r.tagin_note}`)));
    } catch (e) { showError(panel, e); }
  }
  go();
});

// 11 — validation
page("validation", "תקינות הנתונים", "דוח אימות אוטומטי של התנ״ך ביחס למקור ולמקור ביקורת בלתי תלוי.", (root) => {
  const out = h("div");
  root.append(card(null, h("div", { class: "actions" }, h("button", { class: "btn", onclick: () => run() }, "הרץ אימות מחדש (כ־30 שניות)"))), out);
  const ST = { pass: "עבר", fail: "נכשל", warn: "לבדיקה", info: "מידע", not_run: "לא בוצע", incomplete: "לא הושלם" };
  function draw(r) {
    out.innerHTML = "";
    const c = card(null, h("div", { class: "summary" }, h("span", { class: "total" }, "סטטוס כולל: "), h("span", { class: "badge " + r.status }, ST[r.status] || r.status),
      r.created ? h("span", { class: "hint" }, `נוצר ${r.created} · ${r.elapsed_s} שניות`) : null));
    if (r.source) c.append(h("div", { class: "hint" }, `מקור: ${r.source.source} · ${r.source.repo}@${(r.source.commit || "").slice(0, 10)} · רישיון ${r.source.license}`));
    if (r.counts) c.append(h("div", { class: "hint" }, `פסוקים ${r.counts.verses.toLocaleString("he-IL")} · מילים (כתיב) ${r.counts.words_ketiv.toLocaleString("he-IL")} · אותיות (כתיב) ${r.counts.letters_ketiv.toLocaleString("he-IL")} · אותיות (קרי) ${r.counts.letters_qere.toLocaleString("he-IL")}`));
    for (const ch of r.checks || []) {
      c.append(h("div", { class: "result" }, h("div", { class: "head" }, h("span", { class: "badge " + ch.status }, ST[ch.status] || ch.status), h("b", {}, ch.name_he)),
        h("div", {}, ch.summary_he), Object.keys(ch.details || {}).length ? h("details", { class: "calc" }, h("summary", {}, "פרטים"), h("pre", { class: "json" }, JSON.stringify(ch.details, null, 1).slice(0, 20000))) : null));
    }
    out.append(c);
  }
  async function load() { try { draw(await api("/api/validation")); } catch (e) { showError(out, e); } }
  async function run() { loading(out, "מריץ את כל הבדיקות…"); try { draw(await api("/api/validation/run", {})); } catch (e) { showError(out, e); } }
  load();
});

// 12 — history
page("history", "היסטוריית חיפושים", "כל חיפוש נשמר עם ההגדרות המלאות ועם התוצאות, וניתן לייצא אותו.", (root) => {
  const out = h("div"), detail = h("div");
  root.append(out, detail);
  async function load() {
    try {
      const rows = await api("/api/history");
      out.innerHTML = "";
      const tbl = h("table", { class: "grid" }, h("tr", {}, h("th", {}, "מס׳"), h("th", {}, "זמן"), h("th", {}, "חיפוש"), h("th", {}, "תוצאות"), h("th", {}, "")));
      for (const r of rows) {
        tbl.append(h("tr", {}, h("td", {}, r.id), h("td", {}, r.ts), h("td", {}, r.title), h("td", {}, r.total ?? ""),
          h("td", {}, h("span", { class: "row" }, h("button", { class: "btn small secondary", onclick: () => open(r.id) }, "פתח"),
            h("a", { class: "btn small secondary", href: `/api/history/${r.id}/export?format=csv` }, "CSV"),
            h("a", { class: "btn small secondary", href: `/api/history/${r.id}/export?format=json` }, "JSON"),
            h("button", { class: "btn small secondary", onclick: async () => { await api(`/api/history/${r.id}`, undefined, "DELETE"); load(); } }, "מחק")))));
      }
      out.append(card(`${rows.length} חיפושים שמורים`, h("div", { class: "scroll" }, tbl)));
    } catch (e) { showError(out, e); }
  }
  async function open(id) {
    const r = await api(`/api/history/${id}`);
    detail.innerHTML = "";
    detail.append(card(`${r.title} · ${r.ts}`, h("details", { class: "calc" }, h("summary", {}, "הגדרות החיפוש המלאות"), h("pre", { class: "json" }, JSON.stringify(r.request, null, 1)))));
    const res = r.result; res.history_id = r.id;
    if (Array.isArray(res.results)) { const d = h("div"); detail.append(d); renderResults(d, res); }
    else detail.append(card(null, h("pre", { class: "json" }, JSON.stringify(res, null, 1).slice(0, 30000))));
    detail.scrollIntoView({ behavior: "smooth" });
  }
  load();
});

// ---------------------------------------------------------------- shell
let CURRENT_PAGE = "acrostic";
function showPage(id) {
  const p = PAGES.find((x) => x.id === id) || PAGES[0];
  CURRENT_PAGE = p.id;
  store.set("page", p.id);
  document.querySelectorAll("nav.side button").forEach((b) => b.classList.toggle("active", b.dataset.id === p.id));
  const main = $("#page");
  main.innerHTML = "";
  main.append(h("h2", {}, p.title), h("p", { class: "lead" }, p.lead));
  try { p.render(main); } catch (e) { showError(main, e); }
  history.replaceState(null, "", "#" + p.id);
}

async function boot() {
  for (const [k, sel] of [["kq", "#g-kq"], ["maqaf", "#g-maqaf"], ["finals", "#g-finals"]]) {
    const el = $(sel);
    el.value = store.get("g-" + k, el.value);
    el.addEventListener("change", () => store.set("g-" + k, el.value));
  }
  try {
    META = await api("/api/meta");
  } catch (e) {
    $("#page").append(h("div", { class: "card err" }, "לא ניתן לטעון את נתוני המערכת: " + e.message));
    return;
  }
  const s = META.source;
  $("#source-line").textContent = `מקרא על פי המסורה (MAM) · ויקיטקסט · CC BY-SA 4.0 · גרסה ${META.version}`;
  $("#source-line").title = `${s.repo}@${s.commit}`;
  const nav = $("#nav");
  PAGES.forEach((p, i) => nav.append(h("button", { "data-id": p.id, title: p.lead, onclick: () => showPage(p.id) }, h("span", { class: "num" }, i + 1), p.title)));
  watchHelp(() => CURRENT_PAGE);
  showPage(location.hash.slice(1) || store.get("page", "acrostic"));
  window.addEventListener("hashchange", () => showPage(location.hash.slice(1)));
}

boot();
