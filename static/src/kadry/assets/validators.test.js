/* Незалежна перевірка валідаторів: контрольні суми рахуємо ТУТ, своєю
   реалізацією, і лише потім питаємо валідатор. Тест, написаний автором коду,
   доводить лише самоузгодженість. */
global.window = {};
require('./validators.js');
const V = global.window.KADRY_VALID;
let pass = 0, fail = 0;
const t = (name, cond) => { cond ? pass++ : fail++; console.log((cond ? '  OK   ' : '  FAIL ') + name); };

// --- власні реалізації контрольних сум ---
const peselCtrl = d => { const w=[1,3,7,9,1,3,7,9,1,3]; let s=0; for(let i=0;i<10;i++) s+=+d[i]*w[i]; return (10-(s%10))%10; };
const nipCtrl   = d => { const w=[6,5,7,2,3,4,5,6,7]; let s=0; for(let i=0;i<9;i++) s+=+d[i]*w[i]; return s%11; };
const rnokppCtrl= d => { const w=[-1,5,7,9,4,6,10,5,7]; let s=0; for(let i=0;i<9;i++) s+=+d[i]*w[i]; return (s%11)%10; };
const mod97     = iban => { const r = (iban.slice(4)+iban.slice(0,4)).toUpperCase()
    .replace(/[A-Z]/g, c => (c.charCodeAt(0)-55).toString());
  let rem = 0; for (const ch of r) rem = (rem*10 + +ch) % 97; return rem; };

// --- PESEL ---
const peselBase = '4405140135';                        // 10 цифр, контрольну рахуємо самі
const peselOk = peselBase + peselCtrl(peselBase);
t(`pesel(${peselOk}) валідний`, V.pesel(peselOk).ok === true);
const peselBad = peselBase + ((peselCtrl(peselBase)+1)%10);
t(`pesel(${peselBad}) відхилено (зіпсована контрольна)`, V.pesel(peselBad).ok === false);
t('pesel(11 літер) відхилено', V.pesel('abcdefghijk').ok === false);
t('pesel(10 цифр) відхилено — коротко', V.pesel('4405140135').ok === false);
const bd = V.peselBirthDate(peselOk);
t(`peselBirthDate → 1944-05-14 (отримано ${bd.date})`, bd.ok === true && bd.date === '1944-05-14');

// --- NIP ---
let nipOk = null;
for (const base of ['113231629','525224848','777777777','123456789']) {
  if (nipCtrl(base) !== 10) { nipOk = base + nipCtrl(base); break; }
}
t(`nip(${nipOk}) валідний`, V.nip(nipOk).ok === true);
const nipBad = nipOk.slice(0,9) + ((+nipOk[9]+1)%10);
t(`nip(${nipBad}) відхилено`, V.nip(nipBad).ok === false);

// --- IBAN PL ---
const ibanPL = 'PL61109010140000071219812874';
t(`ibanPL(${ibanPL}) mod97=${mod97(ibanPL)} валідний`, mod97(ibanPL) === 1 && V.ibanPL(ibanPL).ok === true);
t('ibanPL зі зміненою цифрою відхилено',
  V.ibanPL('PL61109010140000071219812875').ok === false);
t('ibanPL без префікса PL приймається', V.ibanPL('61109010140000071219812874').ok === true);

// --- РНОКПП ---
const rnBase = '303456789';
const rnOk = rnBase + rnokppCtrl(rnBase);
t(`rnokpp(${rnOk}) валідний`, V.rnokpp(rnOk).ok === true);
t('rnokpp зі зміненою контрольною відхилено',
  V.rnokpp(rnBase + ((rnokppCtrl(rnBase)+1)%10)).ok === false);

// --- транслітерація (постанова КМУ 55/2010) ---
const tr = [
  ['Єрмак', 'Yermak'], ['Андрій', 'Andrii'], ['Ющенко', 'Yushchenko'],
  ['Згурський', 'Zghurskyi'], ['Їжак', 'Yizhak'], ['Хмельницький', 'Khmelnytskyi'],
];
for (const [ua, expect] of tr) {
  const got = V.translitUaToLat(ua);
  t(`translit ${ua} → ${expect} (отримано ${got})`, got === expect);
}

console.log(`\nРАЗОМ: OK=${pass} FAIL=${fail}`);
process.exit(fail ? 1 : 0);
