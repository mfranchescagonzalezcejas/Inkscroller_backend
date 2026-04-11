#!/usr/bin/env bash
# =============================================================================
# smoke_prod.sh — P0-B8 Smoke Test Script (Production)
# =============================================================================
# Verifica los endpoints públicos y seguros del backend en producción.
# No requiere autenticación. No ejecuta operaciones de escritura.
#
# Uso:
#   ./scripts/release/smoke_prod.sh
#   PROD_URL=https://mi-url-custom.run.app ./scripts/release/smoke_prod.sh
#
# Salida:
#   - PASS / FAIL por endpoint
#   - Tiempo de respuesta total
#   - Código de salida 0 (PASS total) o 1 (algún FAIL)
# =============================================================================

set -euo pipefail

PROD_URL="${PROD_URL:-https://inkscroller-backend-806863502436.us-central1.run.app}"
TIMEOUT="${TIMEOUT:-15}"
PASS=true

print_header() {
  printf "\n\033[1;34m== %s ==\033[0m\n" "$1"
}

check_endpoint() {
  local label="$1"
  local url="$2"
  local expected_status="${3:-200}"
  local expected_body="${4:-}"

  printf "  %-45s " "$label"

  local response
  local http_code
  local time_total

  response=$(curl -s --max-time "$TIMEOUT" -w "\n__HTTP_CODE=%{http_code}\n__TIME=%{time_total}" "$url" 2>&1) || {
    printf "\033[1;31m[FAIL]\033[0m curl error\n"
    PASS=false
    return
  }

  http_code=$(printf "%s" "$response" | grep "__HTTP_CODE=" | cut -d= -f2)
  time_total=$(printf "%s" "$response" | grep "__TIME=" | cut -d= -f2)
  local body
  body=$(printf "%s" "$response" | grep -v "^__HTTP_CODE=" | grep -v "^__TIME=")

  if [[ "$http_code" != "$expected_status" ]]; then
    printf "\033[1;31m[FAIL]\033[0m  status=%s (expected %s)  time=%ss\n" "$http_code" "$expected_status" "$time_total"
    PASS=false
    return
  fi

  if [[ -n "$expected_body" ]] && [[ "$body" != *"$expected_body"* ]]; then
    printf "\033[1;31m[FAIL]\033[0m  body does not contain '%s'  time=%ss\n" "$expected_body" "$time_total"
    PASS=false
    return
  fi

  printf "\033[1;32m[PASS]\033[0m  status=%s  time=%ss\n" "$http_code" "$time_total"
}

# ─────────────────────────────────────────────────────────────
print_header "P0-B8 Smoke Test — Production"
printf "target: %s\n" "$PROD_URL"
printf "date:   %s\n" "$(date -u +"%Y-%m-%dT%H:%M:%SZ")"
printf "runner: %s@%s\n" "$(whoami)" "$(hostname)"

# ─────────────────────────────────────────────────────────────
print_header "1. Health Check"
check_endpoint "GET /ping" "${PROD_URL}/ping" "200" '"ok":true'

# ─────────────────────────────────────────────────────────────
print_header "2. Manga Catalog (public, read-only)"
check_endpoint "GET /manga?limit=1&offset=0" "${PROD_URL}/manga?limit=1&offset=0" "200" '"data"'
check_endpoint "GET /manga/search?q=berserk" "${PROD_URL}/manga/search?q=berserk" "200"

# ─────────────────────────────────────────────────────────────
print_header "3. Edge Cases (error handling)"
check_endpoint "GET /manga/%20invalid-id%20 (404 expected)" "${PROD_URL}/manga/%20invalid-id%20" "404"

# ─────────────────────────────────────────────────────────────
print_header "Summary"
if [[ "$PASS" == "true" ]]; then
  printf "\033[1;32m✅ ALL CHECKS PASSED — P0-B8 SMOKE: PASS\033[0m\n"
  exit 0
else
  printf "\033[1;31m❌ SOME CHECKS FAILED — P0-B8 SMOKE: FAIL\033[0m\n"
  exit 1
fi
