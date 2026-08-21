#!/usr/bin/env bash
# Run fayna_camp_portal Odoo unit tests and FAIL the job on any failed/errored test.
#
# Why a wrapper instead of relying on Odoo's exit code:
#   Odoo 17 `--test-enable` does NOT reliably return a non-zero exit code when a
#   test ASSERTION fails (module load errors do exit non-zero, test failures may
#   not). So we ALSO scan the captured log for Odoo's failure markers and force
#   `exit 1`. Both signals are checked — whichever trips, the job goes red.
#
# Env (with sensible CI defaults):
#   DB         test DB name              (default: test_camp)
#   MODULE     module to install+test    (default: fayna_camp_portal)
#   ADDONS     comma addons-path         (default: built from /addons layout)
#   ODOO_BIN   odoo entrypoint           (default: odoo)
#   LOG        log file path             (default: /tmp/odoo-test.log)
#   COVERAGE   "1" → wrap the run in `coverage run` and enforce fail_under
#              (default: unset → no coverage gate)
#   COVERAGE_MIN  minimum coverage % for the gate (default: 70)
set -uo pipefail

DB="${DB:-test_camp}"
MODULE="${MODULE:-fayna_camp_portal}"
ODOO_BIN="${ODOO_BIN:-odoo}"
LOG="${LOG:-/tmp/odoo-test.log}"
ADDONS="${ADDONS:-/addons/fayna_camp_portal,/addons/deps}"
COVERAGE_MIN="${COVERAGE_MIN:-70}"

echo "::group::Odoo test run config"
echo "  module     = ${MODULE}"
echo "  db         = ${DB}"
echo "  addons     = ${ADDONS}"
echo "  test-tags  = /${MODULE}"
echo "  log        = ${LOG}"
echo "::endgroup::"

# --test-enable + --test-tags /<module> runs only this module's tagged tests
# (the leading slash scopes tags to the module). post_install tests included,
# at_install excluded by the tests' own @tagged decorators.
#
# When COVERAGE=1 we wrap the whole Odoo run in `coverage run` so the module's
# Python is measured, then enforce fail_under below. `coverage` must be
# installed in the container (CI installs it; local runs opt in explicitly).
COVERAGE_CMD=()
if [ "${COVERAGE:-0}" = "1" ]; then
  echo "Coverage gate ENABLED (min ${COVERAGE_MIN}%)."
  COVERAGE_CMD=(coverage run --source="/mnt/addons/${MODULE}" --branch -a)
fi
set -x
"${COVERAGE_CMD[@]}" "${ODOO_BIN}" \
  -d "${DB}" \
  --db_host="${PGHOST:-db}" \
  --db_port="${PGPORT:-5432}" \
  --db_user="${PGUSER:-odoo}" \
  --db_password="${PGPASSWORD:-odoo}" \
  --addons-path="${ADDONS}" \
  -i "${MODULE}" \
  --test-enable \
  --test-tags "/${MODULE}" \
  --stop-after-init \
  --no-http \
  --log-level=test \
  2>&1 | tee "${LOG}"
ODOO_RC=${PIPESTATUS[0]}
set +x

echo "::group::Test failure scan"
# Odoo logs one of these on a failed/errored test. We must match REAL failures
# only — NOT the benign success summary "0 failed, 0 error(s)".
#   ... ERROR <db> odoo.addons.<mod>.tests.<file>: FAIL: <Test> ...   (assertion)
#   ... ERROR <db> odoo.tests.runner: ERROR: <Test> ...              (errored)
#   ... <Test>: <n> failed, <m> error(s) of <N> tests               (suite summary)
# Patterns:
#   - per-test marker:  ": FAIL:" / ": ERROR:" on an odoo.tests/odoo.addons.*.tests line
#   - summary counts:   only the Odoo suite summary line, and only when the
#                       failed/error count is NON-ZERO ([1-9]...).
#                       Anchored to the full summary format
#                       "<n> failed, <m> error(s) of <N> tests" so benign
#                       WARNING lines like "attempt 1/2 failed" (rate-limit
#                       backoff) do NOT false-positive.
FAIL_LINES=$(grep -E \
  "(odoo\.tests|odoo\.addons\.[a-z0-9_.]+\.tests)[^ ]*: (FAIL|ERROR):|[1-9][0-9]* failed, [0-9]* error\(s\) of [0-9]+ tests" \
  "${LOG}" || true)

if [ -n "${FAIL_LINES}" ]; then
  echo "Detected failed/errored tests in log:"
  echo "${FAIL_LINES}"
fi
echo "::endgroup::"

echo "Odoo exit code: ${ODOO_RC}"

if [ "${ODOO_RC}" -ne 0 ]; then
  echo "::error::Odoo returned non-zero exit code ${ODOO_RC} — failing job."
  exit 1
fi
if [ -n "${FAIL_LINES}" ]; then
  echo "::error::Failed/errored Odoo tests detected in log — failing job."
  exit 1
fi

# Guard: if nothing looks like a test ran, treat as failure (broken collection).
if ! grep -qE "odoo\.tests" "${LOG}"; then
  echo "::error::No 'odoo.tests' lines found in log — tests did not run. Failing job."
  exit 1
fi

# Coverage gate (opt-in via COVERAGE=1). Generates the report and fails the job
# when the module's line coverage drops below COVERAGE_MIN. Uses the same
# fail_under semantics as pyproject.toml [tool.coverage.report].
if [ "${COVERAGE:-0}" = "1" ]; then
  echo "::group::Coverage report"
  coverage report --fail-under="${COVERAGE_MIN}" --show-missing \
    --omit="*/tests/*,*/migrations/*,__manifest__.py" || {
    echo "::error::Coverage below ${COVERAGE_MIN}% — failing job."
    exit 1
  }
  echo "::endgroup::"
fi

echo "All ${MODULE} tests passed."
exit 0
