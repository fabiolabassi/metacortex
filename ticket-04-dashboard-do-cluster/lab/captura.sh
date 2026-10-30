#!/usr/bin/env bash
# Sobe o retrato com um kubeconfig, tira capturas de tela com o Chrome headless
# e derruba o processo. Guarda tambem o JSON da API e o log do console.
#
#   bash lab/captura.sh <rotulo> <kubeconfig|-> <ns> [<ns> ...]
#   (use "-" para o kubeconfig padrao do usuario)
set -uo pipefail
AQUI=$(cd "$(dirname "$0")" && pwd)
T04=$(dirname "$AQUI")
ROTULO=$1 KC=$2; shift 2
OUT=$T04/evidencias/$ROTULO
PORTA=${PORTA:-8766}
mkdir -p "$OUT"
cd "$T04"

args=(--porta "$PORTA")
[ "$KC" != "-" ] && args+=(--kubeconfig "$KC")
PYTHONPATH=src .venv/bin/python -m retrato "${args[@]}" > "$OUT/console.log" 2>&1 &
PID=$!
trap 'kill $PID 2>/dev/null' EXIT
until curl -s -m 1 "localhost:$PORTA/api/contexto" >/dev/null; do sleep 0.3; done

curl -s "localhost:$PORTA/api/contexto" > "$OUT/api-contexto.json"
curl -s "localhost:$PORTA/api/namespaces" > "$OUT/api-namespaces.json"
for ns in "$@"; do
  curl -s "localhost:$PORTA/api/retrato/$ns" | python3 -m json.tool --no-ensure-ascii > "$OUT/api-retrato-$ns.json"
  timeout 90 google-chrome --headless=new --disable-gpu --no-sandbox --hide-scrollbars \
    --virtual-time-budget=8000 --window-size=1500,1300 \
    --screenshot="$OUT/tela-$ns.png" "http://127.0.0.1:$PORTA/?ns=$ns" >/dev/null 2>&1
  echo "$ROTULO/$ns: $(test -s "$OUT/tela-$ns.png" && echo captura ok || echo SEM captura)"
done
