# Role i kabinety / Ролі та кабінети

> Diátaxis: **explanation** (wyjaśnienie). Dokument dla **właściciela / kupującego** — bez kodu.
> Po co: zrozumieć, kto co widzi w systemie i gdzie loguje się każda osoba.
> Дублюється скорочено в `README.md` (розділ «Ролі та кабінети»). Тут — повний нетехнічний опис.

---

## Krótko / Коротко

Jeden moduł `fayna_camp_portal` obsługuje **całą organizację obozu**. Każda osoba ma swoją rolę.
Po zalogowaniu trafia do **swojego kabinetu** i widzi **tylko to, co jej wolno** — dane medyczne, dane innych dzieci czy finanse są chronione (RODO).

Один модуль `fayna_camp_portal` обслуговує **всю табірну організацію**. У кожної людини є своя роль.
Після входу вона потрапляє у **свій кабінет** і бачить **лише дозволене** — медичні дані, дані чужих дітей і фінанси захищені (RODO).

---

## Tabela ról / Таблиця ролей

| Rola (PL) | Роль (UA) | Co robi / Що робить | Kabinet (gdzie loguje się) / Кабінет (де входить) |
|-----------|-----------|----------------------|----------------------------------------------------|
| **Organizator** | Організатор | Szef całości. Widzi wszystko: zapisy, przychód, zapełnienie obozów, niepodpisane karty, incydenty, terminy do Kuratorium. Może „wejść jako" dowolna rola (każde wejście jest logowane — RODO art. 30). Bo to on odpowiada prawnie za wypoczynek (Rozp. MEN §2.1). / Голова всього. Бачить усе. Може «увійти як» будь-яка роль. | **Panel administratora** — `/admin/dashboard` |
| **Sales** | Менеджер продажів | Sprzedaje miejsca: katalog obozów, zamówienia, zgłoszenia/wsparcie, raporty marketingowe. **Nie widzi** danych medycznych dzieci, dziennika, incydentów. / Продає місця. Не бачить медичних даних, журналу, інцидентів. | Backend Odoo (lista zapisów, sprzedaż) |
| **Kierownik** | Керівник табору | Szef jednego turnusu. Widzi **tylko swój turnus**: raport dzienny, dziennik, kadrę, kartę kwalifikacyjną (sekcje III–V), Program Wypoczynku, checklistę do Kuratorium. / Голова одного турнуса. Бачить лише свій турнус. | Backend Odoo (zakres swojego turnusu) |
| **Wychowawca** | Вихователь | Opiekun jednej grupy. Widzi **tylko swoją grupę**: dziennik zajęć (Załącznik 5), sekcję VI karty, wysyłkę SMS do rodziców (z limitem), czat turnusu. / Опікун однієї групи. Бачить лише свою групу. | Backend Odoo (zakres swojej grupy) |
| **Instructor** | Інструктор | Prowadzi zajęcia/aktywności. Widzi swoje aktywności i ograniczony zakres medyczny **pod aktywność** (np. astma — do biegania). **Nie widzi** pełnej karty medycznej ani incydentów. / Веде активності. Бачить свої активності й обмежену медичну інформацію під активність. | Backend Odoo (swoje aktywności) |
| **Finanse** (księgowy) | Бухгалтер | Liczy pieniądze: budżety obozów — **BEP** (próg rentowności) i **marża** (VAT art. 119 oraz marża biznesowa), kategorie kosztów, plan vs fakt. **Nie widzi** danych medycznych ani wychowawczych. / Рахує гроші: бюджети, BEP, маржа. Не бачить медичних/виховних даних. | Menu **Finanse** (backend) |
| **Parent** (rodzic) | Батько / Мати | Rodzic uczestnika. Widzi **tylko własne dzieci**: karty dzieci, kartę kwalifikacyjną (sekcje I–II + podpis), aktualności (stories) swojego turnusu, dokumenty, lojalność, asystę (escort). / Батько учасника. Бачить лише власних дітей. | **Kabinet rodzica** — `/my` |

---

## Role specjalistyczne (opcjonalne) / Спеціалізовані ролі (опційні)

Nakładają się **na rolę podstawową** — daje się je tylko wybranym osobom.
Накладаються **поверх основної ролі** — видаються лише обраним.

| Rola (PL) | Po co / Навіщо |
|-----------|----------------|
| **Medical Officer** | Dostęp do danych medycznych dziecka (RODO art. 9: alergie, leki, choroby przewlekłe, uwagi lekarza). / Доступ до медданих (RODO art. 9). |
| **Nutrition Officer** | Diety + alergeny EU-14 (Rozp. 1169/2011), plany żywieniowe. / Дієти + 14 алергенів ЄС. |
| **HR Manager** | Weryfikacja kadry: **KRK** (Zaświadczenie o niekaralności) + **RPS** (Rejestr Sprawców Przestępstw na tle seksualnym) + certyfikaty kursów (Rozp. MEN §4, Ustawa Kamilka 2024). / Перевірка кадрів: KRK + RPS + сертифікати. |
| **Emergency Responder / Manager** | Obsługa incydentów (Karta Wypadku §11, Rejestr §12, eskalacja Ustawa Kamilka). / Обробка інцидентів. |

---

## Skróty użyte w systemie / Скорочення в системі

W interfejsie pojawiają się skróty — oto co znaczą (te same podpowiedzi są jako tooltipy w aplikacji):
В інтерфейсі є скорочення — ось що вони означають (ті самі підказки є тултіпами в застосунку):

| Skrót | Pełna nazwa (PL) | Що це (UA) |
|-------|------------------|------------|
| **KRK** | Zaświadczenie o niekaralności (z Krajowego Rejestru Karnego) | Довідка про несудимість |
| **RPS** | Rejestr Sprawców Przestępstw na tle seksualnym | Реєстр осіб, які вчинили статеві злочини |
| **BEP** | Próg rentowności (Break-Even Point) | Точка беззбитковості — скільки дітей, щоб вийти в нуль |
| **KO** | Kuratorium Oświaty | Куратор освіти (наглядовий орган) |
| **marża** | Marża (w tym procedura VAT marża, art. 119 ustawy o VAT) | Маржа (зокрема податок VAT від маржі, ст. 119) |

---

*Fayna Digital · Volodymyr Shevchenko · OPL-1*
