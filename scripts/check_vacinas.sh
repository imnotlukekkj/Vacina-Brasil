#!/usr/bin/env bash
set -euo pipefail

# scripts/check_vacinas.sh
#  - Recupera vacinas normalizadas via /api/mappings
#  - Para cada vacina consulta /api/overview?fabricante=... para obter total
#  - Se SUPABASE env estiver definido, busca amostra de TX_INSUMO via REST e
#    faz a normalização usando o endpoint /normalize
#  - Comportamento seguro: se SUPABASE não estiver configurado, apenas informa
#    e sai com sucesso (0)

API_BASE=${API_BASE:-"http://127.0.0.1:8000"}

echo "Using API base: $API_BASE"

echo "\n== Fetching normalized vaccine list (/api/mappings) =="
map_json=$(curl -sS "$API_BASE/api/mappings") || { echo "Failed to fetch /api/mappings"; exit 1; }
vacinas=$(echo "$map_json" | jq -r '.vacinas[]' 2>/dev/null || true)
if [ -z "${vacinas// /}" ]; then
  echo "No mappings found or /api/mappings returned empty.";
else
  echo "Normalized vaccines:";
  echo "$vacinas" | nl -w2 -s": "
fi

echo "\n== Totals per normalized vaccine (via /api/overview?fabricante=...) =="
if [ -z "${vacinas// /}" ]; then
  echo "No vaccines to iterate.";
else
  while IFS= read -r v; do
    # skip empty
    if [ -z "${v}" ]; then
      continue
    fi
  v_enc=$(echo "$v" | python3 -c 'import urllib.parse,sys; print(urllib.parse.quote(sys.stdin.read().strip()))')
    resp=$(curl -sS "$API_BASE/api/overview?fabricante=$v_enc") || { echo "  $v -> failed to call overview"; continue; }
    total=$(echo "$resp" | jq -r '.total_doses // 0')
    echo "  $v -> total: $total"
  done <<< "$vacinas"
fi

echo "\n== Supabase sample (optional) =="
if [ -z "${SUPABASE_URL-}" ] || [ -z "${SUPABASE_SERVICE_ROLE_KEY-}" ]; then
  echo "SUPABASE_URL or SUPABASE_SERVICE_ROLE_KEY not set; skipping Supabase REST sample."
  echo "If you want the sample, export SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY and re-run this script."
  exit 0
fi

echo "Fetching up to 500 rows from Supabase REST (distribuicao)"
SUPA_URL="$SUPABASE_URL/rest/v1/distribuicao?select=TX_INSUMO,ANO,MES,TX_SIGLA,QTDE&limit=500"
rows=$(curl -sS "$SUPA_URL" -H "apikey: $SUPABASE_SERVICE_ROLE_KEY" -H "Authorization: Bearer $SUPABASE_SERVICE_ROLE_KEY" -H "Accept: application/json" ) || { echo "Failed to fetch from Supabase REST"; exit 1; }
count_rows=$(echo "$rows" | jq 'length' 2>/dev/null || echo "0")
echo "Fetched $count_rows rows"

echo "\nSample of raw TX_INSUMO -> normalized (up to 50 unique):"
echo "$rows" | jq -r '.[].TX_INSUMO' | grep -v null | awk 'NF' | sed 's/\r//g' | sort | uniq | head -n 50 | while IFS= read -r raw; do
  raw_enc=$(echo "$raw" | python3 -c 'import urllib.parse,sys; print(urllib.parse.quote(sys.stdin.read().strip()))')
  norm=$(curl -sS "$API_BASE/normalize?tx_insumo=$raw_enc" | jq -r '.tx_insumo_norm // "<null>"') || norm="<error>"
  echo " - $raw -> $norm"
done

exit 0
