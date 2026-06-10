#!/usr/bin/env bash
# staging_sync.sh — рефреш staging із prod (БД + filestore) + НЕЙТРАЛІЗАЦІЯ + install fayna_camp_portal.
# Запуск: з Mac (оркестрація через ssh; хости з ~/.ssh/config: campscout=PROD read-only, staging-campscout).
# Кожен запуск = репетиція міграції prod (на prod модуль НЕ встановлений).
# Лог: /tmp/staging_sync_<date>.log ; точки відкату: бекап staging-БД перед заміною.
set -euo pipefail

TS=$(date +%Y%m%d_%H%M%S)
LOG="/tmp/staging_sync_${TS}.log"
exec > >(tee -a "$LOG") 2>&1

PROD=campscout
STG=staging-campscout
DB=campscout                  # робоча БД на prod
STG_DB=campscout              # цільова назва на staging (заміняється)
DUMP=/tmp/campscout_prod_${TS}.dump

echo "=== [1/7] PROD: pg_dump (read-only) ==="
ssh $PROD "docker exec campscout_db pg_dump -U odoo -Fc $DB" > "$DUMP"
ls -lh "$DUMP"

echo "=== [2/7] STAGING: бекап поточної БД (rollback point) ==="
ssh $STG "mkdir -p /opt/backups/pre-sprint && docker exec campscout_db pg_dump -U odoo -Fc $STG_DB > /opt/backups/pre-sprint/staging_${STG_DB}_${TS}.dump 2>/dev/null || echo 'staging DB відсутня/порожня — пропускаю бекап'"

echo "=== [3/7] STAGING: заливка дампа ==="
scp -q "$DUMP" $STG:/tmp/prod.dump
ssh $STG "
  docker exec campscout_db psql -U odoo -d postgres -c \"SELECT pg_terminate_backend(pid) FROM pg_stat_activity WHERE datname='$STG_DB' AND pid<>pg_backend_pid();\" || true
  docker exec campscout_db dropdb -U odoo --if-exists $STG_DB
  docker exec campscout_db createdb -U odoo $STG_DB
  docker cp /tmp/prod.dump campscout_db:/tmp/prod.dump
  docker exec campscout_db pg_restore -U odoo -d $STG_DB --no-owner /tmp/prod.dump
  docker exec campscout_db rm /tmp/prod.dump && rm /tmp/prod.dump
"

echo "=== [4/7] STAGING: НЕЙТРАЛІЗАЦІЯ (пошта/SMS/crons OFF — ОБОВ'ЯЗКОВО до старту Odoo) ==="
# docker exec -i обов'язковий — без нього psql не читає heredoc (INC спринту 10.06)
ssh $STG "docker exec -i campscout_db psql -U odoo -d $STG_DB" << 'SQL'
UPDATE ir_mail_server SET active = false;
UPDATE ir_cron SET active = false;
UPDATE ir_config_parameter SET value='http://staging.campscout.eu' WHERE key='web.base.url';
INSERT INTO ir_config_parameter (key, value)
  SELECT 'web.base.url.freeze','True'
  WHERE NOT EXISTS (SELECT 1 FROM ir_config_parameter WHERE key='web.base.url.freeze');
-- SMS: занулити токен провайдера, щоб жодне SMS не пішло
UPDATE ir_config_parameter SET value='DISABLED_ON_STAGING' WHERE key ILIKE '%turbosms%token%' OR key ILIKE '%sms%api%key%';
-- застрахуватись від черги: скасувати вихідні листи з prod-копії
UPDATE mail_mail SET state='cancel' WHERE state='outgoing';
SQL
# верифікація нейтралізації — фейл скрипта якщо не 0
ssh $STG "docker exec campscout_db psql -U odoo -d $STG_DB -tc \"SELECT count(*) FROM ir_mail_server WHERE active;\"" | grep -q '^ *0$' || { echo "🔴 НЕЙТРАЛІЗАЦІЯ НЕ ПРОЙШЛА — СТОП"; exit 1; }

echo "=== [5/7] STAGING: filestore rsync (інкрементний; перший раз ~6.1G) ==="
# через Mac-relay (між серверами прямого ключа нема); -z компресія
rsync -az --delete -e ssh $PROD:/opt/campscout/odoo-data/filestore/$DB/ /tmp/fs_relay_$DB/
# sudo rsync на приймачі — deploy не має прав писати у filestore (власник uid 101; INC спринту 10.06)
rsync -az --delete --rsync-path="sudo rsync" -e ssh /tmp/fs_relay_$DB/ $STG:/opt/campscout/odoo-data/filestore/$STG_DB/
ssh $STG "sudo chown -R 101:101 /opt/campscout/odoo-data/filestore/$STG_DB"

echo "=== [6/7] STAGING: install fayna_camp_portal на prod-копію (репетиція міграції!) ==="
ssh $STG "
  cd /opt/campscout/custom-addons/fayna_camp_portal && git fetch origin && git checkout loop/season-sprint && git pull origin loop/season-sprint && sudo chmod -R o+rX . || true
  # --http-port=8072: інакше Errno 98 — головний odoo тримає 8069 (INC 10.06)
  docker exec campscout_web odoo -c /etc/odoo/odoo.conf -d $STG_DB -i fayna_camp_portal --stop-after-init --http-port=8072 2>&1 | tail -30
  docker restart campscout_web
"

echo "=== [7/7] Перевірка ==="
ssh $STG "docker exec campscout_db psql -U odoo -d $STG_DB -tc \"SELECT name,state FROM ir_module_module WHERE name IN ('campscout_management','fayna_camp_portal');\""
ssh $STG "docker exec campscout_db psql -U odoo -d $STG_DB -tc \"SELECT count(*) FROM ir_mail_server WHERE active;\" | grep -q ' 0' && echo 'NEUTRALIZED ✅' || echo '⚠️ MAIL ЩЕ АКТИВНИЙ — ПЕРЕВІР!'"
echo "DONE $TS — лог: $LOG"
