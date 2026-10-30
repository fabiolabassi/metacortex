#!/usr/bin/env bash
# Roda localmente a mesma validacao da CI. Uso: bash scripts/validate.sh
set -uo pipefail
cd "$(dirname "$0")/.."
falhou=0
etapa() { printf '\n== %s ==\n' "$1"; }

etapa "1/4 testes do verificador (anti-padroes reprovam no que declaram)"
python3 -m unittest discover -s tests || falhou=1

etapa "2/4 padrao Metacortex sobre manifests/"
python3 scripts/check_padrao.py manifests || falhou=1

etapa "3/4 varredura de configuracao (Trivy, todas as severidades)"
# LOW incluso de proposito: e onde o Trivy classifica algumas regras do padrao.
if command -v trivy >/dev/null; then
  trivy config --quiet --exit-code 1 \
    --severity LOW,MEDIUM,HIGH,CRITICAL \
    --config .trivy/trivy.yaml \
    --ignorefile .trivyignore.yaml \
    manifests || falhou=1
else
  echo "trivy nao instalado — etapa pulada (a CI roda)"
fi

etapa "4/4 admissao no cluster (opcional: so roda com kubectl e contexto ativo)"
if command -v kubectl >/dev/null && kubectl cluster-info >/dev/null 2>&1; then
  for ns in manifests/*/00-namespace.yaml; do kubectl apply -f "$ns" >/dev/null || falhou=1; done
  kubectl apply --dry-run=server -R -f manifests/ || falhou=1
else
  echo "sem cluster acessivel — etapa pulada"
fi

echo
if [ "$falhou" -eq 0 ]; then echo "VALIDACAO OK"; else echo "VALIDACAO FALHOU"; fi
exit "$falhou"
