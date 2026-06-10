# fayna_camp_portal — Wymogi prawne (PL)

> Źródło: Materiały szkoleniowe ITW Polska — Niezbędnik Kierownika Wypoczynku 2024
> Podstawa prawna: Ustawa o systemie oświaty + rozporządzenia MEN/MZ
> Aktualizować przy każdej zmianie przepisów.

---

## 1. Żywienie

**Podstawa:** Rozporządzenie MZ z 26.07.2016 r. (Dz.U. 2016 poz. 1154)
Ustawa z 25.08.2006 r. o bezpieczeństwie żywności i żywienia

| Liczba posiłków | I śniadanie | II śniadanie | Obiad | Podwieczorek | Kolacja |
|-----------------|-------------|--------------|-------|--------------|---------|
| 4 posiłki | 20–25% | 15–20% | 35–40% | — | 15–20% |
| 5 posiłków | 20–25% | 15–20% | 35–40% | 5–10% | 10–15% |

**Moduł:** `models/nutrition.py` — pole `meals_per_day` (4 lub 5), walidacja %.

---

## 2. Liczebność grup

**Podstawa:** Art. 92c ustawy o systemie oświaty

| Grupa | Max uczestników / wychowawca |
|-------|------------------------------|
| Ogólna (wiek 10+) | **20 osób** |
| Z dziećmi do 10 r.ż. lub mieszana | **15 osób** |
| Uczestnicy niepełnosprawni / przewlekle chorzy | max **2** w grupie |

**Moduł:** `models/operations.py` — walidacja przy tworzeniu grup; ostrzeżenie gdy przekroczono limit.

---

## 3. Izolatka (sick bay)

| Wymaganie | Wartość |
|-----------|---------|
| Oddzielna dla dziewcząt i chłopców | TAK |
| Odstęp między łóżkami | min **1,5 m** |
| Pościel | komplet + co najmniej 2 zmiany |

**Dokumentacja obowiązkowa (prowadzi kierownik/personel medyczny):**
- Zeszyt porad i zabiegów
- Zeszyt chorych przebywających w izolatce
- Karty kwalifikacyjne uczestników
- Orzeczenia lekarskie personelu (badania sanitarno-epidemiologiczne)

**Moduł:** `models/emergency.py`, `models/participant.py` — karta kwalifikacyjna §5.

---

## 4. Opieka medyczna

**Podstawa:** Ustawa z 27.08.2004 r. o świadczeniach opieki zdrowotnej finansowanych ze środków publicznych

Organizator musi zapewnić dostęp do opieki medycznej poprzez:
- **NFZ** — dane teleadresowe + godziny właściwego świadczeniodawcy, LUB
- **Umowę** z lekarzem, pielęgniarką lub ratownikiem medycznym

**Moduł:** `models/operations.py` — pole `medical_contact` (imię, tel, godziny przyjęć) na camp.camp.

---

## 5. Transport

**Podstawa:** Rozporządzenie Min. Infrastruktury; www.bezpiecznyautokar.gov.pl

| Wymaganie | Wartość |
|-----------|---------|
| Opiekunów w autokarze | 1 / 15 uczniów (nie licząc kierowcy) |
| Oznakowanie pojazdu | żółte tablice z czarnym symbolem dzieci (przód + tył) |
| Max czas jazdy ciągłej | **4,5 godziny** (potem 45 min przerwy) |
| Max dzienny czas prowadzenia | **9 godzin** |
| Wyposażenie | apteczka, gaśnica, potwierdzenie sprawności technicznej |

**Kolumna piesza:**
- Max długość: **50 m**; odstęp między kolumnami: min **100 m**
- Dzieci do 10 r.ż. → chodnik lub pobocze, max 4 osoby w rzędzie
- Przy niedostatecznej widoczności: latarka biała (przód) + czerwona (tył) + elementy odblaskowe

**Moduł:** `models/transport.py` — `transport_type`, `vehicle_capacity`, `supervisor_count`; walidacja 1 opiekun/15.

---

## 6. Wypadek — procedura

**Podstawa:** Art. 92l ustawy o systemie oświaty

| Funkcja | Działanie | Termin |
|---------|-----------|--------|
| Kadra / wychowawca | Pierwsza pomoc, wezwanie służb | Natychmiast |
| Kierownik | Zawiadomić: rodziców, organizatora, kuratora oświaty (wg siedziby + miejsca wypoczynku) | Niezwłocznie |
| Kierownik | Zawiadomić: organ prowadzący szkołę, dyrektora, radę rodziców | Niezwłocznie |
| Kierownik | Prokuratura — przy wypadku śmiertelnym, ciężkim lub zbiorowym | Niezwłocznie |
| Kierownik | Państwowy inspektor sanitarny — przy zatruciu pokarmowym | Niezwłocznie |
| Kierownik | Protokół powypadkowy | W ciągu 14 dni |

**Moduł:** `models/incident_kamilka.py` + `models/incident_notification_log.py` — immutable audit log, 5-min escalation cron, powiadomienie kuratora.

---

## 7. Bezpieczeństwo nad wodą

**Podstawa:** Ustawa z 18.08.2011 r. o bezpieczeństwie osób przebywających na obszarach wodnych

| Wymaganie | Wartość |
|-----------|---------|
| Opiekun + ratownik WOPR | 1 wychowawca + min 1 ratownik przy grupie |
| Temperatura wody | min **18°C** (optymalna 22°C) |
| Temperatura powietrza | wyższa od wody o **4–5°C** |

**Zakazy bezwzględne:**
- Kąpiel w nieznanym zbiorniku / miejscu z zakazem kąpieli
- Skakanie na główkę do nieznanej wody
- Wchodzenie do wody w stanie rozgrzania lub po posiłku
- Zabawy w przytapianie / spychanie z materacy

**Spływ kajakowy:**
- Kamizelka asekuracyjna — obowiązkowo dla nieumiejących pływać, dzieci
- Dzieci poniżej 15 r.ż. → kajak z osobą dorosłą umiejącą pływać
- Odstęp między kajakami: **10–15 m**
- Sygnał STOP na wodzie: cała grupa zatrzymuje się przy brzegu

**Moduł:** aktywności wodne w `models/operations.py` — pole `water_activity_type`, walidacja ratownika.

---

## 8. Czyny karalne nieletnich

**Podstawa:** Ustawa z 26.10.1982 r. o postępowaniu w sprawach nieletnich (Dz.U. 2002/11/109)

| Pojęcie | Definicja |
|---------|-----------|
| Nieletni (czyn karalny) | osoba, która ukończyła **13 lat**, a nie ukończyła **17 lat** |
| Nieletni (demoralizacja) | osoba, która nie ukończyła **18 lat** |
| Środki wychowawcze | do lat **21** |
| Młodociany (k.k.) | sprawca poniżej **21 lat** w chwili czynu, poniżej **24 lat** przy orzekaniu |

**Procedura kierownika:** niezwłoczne zawiadomienie właściwego sądu rodzinnego (sąd wg miejsca zamieszkania/pobytu nieletniego).

**Moduł:** `models/incident_kamilka.py` — rozszerzenie o czyny karalne; pole `incident_type` z wartością `criminal_act`.

---

## Powiązane modele (fayna_camp_portal)

| Model | Przepis |
|-------|---------|
| `camp.camp` | medical_contact (§4), water_supervisor (§7) |
| `camp.participant` | karta kwalifikacyjna §5, disability (§2) |
| `models/nutrition.py` | §1 podział posiłków |
| `models/operations.py` | §2 liczebność, §7 woda |
| `models/transport.py` | §5 transport |
| `models/emergency.py` | izolatka §3 |
| `models/incident_kamilka.py` | §6 wypadek, §8 nieletni |
| `models/incident_notification_log.py` | §6 immutable log kuratora |

---

## 9. Dziennik Zajęć (Załącznik 5 Rozp. MEN 30.03.2016)

**Podstawa:** Rozporządzenie MEN z dnia 30 marca 2016 r. w sprawie wypoczynku dzieci i młodzieży (Dz.U. 2016 poz. 452)
**Forma:** Jeden dziennik na grupę + wychowawcę, prowadzony codziennie.

**Struktura dokumentu (4 sekcje):**

| Sekcja | Zawartość | Odpowiedzialny |
|--------|-----------|----------------|
| **1. Uczestnicy grupy** | L.p., Nazwisko i imię, Rok urodzenia (max 20 poz.) | Kierownik przy otwarciu |
| **2. Tygodniowe plany pracy** | Tydzień I/II/…, Zadania, Termin, Odpowiedzialny, Uwagi o wykonaniu | Wychowawca co tydzień |
| **3. Dziennik Zajęć** | Data, Godzina, Treść zajęcia, Uwagi (osiągnięcia/trudności/wnioski) + podpis | Wychowawca codziennie |
| **4. Uwagi i zalecenia** | Data, Treść, Podpis (wpisy kierownika/kontroli) | Kierownik / KO |

**Dane nagłówkowe dziennika:**
- Miejsce wypoczynku (adres)
- Organizator wypoczynku
- Oznaczenie grupy
- Imię i nazwisko kierownika
- Imię i nazwisko wychowawcy/ów
- Zajęcia rozpoczęto / zakończono (dd-mm-rrrr)

**Moduł:** `models/training.py` → model `camp.dziennik.zajec` (do migracji z `fayna_camp_dziennik_zajec`).
Pola: `date`, `hour_from`, `hour_to`, `activity_description`, `notes`, `supervisor_signature` (Many2one res.users), `week_plan_ids` (One2many), `participant_ids` (Many2many camp.participant).

---

## 10. Karta Kwalifikacyjna Uczestnika Wypoczynku (Załącznik 6)

> ✅ **AKTUALNY WZÓR:** Rozporządzenie MEN z dnia **27 maja 2026 r.** (**Dz.U. 2026 poz. 704**) — nowe brzmienie Załącznika 6.
> Wchodzi w życie **06.06.2026** (7 dni od ogłoszenia 29.05.2026).
> **Przepis przejściowy (§2):** karty na ferie letnie 2026 przekazane rodzicom PRZED 06.06.2026 zachowują ważność (stary wzór 2021 dopuszczalny tylko dla nich).

**Podstawa:** Rozp. MEN 27.05.2026 (Dz.U. 2026/704), zmieniające Rozp. MEN 30.03.2016 (Dz.U. 2016/452, zm. 2021/1548).

**6 sekcji formularza (struktura I–VI bez zmian względem 2021):**

| Sekcja | Zawartość |
|--------|-----------|
| **I. Informacje o wypoczynku** | Forma (kolonia/zimowisko/obóz/biwak/półkolonia/inna), termin, adres+lokalizacja, trasa wędrowna, kraj (zagranica) — podpis organizatora |
| **II. Informacje o uczestniku** | Imię/nazwisko, rodzice, rok urodzenia, PESEL, adres, adres rodziców, tel. (pkt 7), specjalne potrzeby edukacyjne (pkt 8), **stan zdrowia — pkt 9 ROZSZERZONY**, szczepienia (tężec, błonica, inne) — podpis rodziców |
| **III. Decyzja organizatora** | Zakwalifikować / odmówić + uzasadnienie (podpis organizatora) |
| **IV. Potwierdzenie kierownika** | Adres + pobyt od–do (podpis kierownika) |
| **V. Stan zdrowia w trakcie** | Choroby przebyte podczas wypoczynku (podpis kierownika) |
| **VI. Spostrzeżenia wychowawcy** | Obserwacje wychowawcy o pobycie uczestnika |

**⚠️ NOWE w pkt 9 (stan zdrowia) — wzór 2026 vs 2021:**
Stary 2021: uczulenie, choroba lokomocyjna, stałe leki+dawki, aparat ortodontyczny/okulary.
Nowy 2026 dodaje: **uczulenie na jad owadów, pyłki, pokarmy**; **choroby przewlekłe** (wprost); **soczewki kontaktowe**; **dieta niskokaloryczna, wegetarianizm**; oraz pola psycho-behawioralne dla bezpieczeństwa: **problemy z wyrażaniem emocji, problemy z funkcjonowaniem w grupie, lęk wysokości, hydrofobia**.

**Moduł:** `models/participant.py` → `camp.participant` + `camp.qualification.card`.
Pole `health_notes` rozbić na strukturę pkt 9: `allergy_meds/pollen/food/insect`, `chronic_diseases`, `permanent_meds` (lista+dawki), `vision_aid` (okulary/soczewki/aparat), `diet` (selection), `emotional_notes`, `group_func_notes`, `fear_heights` (bool), `hydrophobia` (bool) — ostatnie dwa KRYTYCZNE: blokada/ostrzeżenie przy zapisie na zajęcia wodne (§7) i wysokościowe.
Sekcje I–III wypełnia organizator/system, IV–VI wychowawca/kierownik w trakcie turnusu.

---

## 11. Karta Wypadku

**Pola obowiązkowe:**

| # | Pole |
|---|------|
| 1 | Nazwa placówki (pieczęć) |
| 2 | Imię/nazwisko poszkodowanego, data urodzenia, adres, klasa |
| 3 | Czynność wykonywana podczas wypadku |
| 4 | Rodzaj przeszkolenia BHP (kiedy, przez kogo, czas trwania) |
| 5 | Badanie lekarskie — data, przeciwwskazania |
| 6 | Data i czas wypadku, miejsce |
| 7 | Rodzaj i umiejscowienie uszkodzenia ciała |

**Moduł:** `models/incident_kamilka.py` → rozszerzyć o model `camp.incident.card` jako oddzielny rekord od `camp.incident.kamilka` (wypadek ≠ Kamilka, ale powiązane).

---

## 12. Rejestr Wypadków

> Dokument odrębny od Karty Wypadku (§11). Karta = pojedynczy wypadek; Rejestr = chronologiczny wykaz wszystkich wypadków na wypoczynku. Wymagany podczas kontroli KO (punkt listy kontrolnej: „zeszyt/rejestr wypadku, w którym odnotowuje się każdą udzieloną pomoc medyczną").

**Struktura (10 kolumn):**

| # | Kolumna |
|---|---------|
| 1 | Lp. |
| 2 | Imię i nazwisko (+ wskazanie grupy lub jednostki podziału organizacyjnego) |
| 3 | Data i rodzaj wypadku |
| 4 | Miejsce wypadku i rodzaj zajęć |
| 5 | Rodzaj urazu i jego opis |
| 6 | Okoliczności wypadku |
| 7 | Udzielona pomoc |
| 8 | Środki zapobiegawcze, wydane zarządzenia |
| 9 | Uwagi — wskazanie osoby (Wychowawcy mającego pod opieką dziecko) |
| 10 | Podpis Kierownika Wypoczynku lub placówki |

**Moduł:** `models/incident_kamilka.py` → model `camp.incident.register` — One2many wszystkich `camp.incident.card` w ramach turnusu (`camp.camp`), widok listowy chronologiczny + eksport PDF dla kontroli KO.

---

## 13. Standardy Ochrony Małoletnich (Ustawa Kamilka)

**Podstawa:** Ustawa z 28.07.2023 r. o zmianie ustawy — Kodeks rodzinny i opiekuńczy (tzw. Ustawa Kamilka); obowiązek wdrożenia od **15.02.2024 r.** Każdy organizator działalności z małoletnimi musi posiadać pisemne Standardy Ochrony Małoletnich.

**Wymagane elementy:**
- Zasady bezpiecznych relacji kadra–uczestnik
- Procedura zgłaszania i reagowania na podejrzenie krzywdzenia
- Procedura interwencji (kto, kiedy, do kogo: rodzice, organizator, sąd rodzinny, policja)
- Weryfikacja kadry w Rejestrze Sprawców Przestępstw na Tle Seksualnym (RSPTS, rps.ms.gov.pl) — **PRZED dopuszczeniem do pracy** (art. 21 ustawy z 16.05.2016 r.; brak weryfikacji = kara aresztu / grzywny min. 1000 zł)
- Zasady dostępu małoletnich do internetu i ochrony przed treściami szkodliwymi
- Wersja skrócona, zrozumiała dla małoletnich

**Moduł:** powiązanie z `models/incident_kamilka.py` (procedura interwencji) + `models/staff.py` — pole `rspts_verified` (bool + data weryfikacji) na kadrze; blokada przypisania do turnusu bez weryfikacji RSPTS.

---

## Powiązane modele (fayna_camp_portal) — aktualizacja

| Model | Przepis |
|-------|---------|
| `camp.camp` | medical_contact (§4), water_supervisor (§7) |
| `camp.participant` | karta kwalifikacyjna §10 (sekcje I–VI), disability (§2) |
| `camp.qualification.card` | §10 — sekcje I–VI jako osobny rekord |
| `camp.dziennik.zajec` | §9 — dzienny zapis zajęć (migracja z fayna_camp_dziennik_zajec) |
| `camp.week.plan` | §9 sekcja 2 — tygodniowy plan pracy |
| `camp.incident.card` | §11 karta wypadku |
| `camp.incident.register` | §12 rejestr wypadków (chronologiczny) |
| `models/staff.py` | §13 rspts_verified (weryfikacja RSPTS) |
| `models/nutrition.py` | §1 podział posiłków |
| `models/operations.py` | §2 liczebność, §7 woda |
| `models/transport.py` | §5 transport |
| `models/emergency.py` | izolatka §3 |
| `models/incident_kamilka.py` | §6 wypadek (procedura), §8 nieletni, §13 interwencja |
| `models/incident_notification_log.py` | §6 immutable log kuratora |

---

*Źródło pierwotne: ITW Polska — Niezbędnik Kierownika Wypoczynku 2024 (prawa zastrzeżone ITW)*
*Karta Kwalifikacyjna: Rozp. MEiN 22.07.2021 (Dz.U. 2021/1548) — oficjalny wzór MEN (wersja w materiałach; nowszy wzór 2026 NIE został dostarczony)*
*Dziennik Zajęć: Rozp. MEN 30.03.2016 (Dz.U. 2016/452) — Załącznik 5*
*Rejestr Wypadków: wzór z materiałów ITW 2024*
*Standardy Ochrony Małoletnich: Ustawa Kamilka (zmiana KRO z 28.07.2023, obowiązek od 15.02.2024)*
*Opracowanie dla modułu: Fayna Digital 2026-06-07*
