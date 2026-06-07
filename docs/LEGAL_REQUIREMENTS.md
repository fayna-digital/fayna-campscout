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

*Źródło pierwotne: ITW Polska — Niezbędnik Kierownika Wypoczynku 2024 (prawa zastrzeżone ITW)*  
*Opracowanie dla modułu: Fayna Digital 2026-06-07*
