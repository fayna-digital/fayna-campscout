# Odoo 17 Fayna CampScout (client data) — scaffold (Phase 7)

![Odoo Version](https://img.shields.io/badge/Odoo-17.0%20Community-purple)
![Python](https://img.shields.io/badge/Python-3.10+-blue)
![Phase](https://img.shields.io/badge/Phase-7-red)
![License](https://img.shields.io/badge/License-LGPL--3-green.svg)
![Status](https://img.shields.io/badge/Status-Scaffold-orange)

**Developed by [Fayna Digital](https://www.fayna.agency) for CampScout and the broader Fayna Camp vertical stack.**
**Author: Volodymyr Shevchenko**

---

Thin client-specific data layer for CampScout (product records, legal pages, brand).

Phase 7 of the master plan: `CAMPSCOUT_MASTER_TZ.md §16`.

Current state: **scaffold only** — installable but inert. Feature flag
`fayna_campscout.active` defaults to `False`. Implementation proceeds in
increments listed in `docs/TZ.md`.

---

## Features (planned)

Client-specific records ONLY (21 product.template + events + FAQ + legal copy + brand theme).

---

## Architecture

```
fayna_campscout/
├── __manifest__.py
├── __init__.py
├── data/ir_config_parameter.xml       # feature flag
├── models/                             # Phase 7 implementation
├── tests/test_scaffold.py              # install + flag + deps sanity
├── docs/TZ.md                          # per-module TZ
├── .github/workflows/ci.yml            # gate-2 CI
├── .pre-commit-config.yaml             # gate-1 pre-commit
├── pyproject.toml
├── LICENSE
├── CHANGELOG.md
└── README.md
```

---

## Installation

```bash
cd /opt/campscout/custom-addons
sudo -u \#1000 git clone https://github.com/VladSh77/fayna-campscout.git fayna_campscout
docker exec campscout_web odoo -c /etc/odoo/odoo.conf -d campscout \
    -i fayna_campscout --stop-after-init --no-http
docker restart campscout_web
```

Module installs as **inert** (feature flag `False`). No behaviour change until flip.

---

## License

LGPL-3 — see [LICENSE](LICENSE).

---

*Developed by [Fayna Digital](https://www.fayna.agency) · Volodymyr Shevchenko*
