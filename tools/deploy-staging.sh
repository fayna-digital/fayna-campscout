#!/usr/bin/env bash
# =============================================================================
# Безпечний staging-деплой Odoo-модуля — «кнопка» Platform Engineering.
# Інкапсулює правильну послідовність, щоб НЕ повторювати казус 2026-06-25
# (stale .pyc → running odoo тримав старий Selection попри новий код+DB).
#
# Usage:    tools/deploy-staging.sh [branch] [module]
# Rollback: tools/deploy-staging.sh <попередня-гілка> [module]   (+ restart)
#
# Чому саме так (уроки 25.06):
#   1. clear .pyc ПЕРЕД -u — стара байт-компіляція = «код не оновився» (корінь казусу).
#   2. -u --no-http — без нього docker-exec другий odoo б'ється з основним → Exit 255
#      ('Address already in use').
#   3. чистий restart ПІСЛЯ -u — щоб реєстр (Selection/fields) перечитався з нуля.
#   4. verify наприкінці — Iron Law: не «задеплоєно», а ДОВЕДЕНО (login 200 + перевірка).
#   5. ЖОДНИХ ручних SQL UPDATE — зміни даних лише через migrations/<version>/.
# =============================================================================
set -euo pipefail

BRANCH="${1:-$(git branch --show-current)}"
MODULE="${2:-fayna_camp_portal}"
SSH_HOST="staging-campscout"
CONTAINER="campscout_web"
DB="campscout"
ADDON="/opt/campscout/custom-addons/${MODULE}"
CONF="/etc/odoo/odoo.conf"

echo "==> [1/6] push гілки ${BRANCH} (з upstream — нова гілка інакше не пушиться)"
git push -u origin "${BRANCH}"

echo "==> [2-6] safe-deploy на ${SSH_HOST}:${CONTAINER}"
ssh -o ConnectTimeout=180 "${SSH_HOST}" "set -e
  cd '${ADDON}'
  echo '  [2/6] checkout + pull ${BRANCH}'
  git fetch origin >/dev/null 2>&1
  git checkout '${BRANCH}' 2>&1 | tail -1
  git pull 2>&1 | tail -1
  sudo chmod -R o+rX .

  echo '  [3/6] CLEAR .pyc (корінь казусу — stale bytecode)'
  find . -name '*.pyc' -delete 2>/dev/null || true
  find . -name __pycache__ -type d -exec rm -rf {} + 2>/dev/null || true

  echo '  [4/6] -u (запускає migrations/<version>/) — --no-http проти Exit 255'
  docker exec ${CONTAINER} odoo -c ${CONF} -d ${DB} -u ${MODULE} --stop-after-init --no-http 2>&1 \
    | grep -iE 'ERROR|CRITICAL|Traceback|ParseError|ValueError|migration|loaded' | grep -vi werkzeug | tail -8 || true
  echo \"  u_exit=\${PIPESTATUS[0]}\"

  echo '  [5/6] чистий restart (перечитати реєстр Selection/fields)'
  docker restart ${CONTAINER} >/dev/null 2>&1
  sleep 11

  echo '  [6/6] VERIFY (Iron Law)'
  curl -s -o /dev/null -w '  staging login %{http_code}\n' -k https://staging.campscout.eu/web/login
"
echo "==> DONE. Перевір фічу скріном/shell. Rollback: tools/deploy-staging.sh <попередня-гілка> ${MODULE}"
