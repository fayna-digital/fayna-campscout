/* Copyright Fayna Digital — Volodymyr Shevchenko
 * License OPL-1 (Odoo Proprietary License v1.0) — see LICENSE for full terms.
 *
 * Слід спроби заповнення (чернетка) для публічних форм порталу.
 *
 * НАВІЩО. PDF генерується цілком у браузері; між натисканням кнопки й POST-ом
 * готового документа минає 1–5 с (заміряно 0,7–2,1 с на десктопі). Якщо в цю
 * мить сторінку закрито — на сервері не лишається НІЧОГО, і організатор не знає
 * навіть, що людина починала. iOS Safari вивантажує вкладку при перемиканні
 * застосунку, блокуванні екрана й показі діалогу «Zapisz plik», тож вікно
 * втрати там ширше.
 *
 * ЯК. `navigator.sendBeacon` — єдиний канал, який браузер зобов'язаний
 * доставити вже ПІСЛЯ вивантаження сторінки (fetch у `pagehide` обривається).
 * Тіло — Blob text/plain: application/json зробив би CORS-preflight, якого
 * beacon не вміє.
 *
 * ІНВАЗІЙНІСТЬ. Файл самодостатній: підключається одним <script> і нічого не
 * знає про конкретну форму — сам знаходить поля й кнопки. Жодна помилка тут не
 * повинна ламати саму форму, тому все загорнуте в try/catch.
 */
(function () {
  "use strict";

  var ENDPOINT = "/camp/submit-draft";
  var QUIET_MS = 4000;          // не частіше одного beacon на 4 с для набору тексту
  var sid = null, timer = null, lastSent = 0, everFilled = false;

  function uuid() {
    try {
      if (window.crypto && crypto.randomUUID) return crypto.randomUUID();
    } catch (e) { /* старі Safari */ }
    return "sid-" + Date.now() + "-" + Math.random().toString(36).slice(2, 10);
  }

  function docType() {
    var p = location.pathname;
    if (p.indexOf("zwrot") >= 0) return "zwrot";
    if (p.indexOf("rodzice") >= 0) return "rodzic";
    if (p.indexOf("campscout") >= 0 || p.indexOf("wilcza") >= 0) return "wychowawca";
    return "unknown";
  }

  /* Ключ поля — те, що дасть людині зрозуміти, ЩО саме заповнювали:
     name → id → текст найближчого <label>. */
  function keyOf(el) {
    if (el.name) return el.name;
    if (el.id) return el.id;
    var lab = el.closest("label") || (el.id && document.querySelector('label[for="' + el.id + '"]'));
    if (lab && lab.textContent) return lab.textContent.trim().slice(0, 40);
    return el.tagName.toLowerCase() + "-" + (el.type || "");
  }

  /* Збираємо лише те, що людина справді ВВЕЛА.

     Частина полів має значення, проставлені в розмітці заздалегідь (типові дати
     турнусу, «1/12» у PIT-2). Якщо їх рахувати за заповнені, кожне випадкове
     відкриття сторінки лишало б чернетку з трьох «полів», і звіт «хто почав і не
     закінчив» потонув би в порожніх записах. Тому значення, що дорівнює
     початковому (defaultValue / defaultChecked), пропускаємо. */
  function collect() {
    var out = {};
    try {
      var els = document.querySelectorAll("input, select, textarea");
      for (var i = 0; i < els.length; i++) {
        var el = els[i];
        if (el.type === "file" || el.type === "hidden" || el.disabled) continue;
        var k = keyOf(el), v = "";
        if (el.type === "checkbox") {
          if (!el.checked || el.defaultChecked) continue;
          v = "TAK";
        } else if (el.type === "radio") {
          if (!el.checked || el.defaultChecked) continue;
          v = el.value || "TAK";
        } else if (el.tagName === "SELECT") {
          var opt = el.options[el.selectedIndex];
          if (!opt || opt.defaultSelected) continue;
          v = (el.value || "").trim();
        } else {
          v = (el.value || "").trim();
          if (v === String(el.defaultValue || "").trim()) continue;
        }
        if (!v) continue;
        out[k] = String(v).slice(0, 300);
      }
    } catch (e) { /* ніколи не ламаємо форму */ }
    return out;
  }

  function send(stage, force) {
    try {
      var now = Date.now();
      if (!force && now - lastSent < QUIET_MS) return;
      var fields = collect();
      var filled = Object.keys(fields).length;
      if (filled) everFilled = true;
      // порожню сторінку (бот, випадкове відкриття) не логуємо — крім явного кліку
      if (!everFilled && stage !== "clicked") return;
      lastSent = now;
      var body = JSON.stringify({
        sid: sid, doc_type: docType(), stage: stage,
        url: location.pathname, fields: fields
      });
      var sent = false;
      if (navigator.sendBeacon) {
        sent = navigator.sendBeacon(ENDPOINT, new Blob([body], { type: "text/plain;charset=UTF-8" }));
      }
      if (!sent) {
        // fallback: keepalive тримає запит живим при вивантаженні сторінки
        fetch(ENDPOINT, { method: "POST", body: body, keepalive: true,
                          headers: { "Content-Type": "text/plain;charset=UTF-8" } })
          .catch(function () {});
      }
    } catch (e) { /* мовчки */ }
  }

  /* Локальна копія введеного — щоб випадкове перезавантаження чи «назад» не
     стирало 45 заповнених полів.

     Свідомо sessionStorage, а НЕ localStorage: форму часто заповнюють зі
     спільного планшета табору, і localStorage підсунув би наступному кандидату
     дані попереднього — це витік персональних даних. sessionStorage живе в межах
     однієї вкладки й помирає разом з нею. Втрату при закритті вкладки покриває
     не він, а слід на сервері. */
  var LS_KEY = "campscout_draft_" + location.pathname;

  function saveLocal() {
    try {
      var f = collect();
      if (!Object.keys(f).length) return;
      sessionStorage.setItem(LS_KEY, JSON.stringify({ t: Date.now(), fields: f }));
    } catch (e) { /* приватний режим / переповнення — не критично */ }
  }

  function clearLocal() {
    try { sessionStorage.removeItem(LS_KEY); } catch (e) { /* noop */ }
  }

  function restoreLocal() {
    try {
      var raw = sessionStorage.getItem(LS_KEY);
      if (!raw) return;
      var data = JSON.parse(raw);
      if (!data || !data.fields) return;
      var els = document.querySelectorAll("input, select, textarea"), n = 0;
      for (var i = 0; i < els.length; i++) {
        var el = els[i], v = data.fields[keyOf(el)];
        if (v === undefined || el.type === "file" || el.type === "hidden") continue;
        if (el.type === "checkbox") { el.checked = (v === "TAK"); }
        else if (el.type === "radio") { if (el.value === v) el.checked = true; else continue; }
        else { el.value = v; }
        el.dispatchEvent(new Event("change", { bubbles: true }));
        n++;
      }
      if (n) everFilled = true;
    } catch (e) { /* noop */ }
  }

  function onEdit() {
    saveLocal();
    clearTimeout(timer);
    timer = setTimeout(function () { send("typing", false); }, 1200);
  }

  function init() {
    sid = uuid();
    // форма додає той самий sid у фінальний POST — так подання зшивається з чернеткою
    try { window.__draftSid = sid; } catch (e) { /* noop */ }
  }

  /* Зшивання чернетки з поданням без жодної правки самих форм: перехоплюємо
     fetch до /camp/submit-document і дописуємо той самий sid. Сервер по ньому
     закриє чернетку, і вдале подання не потрапить у звіт «не закінчив». */
  function patchFetch() {
    if (!window.fetch) return;
    var orig = window.fetch;
    window.fetch = function (input, opts) {
      var isSubmit = false;
      try {
        var url = typeof input === "string" ? input : (input && input.url) || "";
        if (url.indexOf("submit-document") >= 0 && opts && typeof opts.body === "string") {
          isSubmit = true;
          var o = JSON.parse(opts.body);
          if (o && typeof o === "object" && !o.sid) {
            o.sid = sid;
            opts = Object.assign({}, opts, { body: JSON.stringify(o) });
          }
        }
      } catch (e) { /* будь-який збій — шлемо запит незміненим */ }
      var p = orig.apply(this, [input, opts]);
      if (isSubmit) {
        // копію стираємо лише після ПІДТВЕРДЖЕНОЇ доставки (resp.ok), а не таймером
        // від ініціації запиту: збій мережі не має стирати єдину вцілілу копію введеного
        p.then(function (resp) { if (resp && resp.ok) clearLocal(); })
         .catch(function () { /* доставки не було — копія лишається */ });
      }
      return p;
    };
  }

  try {
    init();
    patchFetch();
    if (document.readyState === "loading") {
      document.addEventListener("DOMContentLoaded", restoreLocal);
    } else {
      restoreLocal();
    }
    document.addEventListener("input", onEdit, true);
    document.addEventListener("change", onEdit, true);

    /* capture=true — маячок іде ДО обробника кнопки, тобто до генерації PDF:
       саме в цьому проміжку раніше й губилися подання. */
    document.addEventListener("click", function (ev) {
      var t = ev.target;
      if (!t) return;
      var btn = t.closest ? t.closest("button, input[type=submit]") : null;
      if (btn) send("clicked", true);
    }, true);

    /* pagehide ловить і закриття вкладки, і перехід у фон на iOS;
       visibilitychange — блокування екрана та перемикання застосунку. */
    window.addEventListener("pagehide", function () { send("leaving", true); }, true);
    document.addEventListener("visibilitychange", function () {
      if (document.visibilityState === "hidden") send("leaving", true);
    }, true);
  } catch (e) { /* маячок не має права зламати форму */ }
})();
