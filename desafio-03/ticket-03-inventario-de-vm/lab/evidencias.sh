#!/usr/bin/env bash
# Gera as evidencias de execucao contra as VMs do laboratorio. Cada caso grava
# o comando (com a chave mascarada), stdout, stderr e codigo de saida.
#
#   bash lab/evidencias.sh conforme      # VM 127.0.0.1:2221 (precisa estar de pe)
#   bash lab/evidencias.sh desvios       # VM 127.0.0.1:2222
#   bash lab/evidencias.sh inalcancavel  # nao precisa de VM
set -uo pipefail
RAIZ=$(cd "$(dirname "$0")/.." && pwd)
CHAVES=${CACHE:-$HOME/.cache/metacortex-vms}/keys
EV=$RAIZ/evidencias
cd "$RAIZ"

caso() {  # caso <dir> <nome> <args do roster-audit...>
  local rotulo=$1/$2 dir=$EV/$1 nome=$2; shift 2
  mkdir -p "$dir"
  local mostrado=${*//$CHAVES\//<chaves>/}
  PYTHONPATH=src python3 -m roster_audit "$@" > "$dir/$nome.stdout" 2> "$dir/$nome.stderr"
  local rc=$?
  { echo "\$ roster-audit $mostrado"; echo "codigo de saida: $rc"; } > "$dir/$nome.cmd"
  printf '%-48s exit=%s\n' "$rotulo" "$rc"
}

mesmo_resultado() {  # compara dois JSON ignorando coletado_em
  python3 - "$1" "$2" <<'PY'
import json, sys
a, b = (json.load(open(f)) for f in sys.argv[1:3])
ta, tb = a["host"].pop("coletado_em"), b["host"].pop("coletado_em")
print("coletado_em: {} -> {}".format(ta, tb))
print("IDENTICO (exceto coletado_em)" if a == b else "DIFERENTE")
sys.exit(0 if a == b else 1)
PY
}

case "${1:-}" in
  conforme|desvios)
    n=$([ "$1" = conforme ] && echo 01-host-conforme || echo 02-host-com-desvios)
    p=$([ "$1" = conforme ] && echo 2221 || echo 2222)
    base=(--endereco 127.0.0.1 --porta "$p" --usuario auditor --chave "$CHAVES/auditor")
    caso "$n" sem-sudo-markdown "${base[@]}"
    caso "$n" sem-sudo-json "${base[@]}" --formato json
    caso "$n" com-sudo-markdown "${base[@]}" --sudo
    caso "$n" com-sudo-json-execucao-1 "${base[@]}" --sudo --formato json
    sleep 5  # para coletado_em mudar entre as duas execucoes
    caso "$n" com-sudo-json-execucao-2 "${base[@]}" --sudo --formato json
    mesmo_resultado "$EV/$n/com-sudo-json-execucao-1.stdout" "$EV/$n/com-sudo-json-execucao-2.stdout" \
      | tee "$EV/$n/determinismo.txt"
    ;;
  inalcancavel)
    n=03-host-inalcancavel
    tmp=$(mktemp -d); trap 'rm -rf "$tmp"' EXIT
    cp "$CHAVES/auditor" "$tmp/chave-aberta"; chmod 644 "$tmp/chave-aberta"
    caso "$n" endereco-sem-resposta --endereco 10.255.255.1 --usuario auditor --chave "$CHAVES/auditor" --timeout 3
    caso "$n" nome-inexistente --endereco vm-que-nao-existe.invalid --usuario auditor --chave "$CHAVES/auditor"
    caso "$n" ssh-fora-do-ar --endereco 127.0.0.1 --porta 2299 --usuario auditor --chave "$CHAVES/auditor"
    caso "$n" chave-recusada --endereco 127.0.0.1 --porta 2221 --usuario auditor --chave "$CHAVES/dozer"
    caso "$n" chave-com-permissao-aberta --endereco 127.0.0.1 --porta 2221 --usuario auditor --chave "$tmp/chave-aberta"
    caso "$n" chave-inexistente --endereco 127.0.0.1 --porta 2221 --usuario auditor --chave /nao/existe
    # Nenhuma saida pode conter o caminho ou o conteudo da chave (RNF-03).
    if grep -rl -e "$CHAVES" -e "$tmp" -e "$(sed -n 2p "$CHAVES/auditor")" "$EV/$n"/*.stdout "$EV/$n"/*.stderr; then
      echo "FALHA: chave exposta" | tee "$EV/$n/chave-nao-exposta.txt"
    else
      echo "OK: nenhuma saida contem caminho ou conteudo da chave" | tee "$EV/$n/chave-nao-exposta.txt"
    fi
    ;;
  *) sed -n '2,7p' "$0"; exit 2 ;;
esac
