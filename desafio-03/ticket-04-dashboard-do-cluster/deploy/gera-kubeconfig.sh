#!/usr/bin/env bash
# Gera um kubeconfig com token de uma ServiceAccount, para rodar o retrato com
# a identidade de leitura (ou, no laboratorio, com as identidades de teste).
# Uso: bash gera-kubeconfig.sh <sa> <destino> [duracao=8h] [namespace-do-contexto] [contexto-admin]
set -euo pipefail
SA=$1 DEST=$2 DUR=${3:-8h} NS=${4:-default} CTX=${5:-$(kubectl config current-context)}
SERVER=$(kubectl config view --raw -o jsonpath="{.clusters[?(@.name==\"$CTX\")].cluster.server}")
CA=$(kubectl config view --raw -o jsonpath="{.clusters[?(@.name==\"$CTX\")].cluster.certificate-authority-data}")
TOKEN=$(kubectl --context "$CTX" -n kube-system create token "$SA" --duration="$DUR")
umask 077
cat > "$DEST" <<KC
apiVersion: v1
kind: Config
current-context: $SA
clusters:
  - name: lab
    cluster: {server: "$SERVER", certificate-authority-data: "$CA"}
users:
  - name: $SA
    user: {token: "$TOKEN"}
contexts:
  - name: $SA
    context: {cluster: lab, user: $SA, namespace: $NS}
KC
echo "kubeconfig de $SA em $DEST (token: $DUR)"
