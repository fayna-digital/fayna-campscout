// AUTO-GENERATED браузерний бандл (build_browser.js). НЕ редагувати вручну.
(function(){
"use strict";
// Спільний модуль pdfmake для пакету документів вихователя CampScout (JDG — Volodymyr Shevchenko)
const FOREST = '#1B4332', GOLD = '#F7CB74', INK = '#1c2420';

// Реквізити CampScout — JDG, БЕЗ KRS (JDG не має KRS), з ROT (реєстр туроператора)
const CAMPSCOUT = {
  nazwa: 'CAMPSCOUT — Volodymyr Shevchenko',
  adres: 'ul. Kaliska 45, 63-400 Ostrów Wielkopolski',
  nip: '6222847059',
  regon: '524720757',
  rot: '1129',
  email: 'admin@campscout.eu',
  reprezentant: 'Volodymyr Shevchenko',
};


// вектор-чекбокс: порожній квадрат або зелений із галкою
function box(checked) {
  const c = [{
    type: 'rect', x: 0, y: 1.5, w: 8.5, h: 8.5, lineWidth: .8,
    lineColor: checked ? FOREST : '#888',
    ...(checked ? { color: FOREST } : {}),
  }];
  if (checked) { // біла галка
    c.push({ type: 'line', x1: 1.8, y1: 6, x2: 3.6, y2: 8, lineWidth: 1.1, lineColor: '#fff' });
    c.push({ type: 'line', x1: 3.6, y1: 8, x2: 7, y2: 3, lineWidth: 1.1, lineColor: '#fff' });
  }
  return { canvas: c, width: 13 };
}

// чекбокс + підпис (рядок)
function cbLine(checked, text) {
  return { columns: [box(checked), { text, width: '*', fontSize: 9 }], columnGap: 3, margin: [0, 2, 0, 2] };
}

// TAK/NIE (lang='ua' → ТАК/НІ) для комірки таблиці; розпізнає значення в обох варіантах написання
function yn(val, lang) {
  const isUA = lang === 'ua';
  const yesLabel = isUA ? 'ТАК' : 'TAK';
  const noLabel = isUA ? 'НІ' : 'NIE';
  const isYes = val === 'TAK' || val === 'ТАК';
  const isNo = val === 'NIE' || val === 'НІ';
  return {
    columns: [
      box(isYes), { text: yesLabel, width: 'auto', fontSize: 8.6, margin: [2, 0, 8, 0] },
      box(isNo), { text: noLabel, width: 'auto', fontSize: 8.6, margin: [2, 0, 0, 0] },
    ],
    columnGap: 1,
  };
}

function fld(v) { return { text: String(v), bold: true, color: FOREST, decoration: 'underline' }; }

// нумер угоди/умови, спільний для пакету документів вихователя (PL і UA)
const UMOWA_NR = '1/WYC/2026';

function header(lang) {
  const repLine = lang === 'ua'
    ? `представник: ${CAMPSCOUT.reprezentant} — власник (організатор)`
    : `reprezentant: ${CAMPSCOUT.reprezentant} — właściciel (organizator)`;
  return [
    { text: 'CAMPSCOUT', bold: true, fontSize: 12, color: FOREST },
    { text: `${CAMPSCOUT.nazwa} · ${CAMPSCOUT.adres}`, fontSize: 7.2, color: '#555' },
    { text: `NIP ${CAMPSCOUT.nip} · REGON ${CAMPSCOUT.regon} · ROT ${CAMPSCOUT.rot} · ${repLine} · ${CAMPSCOUT.email}`, fontSize: 7.2, color: '#555' },
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


const KADRY_DOCS = {};

/* ==== doc_umowa_wychowawca_pl.js ==== */
{
// Umowa zlecenia (instruktor) nr 1/WYC/2026 — pdfmake docDefinition, CampScout (POLSKA)
// Wynagrodzenie: 220 zł/dzień, nie niżej minimalnej stawki godzinowej (31,40 zł/h); ewidencja godzin (dziennik zajęć)

// data zawarcia umowy — FIKSOWANA (nie new Date()!)
const DATA_ZAWARCIA = '07.07.2026';
// domyślny okres obozu, jeśli formularz nie poda dat
const DEFAULT_DATA_OD = '2026-07-08';
const DEFAULT_DATA_DO = '2026-07-21';

const TERMS = {
  nr: '1/WYC/2026',
  stawka_godz: '31,40', // zł/godzinę — minimalna stawka godzinowa 2026 (Dz.U. 2025 poz. 1242)
  okres_wypow: '7',     // dni
  okres_obowiazu: '12', // m-cy po umowie (non-compete)
};

// pusta linia do podpisu/uzupełnienia
function bl(w) {
  const n = Math.round((w || 180) / 5.8);
  return { text: ' '.repeat(n), decoration: 'underline', color: '#999' };
}

// wypełnione pole lub pusta linia
function vline(v, w) {
  return (v !== undefined && v !== null && String(v).trim() !== '') ? fld(String(v)) : bl(w);
}

function adresZam(A) {
  const parts = [];
  if (A.adres_zam_ulica) parts.push(String(A.adres_zam_ulica).trim());
  const line2 = [A.adres_zam_kod, A.adres_zam_miasto].filter(Boolean).map(s => String(s).trim()).join(' ');
  if (line2) parts.push(line2);
  return parts.join(', ');
}

function p(content, extra) {
  return Object.assign({ text: content, alignment: 'justify', margin: [0, 4, 0, 0] }, extra || {});
}

// DD.MM.YYYY z wiodącym zerem
function fmtPL(dateStr) {
  const d = new Date(dateStr + 'T00:00:00');
  const dd = String(d.getDate()).padStart(2, '0');
  const mm = String(d.getMonth() + 1).padStart(2, '0');
  return `${dd}.${mm}.${d.getFullYear()}`;
}

function docUmowaWychowawcaPL(A) {
  A = A || {};

  const nameInst = A.fullname || 'Imię i nazwisko';
  const zam = adresZam(A);
  const zamNode = zam ? fld(zam) : bl(220);

  // Daty obozu — z formularza, w razie braku domyślny termin 08–21.07.2026
  const data_od = fmtPL(A.data_od || DEFAULT_DATA_OD);
  const data_do = fmtPL(A.data_do || DEFAULT_DATA_DO);

  const content = [
    ...header(),
    ...h1('UMOWA ZLECENIA nr ' + (A.umowa_nr || TERMS.nr), 'instruktor prowadzący zajęcia na wypoczynku dzieci i młodzieży (art. 734 i nast. Kodeksu cywilnego)'),

    p(['zawarta w Ostrowie Wielkopolskim w dniu ', fld(DATA_ZAWARCIA), ' pomiędzy:']),
    p([
      { text: CAMPSCOUT.reprezentant, bold: true },
      `, prowadzącym jednoosobową działalność gospodarczą pod firmą „${CAMPSCOUT.nazwa}", wpisanym do CEIDG, ${CAMPSCOUT.adres}, NIP ${CAMPSCOUT.nip}, REGON ${CAMPSCOUT.regon}, ROT ${CAMPSCOUT.rot}, zwanym dalej „Zleceniodawcą",`,
    ]),
    p('a'),
    p([
      'Panem/Panią ', fld(nameInst), ', zamieszkałym/zamieszkałą ', zamNode,
      ', legitymującym/legitymującą się dokumentem tożsamości ', vline(A.dowod, 150),
      ', PESEL ', vline(A.pesel, 150),
      ', zwanym/zwaną dalej „Zleceniobiorcą", zwanymi dalej łącznie „Stronami".',
    ]),

    h2('§ 1. Przedmiot umowy'),
    p('1. Zleceniodawca zleca, a Zleceniobiorca zobowiązuje się do osobistego wykonywania czynności instruktorskich, polegających na przygotowaniu i prowadzeniu zajęć programowych (w szczególności animacyjnych, sportowo-rekreacyjnych i edukacyjnych) dla uczestników wypoczynku organizowanego przez Zleceniodawcę pod marką CampScout, zgodnie z ustalonym harmonogramem zajęć (programem obozu, m.in. programem «Mafia»).'),
    p('2. Zakres czynności obejmuje w szczególności: przygotowanie i prowadzenie zajęć zgodnie z harmonogramem, dbałość o bezpieczeństwo uczestników w czasie prowadzonych zajęć, współpracę z pozostałą kadrą obozu oraz bieżącą dokumentację i raportowanie do kierownika obozu, zgodnie z wewnętrznymi standardami CampScout.'),
    p('3. Zleceniobiorca zobowiązuje się do osobistego wykonania czynności z zachowaniem należytej staranności wymaganej od profesjonalisty (art. 355 § 2 Kodeksu cywilnego), z poszanowaniem dobrego imienia Zleceniodawcy oraz zgodnie z wewnętrznymi standardami bezpieczeństwa marki CampScout.'),
    p('4. Powierzenie wykonania zlecenia osobie trzeciej (substytucja) jest wyłączone (art. 738 § 1 Kodeksu cywilnego).'),
    p('5. Zlecenie ma charakter starannego działania; Zleceniobiorca nie gwarantuje osiągnięcia określonego rezultatu.'),

    h2('§ 2. Sposób wykonywania zlecenia i charakter umowy'),
    p('1. Zleceniobiorca samodzielnie dobiera metody prowadzenia zajęć oraz organizuje sposób ich wykonania, z zachowaniem należytej staranności, standardów bezpieczeństwa CampScout i obowiązujących przepisów prawa.'),
    p('2. Zajęcia realizowane są w godzinach wynikających z harmonogramu zajęć uzgodnionego przez Strony. Zleceniobiorca nie pozostaje w całodobowej dyspozycji Zleceniodawcy i zachowuje czas wolny od czynności objętych zleceniem. O kwalifikacji prawnej stosunku łączącego Strony decydują rzeczywiste warunki wykonywania czynności (art. 22 § 1¹ Kodeksu pracy); niniejsza umowa nie zastępuje umowy o pracę i nie może być zawarta w warunkach charakterystycznych dla stosunku pracy.'),

    h2('§ 3. Czas trwania umowy'),
    p(['1. Niniejszą umowę zawiera się na czas określony od dnia ', fld(data_od), ' do dnia ', fld(data_do), '.']),
    p('2. Po upływie powyższego okresu Strony mogą zawrzeć kolejną umowę.'),

    h2('§ 4. Wynagrodzenie'),
    p(['1. Zleceniobiorcy przysługuje wynagrodzenie w wysokości ', fld('220 zł'), ' brutto za dzień wykonywania zlecenia (prowadzenia zajęć programowych).']),
    p('2. Niezależnie od sposobu ustalenia wynagrodzenia, wynagrodzenie Zleceniobiorcy za każdą godzinę wykonania zlecenia nie będzie niższe niż minimalna stawka godzinowa ustalona zgodnie z ustawą z dnia 10 października 2002 r. o minimalnym wynagrodzeniu za pracę, obowiązująca w okresie rozliczeniowym (informacyjnie, wg stanu na dzień zawarcia umowy — 31,40 zł brutto/godz.). W razie gdyby wynagrodzenie dzienne nie pokrywało tej kwoty, Zleceniodawca dokona wyrównania w terminie wypłaty.'),
    p('3. Zleceniobiorca prowadzi i przekazuje ewidencję liczby godzin wykonania zlecenia w formie dokumentowej (m.in. w postaci dziennika prowadzonych zajęć) przed terminem wypłaty. W razie nieprzekazania ewidencji przyjmuje się liczbę godzin wynikającą z harmonogramu programu obozu, przy czym Zleceniobiorca może obalić to domniemanie własnymi dowodami; przyjęta liczba godzin nie może skutkować wynagrodzeniem niższym niż minimalna stawka godzinowa. Ewidencja przechowywana jest przez 3 lata od dnia wymagalności wynagrodzenia.'),
    p('4. Wynagrodzenie płatne jest w terminie 14 dni od zakończenia turnusu, przelewem na rachunek bankowy wskazany przez Zleceniobiorcę. Zleceniodawca, jako płatnik, odprowadza należne składki i zaliczki zgodnie z przepisami, na podstawie Oświadczenia zleceniobiorcy (załącznik nr 4).'),

    h2('§ 5. Obowiązki Zleceniodawcy'),
    p('Zleceniodawca zobowiązuje się do: terminowej zapłaty wynagrodzenia, zapewnienia bezpiecznych warunków wykonywania zajęć oraz niezbędnego wyposażenia, a także udzielenia informacji dotyczących programu i zasad bezpieczeństwa.'),

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
          { text: nameInst, fontSize: 8, color: '#444' },
        ], alignment: 'center' },
      ],
      margin: [0, 16, 0, 0],
      unbreakable: true,
    },
  ];

  return {
    pageSize: 'A4',
    pageMargins: [40, 44, 40, 40],
    defaultStyle: { font: 'Roboto', fontSize: 9, color: INK },
    content,
  };
}


KADRY_DOCS.docUmowaWychowawcaPL = docUmowaWychowawcaPL;
}

/* ==== doc_kwest_wychowawca_pl.js ==== */
{
// Kwestionariusz osobowy (załącznik nr 3 do Umowy zlecenia nr 1/WYC/2026) — pdfmake docDefinition
// dla wychowawcy CampScout (POLSKA). Struktura wg pakietu Daniela (hr-pack-fayna/web/doc_kwest.js).

// pusta podkreślona linia (odpowiednik bl() z pakietu Daniela)
function bl(n) {
  return { text: ' '.repeat(n || 40), decoration: 'underline', color: '#999' };
}
// wartość z A (pusty string dla null/undefined/true/false)
function a(A, key) {
  const v = A[key];
  if (v === undefined || v === null || v === true || v === false) return '';
  return String(v).trim();
}
// wypełnione pole (fld) lub pusta linia
function vline(A, key) {
  const v = a(A, key);
  return v ? fld(v) : bl();
}
function adresZam(A) {
  const parts = [];
  if (a(A, 'adres_zam_ulica')) parts.push(a(A, 'adres_zam_ulica'));
  const line2 = [a(A, 'adres_zam_kod'), a(A, 'adres_zam_miasto')].filter(Boolean).join(' ');
  if (line2) parts.push(line2);
  return parts.join(', ');
}

function docKwestPL(A) {
  A = A || {};
  const fullname = A.fullname || 'Imię i nazwisko';
  const dataMiejsce = [a(A, 'data_urodzenia'), a(A, 'miejsce_urodzenia')].filter(Boolean).join(' — ');
  const azf = adresZam(A);

  // [etykieta, treść wartości]
  const rows = [
    ['Imię i nazwisko', fld(fullname)],
    ['Nazwisko rodowe', vline(A, 'nazwisko_rodowe')],
    ['Imiona rodziców', vline(A, 'imiona_rodzicow')],
    ['Data i miejsce urodzenia', dataMiejsce ? fld(dataMiejsce) : bl()],
    ['Obywatelstwo', vline(A, 'obywatelstwo')],
    ['PESEL', vline(A, 'pesel')],
    ['Adres zameldowania', azf ? fld(azf) : bl()],
    ['Adres do korespondencji (jeśli inny)', vline(A, 'adres_koresp')],
    ['Telefon', vline(A, 'tel')],
    ['E-mail', vline(A, 'email')],
    ['Wykształcenie', vline(A, 'wyksztalcenie')],
    ['Zawód wykonywany', vline(A, 'zawod')],
    ['Oddział NFZ', vline(A, 'nfz')],
    ['Urząd Skarbowy', vline(A, 'us')],
    ['Numer rachunku bankowego', vline(A, 'iban')],
  ];

  const body = rows.map(([l, v]) => [
    { text: l, fillColor: '#f7f7f5', bold: true },
    v,
  ]);

  return {
    pageSize: 'A4',
    pageMargins: [40, 44, 40, 40],
    defaultStyle: { font: 'Roboto', fontSize: 9, color: INK },
    content: [
      ...header(),
      ...h1('KWESTIONARIUSZ OSOBOWY', 'Zleceniobiorca — załącznik nr 3 do umowy zlecenia'),
      {
        text: 'Prosimy wypełnić drukowanymi literami. Dane służą zawarciu i wykonaniu umowy zlecenia oraz realizacji obowiązków podatkowych i ubezpieczeniowych.',
        italics: true, fontSize: 7.6, color: '#666', margin: [0, 0, 0, 6],
      },
      {
        table: { widths: ['44%', '*'], body },
        layout: { hLineColor: () => '#c9c9c9', vLineColor: () => '#c9c9c9' },
        fontSize: 8.6,
      },
      {
        table: { widths: ['*'], body: [[{ stack: [
          { text: 'Oświadczenie o tożsamości i zgodności danych', bold: true, color: FOREST, margin: [0, 0, 0, 4] },
          { text: 'Oświadczam, że powyższe dane są zgodne ze stanem faktycznym oraz zobowiązuję się niezwłocznie informować Zleceniodawcę o ich zmianie.', fontSize: 8.2, margin: [0, 0, 0, 3] },
          { text: `Potwierdzam zapoznanie się z Klauzulą informacyjną RODO (załącznik nr 2). Dane zawarte w niniejszym kwestionariuszu są przetwarzane przez ${CAMPSCOUT.nazwa} na podstawie art. 6 ust. 1 lit. b i c RODO (zawarcie i wykonanie umowy oraz obowiązki prawne Zleceniodawcy) — zgoda nie jest wymagana.`, fontSize: 8.2 },
        ] }]] },
        layout: { hLineColor: () => '#d8d8d8', vLineColor: () => '#d8d8d8' },
        margin: [0, 8, 0, 0],
      },
      {
        columns: [
          { text: '______________________________\nMiejscowość i data', fontSize: 14, lineHeight: 1, color: '#444', alignment: 'center' },
        { text: '______________________________\nCzytelny podpis', fontSize: 14, lineHeight: 1, color: '#444', alignment: 'center' },
        ],
        margin: [0, 30, 0, 0], unbreakable: true,
      },
    ],
  };
}


KADRY_DOCS.docKwestPL = docKwestPL;
}

/* ==== doc_rodo_wychowawca_pl.js ==== */
{
// Klauzula informacyjna RODO (art. 13) — załącznik nr 2 do umowy wychowawcy CampScout (POLSKA)
// Administrator = CAMPSCOUT (JDG — Volodymyr Shevchenko), BEZ KRS (JDG nie ma KRS)

function docRODOPL(A) {
  A = A || {};

  const nameInst = A.fullname || 'Imię i nazwisko';

  const rows = [
    ['Administrator', `${CAMPSCOUT.nazwa}, ${CAMPSCOUT.adres}, NIP ${CAMPSCOUT.nip}, REGON ${CAMPSCOUT.regon}, ROT ${CAMPSCOUT.rot}. Kontakt: ${CAMPSCOUT.email}`],
    ['Cele i podstawy', 'Zawarcie i wykonanie umowy zlecenia (art. 6 ust. 1 lit. b); obowiązki podatkowe i ubezpieczeniowe (lit. c); ustalenie, dochodzenie lub obrona przed roszczeniami – na podstawie prawnie uzasadnionego interesu Administratora (art. 6 ust. 1 lit. f RODO)'],
    ['Okres przechowywania', 'Umowa – 6 lat; dokumentacja podatkowa – 5 lat; dokumentacja ZUS – zgodnie z przepisami; roszczenia – do upływu przedawnienia'],
    ['Odbiorcy danych', 'US, ZUS, NFZ, biuro rachunkowe, dostawcy IT (na podstawie umów powierzenia)'],
    ['Prawa', 'Dostęp, sprostowanie, usunięcie, ograniczenie, przenoszenie, sprzeciw, a w zakresie danych przetwarzanych na podstawie zgody — jej wycofanie w dowolnym momencie'],
    ['Skarga', 'Prezes Urzędu Ochrony Danych Osobowych, ul. Stawki 2, 00-193 Warszawa'],
    ['Profilowanie', 'Dane nie są wykorzystywane do zautomatyzowanego podejmowania decyzji ani profilowania'],
    ['Przekazywanie poza EOG', 'Dane nie są przekazywane poza EOG bez wymaganych zabezpieczeń'],
  ];

  const body = [[
    { text: 'Element', fillColor: '#f0f4f1', color: FOREST, bold: true },
    { text: 'Treść', fillColor: '#f0f4f1', color: FOREST, bold: true },
  ]].concat(rows.map(([l, t]) => [{ text: l, fillColor: '#f7f7f5', bold: true }, { text: t }]));

  const content = [
    ...header(),
    ...h1('KLAUZULA INFORMACYJNA RODO', 'art. 13 RODO — przetwarzanie danych zleceniobiorcy (załącznik nr 2)'),

    { text: ['Imię i nazwisko: ', fld(nameInst)], margin: [0, 0, 0, 4] },

    h2('Klauzula informacyjna (art. 13 RODO)'),
    { table: { widths: [150, '*'], body }, layout: { hLineColor: () => '#c9c9c9', vLineColor: () => '#c9c9c9' }, fontSize: 8.6 },

    { text: 'Dane niezbędne do zawarcia i wykonania umowy oraz realizacji obowiązków prawnych są przetwarzane na podstawie art. 6 ust. 1 lit. b i c RODO — zgoda nie jest wymagana i nie warunkuje zawarcia umowy.', fontSize: 8.2, margin: [0, 6, 0, 2] },
    { text: `Pełna informacja: ${CAMPSCOUT.email}`, fontSize: 8.2, margin: [0, 0, 0, 6] },

    {
      table: {
        widths: ['*'],
        body: [[{
          stack: [
            { text: 'Zgody dobrowolne', bold: true, color: FOREST, margin: [0, 0, 0, 4] },
            cbLine(!!A.zgoda_marketing, '(dobrowolnie) Wyrażam zgodę na przetwarzanie moich danych w celach marketingowych — informowania o nowych ofertach i współpracy z CampScout (art. 6 ust. 1 lit. a RODO).'),
            cbLine(!!A.zgoda_wizerunek, '(dobrowolnie) Wyrażam zgodę na utrwalanie i wykorzystanie mojego wizerunku (zdjęcia/nagrania zespołowe) do celów wewnętrznych i promocyjnych CampScout (art. 6 ust. 1 lit. a RODO).'),
            { text: 'Zgody są dobrowolne, można je wycofać w każdym czasie, a ich brak nie wpływa na zawarcie ani ważność umowy.', italics: true, fontSize: 7.6, color: '#666', margin: [0, 3, 0, 0] },
          ],
        }]],
      },
      layout: { hLineColor: () => '#d8d8d8', vLineColor: () => '#d8d8d8' },
      margin: [0, 2, 0, 0],
    },

    {
      columns: [
        { text: '______________________________\nMiejscowość i data', fontSize: 14, lineHeight: 1, color: '#444', alignment: 'center' },
        { text: '______________________________\nCzytelny podpis', fontSize: 14, lineHeight: 1, color: '#444', alignment: 'center' },
      ],
      margin: [0, 30, 0, 0], unbreakable: true,
    },
  ];

  return {
    pageSize: 'A4',
    pageMargins: [40, 44, 40, 40],
    defaultStyle: { font: 'Roboto', fontSize: 9, color: INK },
    content,
  };
}


KADRY_DOCS.docRODOPL = docRODOPL;
}

/* ==== doc_zus_wychowawca_pl.js ==== */
{
// Oświadczenie zleceniobiorcy (ZUS/US + podatki) — załącznik nr 4 do Umowy zlecenia wychowawcy CampScout (POLSKA)
// Struktura dosłownie wg hr-pack-fayna/web/doc_zus.js :: docZUS() (Sekcja A-E), dostosowana do CampScout (JDG).
// FIKS: Sekcja D — KUP wyłącznie 20% (standardowe). Wariant 50% (§ 7 — prawa autorskie) USUNIĘTY,
// ponieważ umowa wychowawcy CampScout nie zawiera § 7 o przeniesieniu praw autorskich.
function h2(t) { return { text: t, fontSize: 9.5, color: FOREST, bold: true, margin: [0, 6, 0, 2] }; }

const NR = '1/WYC/2026'; // nr Umowy zlecenia, do której niniejsze oświadczenie jest załącznikiem nr 4

// pusta podkreślona linia (odpowiednik `bl` z referencji)
function bl(w) {
  return { canvas: [{ type: 'line', x1: 0, y1: 9, x2: w || 160, y2: 9, lineWidth: 0.8, lineColor: '#999' }], margin: [0, 0, 0, 0] };
}
// wartość z A → fld(...) albo pusta linia
function vline(A, key, w) {
  const v = A[key];
  return (v !== undefined && v !== null && String(v).trim() !== '') ? fld(String(v).trim()) : bl(w);
}
// adres zamieszkania (ulica, kod miasto)
function adresZam(A) {
  const parts = [];
  if (A.adres_zam_ulica) parts.push(String(A.adres_zam_ulica).trim());
  const line2 = [A.adres_zam_kod, A.adres_zam_miasto].filter(Boolean).map(x => String(x).trim()).join(' ');
  if (line2) parts.push(line2);
  const reg = [A.adres_zam_woj, A.adres_zam_powiat_gmina].filter(Boolean).map(x => String(x).trim()).join(' / ');
  const base = parts.join(', ');
  return [base, reg].filter(Boolean).join(', ');
}

function lblCell(t) { return { text: t, fillColor: '#f7f7f5', bold: true }; }

function docZUSPL(A) {
  A = A || {};
  const nr = A.umowa_nr || NR;
  const fullname = A.fullname || 'Imię i nazwisko';

  // --- Sekcja A — Dane ---
  const adr = adresZam(A);
  const telEmail = [A.tel, A.email].filter(Boolean).map(x => String(x).trim()).join(' / ');
  const usNfz = [A.us, A.nfz].filter(Boolean).map(x => String(x).trim()).join(' / ');
  const aRows = [
    ['Imię i nazwisko', fld(fullname)],
    ['PESEL', vline(A, 'pesel', 150)],
    ['Data urodzenia', vline(A, 'data_urodzenia', 150)],
    ['NIP (jeśli dotyczy)', bl(150)],
    ['Dowód osobisty / paszport', vline(A, 'dowod', 150)],
    ['Adres zamieszkania', adr ? fld(adr) : bl(220)],
    ['Adres zameldowania (jeśli inny)', vline(A, 'adres_koresp', 220)],
    ['Telefon / e-mail', telEmail ? fld(telEmail) : bl(220)],
    ['Urząd Skarbowy / Oddział NFZ', usNfz ? fld(usNfz) : bl(220)],
    ['Numer rachunku bankowego', vline(A, 'iban', 220)],
  ];
  const aBody = aRows.map(([l, v]) => [lblCell(l), v]);

  // --- Sekcja B — Status ubezpieczeniowy (9 pozycji TAK/NIE) ---
  const bItems = [
    ['zus1', 'Jestem zatrudniony u innego pracodawcy z wynagrodzeniem co najmniej minimalnym'],
    ['zus2', 'Wykonuję inną umowę zlecenia objętą obowiązkowym ZUS'],
    ['zus3', 'Prowadzę działalność gospodarczą objętą obowiązkowym ZUS'],
    ['zus4', 'Jestem emerytem'],
    ['zus5', 'Jestem rencistą'],
    ['zus6', 'Jestem studentem/uczniem i nie ukończyłem 26 lat'],
    ['zus7', 'Jestem zarejestrowany jako bezrobotny'],
    ['zus8', 'Przebywam na urlopie macierzyńskim/wychowawczym lub mam świadczenie przedemerytalne'],
    ['zus9', 'Podlegam ubezpieczeniu w KRUS'],
  ];
  const bHead = [
    { text: '#', fillColor: '#f0f4f1', color: FOREST, bold: true },
    { text: 'Oświadczam, że:', fillColor: '#f0f4f1', color: FOREST, bold: true },
    { text: 'TAK / NIE', fillColor: '#f0f4f1', color: FOREST, bold: true },
  ];
  const bBody = [bHead].concat(bItems.map(([k, t], i) => [
    { text: String(i + 1), alignment: 'center' },
    { text: t },
    yn(A[k]),
  ]));

  return {
    pageSize: 'A4', pageMargins: [40, 44, 40, 40], defaultStyle: { font: 'Roboto', fontSize: 9, color: INK },
    content: [
      ...header(),
      ...h1('OŚWIADCZENIE ZLECENIOBIORCY (ZUS/US + PODATKI)', 'status ubezpieczeniowy, wnioski o ubezpieczenia i oświadczenia podatkowe'),
      { text: `Załącznik nr 4 do Umowy zlecenia nr ${nr}`, italics: true, fontSize: 7.6, color: '#666', margin: [0, 0, 0, 4] },

      h2('Sekcja A — Dane (drukowanymi literami)'),
      { table: { widths: [180, '*'], body: aBody }, layout: { hLineColor: () => '#c9c9c9', vLineColor: () => '#c9c9c9' }, fontSize: 8.6 },

      h2('Sekcja B — Status ubezpieczeniowy (zaznacz TAK/NIE)'),
      { table: { widths: [22, '*', 110], body: bBody }, layout: { hLineColor: () => '#c9c9c9', vLineColor: () => '#c9c9c9' }, fontSize: 8.6 },
      { text: 'W przypadku zaznaczenia NIE we wszystkich pozycjach niniejsze zlecenie stanowi jedyny tytuł do ubezpieczeń i podlega pełnemu oskładkowaniu. Przy „TAK” w poz. 1 należy potwierdzić, że podstawa z innego tytułu wynosi co najmniej minimalne wynagrodzenie; przy „TAK” w poz. 6 należy załączyć dokument potwierdzający status studenta.', italics: true, fontSize: 7.6, color: '#666', margin: [0, 4, 0, 2] },

      h2('Sekcja C — Wnioski o ubezpieczenia dobrowolne'),
      cbLine(!!A.dobr_emer_rent, 'Wnoszę o objęcie dobrowolnym ubezpieczeniem emerytalnym i rentowym z tytułu niniejszej umowy.'),
      cbLine(!!A.dobr_chor, 'Wnoszę o objęcie dobrowolnym ubezpieczeniem chorobowym (nie dotyczy studentów do 26 r.ż.).'),

      h2('Sekcja D — Oświadczenia podatkowe (PIT)'),
      {
        columns: [
          box(!!A.pit2),
          {
            width: '*', fontSize: 9, text: [
              'Wnoszę o stosowanie kwoty zmniejszającej zaliczkę na podatek (PIT-2): ',
            ],
          },
        ], columnGap: 3, margin: [0, 2, 0, 0],
      },
      {
        columns: [
          box(A.pit2_czesc === '1/12'), { text: '1/12', width: 'auto', fontSize: 8.6, margin: [2, 0, 8, 0] },
          box(A.pit2_czesc === '1/24'), { text: '1/24', width: 'auto', fontSize: 8.6, margin: [2, 0, 8, 0] },
          box(A.pit2_czesc === '1/36'), { text: '1/36.', width: 'auto', fontSize: 8.6, margin: [2, 0, 0, 0] },
        ], columnGap: 1, margin: [16, 1, 0, 2],
      },
      cbLine(!!A.bez_zaliczki, 'Wnoszę o niepobieranie zaliczki na podatek — przewiduję, że roczny dochód nie przekroczy kwoty wolnej (art. 41 ust. 1c ustawy o PIT).'),
      {
        columns: [
          { text: 'Koszty uzyskania przychodu: ', width: 'auto', fontSize: 9 },
          box(A.kup === '20'), { text: '20% (standardowe).', width: '*', fontSize: 8.6, margin: [2, 0, 0, 0] },
        ], columnGap: 1, margin: [0, 2, 0, 2],
      },
      {
        columns: [
          { text: 'Ulga dla młodych (do 26 r.ż., art. 21 ust. 1 pkt 148 ustawy o PIT): ', width: 'auto', fontSize: 9 },
          box(A.ulga26 === 'dotyczy'), { text: 'dotyczy', width: 'auto', fontSize: 8.6, margin: [2, 0, 8, 0] },
          box(A.ulga26 === 'nie_dotyczy'), { text: 'nie dotyczy.', width: 'auto', fontSize: 8.6, margin: [2, 0, 8, 0] },
          box(!!A.ulga26_niestosowac), { text: 'Wnoszę o niestosowanie ulgi.', width: '*', fontSize: 8.6, margin: [2, 0, 0, 0] },
        ], columnGap: 1, margin: [0, 2, 0, 2],
      },

      // Sekcja E і блок підпису — нерозривний блок (переливається РАЗОМ, не сиротою).
      {
        unbreakable: true,
        stack: [
          h2('Sekcja E — Oświadczenia końcowe'),
          { text: '1. Oświadczam, że powyższe dane są prawdziwe i zgodne ze stanem faktycznym; w razie podania nieprawdziwych danych ponoszę odpowiedzialność za szkodę wyrządzoną Zleceniodawcy.', fontSize: 8.2, margin: [0, 1, 0, 1] },
          { text: '2. Zobowiązuję się niezwłocznie informować Zleceniodawcę o każdej zmianie statusu mającej wpływ na ubezpieczenia lub rozliczenia podatkowe.', fontSize: 8.2, margin: [0, 1, 0, 1] },
          { text: '3. Zapoznałem się z klauzulą informacyjną RODO Zleceniodawcy (załącznik nr 2).', fontSize: 8.2, margin: [0, 1, 0, 1] },
          {
            columns: [
              { stack: [
                { text: ' ', margin: [0, 0, 0, 26] },
                { text: '______________________________', fontSize: 11, lineHeight: 1, color: '#444' },
                { text: 'Miejscowość i data', fontSize: 9, color: '#444', margin: [0, 3, 0, 0] },
              ], alignment: 'center' },
              { stack: [
                { text: ' ', margin: [0, 0, 0, 26] },
                { text: '______________________________', fontSize: 11, lineHeight: 1, color: '#444' },
                { text: 'Czytelny podpis', fontSize: 9, color: '#444', margin: [0, 3, 0, 0] },
              ], alignment: 'center' },
            ],
            margin: [0, 16, 0, 0],
          },
        ],
      },
    ],
  };
}


KADRY_DOCS.docZUSPL = docZUSPL;
}

/* ==== doc_upowaznienie_wychowawca_pl.js ==== */
{
// Upoważnienie do przetwarzania danych osobowych (art. 29 RODO)
// Załącznik nr 1 do Umowy zlecenia nr 1/WYC/2026 — dla wychowawcy CampScout (JDG — Volodymyr Shevchenko).
// Struktura §1–§6 zgodna ze wzorem hr-pack-fayna/web/doc_upowaznienie.js, dostosowana do CampScout i danych dzieci (art. 9 RODO).
function h1(t, sub) { return [ { text: t, fontSize: 13, color: FOREST, bold: true, margin: [0, 2, 0, 1] }, { text: sub, fontSize: 8.5, color: GOLD, bold: true, margin: [0, 0, 0, 5] } ]; }
function h2(t) { return { text: t, fontSize: 9.5, color: FOREST, bold: true, margin: [0, 6, 0, 2] }; }

const NR_UMOWY = '1/WYC/2026';
// data sporządzenia — FIKSOWANA (nie new Date())
const DATA_SPORZADZENIA = '07.07.2026';

// pusta linia do uzupełnienia (podkreślona)
function bl(w) {
  const n = Math.round((w || 180) / 5.8);
  return { text: ' '.repeat(n), decoration: 'underline', color: '#999' };
}

// wypełnione pole (podkreślone) lub pusta linia
function vline(v, w) {
  return (v !== undefined && v !== null && String(v).trim() !== '') ? fld(String(v)) : bl(w);
}

function p(content, extra) {
  return Object.assign({ text: content, alignment: 'justify', margin: [0, 2, 0, 0] }, extra || {});
}

function docUpowaznieniePL(A) {
  A = A || {};
  const nr = A.umowa_nr || NR_UMOWY;
  const nameInst = A.fullname || 'Imię i nazwisko';

  const content = [
    ...header(),
    ...h1('UPOWAŻNIENIE DO PRZETWARZANIA DANYCH OSOBOWYCH',
      'art. 29 RODO — załącznik nr 1 do Umowy zlecenia'),

    { text: `Załącznik nr 1 do Umowy zlecenia nr ${nr}`, italics: true, fontSize: 7.6, color: '#666', margin: [0, 0, 0, 4] },
    p(['Sporządzone w Ostrowie Wielkopolskim dnia ', fld(DATA_SPORZADZENIA), '.']),
    p([
      { text: CAMPSCOUT.nazwa, bold: true },
      `, ${CAMPSCOUT.adres}, NIP ${CAMPSCOUT.nip}, REGON ${CAMPSCOUT.regon}, ROT ${CAMPSCOUT.rot}, `,
      `reprezentowany przez ${CAMPSCOUT.reprezentant} — właściciela (organizatora), jako administrator danych osobowych (dalej „Administrator”), `,
      'niniejszym upoważnia ', fld(nameInst), ', PESEL ', vline(A.pesel, 150),
      ' (dalej „Osoba upoważniona”), będącą Zleceniobiorcą z ww. Umowy zlecenia, do przetwarzania danych osobowych ',
      { text: 'w imieniu i na polecenie Administratora', bold: true },
      ', w zakresie i na zasadach określonych poniżej (art. 29 RODO).',
    ]),

    h2('§ 1. Podstawa i charakter upoważnienia'),
    p(`1. Osoba upoważniona przetwarza dane osobowe wyłącznie w ramach wykonywania Umowy zlecenia nr ${nr}, pod zwierzchnictwem i zgodnie z udokumentowanymi poleceniami Administratora; nie jest odrębnym administratorem ani podmiotem przetwarzającym.`),
    p('2. Przetwarzanie odbywa się w dokumentacji obozowej (m.in. karty kwalifikacyjne uczestników, listy, ewidencja) oraz w narzędziach i na nośnikach udostępnionych lub wskazanych przez Administratora.'),

    h2('§ 2. Zakres danych i kategorie osób'),
    p('1. Rodzaj danych: dane identyfikacyjne i kontaktowe dzieci i młodzieży — uczestników obozów CampScout (imię, nazwisko, data urodzenia, adres, PESEL) oraz ich rodziców/opiekunów prawnych (imię, nazwisko, telefon, e-mail, adres), a także dane dotyczące przebiegu obozu. W zakresie niezbędnym do zapewnienia bezpieczeństwa i opieki — dane dotyczące stanu zdrowia uczestników (choroby, alergie, przyjmowane leki, zalecenia lekarskie), stanowiące dane szczególnej kategorii w rozumieniu art. 9 RODO.'),
    p('2. Kategorie osób: dzieci i młodzież — uczestnicy obozów CampScout, ich rodzice/opiekunowie prawni, a w razie potrzeby inni pracownicy i współpracownicy Administratora.'),
    p([
      { text: 'Minimalizacja (art. 5 ust. 1 lit. c RODO): ', bold: true },
      'Osoba upoważniona przetwarza wyłącznie dane niezbędne do wykonywania obowiązków wychowawcy/instruktora na obozie. Dostęp do danych szczególnej kategorii (art. 9 RODO — stan zdrowia dzieci) przysługuje wyłącznie w zakresie ściśle niezbędnym do zapewnienia bezpieczeństwa i opieki nad uczestnikami.',
    ]),

    h2('§ 3. Obowiązki Osoby upoważnionej'),
    p('1. Przetwarza dane wyłącznie na udokumentowane polecenie i zgodnie z instrukcjami Administratora oraz kierownika obozu.'),
    p('2. Zachowuje w tajemnicy dane oraz sposoby ich zabezpieczenia — w czasie trwania Umowy zlecenia i bezterminowo po jej ustaniu.'),
    p('3. Stosuje środki bezpieczeństwa wskazane przez Administratora (art. 32 RODO); wobec danych szczególnej kategorii (stan zdrowia dzieci) — z najwyższą starannością, w szczególności nie pozostawia dokumentacji bez nadzoru i chroni ją przed dostępem osób nieuprawnionych.'),
    p('4. Nie kopiuje, nie fotografuje, nie eksportuje ani nie przechowuje danych poza dokumentacją i systemami udostępnionymi przez Administratora i nie udostępnia ich osobom trzecim.'),
    p('5. Niezwłocznie, nie później niż w ciągu 24 godzin, zawiadamia Administratora (kierownika obozu) o każdym podejrzeniu lub stwierdzeniu naruszenia ochrony danych.'),
    p('6. Pomaga Administratorowi w realizacji praw osób, których dane dotyczą (rodziców/opiekunów), oraz w wykonaniu obowiązków z art. 32–36 RODO.'),

    h2('§ 4. Dane podmiotów obsługiwanych przez Administratora'),
    p('W zakresie, w jakim Administrator przetwarza dane jako podmiot przetwarzający na rzecz osób trzecich (np. innych organizatorów lub partnerów CampScout), Osoba upoważniona przetwarza te dane wyłącznie w granicach poleceń Administratora oraz zgody i poleceń administratorów tych danych.'),

    h2('§ 5. Czas obowiązywania i ustanie'),
    p(`1. Upoważnienie obowiązuje przez czas trwania Umowy zlecenia nr ${nr} i wygasa wraz z nią lub z chwilą jego odwołania przez Administratora.`),
    p('2. Z chwilą ustania Osoba upoważniona zaprzestaje przetwarzania, zwraca lub trwale usuwa nośniki i dokumentację zawierającą dane i nie zachowuje ich kopii, chyba że przepisy nakazują dalsze przechowywanie.'),

    // §6 і блок підпису — один нерозривний блок: якщо не влазить, переливається
    // РАЗОМ (не сиротою) на наступну сторінку, з нормальним місцем під підпис.
    {
      unbreakable: true,
      stack: [
        h2('§ 6. Odpowiedzialność'),
        p(`Do naruszenia obowiązków wynikających z niniejszego upoważnienia stosuje się odpowiednio postanowienia § 6 Umowy zlecenia nr ${nr} (poufność). Upoważnienie sporządzono w dwóch egzemplarzach, po jednym dla każdej ze Stron.`),
        {
          columns: [
            { stack: [
              { text: ' ', margin: [0, 0, 0, 26] },
              { text: '______________________________', fontSize: 11, lineHeight: 1, color: '#444' },
              { text: 'Administrator (udzielający upoważnienia)', fontSize: 8.5, color: FOREST, bold: true, margin: [0, 3, 0, 0] },
              { text: CAMPSCOUT.reprezentant, fontSize: 8, color: '#444' },
            ], alignment: 'center' },
            { stack: [
              { text: ' ', margin: [0, 0, 0, 26] },
              { text: '______________________________', fontSize: 11, lineHeight: 1, color: '#444' },
              { text: 'Osoba upoważniona (potwierdzam przyjęcie)', fontSize: 8.5, color: FOREST, bold: true, margin: [0, 3, 0, 0] },
              { text: nameInst, fontSize: 8, color: '#444' },
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


KADRY_DOCS.docUpowaznieniePL = docUpowaznieniePL;
}

/* ==== doc_wolontariat_wychowawca_ua.js ==== */
{
// Договір про волонтерську діяльність (виховник) — ТОВ «КЕМПСКАУТ» (Україна) → волонтер-виховник.
// Виїзний дитячий табір у Республіці Польща. Reuse зі зразка № К01/2025 (координатор Р. Шамайко).
// Правова основа: ЗУ «Про волонтерську діяльність» №3236-VI + Ustawa o działalności pożytku publicznego i o wolontariacie (Dz.U. 2003 nr 96 poz. 873).

// Реквізити української організації (з реєстру / зразка К01/2025)
const TOV = {
  nazwa: 'ТОВАРИСТВО З ОБМЕЖЕНОЮ ВІДПОВІДАЛЬНІСТЮ «КЕМПСКАУТ»',
  korotko: 'ТОВ «КЕМПСКАУТ»',
  edrpou: '45010375',
  misto: 'м. Тернопіль, Україна',
  adresa: '46016, Тернопільська обл., м. Тернопіль, вул. Київська, буд. 3, кв. 6',
  kerivnyk: 'Шевченко Володимир Павлович',
  email: 'admin@campscout.com.ua',
  tel: '+38(063)0202948',
};

const DATA_UKLADENNA = '07.07.2026';
const DEFAULT_OD = '2026-07-08';
const DEFAULT_DO = '2026-07-21';

function bl(w) {
  const n = Math.round((w || 160) / 5.6);
  return { text: ' '.repeat(n), decoration: 'underline', color: '#999' };
}
function vline(v, w) {
  return (v !== undefined && v !== null && String(v).trim() !== '') ? fld(String(v)) : bl(w);
}
function fmt(dateStr) {
  const d = new Date(dateStr + 'T00:00:00');
  const dd = String(d.getDate()).padStart(2, '0');
  const mm = String(d.getMonth() + 1).padStart(2, '0');
  return `${dd}.${mm}.${d.getFullYear()}`;
}
function p(content, extra) {
  return Object.assign({ text: content, alignment: 'justify', margin: [0, 3, 0, 0] }, extra || {});
}
function li(t) { return { text: '• ' + t, margin: [10, 1.5, 0, 0], fontSize: 8.8 }; }

// Українська шапка ТОВ КЕМПСКАУТ (не CampScout PL!)
function ukrHeader() {
  return [
    { text: TOV.korotko, bold: true, fontSize: 12, color: FOREST },
    { text: `${TOV.nazwa} · ЄДРПОУ ${TOV.edrpou}`, fontSize: 7.2, color: '#555' },
    { text: TOV.adresa, fontSize: 7.2, color: '#555' },
    { text: 'Виїзний дитячий табір (Республіка Польща) · діє за законодавством України', fontSize: 7.2, color: '#555' },
    { canvas: [{ type: 'line', x1: 0, y1: 2, x2: 515, y2: 2, lineWidth: 2, lineColor: GOLD }], margin: [0, 4, 0, 10] },
  ];
}

function docWolontariatWychowawcaUA(A) {
  A = A || {};
  const name = A.fullname || 'Прізвище, імʼя, по батькові';
  const zam = [A.adres_zam_ulica, [A.adres_zam_kod, A.adres_zam_miasto].filter(Boolean).join(' ')].filter(Boolean).join(', ');
  const od = fmt(A.data_od || DEFAULT_OD);
  const doD = fmt(A.data_do || DEFAULT_DO);

  const content = [
    ...ukrHeader(),
    { text: 'ДОГОВІР про волонтерську діяльність', fontSize: 13, bold: true, color: FOREST, alignment: 'center', margin: [0, 0, 0, 1] },
    { text: '(виховник виїзного дитячого табору)', fontSize: 9, bold: true, color: GOLD, alignment: 'center', margin: [0, 0, 0, 8] },
    {
      columns: [
        { text: ['№ ', fld(A.umowa_nr_ua || '___/2026')], fontSize: 9 },
        { text: [TOV.misto.replace('м. ', 'м. '), ', ', fld(DATA_UKLADENNA)], fontSize: 9, alignment: 'right' },
      ], margin: [0, 0, 0, 6],
    },

    p([
      { text: TOV.korotko, bold: true },
      `, що діє відповідно до законодавства України, в особі керівника ${TOV.kerivnyk}, який діє на підставі Статуту, надалі — «Організатор», з однієї сторони, та`,
    ]),
    p([
      'громадянин(ка) ', fld(name), ', паспорт (документ, що посвідчує особу): ', vline(A.dowod, 150),
      ', що проживає за адресою: ', zam ? fld(zam) : bl(200),
      ', тел.: ', vline(A.tel, 110), ', надалі — «Волонтер», з іншої сторони, разом — «Сторони», уклали цей Договір про таке:',
    ]),

    h2('1. Предмет Договору'),
    p(['1.1. Організатор залучає, а Волонтер зобовʼязується на ', { text: 'безоплатній основі', bold: true }, ' виконувати волонтерську діяльність з опіки, виховання та супроводу дітей — учасників виїзного дитячого табору, що проводиться у період з ', fld(od), ' по ', fld(doD), ' на території Республіки Польща.']),
    p('1.2. Волонтерська діяльність здійснюється відповідно до Закону України «Про волонтерську діяльність» № 3236-VI, законодавства Республіки Польща (Ustawa z dnia 24 kwietnia 2003 r. o działalności pożytku publicznego i o wolontariacie, Dz. U. 2003 nr 96 poz. 873) та положень цього Договору.'),
    p('1.3. Волонтерська діяльність не має на меті одержання прибутку та не є оплачуваною працею; цей Договір не є трудовим договором і не породжує трудових відносин.'),

    h2('2. Обовʼязки Волонтера'),
    li('здійснювати опіку та нагляд за дітьми, забезпечувати їхню безпеку, гігієну та дотримання розпорядку дня табору;'),
    li('організовувати та супроводжувати дітей під час занять, ігор, харчування, відпочинку та переміщень;'),
    li('дотримуватися програми табору, внутрішніх правил, етичних норм і стандартів Організатора;'),
    li('проходити вступний та поточні інструктажі (безпека, протидія булінгу, реагування на надзвичайні ситуації, перша допомога);'),
    li('негайно інформувати керівництво табору про події, що загрожують безпеці чи здоровʼя дітей;'),
    li('дотримуватися конфіденційності щодо персональних даних дітей, їхніх батьків та інших волонтерів;'),
    li('не залишати дітей без нагляду та не вживати алкоголь чи заборонені речовини під час виконання обовʼязків.'),

    h2('3. Права Волонтера'),
    li('отримувати від Організатора інформацію, необхідну для виконання волонтерської діяльності;'),
    li('отримувати харчування та проживання на рівні з кадрою табору;'),
    li('бути застрахованим від нещасних випадків на період перебування у таборі (NNW);'),
    li('отримати довідку/сертифікат про виконання волонтерської діяльності виховника;'),
    li('звертатися до Організатора з пропозиціями щодо покращення організації роботи.'),

    h2('4. Обовʼязки Організатора'),
    p('4.1. Підготовка та інформування: надати опис обовʼязків і меж відповідальності, забезпечити вступний інструктаж, ознайомити з програмою, розпорядком і порядком реагування на надзвичайні ситуації.'),
    p('4.2. Безпека і страхування: забезпечити умови згідно з нормами безпеки та гігієни за польським законодавством; застрахувати Волонтера від нещасних випадків (NNW — ubezpieczenie następstw nieszczęśliwych wypadków); надати доступ до медичної допомоги.'),
    p('4.3. Логістична підтримка: забезпечити належні умови проживання, харчування та необхідні матеріали/інвентар.'),
    p('4.4. Координація: призначити відповідального координатора/ментора, забезпечити зворотний звʼязок і підтримку.'),
    p('4.5. Юридична відповідальність: оформити письмову угоду про волонтерську діяльність; дотримуватися польського Закону про громадську діяльність і волонтерство; інформувати про правила обробки персональних даних згідно з GDPR.'),
    p('4.6. Визнання: на прохання Волонтера видати довідку/сертифікат про виконану волонтерську діяльність із зазначенням дати, місця та обсягу обовʼязків.'),

    h2('5. Права Організатора'),
    p('5.1. Контроль та управління діяльністю волонтера: визначати обсяг, форму та графік волонтерської діяльності відповідно до потреб табору; давати волонтеру обовʼязкові для виконання завдання, що відповідають його компетенціям і домовленостям; контролювати дотримання волонтером розпорядку дня, правил табору; вимагати від волонтера інформування про всі важливі ситуації, повʼязані з дітьми (інциденти, скарги, зміни у стані здоровʼя тощо).'),
    p('5.2. Реагування на неналежну поведінку або порушення: проводити оцінку ефективності виконання волонтером своїх обовʼязків та давати конструктивний зворотний звʼязок; у разі порушення дисципліни, правил безпеки чи етики — робити усне або письмове зауваження; у випадку систематичного невиконання обовʼязків або грубих порушень — призупинити або достроково припинити участь волонтера в таборі з відповідним записом в облікових документах; вимагати компенсації збитків, завданих через умисні або грубі дії волонтера, якщо це прямо передбачено договором та законодавством.'),
    p('5.3. Вимога дотримання стандартів безпеки: вимагати від волонтера проходження інструктажів, ознайомлення з процедурами безпеки, протипожежними нормами, політикою захисту дітей; усунути волонтера від роботи у випадку, якщо його поведінка створює загрозу життю, здоровʼю дітей або інших учасників табору.'),
    p('5.4. Комунікація та внутрішній порядок: встановлювати внутрішні канали комунікації (наради, звітність, онлайн-групи) та вимагати їх використання; обмежити або заборонити волонтеру публікацію фото/відео з дітьми у соціальних мережах без дозволу батьків або керівництва; погоджувати усі ініціативи волонтера, які стосуються нових програм, активностей, або залучення зовнішніх осіб.'),
    p('5.5. Право на обробку персональних даних: обробляти персональні дані волонтера (імʼя, контакти, паспортні дані, страхування) з метою організації табору відповідно до законодавства (включаючи GDPR); зберігати документи, повʼязані з участю волонтера в таборі, у межах терміну, необхідного для звітності або юридичного обґрунтування діяльності.'),

    h2('6. Обробка персональних даних (GDPR)'),
    p('6.1. Волонтер надає згоду на обробку своїх персональних даних Організатором відповідно до Регламенту ЄС 2016/679 (GDPR) у звʼязку з укладенням та виконанням цього Договору.'),
    p('6.2. Волонтер, отримуючи доступ до персональних даних дітей — учасників табору (у тому числі даних про стан здоровʼя, що є особливою категорією даних), зобовʼязується обробляти їх виключно в межах виконання цього Договору, за вказівками Організатора, та зберігати конфіденційність безстроково.'),
    p('6.3. Волонтер має право на доступ до своїх даних, їх виправлення, обмеження обробки або вимогу видалення.'),

    h2('7. Строк дії та припинення'),
    p(['7.1. Договір набирає чинності з моменту підписання та діє до ', fld(doD), '.']),
    p('7.2. Договір може бути розірвано достроково за ініціативою будь-якої зі Сторін з письмовим повідомленням не пізніше ніж за 3 календарні дні, а у разі загрози безпеці дітей — негайно.'),

    h2('8. Прикінцеві положення'),
    p('8.1. Спори вирішуються шляхом переговорів, а в разі недосягнення згоди — відповідно до законодавства України та Республіки Польща.'),
    p('8.2. Договір складено у двох примірниках, по одному для кожної зі Сторін.'),

    {
      columns: [
        { stack: [
          { text: 'Організатор', bold: true, fontSize: 8.5, color: FOREST },
          { text: TOV.korotko + ',', fontSize: 8 },
          { text: 'ЄДРПОУ ' + TOV.edrpou, fontSize: 8 },
          { text: TOV.tel + ', ' + TOV.email, fontSize: 8 },
          { text: '______________________________', margin: [0, 26, 0, 0], fontSize: 11, lineHeight: 1 },
          { text: TOV.kerivnyk, fontSize: 8, color: '#444' },
        ] },
        { stack: [
          { text: 'Волонтер', bold: true, fontSize: 8.5, color: FOREST },
          { text: ' ', fontSize: 8 },
          { text: ' ', fontSize: 8 },
          { text: '______________________________', margin: [0, 26, 0, 0], fontSize: 11, lineHeight: 1 },
          { text: name, fontSize: 8, color: '#444' },
        ] },
      ],
      columnGap: 24, margin: [0, 24, 0, 0], unbreakable: true,
    },
  ];

  return {
    pageSize: 'A4',
    pageMargins: [40, 40, 40, 38],
    defaultStyle: { font: 'Roboto', fontSize: 9, color: INK },
    content,
  };
}


KADRY_DOCS.docWolontariatWychowawcaUA = docWolontariatWychowawcaUA;
}

/* ==== doc_zgoda_rspts_ua.js ==== */
{
// Заява-згода на перевірку кандидата за реєстрами осіб, засуджених за злочини проти статевої
// свободи та недоторканості неповнолітніх (безпека дітей) — додаток до пакету документів
// вихователя CampScout (УКРАЇНСЬКА). Адміністратор = CAMPSCOUT (JDG — Volodymyr Shevchenko).

const DATA_UKLADENNA = '07.07.2026';

function bl(w) {
  const n = Math.round((w || 160) / 5.6);
  return { text: ' '.repeat(n), decoration: 'underline', color: '#999' };
}
function vline(v, w) {
  return (v !== undefined && v !== null && String(v).trim() !== '') ? fld(String(v)) : bl(w);
}
function p(content, extra) {
  return Object.assign({ text: content, alignment: 'justify', margin: [0, 5, 0, 0], fontSize: 9 }, extra || {});
}

function docZgodaRSPTS(A) {
  A = A || {};
  const name = A.fullname || "Прізвище, ім'я, по батькові";

  const content = [
    ...header('ua'),
    ...h1(
      'ЗАЯВА-ЗГОДА на перевірку кандидата за реєстрами осіб,',
      'які вчинили злочини проти статевої свободи та недоторканості неповнолітніх',
    ),

    p([
      `${CAMPSCOUT.nazwa}, як організатор дитячого табору, з метою забезпечення безпеки дітей — учасників табору, `,
      'здійснює перевірку кандидатів у кадровий склад табору (виховників, інструкторів, волонтерів) за наявними реєстрами осіб, ',
      'засуджених за злочини проти статевої свободи та недоторканості неповнолітніх (в Україні та/або в Республіці Польща — ',
      'за місцем фактичного проведення табору), перед допуском кандидата до роботи з дітьми.',
    ]),

    h2('Дані кандидата'),
    p(["Прізвище, ім'я, по батькові: ", fld(name)]),
    p(['Дата народження: ', vline(A.data_urodzenia, 130)]),
    p(['Документ, що посвідчує особу: ', vline(A.dowod, 200)]),

    h2('Текст згоди'),
    p(['1. Я, ', fld(name), ', свідомо та добровільно надаю ', { text: CAMPSCOUT.nazwa, bold: true }, ' згоду на здійснення перевірки моєї особи за реєстрами, зазначеними вище, з метою підтвердження відсутності перешкод для роботи з дітьми.']),
    p('2. Я надаю згоду на обробку моїх персональних даних (включно з даними, що стосуються можливої судимості) виключно для цілей такої перевірки, відповідно до Регламенту ЄС 2016/679 (GDPR) та законодавства України про захист персональних даних.'),
    p("3. Я підтверджую, що мені відомо про мету перевірки — забезпечення безпеки дітей, — і розумію, що результати перевірки можуть впливати на рішення щодо мого допуску до роботи в таборі."),
    p('4. Я заявляю, що надані мною дані є правдивими, і зобовʼязуюсь негайно повідомити організатора, якщо стосовно мене розпочнеться кримінальне провадження за злочини проти статевої свободи чи недоторканості неповнолітніх.'),
    p('5. Ця згода діє на період підготовки та проведення табору і зберігається організатором відповідно до строків, встановлених для кадрової документації.'),

    {
      columns: [
        { text: ['Місце і дата: ', fld(DATA_UKLADENNA)], fontSize: 9 },
      ],
      margin: [0, 16, 0, 0],
    },

    {
      columns: [
        { stack: [
          { text: 'Кандидат', bold: true, fontSize: 8.5, color: FOREST },
          { text: ' ', fontSize: 8 },
          { text: '______________________________', margin: [0, 26, 0, 0], fontSize: 11, lineHeight: 1 },
          { text: '(підпис, П.І.Б.)', fontSize: 8, color: '#444' },
        ] },
      ],
      margin: [0, 10, 0, 0], unbreakable: true,
    },
  ];

  return {
    pageSize: 'A4',
    pageMargins: [40, 44, 40, 40],
    defaultStyle: { font: 'Roboto', fontSize: 9, color: INK },
    content,
  };
}


KADRY_DOCS.docZgodaRSPTS = docZgodaRSPTS;
}

/* ==== doc_zgoda_rspts_pl.js ==== */
{
// Oświadczenie-zgoda na weryfikację kandydata w rejestrach osób skazanych za przestępstwa
// przeciwko wolności seksualnej i nietykalności małoletnich (bezpieczeństwo dzieci) — załącznik
// do pakietu dokumentów instruktora CampScout (POLSKA). Administrator = CAMPSCOUT (JDG — Volodymyr Shevchenko).

const DATA_SPORZADZENIA = '07.07.2026';

function bl(w) {
  const n = Math.round((w || 160) / 5.6);
  return { text: ' '.repeat(n), decoration: 'underline', color: '#999' };
}
function vline(v, w) {
  return (v !== undefined && v !== null && String(v).trim() !== '') ? fld(String(v)) : bl(w);
}
function p(content, extra) {
  return Object.assign({ text: content, alignment: 'justify', margin: [0, 5, 0, 0], fontSize: 9 }, extra || {});
}

function docZgodaRSPTSPL(A) {
  A = A || {};
  const name = A.fullname || 'Imię i nazwisko';

  const content = [
    ...header(),
    ...h1(
      'OŚWIADCZENIE-ZGODA na weryfikację kandydata w rejestrach osób,',
      'które popełniły przestępstwa przeciwko wolności seksualnej i nietykalności małoletnich',
    ),

    p([
      `${CAMPSCOUT.nazwa}, jako organizator obozu dla dzieci, w celu zapewnienia bezpieczeństwa dzieci — uczestników obozu, `,
      'dokonuje weryfikacji kandydatów do kadry obozu (wychowawców, instruktorów, wolontariuszy) w dostępnych rejestrach osób ',
      'skazanych za przestępstwa przeciwko wolności seksualnej i nietykalności małoletnich (w Ukrainie i/lub w Rzeczypospolitej Polskiej — ',
      'wedle miejsca faktycznego prowadzenia obozu), przed dopuszczeniem kandydata do pracy z dziećmi.',
    ]),

    h2('Dane kandydata'),
    p(['Imię i nazwisko: ', fld(name)]),
    p(['Data urodzenia: ', vline(A.data_urodzenia, 130)]),
    p(['Dokument tożsamości: ', vline(A.dowod, 200)]),

    h2('Treść zgody'),
    p(['1. Ja, ', fld(name), ', świadomie i dobrowolnie udzielam ', { text: CAMPSCOUT.nazwa, bold: true }, ' zgody na dokonanie weryfikacji mojej osoby w rejestrach wskazanych powyżej, w celu potwierdzenia braku przeszkód do pracy z dziećmi.']),
    p('2. Wyrażam zgodę na przetwarzanie moich danych osobowych (w tym danych dotyczących ewentualnej karalności) wyłącznie w celu takiej weryfikacji, zgodnie z Rozporządzeniem UE 2016/679 (RODO) oraz przepisami o ochronie danych osobowych.'),
    p('3. Potwierdzam, że znany jest mi cel weryfikacji — zapewnienie bezpieczeństwa dzieci — i rozumiem, że jej wynik może mieć wpływ na decyzję o moim dopuszczeniu do pracy w obozie.'),
    p('4. Oświadczam, że podane przeze mnie dane są prawdziwe i zobowiązuję się niezwłocznie poinformować organizatora, jeżeli wobec mnie zostanie wszczęte postępowanie karne o przestępstwa przeciwko wolności seksualnej lub nietykalności małoletnich.'),
    p('5. Niniejsza zgoda obowiązuje przez okres przygotowań i trwania obozu i jest przechowywana przez organizatora zgodnie z terminami przewidzianymi dla dokumentacji kadrowej.'),

    {
      columns: [
        { text: ['Miejscowość i data: ', fld(DATA_SPORZADZENIA)], fontSize: 9 },
      ],
      margin: [0, 16, 0, 0],
    },

    {
      columns: [
        { stack: [
          { text: 'Kandydat', bold: true, fontSize: 8.5, color: FOREST },
          { text: ' ', fontSize: 8 },
          { text: '______________________________', margin: [0, 20, 0, 0], fontSize: 14, lineHeight: 1 },
          { text: '(podpis, imię i nazwisko)', fontSize: 8, color: '#444' },
        ] },
      ],
      margin: [0, 10, 0, 0], unbreakable: true,
    },
  ];

  return {
    pageSize: 'A4',
    pageMargins: [40, 44, 40, 40],
    defaultStyle: { font: 'Roboto', fontSize: 9, color: INK },
    content,
  };
}


KADRY_DOCS.docZgodaRSPTSPL = docZgodaRSPTSPL;
}


// Налаштування шрифтів для pdfMake (vfs_fonts.js вже підвантажив pdfMake.vfs)
if (typeof pdfMake !== 'undefined') {
  pdfMake.fonts = { Roboto: { normal:'Roboto-Regular.ttf', bold:'Roboto-Medium.ttf', italics:'Roboto-Italic.ttf', bolditalics:'Roboto-MediumItalic.ttf' } };
}
function fname(A){ return (A.fullname||'kadra').replace(/\s+/g,'_'); }

function docDefPL(A){
  // pageBreak:'before' вішається на ПЕРШИЙ елемент кожного наступного документа
  // (а не на окремий порожній маркер) — інакше фантомний рядок з'їдає ~13pt
  // і підпис (кінець документа) сиротою вилітає на майже порожню наступну сторінку.
  const parts = [KADRY_DOCS.docUmowaWychowawcaPL, KADRY_DOCS.docKwestPL, KADRY_DOCS.docRODOPL, KADRY_DOCS.docZUSPL, KADRY_DOCS.docUpowaznieniePL, KADRY_DOCS.docZgodaRSPTSPL];
  let content = [];
  parts.forEach((fn, i) => {
    const c = fn(A).content.slice();
    if (i>0 && c.length) c[0] = Object.assign({}, c[0], { pageBreak:'before' });
    content = content.concat(c);
  });
  return { pageSize:'A4', pageMargins:[40,44,40,40], defaultStyle:{font:'Roboto',fontSize:9,color:INK}, content };
}
function genPL(A){ pdfMake.createPdf(docDefPL(A)).download('umowa_instruktor_PL_'+fname(A)+'.pdf'); }
function genUA(A){ pdfMake.createPdf(KADRY_DOCS.docWolontariatWychowawcaUA(A)).download('dogovir_wolontariat_UA_'+fname(A)+'.pdf'); }
function genRSPTS(A){ pdfMake.createPdf(KADRY_DOCS.docZgodaRSPTS(A)).download('zgoda_rspts_'+fname(A)+'.pdf'); }

// ОДИН PDF з усіма документами (PL-пакет + UA-договір + RSPTS) — браузери
// блокують 2-й+ .download() поспіль (та сама проблема, що й у форми Данієля,
// виправлена там через combinePDF). Тут той самий фікс: усе в один файл.
function docDefAll(A_PL, A_UA){
  const parts = [
    ...docDefPL(A_PL).content,
  ];
  const uaContent = KADRY_DOCS.docWolontariatWychowawcaUA(A_UA).content.slice();
  if (uaContent.length) uaContent[0] = Object.assign({}, uaContent[0], { pageBreak:'before' });
  const rsptsContent = KADRY_DOCS.docZgodaRSPTS(A_UA).content.slice();
  if (rsptsContent.length) rsptsContent[0] = Object.assign({}, rsptsContent[0], { pageBreak:'before' });
  const content = parts.concat(uaContent, rsptsContent);
  return { pageSize:'A4', pageMargins:[40,44,40,40], defaultStyle:{font:'Roboto',fontSize:9,color:INK}, content };
}
function genALL(A_PL, A_UA){ pdfMake.createPdf(docDefAll(A_PL, A_UA)).download('dokumenty_kadra_'+fname(A_PL)+'.pdf'); }

const api = { genPL, genUA, genRSPTS, genALL, docDefPL, docDefAll, _docs: KADRY_DOCS };
if (typeof window !== 'undefined') window.KADRY = api;
if (typeof module !== 'undefined' && module.exports) module.exports = api;
})();
