#!/usr/bin/env bash
# Gera um kubeconfig so-leitura para o mcp-server-kubernetes, fora do repo.
# Uso: bash gera-kubeconfig.sh [contexto-admin] [destino]
set -euo pipefail
CTX=${1:-kind-kind}
DEST=${2:-$HOME/.kube/triagem-leitura.yaml}
kubectl --context "$CTX" apply -f "$(dirname "$0")/rbac-triagem-leitura.yaml" >/dev/null
SERVER=$(kubectl config view --raw -o jsonpath="{.clusters[?(@.name==\"$CTX\")].cluster.server}")
CA=$(kubectl config view --raw -o jsonpath="{.clusters[?(@.name==\"$CTX\")].cluster.certificate-authority-data}")
TOKEN=$(kubectl --context "$CTX" -n kube-system create token triagem-leitura --duration=24h)
umask 077
cat > "$DEST" <<KC
apiVersion: v1
kind: Config
current-context: triagem-leitura
clusters:
  - name: triagem
    cluster: {server: "$SERVER", certificate-authority-data: "$CA"}
users:
  - name: triagem-leitura
    user: {token: "$TOKEN"}
contexts:
  - name: triagem-leitura
    context: {cluster: triagem, user: triagem-leitura}
KC
echo "kubeconfig so-leitura em $DEST (token valido por 24h)"
