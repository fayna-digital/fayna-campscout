# PLAN — fayna_camp_portal

> План реалізації ТЗ ([TZ.md](TZ.md)) за [REPO_STANDARD](../../fayna-digital-docs/contributing/REPO_STANDARD.md).
> Dependency graph + фази + checkpoints. Оновлювати після кожного закритого пункту.
> Контекст: модуль ~95% реалізований (27 моделей), staging ✅ / prod ❌. Лишилися правові доповнення, тести критичних шляхів і **міграція даних** — це блокери prod-gate.

---

## Dependency graph (що від чого залежить)

```
[campscout_management моноліт]  ←── ще активний на prod (97 клієнтів + 36 дітей)
            │
            │  МІГРАЦІЯ ДАНИХ (P1 — найбільший блокер)
            ▼
[fayna_camp_portal]  ── depends ──▶ fayna_rodo_compliance (RODO consent/art.9)
            │                       fayna_sms_base (SMS dispatcher) ──▶ fayna_sms_turbosms
            │
            ├── Правові моделі (P2): qualification card wzór2026 · incident.register §12
            │        incident.card §11 · staff.rspts_verified §13
            │            └─ залежать від: participant.py · emergency.py · operations.py (вже є)
            │
            ├── Тести критичних шляхів (P3) ── залежать від усіх моделей вище
            │
            └── i18n UA 63%→100% (P4) ── незалежна, паралельна

PROD-GATE (ЗАКОН): P1 + P3 + human QA green  ⇒  тільки тоді prod
```

---

## Фаза P1 — Міграція даних `campscout_management → portal` 🔴 блокер

> Найбільший ризик: втрата юр.карток + RODO audit trail при переносі ~97 клієнтів + 36 дітей.

- [ ] **P1.1** Інвентар даних на старих таблицях (`campscout_management`): клієнти, діти, реєстрації, consent-логи.
- [ ] **P1.2** Mapping старих моделей → нові (`camp.participant`, `res.partner`, consent).
- [ ] **P1.3** Міграційний скрипт (idempotent, dry-run спершу) + бекап перед запуском.
- [ ] **P1.4** Звірка контрольних сум: к-сть записів до/після, цілісність RODO trail.
- **Checkpoint:** 0 втрачених карток, RODO trail повний → P1 done.

## Фаза P2 — Правові доповнення (wzór 2026 / Ustawa Kamilka)

- [ ] **P2.1** Картка кваліфікаційна wzór 2026 (Dz.U.2026/704 §10) — поля п.9: hydrofobia, lęk wysokości, choroby przewlekłe, soczewki, dieta, emocje → `camp.participant`.
- [ ] **P2.2** `camp.incident.register` (§12) — Rejestr Wypadków, 10 колонок.
- [ ] **P2.3** `camp.incident.card` (§11) — Karta Wypadku.
- [ ] **P2.4** `staff.rspts_verified` (§13) — Standardy Ochrony Małoletnich; блокада допуску кадри без weryfikacji RSPTS.
- **Checkpoint:** усі поля/моделі присутні, views + ACL + record rules налаштовані.

## Фаза P3 — Тести критичних правових шляхів 🔴 блокер prod-gate

> Поточні тести — лише smoke/portal. Критичні правові шляхи НЕ покриті.

- [ ] **P3.1** Kamilka: `severity='kamilka'` обходить opt-in; 5-хв escalation cron спрацьовує; notification log immutable.
- [ ] **P3.2** SMS cost-guard: ліміт 100/300 блокує понадлімітну розсилку; audit log пише.
- [ ] **P3.3** Immutability: `write`/`unlink` на `admin_access_log` / `staff_sms_log` → `UserError`.
- [ ] **P3.4** RODO field-level: portal-user НЕ бачить art.9 полів; view-as через `with_user` зберігає record rules.
- [ ] **P3.5** Coverage ≥70% критичних шляхів; `QUALITY_AUDIT_*.md` перед gate.
- **Checkpoint:** coverage ≥70%, усі правові інваріанти під тестом.

## Фаза P4 — i18n + polish (паралельно)

- [ ] **P4.1** UA 63%→100% для kierownik/wychowawca backend.
- [ ] **P4.2** Portal `/my/*` mobile audit (обов'язковий перед go-live).
- [ ] **P4.3** Прибрати/задокументувати scaffold: `campscout.portal.session/.menu`, `api.py /api/v1/*`.

## Фаза P5 — Prod-gate

- [ ] **P5.1** Весь модуль на Hetzner staging (розблокувати SSH key — окремий infra-блокер).
- [ ] **P5.2** Human QA green по всіх ролях.
- [ ] **P5.3** Виправити биті посилання в CHANGELOG (див. Open Questions TZ).
- **Checkpoint (ЗАКОН):** P1 + P3 done + QA green → deploy prod.

---

## Зв'язки

- [TZ.md](TZ.md) · [LEGAL_REQUIREMENTS.md](LEGAL_REQUIREMENTS.md) · [CABINET_STATUS.md](CABINET_STATUS.md)
- Kanban: [[projects/kanban]] §🟠 CampScout ядро · §🔵 перенесення Групи B
- [CAMPSCOUT_MASTER_TZ.md](../../fayna-digital-docs/contributing/CAMPSCOUT_MASTER_TZ.md) §16
