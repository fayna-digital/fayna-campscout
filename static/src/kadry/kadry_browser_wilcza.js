// Генератор umowa zlecenia для табору CampScout «Na Wilczej Ścieżce» (turnus 58).
// Одна універсальна форма (instruktor / ratownik wodny). pdfMake docDefinition,
// працює і в браузері (window.KADRY_WILCZA), і в Node (module.exports — для verify.js).
//
// ANTI-REGRESSION (INC 2026-07-07, canvas-stretch): НІКОЛИ не використовувати pdfMake
// `canvas` для ліній/чекбоксів усередині клітинки таблиці — воно ламає розрахунок
// висоти рядка на межі сторінки (секція роздувається 2→18 стор.). Тут ліній-у-таблиці
// немає; bl() = текст з underline, fld() = текст з underline (обидва безпечні).
(function () {
"use strict";

const FOREST = '#1B4332', GOLD = '#F7CB74', INK = '#1c2420';

// Реквізити CampScout — JDG (Volodymyr Shevchenko), БЕЗ KRS, з ROT
const CAMPSCOUT = {
  nazwa: 'CAMPSCOUT — Volodymyr Shevchenko',
  adres: 'ul. Kaliska 45, 63-400 Ostrów Wielkopolski',
  nip: '6222847059',
  regon: '524720757',
  rot: '1129',
  email: 'admin@campscout.eu',
  reprezentant: 'Volodymyr Shevchenko',
};

// Турнус 58 «Na Wilczej Ścieżce» — miejsce wykonywania zaszyte (з проду)
const TURNUS = {
  nazwa: 'Na Wilczej Ścieżce',
  miejsce: 'Baza Obozowa Chorągwi Zachodniopomorskiej ZHP, ul. Rzeczna 3, 72-350 Pogorzelica (woj. zachodniopomorskie)',
};

const TERMS = {
  nr_default: '1/WIL/2026',
  stawka_godz: '31,40', // zł/godz — minimalna stawka godzinowa 2026 (Dz.U. 2025 poz. 1242)
  okres_wypow: '7',     // dni
  okres_obowiazu: '12', // m-cy po umowie (non-compete)
};
// data zawarcia — fallback (nie new Date() w kodzie szablonu). Форма підставляє свою.
const DATA_ZAWARCIA_FALLBACK = '12.07.2026';

// ── хелпери оформлення (ті самі, що у campscout_pdf.js — безпечні, без canvas-у-таблиці) ──
function fld(v) { return { text: String(v), bold: true, color: FOREST, decoration: 'underline' }; }

// порожня підкреслена лінія (текст з underline — НЕ canvas)
function bl(w) {
  const n = Math.round((w || 180) / 5.8);
  return { text: ' '.repeat(n), decoration: 'underline', color: '#999' };
}

// заповнене поле або порожня лінія (нічого не вигадуємо для порожнього)
function vline(v, w) {
  return (v !== undefined && v !== null && String(v).trim() !== '') ? fld(String(v).trim()) : bl(w);
}

function header() {
  return [
    { text: 'CAMPSCOUT', bold: true, fontSize: 12, color: FOREST },
    { text: `${CAMPSCOUT.nazwa} · ${CAMPSCOUT.adres}`, fontSize: 7.2, color: '#555' },
    { text: `NIP ${CAMPSCOUT.nip} · REGON ${CAMPSCOUT.regon} · ROT ${CAMPSCOUT.rot} · reprezentant: ${CAMPSCOUT.reprezentant} — właściciel (organizator) · ${CAMPSCOUT.email}`, fontSize: 7.2, color: '#555' },
    { canvas: [{ type: 'line', x1: 0, y1: 2, x2: 515, y2: 2, lineWidth: 2, lineColor: GOLD }], margin: [0, 4, 0, 10] },
  ];
}
function h1(t, sub) {
  return [
    { text: t, fontSize: 13, color: FOREST, bold: true, margin: [0, 2, 0, 1] },
    { text: sub, fontSize: 8.5, color: GOLD, bold: true, margin: [0, 0, 0, 10] },
  ];
}
function h2(t) { return { text: t, fontSize: 9.5, color: FOREST, bold: true, margin: [0, 9, 0, 3] }; }
function p(content, extra) {
  return Object.assign({ text: content, alignment: 'justify', margin: [0, 4, 0, 0] }, extra || {});
}

function adresZam(A) {
  const parts = [];
  if (A.adres_zam_ulica) parts.push(String(A.adres_zam_ulica).trim());
  const line2 = [A.adres_zam_kod, A.adres_zam_miasto].filter(Boolean).map(s => String(s).trim()).join(' ');
  if (line2) parts.push(line2);
  return parts.join(', ');
}

// DD.MM.YYYY. Приймає 'YYYY-MM-DD' (input[type=date]) або вже 'DD.MM.YYYY'.
function fmtPL(dateStr) {
  if (!dateStr) return '';
  const s = String(dateStr).trim();
  if (/^\d{2}\.\d{2}\.\d{4}$/.test(s)) return s; // вже у форматі
  const d = new Date(s + 'T00:00:00');
  if (isNaN(d)) return s;
  const dd = String(d.getDate()).padStart(2, '0');
  const mm = String(d.getMonth() + 1).padStart(2, '0');
  return `${dd}.${mm}.${d.getFullYear()}`;
}

// 220 → "220,00 zł" ; "300,5" → "300,50 zł"
function money(v) {
  const n = Number(String(v).replace(',', '.'));
  if (isNaN(n)) return String(v || '');
  return n.toFixed(2).replace('.', ',') + ' zł';
}

// jednostka з форми → повний зворот для §4.1
const JEDNOSTKA_LABEL = {
  'za miesiąc': 'za miesiąc',
  'za dzień': 'za dzień',
  'za dyżur': 'za dyżur',
  'za cały turnus': 'za cały turnus',
};

function docUmowaZleceniaWilcza(A) {
  A = A || {};

  const nr = A.umowa_nr || TERMS.nr_default;
  const nameZ = A.fullname || 'Imię i nazwisko';
  const zam = adresZam(A);
  const zamNode = zam ? fld(zam) : bl(220);
  // data zawarcia: з форми → fld; відсутня (blank-режим) → порожня підкреслена лінія
  const dataZawarciaNode = A.data_zawarcia ? fld(fmtPL(A.data_zawarcia)) : bl(90);

  const data_od = A.data_od ? fmtPL(A.data_od) : bl(90);
  const data_do = A.data_do ? fmtPL(A.data_do) : bl(90);
  const dataOdNode = (typeof data_od === 'string') ? fld(data_od) : data_od;
  const dataDoNode = (typeof data_do === 'string') ? fld(data_do) : data_do;

  const przedmiot = (A.przedmiot && String(A.przedmiot).trim())
    ? String(A.przedmiot).trim()
    : null;
  const kwalifikacje = (A.kwalifikacje && String(A.kwalifikacje).trim())
    ? String(A.kwalifikacje).trim()
    : null;

  const jednostkaNode = A.jednostka
    ? { text: (JEDNOSTKA_LABEL[A.jednostka] || A.jednostka), bold: true }
    : bl(110); // blank-режим → порожня лінія під jednostkę
  const kwotaNode = A.kwota ? fld(money(A.kwota)) : bl(120);
  // етикетка посади (instruktor/medyk/kierownik) — у blank-режимі порожня лінія
  const stanowiskoNode = vline(A.stanowisko_label, 220);

  // ── § 1. Przedmiot umowy (динамічна нумерація) ──
  const s1 = [];
  s1.push(p([
    '1. Zleceniodawca zleca, a Zleceniobiorca zobowiązuje się do osobistego wykonywania na rzecz Zleceniodawcy, w ramach wypoczynku dzieci i młodzieży organizowanego pod marką CampScout (turnus „',
    { text: TURNUS.nazwa, bold: true }, '"), następujących czynności: ',
    przedmiot ? fld(przedmiot) : bl(320), '.',
  ]));
  s1.push(p(['2. Miejsce wykonywania zlecenia: ', { text: TURNUS.miejsce, bold: true }, '.']));
  if (kwalifikacje) {
    s1.push(p(['3. Zleceniobiorca oświadcza, że posiada kwalifikacje/uprawnienia niezbędne do wykonania zlecenia: ', fld(kwalifikacje), '.']));
  }
  const n4 = kwalifikacje ? '4' : '3';
  const n5 = kwalifikacje ? '5' : '4';
  const n6 = kwalifikacje ? '6' : '5';
  s1.push(p(`${n4}. Zleceniobiorca zobowiązuje się do osobistego wykonania czynności z zachowaniem należytej staranności wymaganej od profesjonalisty (art. 355 § 2 Kodeksu cywilnego), z poszanowaniem dobrego imienia Zleceniodawcy oraz zgodnie z wewnętrznymi standardami bezpieczeństwa marki CampScout.`));
  s1.push(p(`${n5}. Powierzenie wykonania zlecenia osobie trzeciej (substytucja) jest wyłączone (art. 738 § 1 Kodeksu cywilnego).`));
  s1.push(p(`${n6}. Zlecenie ma charakter starannego działania; Zleceniobiorca nie gwarantuje osiągnięcia określonego rezultatu.`));

  const content = [
    ...header(),
    ...h1('UMOWA ZLECENIA nr ' + nr, 'zlecenie usług na wypoczynku dzieci i młodzieży (art. 734 i nast. Kodeksu cywilnego)'),

    p(['zawarta w Ostrowie Wielkopolskim w dniu ', dataZawarciaNode, ' pomiędzy:']),
    p([
      { text: CAMPSCOUT.reprezentant, bold: true },
      `, prowadzącym jednoosobową działalność gospodarczą pod firmą „${CAMPSCOUT.nazwa}", wpisanym do CEIDG, ${CAMPSCOUT.adres}, NIP ${CAMPSCOUT.nip}, REGON ${CAMPSCOUT.regon}, ROT ${CAMPSCOUT.rot}, zwanym dalej „Zleceniodawcą",`,
    ]),
    p('a'),
    p([
      'Panem/Panią ', fld(nameZ), ', zamieszkałym/zamieszkałą ', zamNode,
      ', legitymującym/legitymującą się dokumentem tożsamości ', vline(A.dowod, 150),
      ', PESEL ', vline(A.pesel, 150),
      ', zwanym/zwaną dalej „Zleceniobiorcą", zwanymi dalej łącznie „Stronami".',
    ]),
    p(['Stanowisko / funkcja na turnusie: ', stanowiskoNode, '.']),

    h2('§ 1. Przedmiot umowy'),
    ...s1,

    h2('§ 2. Sposób wykonywania zlecenia i charakter umowy'),
    p('1. Zleceniobiorca samodzielnie dobiera metody wykonania zlecenia oraz organizuje sposób jego realizacji, z zachowaniem należytej staranności, standardów bezpieczeństwa CampScout i obowiązujących przepisów prawa.'),
    p('2. Czynności realizowane są w godzinach wynikających z harmonogramu uzgodnionego przez Strony. Zleceniobiorca nie pozostaje w całodobowej dyspozycji Zleceniodawcy i zachowuje czas wolny od czynności objętych zleceniem. O kwalifikacji prawnej stosunku łączącego Strony decydują rzeczywiste warunki wykonywania czynności (art. 22 § 1¹ Kodeksu pracy); niniejsza umowa nie zastępuje umowy o pracę i nie może być zawarta w warunkach charakterystycznych dla stosunku pracy.'),

    h2('§ 3. Czas trwania umowy'),
    p(['1. Niniejszą umowę zawiera się na czas określony od dnia ', dataOdNode, ' do dnia ', dataDoNode, '.']),
    p('2. Po upływie powyższego okresu Strony mogą zawrzeć kolejną umowę.'),

    h2('§ 4. Wynagrodzenie'),
    p(['1. Zleceniobiorcy przysługuje wynagrodzenie w wysokości ', kwotaNode, ' brutto ', jednostkaNode, ' wykonywania zlecenia.']),
    p(`2. Niezależnie od sposobu ustalenia wynagrodzenia, wynagrodzenie Zleceniobiorcy za każdą godzinę wykonania zlecenia nie będzie niższe niż minimalna stawka godzinowa ustalona zgodnie z ustawą z dnia 10 października 2002 r. o minimalnym wynagrodzeniu za pracę, obowiązująca w okresie rozliczeniowym (informacyjnie, wg stanu na dzień zawarcia umowy — ${TERMS.stawka_godz} zł brutto/godz.). W razie gdyby ustalone wynagrodzenie nie pokrywało tej kwoty, Zleceniodawca dokona wyrównania w terminie wypłaty.`),
    p('3. Zleceniobiorca prowadzi i przekazuje ewidencję liczby godzin wykonania zlecenia w formie dokumentowej przed terminem wypłaty. W razie nieprzekazania ewidencji przyjmuje się liczbę godzin wynikającą z harmonogramu turnusu, przy czym Zleceniobiorca może obalić to domniemanie własnymi dowodami; przyjęta liczba godzin nie może skutkować wynagrodzeniem niższym niż minimalna stawka godzinowa. Ewidencja przechowywana jest przez 3 lata od dnia wymagalności wynagrodzenia.'),
    p('4. Wynagrodzenie płatne jest w terminie 14 dni od zakończenia turnusu, przelewem na rachunek bankowy wskazany przez Zleceniobiorcę. Zleceniodawca, jako płatnik składek, odprowadza należne składki i zaliczki zgodnie z przepisami, na podstawie Oświadczenia zleceniobiorcy (załącznik nr 4).'),

    h2('§ 5. Obowiązki Zleceniodawcy'),
    p('Zleceniodawca zobowiązuje się do: terminowej zapłaty wynagrodzenia, zapewnienia bezpiecznych warunków wykonywania zlecenia oraz niezbędnego wyposażenia, a także udzielenia informacji dotyczących programu i zasad bezpieczeństwa obowiązujących na turnusie.'),

    h2('§ 6. Poufność, zakaz konkurencji i ochrona danych'),
    p('1. Zleceniobiorca zobowiązuje się do zachowania w tajemnicy wszelkich informacji oraz danych osobowych Zleceniodawcy, jego klientów, a także uczestników wypoczynku i ich opiekunów, do których uzyska dostęp w związku z wykonywaniem umowy. Obowiązek ten szczególnie dotyczy danych dzieci i młodzieży oraz informacji o stanie ich zdrowia (dane szczególnej kategorii w rozumieniu art. 9 RODO). Obowiązek poufności obowiązuje bezterminowo po ustaniu umowy.'),
    p(`2. W trakcie obowiązywania umowy oraz przez ${TERMS.okres_obowiazu} miesięcy po jej ustaniu Zleceniobiorca nie będzie organizował ani uczestniczył w organizacji konkurencyjnych obozów lub kolonii dla dzieci i młodzieży, kierowanych do klientów CampScout, z którymi zapoznał się wyłącznie w związku z wykonywaniem niniejszej umowy, ani nie będzie wykorzystywał uzyskanej w związku z umową bazy klientów.`),
    p('3. Zasady przetwarzania danych osobowych reguluje Upoważnienie do przetwarzania danych osobowych (art. 29 RODO, załącznik nr 1) oraz Klauzula informacyjna RODO (załącznik nr 2).'),

    h2('§ 7. Rozwiązanie umowy'),
    p(['1. Każdej ze Stron przysługuje prawo wypowiedzenia umowy z zachowaniem ', fld(TERMS.okres_wypow), '-dniowego okresu wypowiedzenia.']),
    p('2. Z ważnych powodów każda ze Stron może wypowiedzieć umowę ze skutkiem natychmiastowym (art. 746 § 3 Kodeksu cywilnego); prawa tego nie można skutecznie wyłączyć.'),
    p('3. W razie wypowiedzenia Zleceniobiorcy przysługuje wynagrodzenie odpowiadające faktycznie wykonanym godzinom do dnia rozwiązania umowy.'),
    p('4. W razie wypowiedzenia umowy przez Zleceniobiorcę bez ważnego powodu Zleceniodawca może dochodzić naprawienia szkody powstałej wskutek konieczności zapewnienia zastępstwa (art. 746 § 2 Kodeksu cywilnego).'),
    p('5. Wypowiedzenie wymaga formy dokumentowej.'),

    // § 8 + блок підпису — один нерозривний блок (не сиротою на межі сторінки)
    {
      unbreakable: true,
      stack: [
        h2('§ 8. Postanowienia końcowe'),
        p('1. W sprawach nieuregulowanych stosuje się przepisy Kodeksu cywilnego, w szczególności art. 734 i nast.'),
        p('2. Zmiany umowy wymagają formy pisemnej pod rygorem nieważności.'),
        p('3. Spory rozstrzyga sąd właściwy dla miejsca wykonywania działalności gospodarczej Zleceniodawcy.'),
        p('4. Umowę sporządzono w dwóch jednobrzmiących egzemplarzach, po jednym dla każdej ze Stron.'),
        p('5. Załączniki: nr 1 – Upoważnienie do przetwarzania danych osobowych (art. 29 RODO); nr 2 – Klauzula informacyjna RODO (art. 13 RODO); nr 3 – Kwestionariusz osobowy; nr 4 – Oświadczenie ZUS/US i podatki.'),
        {
          columns: [
            { stack: [
              { text: ' ', margin: [0, 0, 0, 26] },
              { text: '______________________________', fontSize: 11, lineHeight: 1, color: '#444' },
              { text: 'Zleceniodawca', fontSize: 8.5, color: FOREST, bold: true, margin: [0, 3, 0, 0] },
              { text: CAMPSCOUT.reprezentant, fontSize: 8, color: '#444' },
            ], alignment: 'center' },
            { stack: [
              { text: ' ', margin: [0, 0, 0, 26] },
              { text: '______________________________', fontSize: 11, lineHeight: 1, color: '#444' },
              { text: 'Zleceniobiorca', fontSize: 8.5, color: FOREST, bold: true, margin: [0, 3, 0, 0] },
              { text: nameZ, fontSize: 8, color: '#444' },
            ], alignment: 'center' },
          ],
          margin: [0, 16, 0, 0],
        },
      ],
    },
  ];

  return {
    pageSize: 'A4',
    pageMargins: [40, 44, 40, 40],
    defaultStyle: { font: 'Roboto', fontSize: 9, color: INK },
    content,
  };
}

// ── ПАКЕТ із 5 документів ──
// Реюз 4 додатків із наявного бандла kadry_browser_campscout.js (docKwestPL/
// docRODOPL/docZUSPL/docUpowaznieniePL) — ті самі перевірені генератори, що й
// у формі campscout (виправлений box()=table, ZUS без canvas-stretch). Тут
// підмінюємо лише перший документ — umowa zlecenia «Na Wilczej Ścieżce».
// deps = { docKwestPL, docRODOPL, docZUSPL, docUpowaznieniePL } — у браузері
// беруться з window.KADRY._docs, у Node передаються явно (verify.js).
function resolveDeps(deps) {
  if (deps) return deps;
  if (typeof window !== 'undefined' && window.KADRY && window.KADRY._docs) return window.KADRY._docs;
  return null;
}

// Склеює content кількох генераторів в один docDefinition з pageBreak:'before'
// на першому елементі кожного НАСТУПНОГО документа (той самий патерн, що
// docDefPL у campscout — не сирота-підпис на межі сторінки).
function assemblePackage(generators, A) {
  let content = [];
  generators.forEach((fn, i) => {
    const c = fn(A).content.slice();
    if (i > 0 && c.length) c[0] = Object.assign({}, c[0], { pageBreak: 'before' });
    content = content.concat(c);
  });
  return { pageSize: 'A4', pageMargins: [40, 44, 40, 40], defaultStyle: { font: 'Roboto', fontSize: 9, color: INK }, content };
}

// Повний пакет за посадою (A.stanowisko):
//   instruktor / medyk → PL-пакет 5 док.: umowa zlecenia + Kwestionariusz + RODO + ZUS + Upoważnienie.
//   kierownik          → той самий PL-пакет + UA Договір волонтера (opieka, ТОВ «КЕМПСКАУТ»),
//                        як у моделі Поліни (zlecenie на інструктаж + wolontariat на опіку).
// UA-генератор реюзаний з kadry_browser_campscout.js (docWolontariatWychowawcaUA);
// umowa_nr_ua має ВЛАСНИЙ незалежний номер (buildA у wilcza.html: idW=genID(), A.umowa_nr_ua = idW + '/WOL/2026'),
// відмінний від номера PL-пакета zlecenia (idZ + '/WIL/2026').
function docDefFor(A, deps) {
  const K = resolveDeps(deps);
  if (!K || !K.docKwestPL) {
    throw new Error('kadry_browser_campscout.js не завантажений — window.KADRY._docs недоступний (потрібні генератори додатків).');
  }
  const gens = [docUmowaZleceniaWilcza, K.docKwestPL, K.docRODOPL, K.docZUSPL, K.docUpowaznieniePL];
  if (A && A.stanowisko === 'kierownik') {
    if (!K.docWolontariatWychowawcaUA) {
      throw new Error('Генератор UA Договору волонтера (docWolontariatWychowawcaUA) недоступний у window.KADRY._docs.');
    }
    gens.push(K.docWolontariatWychowawcaUA);
  }
  return assemblePackage(gens, A);
}

// Зворотна сумісність / зручний аліас
function docDefPackage(A, deps) { return docDefFor(A, deps); }

// ── браузерне API ──
if (typeof pdfMake !== 'undefined') {
  pdfMake.fonts = pdfMake.fonts || { Roboto: { normal: 'Roboto-Regular.ttf', bold: 'Roboto-Medium.ttf', italics: 'Roboto-Italic.ttf', bolditalics: 'Roboto-MediumItalic.ttf' } };
}
function fname(A) { return String((A && (A.nazwisko || A.fullname)) || 'kadra').replace(/\s+/g, '_'); }
function genPackage(A) { return pdfMake.createPdf(docDefFor(A)).download(fname(A) + '_dokumenty_wilcza.pdf'); }

const api = {
  docUmowaZleceniaWilcza, docDefWilcza: docUmowaZleceniaWilcza,
  assemblePackage, docDefFor, docDefPackage, genPackage, money, fmtPL,
};
if (typeof window !== 'undefined') window.KADRY_WILCZA = api;
if (typeof module !== 'undefined' && module.exports) module.exports = api;

})();
