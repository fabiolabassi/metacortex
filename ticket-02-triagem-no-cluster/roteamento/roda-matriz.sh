#!/usr/bin/env bash
# Roda cada frase numa sessao limpa (claude -p, sem historico) com as duas
# skills instaladas no projeto e registra qual skill disparou. Escrita e shell
# ficam bloqueados: a matriz mede roteamento, nao deixa a sessao agir.
# Uso: bash roda-matriz.sh <rotulo-da-rodada> [arquivo-de-frases]
set -uo pipefail
RAIZ=$(git -C "$(dirname "$0")" rev-parse --show-toplevel)
T=$RAIZ/desafio-03/ticket-02-triagem-no-cluster
RODADA=${1:?rotulo da rodada}
FRASES=${2:-$T/roteamento/frases.txt}
OUT=$T/roteamento/$RODADA
mkdir -p "$OUT"
cd "$RAIZ"
n=0
while IFS= read -r frase; do
  n=$((n+1)); i=$(printf '%02d' $n)
  ( timeout 600 claude -p "$frase" --model claude-opus-5-5 --output-format stream-json --verbose \
      --no-session-persistence --strict-mcp-config --mcp-config "$T/acesso/mcp.json" \
      --allowedTools "mcp__kubernetes Skill Read Grep Glob" \
      --disallowedTools "Bash Write Edit WebFetch WebSearch Agent" \
      > "$OUT/$i.jsonl" 2> "$OUT/$i.err" < /dev/null ) &
  if (( n % 5 == 0 )); then wait; fi
done < "$FRASES"
wait
n=0
printf '| # | Frase | Skill disparada | Turnos | Custo US$ |\n|---|---|---|---|---|\n' > "$OUT/resultado.md"
while IFS= read -r frase; do
  n=$((n+1)); i=$(printf '%02d' $n)
  python3 - "$OUT/$i.jsonl" "$frase" "$i" >> "$OUT/resultado.md" <<'PY'
import json, sys
skills, res = [], {}
for l in open(sys.argv[1]):
    try: d = json.loads(l)
    except Exception: continue
    if d.get("type") == "assistant":
        for c in d["message"]["content"]:
            if c.get("type") == "tool_use" and c["name"] == "Skill":
                skills.append(c["input"].get("skill"))
    if d.get("type") == "result": res = d
print("| {} | {} | {} | {} | {:.3f} |".format(sys.argv[3], sys.argv[2], ", ".join(skills) or "nenhuma",
      res.get("num_turns"), res.get("total_cost_usd") or 0))
PY
done < "$FRASES"
cat "$OUT/resultado.md"
