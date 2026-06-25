#!/usr/bin/env bash
# =============================================================================
# Безпечний staging-деплой Odoo-модуля — «кнопка» Platform Engineering.
# Вшиває ВСІ анти-казус механізми, доведені інцидентами CampScout:
#   • clear .pyc            — казус 25.06 (stale байт-код → старий Selection)
#   • гейт міграції за exit — не свопимо живий сервіс, якщо -u впав
#   • wait-for-green loop   — казус швидких пушів (не йдемо далі без 200 OK)
#   • chmod -R o+rX         — landmine перми 660 (git pull → odoo не читає → аутедж)
#   • rollback              — health FAIL → відкат коду + гучний алерт
#
# Деплой іде через ssh-alias `staging-campscout` (порт 2222, user deploy, ключ —
# усе в ~/.ssh/config). Прод цим скриптом НЕ чіпаємо (окремий гейт + «ок»).
#
# Usage:    tools/deploy-staging.sh [branch] [module]
# Rollback виконується автоматично; ручний: git checkout <prev> на сервері + restart.
# =============================================================================
set -euo pipefail

BRANCH="${1:-$(git branch --show-current)}"
MODULE="${2:-fayna_camp_portal}"
SSH_HOST="staging-campscout"        # ~/.ssh/config: 178.104.186.74:2222 user=deploy
CONTAINER="campscout_web"
DB="campscout"
ADDON="/opt/campscout/custom-addons/${MODULE}"
CONF="/etc/odoo/odoo.conf"
URL="https://staging.campscout.eu/web/webclient/version_info"   # 200 = Odoo живий

echo "==> [1/2] push гілки ${BRANCH}"
git push -u origin "${BRANCH}"

echo "==> [2/2] safe-deploy на ${SSH_HOST}:${CONTAINER}"
ssh -o ConnectTimeout=180 "${SSH_HOST}" "set -euo pipefail
  cd '${ADDON}'

  echo '  [a] record rollback-point + pull ${BRANCH}'
  PREV=\$(git rev-parse HEAD)                       # точка відкату ПЕРЕД змінами
  echo \"      prev=\$PREV\"
  git fetch origin >/dev/null 2>&1
  git checkout '${BRANCH}' 2>&1 | tail -1
  git pull 2>&1 | tail -1

  echo '  [b] perms (landmine 660 → o+rX, інакше odoo не читає → аутедж)'
  sudo chmod -R o+rX .

  echo '  [c] CLEAR .pyc (казус 25.06 stale байт-код)'
  find . -name '*.pyc' -delete 2>/dev/null || true
  find . -name __pycache__ -type d -exec rm -rf {} + 2>/dev/null || true

  echo '  [d] МІГРАЦІЯ (one-off --stop-after-init) — ГЕЙТ за exit-кодом'
  if ! docker exec ${CONTAINER} odoo -c ${CONF} -d ${DB} -u ${MODULE} --stop-after-init --no-http \
       > /tmp/deploy_migrate.log 2>&1; then
    echo '  ❌ МІГРАЦІЯ ВПАЛА — НЕ свопимо живий сервіс. Останні рядки:'
    grep -iE 'ERROR|CRITICAL|Traceback|ParseError' /tmp/deploy_migrate.log | tail -8
    echo \"  ↩ ROLLBACK коду на \$PREV\"; git checkout \$PREV >/dev/null 2>&1; sudo chmod -R o+rX .
    exit 1
  fi
  echo '      міграція exit=0 ✅'

  echo '  [e] restart (перечитати реєстр)'
  docker restart ${CONTAINER} >/dev/null 2>&1

  echo '  [f] WAIT-FOR-GREEN (200 OK, кожні 5с, ліміт 2 хв)'
  ok=0
  for i in \$(seq 1 24); do
    code=\$(curl -s -o /dev/null -w '%{http_code}' -k '${URL}' || echo 000)
    if [ \"\$code\" = '200' ]; then echo \"      green за \$((i*5))с (200) ✅\"; ok=1; break; fi
    echo \"      ...\$code (спроба \$i/24)\"; sleep 5
  done
  if [ \"\$ok\" != '1' ]; then
    echo '  ❌ НЕ green за 2 хв → ROLLBACK'
    git checkout \$PREV >/dev/null 2>&1; sudo chmod -R o+rX .
    docker restart ${CONTAINER} >/dev/null 2>&1
    echo \"  ↩ відкочено на \$PREV. ⚠️ ПЕРЕВІР БД вручну (міграція могла застосуватись — Expand-Contract!)\"
    exit 1
  fi
  echo '  ✅ DEPLOY OK — staging green, перми ок, міграція застосована.'
"
echo "==> DONE (${BRANCH} → ${MODULE} на staging). Перевір фічу скріном/shell за потреби."
