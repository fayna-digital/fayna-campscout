"""E2E критичні шляхи CampScout — Playwright проти staging.

Запускається в CI (.github/workflows/e2e.yml) з secrets:
  E2E_BASE_URL (напр. https://staging.campscout.eu), E2E_ADMIN_LOGIN, E2E_ADMIN_PASSWORD.

Філософія (qa-test-automation): E2E покриває ЛИШЕ критичні бізнес-шляхи (~10% пірамідою),
де злам = втрата грошей/довіри. Решта — pytest unit/integration у самому Odoo.

⚠️ ПЕРШИЙ ПРОГІН = КАЛІБРУВАННЯ. Селектори нижче — стандартні для Odoo 17, але проти
реального staging можуть потребувати уточнення (action-id меню Kadra, точні лейбли).
Скелети, що залежать від навігації меню, поки @skip — знімаємо skip після калібрування.
"""

import os

import pytest
from playwright.sync_api import Page, expect

BASE = os.environ.get("E2E_BASE_URL", "https://staging.campscout.eu").rstrip("/")
LOGIN = os.environ.get("E2E_ADMIN_LOGIN", "admin")
PW = os.environ.get("E2E_ADMIN_PASSWORD", "")


def _login(page: Page):
    """Логін у backend Odoo. Стандартна форма /web/login."""
    page.goto(f"{BASE}/web/login")
    page.fill("input[name='login']", LOGIN)
    page.fill("input[name='password']", PW)
    page.click("button[type='submit']")
    # після успіху Odoo редіректить на /web або /odoo. НЕ networkidle: бекенд Odoo
    # тримає постійний /websocket (bus), тож networkidle не настає ніколи
    # (run 28609515164: load fired, networkidle timeout). Детермінований критерій —
    # пішли зі сторінки логіну; невдалий логін перезавантажує /web/login → timeout.
    page.wait_for_url(lambda url: "/login" not in url, timeout=30000)


def test_login_smoke(page: Page):
    """#1 критичний шлях: логін взагалі працює (бекенд живий, сесія створюється).

    Це smoke — якщо червоний, реліз блокується одразу (Gate 4), бо ніхто не зайде.
    """
    _login(page)
    # на сторінці логіну є поле password; після успіху його НЕ має бути
    assert (
        page.locator("input[name='password']").count() == 0
    ), "лишились на логіні — авторизація не пройшла"


@pytest.mark.skip(
    reason="калібрувати навігацію меню Kadra проти staging (action-id), тоді зняти skip"
)
def test_staff_role_dropdown_is_canon(page: Page):
    """Анти-казус 25.06: дропдаун ролей Kadra показує КАНОН-ключі, не старі.

    Саме цей тест упіймав би stale .pyc (дропдаун лишився на 'activity_lead').
    """
    _login(page)
    # TODO калібрування: точний шлях до форми camp.staff (меню/action-id зі staging)
    page.get_by_role("button", name="Dodaj").first.click()
    dd = page.locator("[name='role']")
    expect(dd).to_contain_text("Kierownik wypoczynku")  # канон
    expect(dd).not_to_contain_text("activity_lead")  # старий ключ зник


@pytest.mark.skip(reason="калібрувати флоу реєстрації дитини в порталі батьків проти staging")
def test_parent_registers_child(page: Page):
    """Критичний шлях грошей: батько реєструє дитину в табір (портал /my/*)."""
    _login(page)
    # TODO калібрування проти реального порталу /my/
    raise NotImplementedError("заповнити після калібрування селекторів")
