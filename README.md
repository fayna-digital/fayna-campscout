# Odoo 17 Camp Portal — zarządzanie obozami dziecięcymi

![Odoo Version](https://img.shields.io/badge/Odoo-17.0%20Community-purple)
![Python](https://img.shields.io/badge/Python-3.10+-blue)
![PL Law](https://img.shields.io/badge/PL%20Law-Rozp.%20MEN%202016-red)
![License](https://img.shields.io/badge/License-OPL--1-blue.svg)
![Status](https://img.shields.io/badge/Status-Active%20Development-orange)

**Opracowane przez [Fayna Digital](https://www.fayna.agency) dla polskiego rynku organizatorów obozów**
**Autor: Volodymyr Shevchenko**

---

Pojedynczy moduł Odoo 17 (`fayna_camp_portal`, wersja `17.0.4.1.8`) zawierający całą logikę biznesową organizatora obozów dziecięcych — od publicznego katalogu i portalu rodzica, przez karty kwalifikacyjne, dziennik zajęć, rejestr leków, protokół awaryjny (Ustawa Kamilka 2024), po zgłoszenia do kuratorium, szkolenia kadry i rozgłoszenia SMS. Moduł obsługuje obozy przez cały rok — wakacje letnie, ferie zimowe i inne turnusy (w kodzie m.in. strona oferty `oferta/ferie2027`). Zbudowany na natywnych mechanizmach Odoo (`mail.thread`, `portal`, `event`, `sale`, `loyalty`, `sms`).

Referencyjne wdrożenie: [CampScout](https://campscout.eu) — obozy dziecięce w Polsce.

---

## Co faktycznie robi ten kod

Poniższy opis pochodzi z bezpośredniej analizy plików w tym repozytorium (`models/`, `controllers/`, `views/`, `data/`, `wizards/`, `tests/`), a nie z dokumentacji.

### RBAC — 6 ról + role specjalistyczne

`security/groups.xml` definiuje 6 ról podstawowych (Organizator / Sales / Kierownik / Wychowawca / Instructor / Parent) oraz role specjalistyczne (medical / HR / nutrition / emergency responder / manager). Dostęp jest ograniczany przez:
- **ACL na poziomie pól** — dane zdrowotne RODO Art.9 (alergie, leki, choroby przewlekłe, notatki lekarza) są maskowane na poziomie ORM w `models/art9_security.py` (guard `read()`), z testami `tests/test_art9_access.py` i `tests/test_art9_http_isolation.py`.
- **Reguły rekordów** (`security/record_rules.xml`) — zakres per zmiana dla kadry, rodzic widzi tylko własne dzieci.

### Portal rodzica (`/my/*`)

`controllers/portal.py` (734 linie) nadpisuje `CustomerPortal.home()` dla `/my` i `/my/home`, wstrzykując dane hero (uczestnicy, aktywne/nadchodzące rejestracje) do renderu początkowego — bo w Odoo 17 `_prepare_home_portal_values()` działa tylko przez AJAX `/my/counters`. Kluczowe mechanizmy:
- **Whitelist pól edytowalnych** `PARTICIPANT_PORTAL_EDITABLE_FIELDS` — jedyna bariera między portalem a zapisem: submit pisze przez `sudo()`, więc pole spoza listy nie może trafić do `write()` z portalu.
- **`CAMP_DAY_PUBLIC_REPORT_FIELDS`** — ścisła whitelist pól `camp.daily.report` wystawianych rodzicom na `/my/camp-day`; pola serwisowe (incydenty zdrowotne, notatki dyscyplinarne, notatki kierownika) nigdy nie trafiają do portalu.

### Rejestr leków (`models/medication.py`, 787 linii)

`camp.medication.*` — pełny obieg leków: rodzic zdaje lek medykowi (z żywym podpisem zgody wg wzorca `camp.escort` — Binary PNG + `signed_date`/`ip`/`by` + log RODO), system generuje zagregowany grafik wydań (`camp.medication.schedule`), medyk odznacza „Wydano"/„Pominięto" z tabletu, cron łapie przeterminowane `pending → missed → mail.activity` do kierownika. Dla leków krytycznych (`is_critical`, przypadek Tsybulko — leki psychiatryczne) dodatkowo SMS `CRITICAL` przez `fayna.sms.dispatcher`. Dane leków to kategoria specjalna RODO Art.9 — ten sam gate pól co w `camp.participant`.

### Rate-limit i retry (`models/rate_limit.py`)

Dwa czyste helpery (bez modelu, unit-testowalne):
1. **Rate-limit publicznych formularzy** — honeypot + limit częstotliwości per IP (domyślnie 5 zgłoszeń / 5 min), klucz przechowywany w `ir.config_parameter`.
2. **Retry z wykładniczym backoffem** — dla integracji wychodzących (KSeF, SMS, Zadarma, SendPulse): retry przejściowych błędów z wykładniczym opóźnieniem do limitu, potem log i dalsze działanie (nigdy nie blokuje sprzedaży).

### SMS — trzy priorytety + Ustawa Kamilka

`models/sms_notify.py` nadpisuje `mail.thread._notify_thread_by_sms` i czyta atrybut klasy `_notify_priority` (`CRITICAL` / `IMPORTANT` / `INFO` / `CRITICAL_OVERRIDE`). `models/incident_kamilka.py` dodaje `severity='kamilka'`, które wymusza `CRITICAL_OVERRIDE` (pomija `sms_opt_in` — podstawa prawna GDPR art.6.1.d, interes żywotny). `data/cron_kamilka_escalation.xml` — cron co 5 minut eskaluje do zastępcy kierownika / organizatora, jeśli główny nie potwierdził. Każde zgłoszenie trafia do niezmiennego `camp.incident.notification.log` (append-only, bez `unlink()` nawet przez superusera). Rozgłoszenie SMS przez wychowawcę — kreator `wizards/staff_sms_composer.py` z guardem kosztu i limitem miesięcznym, audyt w `models/staff_sms_log.py`.

### Zgodność z polskim prawem obozowym

- **Karta kwalifikacyjna** — `models/participant.py`, 5 sekcji wg Rozp. MEN 30.03.2016, z workflow podpisu rodzica i niezmiennością pól po podpisie (`_PROTECTED_AFTER_SIGNOFF`); edycje po podpisie przez przepływ `amend()`.
- **Dziennik zajęć** — `camp.dziennik` (Załącznik 5), podpis wychowawcy blokuje `write()` poza polem `notes`.
- **Program Wypoczynku** — `camp.program.wypoczynku` (Załącznik 9), maszyna stanów `draft → submitted → approved`.
- **Zgłoszenie do Kuratorium** — `camp.kuratorium.notification` (Załącznik 1), auto-termin 21 dni przed startem, cron blokuje start zmiany bez zgłoszenia.
- **Teczka kontroli KO** — `models/teczka_ko.py` (folder gotowości do kontroli Kuratorium).
- **Regulamin** — `models/regulamin.py` (+ potwierdzenie kadry).
- **Karta Wypadku** — `models/incident_card.py` (16 pkt).

### Dashboard organizatora z view-as

`controllers/admin.py` — `/admin/dashboard` (renderowany po stronie serwera, karty KPI) oraz `/admin/as-{rola}` — wcielenie w dowolną rolę przez `env(user=...)` (zachowuje ACL, nigdy sudo). Każde wcielenie logowane do `camp.admin.access.log` (RODO art.30, retencja 7 lat — `models/retention.py`).

### Inne moduły w kodzie

- `models/budget.py` + `data/budget_categories.xml` + `data/fiscal_positions.xml` — budżety obozów (BEP, marże VAT/biznesowe).
- `models/transport.py` — rezerwacja busa/autokaru na zmianę.
- `models/stories.py` — kanał wiadomości dla rodziców.
- `models/training.py` — szkolenia kadry (rozszerza `slide.channel`).
- `models/recruitment.py` + `models/staffing.py` — wakaty kadry i aplikacje kandydatów.
- `models/camp_escort.py` — indywidualna asysta/konwój uczestnika z podpisem.
- `models/camp_group.py` — grupa wychowawcza (art. 92c).
- `controllers/health.py` — endpoint zdrowia.
- `wizards/camp_create_wizard.py` — kreator tworzenia obozu.
- `models/event_channel_create.py` — auto-tworzenie `discuss.channel` na zmianę.
- `models/auto_subscribe_extensions.py` — auto-subskrypcja obserwujących na participant/journal/incident.

### i18n

Natywne tłumaczenia Odoo `.po` — `i18n/uk_UA.po` (ukraiński) i `i18n/pl_PL.po` (polski), 374+ przetłumaczonych stringów.

---

## Struktura repozytorium

```
fayna-campscout/
├── __manifest__.py                  # v17.0.4.1.8 · OPL-1 · application=True
├── hooks.py                         # post_init_hook — dane seed, domyślna konfiguracja
├── models/                          # 40 plików modeli (camp.*, patrz wyżej)
├── controllers/                     # 9 kontrolerów (portal, admin, kiosk, kadry_forms,
│                                    #   recruitment_portal, escort_portal, document_submission, health)
├── views/                           # 30+ plików widoków (camp, participant, operations,
│                                    #   nutrition, emergency, commercial, training, transport,
│                                    #   stories, reports, sms, staff_sms, admin, budget, medication,
│                                    #   incident_card, regulamin, teczka, program, recruitment,
│                                    #   staffing, group, escort, kiosk, menu_scoping, res_company)
├── templates/                       # szablony QWeb (portal, website, admin_dashboard)
├── security/                        # groups.xml, ir.model.access.csv, record_rules.xml
├── data/                            # ir_config_parameter, cron, cron_kamilka_escalation,
│                                    #   sms_templates, sms_child_templates, budget_categories,
│                                    #   fiscal_positions, fayna_sms_provider_data
├── wizards/                         # staff_sms_composer.py, camp_create_wizard.py
├── i18n/                            # uk_UA.po, pl_PL.po
├── migrations/                      # post-migrate dla wersji 17.0.4.0.0 → 17.0.4.1.8
├── tests/                           # 60+ plików testów (pytest + framework Odoo)
├── tools/                           # deploy-staging.sh, seed_test_camp_durdom.py, run_odoo_tests.sh
├── demo/demo.xml
└── docs/                            # per-modułowe TZ + notatki ARCHITECTURE
```

---

## Zależności

`__manifest__.py` deklaruje twarde zależności: `base`, `mail`, `contacts`, `portal`, `website`, `website_slides`, `sale`, `event`, `event_sale`, `website_event`, `website_sale`, `account`, `loyalty`, `sms`, oraz moduły siostrzane **`fayna_rodo_compliance`** (log zgód + retencja) i **`fayna_sms_base`** (dyspozytor SMS multi-provider).

---

## Instalacja

### 1. Klonowanie do custom-addons

```bash
cd /opt/<klient>/custom-addons
git clone https://github.com/VladSh77/fayna-campscout.git
git clone https://github.com/VladSh77/fayna-rodo-compliance.git
git clone https://github.com/VladSh77/fayna_sms_base.git
```

### 2. Najpierw zainstaluj zależności

`fayna_camp_portal` deklaruje `fayna_rodo_compliance` i `fayna_sms_base` jako twarde zależności; zainstaluj je przed tym modułem, aby podwójny zapis zgód i dyspozytor SMS istniały zanim wystrzeli hook post_init.

```bash
docker stop <klient>_web

docker run --rm \
    -v /opt/<klient>/custom-addons:/mnt/custom-addons:ro \
    -v /opt/<klient>/odoo-data:/var/lib/odoo:rw \
    -v /opt/<klient>/config:/etc/odoo:rw \
    --network <klient>_net \
    odoo:17.0 \
    odoo -c /etc/odoo/odoo.conf -d <db> \
    -i fayna_rodo_compliance,fayna_sms_base --stop-after-init --no-http
```

### 3. Zainstaluj ten moduł

```bash
docker run --rm \
    -v /opt/<klient>/custom-addons:/mnt/custom-addons:ro \
    -v /opt/<klient>/odoo-data:/var/lib/odoo:rw \
    -v /opt/<klient>/config:/etc/odoo:rw \
    --network <klient>_net \
    odoo:17.0 \
    odoo -c /etc/odoo/odoo.conf -d <db> \
    -i fayna_camp_portal --stop-after-init --no-http

docker start <klient>_web
```

Lub przez UI: **Apps → Update Apps List → szukaj `Camp Portal` → Install**.

---

## Konfiguracja

### Krok 1 — token dostawcy SMS

Skonfiguruj dane TurboSMS (lub alternatywnego dostawcę) przez **Settings → Technical → System Parameters** (tryb deweloperski):

| Klucz | Wartość |
|-------|---------|
| `fayna_sms_base.turbosms_token` | Token API TurboSMS z https://my.turbosms.ua |
| `fayna_sms_base.default_sender` | Alias nadawcy zarejestrowany u dostawcy |
| `fayna_camp_portal.sms_kierownik_monthly_limit` | Miesięczny limit rozgłoszeń dla kierownika (domyślnie `300`) |
| `fayna_camp_portal.sms_wychowawca_monthly_limit` | Miesięczny limit rozgłoszeń dla wychowawcy (domyślnie `100`) |

Grupa Organizator pomija miesięczny limit per-rola (uzasadnione operacyjne nadpisanie; nadal logowane).

### Krok 2 — ustawienia Kuratorium

Zgodnie z Rozp. MEN 30.03.2016 §3, każda zmiana obozu musi być zgłoszona do regionalnego Kuratorium Oświaty z wyprzedzeniem.

| Klucz | Wartość |
|-------|---------|
| `fayna_camp_portal.kuratorium_voivodeship` | Kod województwa (np. `mazowieckie`) |
| `fayna_camp_portal.kuratorium_office_email` | Adres e-mail regionalnego Kuratorium |
| `fayna_camp_portal.kuratorium_organizator_nip` | NIP organizatora (identyfikator podmiotu prawnego) |
| `fayna_camp_portal.kuratorium_advance_days` | Dni przed startem obozu na wysłanie zgłoszenia (domyślnie `21`) |

### Krok 3 — branding

Logo, kolor marki i stopka e-mail są odczytywane z aktywnej firmy. Hero portalu (`/my`) używa tokenów projektowych `static/src/scss/portal_hero.scss` — nadpisuj przez moduł motywu potomnego, a nie edytując SCSS w miejscu.

---

## Testy

```bash
# Lokalnie (ephemeral Odoo z zamontowanymi modułami)
docker run -d --name camp_dev \
    -v $(pwd)/fayna_camp_portal:/mnt/custom-addons/fayna_camp_portal \
    -v $(pwd)/fayna-rodo-compliance:/mnt/custom-addons/fayna_rodo_compliance \
    -v $(pwd)/fayna_sms_base:/mnt/custom-addons/fayna_sms_base \
    -p 8069:8069 \
    odoo:17.0

docker exec camp_dev odoo \
    -c /etc/odoo/odoo.conf -d <db> \
    --test-enable --stop-after-init -u fayna_camp_portal
```

Repozytorium zawiera 60+ plików testów pokrywających m.in.: dostęp Art.9 (HTTP i ORM), rejestr leków, karty kwalifikacyjne, dziennik, incydenty, budżety, role (organizator/kierownik/wychowawca/instructor/parent), escorts, rekrutację, rate-limit, retencję dokumentów, zgodę RODO, wielofirmowość, liczbę zapytań.

---

## Troubleshooting

| Błąd | Przyczyna | Rozwiązanie |
|-------|-----------|-------------|
| `Module fayna_rodo_compliance not found` | Brak twardej zależności w addons_path | Sklonuj `fayna-rodo-compliance` do custom-addons; zrestartuj Odoo i zaktualizuj Apps List |
| `_prepare_home_portal_values not called for /my hero` | Odoo 17 wywołuje je tylko na AJAX `/my/counters` | Już obsłużone — `controllers/portal.py::home()` nadpisuje render początkowy przez `_prepare_campscout_hero_values()` |
| Edycje karty kwalifikacyjnej cicho cofane | Pole jest w `_PROTECTED_AFTER_SIGNOFF` po podpisie | Użyj przepływu `amend()` — tworzy nowy podpisany rekord + archiwizuje poprzedni |
| SMS Kamilka nie pomija `sms_opt_in` | Model nie ma atrybutu klasy `_notify_priority = "CRITICAL_OVERRIDE"` | Ustaw atrybut na modelu (lub rozszerz nakładkę `incident_kamilka.py`) — `sms_notify.py` czyta go przez `getattr(type(self), "_notify_priority", None)` |
| `discuss.channel` nie tworzy się przy zmianie | Odoo 17 zmienił `mail.channel` → `discuss.channel`; stare zapisy `channel_partner_ids` cicho no-op | Użyj `channel.add_members(partner_ids=[...])` — już obsłużone w `event_channel_create.py` |
| `/admin/dashboard` zwraca 403 dla Organizatora | Użytkownik nie ma `group_camp_organizator` | Przypisz `Organizator Wypoczynku (top-level)` w formularzu użytkownika — implikuje wszystkie podrole |
| Tłumaczenia nie łapią się po edycji `.po` | Odoo cache'uje skompilowane `.mo` do załadowania modułu | Zrestartuj Odoo z `-u fayna_camp_portal --i18n-overwrite` |
| Rozgłoszenie SMS wychowawcy trafia na limit | Licznik miesięczny jest per-rola per-kadra per-miesiąc kalendarzowy | Podnieś `fayna_camp_portal.sms_wychowawca_monthly_limit` lub użyj nadpisania Organizatora |

---

## Licencja

OPL-1 (Odoo Proprietary License v1.0) — zobacz [LICENSE](LICENSE)

---

*Opracowane przez [Fayna Digital](https://www.fayna.agency) · Volodymyr Shevchenko*
