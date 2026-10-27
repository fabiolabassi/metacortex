#!/usr/bin/env bash
# Sobe no cluster local os dois workloads do dashboard com os manifests gerados
# pela skill padrao-de-manifests (Ticket 01):
#   orion-prod  fake-shop   ../ticket-01-padrao-de-manifests/execucoes/escrita-fake-shop/manifests
#   nyx-dev     kube-news   ../workloads/nyx-dev
# "Espelha" as imagens publicas como registry.metacortex.io/... (o papel do Loom)
# e carrega no kind, porque o registry interno nao existe fora do parque.
# Senhas sao geradas aqui e vao so para Secrets no cluster, nunca para arquivo.
set -euo pipefail
AQUI=$(cd "$(dirname "$0")" && pwd)
T04=$(dirname "$AQUI")
CTX=${CTX:-kind-kind}
K="kubectl --context $CTX"

espelha() {  # espelha <origem> <destino>
  docker pull -q "$1" >/dev/null
  # Reconstroi como imagem de plataforma unica: um indice multi-plataforma
  # (caso do kube-news) entra no containerd do kind "incomplete (1/10)" e o
  # kubelet tenta o pull mesmo com IfNotPresent.
  printf "FROM %s\nLABEL io.metacortex.espelho-de=%s\n" "$1" "$1" | docker build -q -t "$2" - >/dev/null
  docker exec "${CTX#kind-}-control-plane" ctr -n k8s.io images rm "$2" >/dev/null 2>&1 || true
  kind load docker-image "$2" --name "${CTX#kind-}" >/dev/null
  echo "espelhada: $1 -> $2"
}

banco() {  # banco <ns> <nome> <db> <usuario>  (cria Secret com senha aleatoria e o Postgres)
  local senha; senha=$(openssl rand -hex 16)
  $K -n "$1" create secret generic "$2" --from-literal=username="$4" --from-literal=password="$senha" \
    --dry-run=client -o yaml | $K apply -f - >/dev/null
  sed -e "s/__NS__/$1/g; s/__NOME__/$2/g; s/__DB__/$3/g; s/__USUARIO__/$4/g" "$AQUI/postgres.yaml" | $K apply -f -
  $K -n "$1" rollout status deploy/"$2" --timeout=120s
}

espelha fabricioveronez/fake-shop:v1 registry.metacortex.io/orion/fake-shop:v1
espelha fabricioveronez/kube-news:v1 registry.metacortex.io/nyx/kube-news:v1

# --- orion-prod: fake-shop ---------------------------------------------------
FS=$T04/../ticket-01-padrao-de-manifests/execucoes/escrita-fake-shop/manifests
$K apply -f "$FS/00-namespace.yaml"
banco orion-prod orion-db ecommerce ecommerce
# DB_HOST do manifesto gerado e "orion-db.orion-prod.svc.cluster.local" (TODO do
# time-orion); o banco de laboratorio atende nesse nome.
$K apply -f "$FS/10-serviceaccount.yaml" -f "$FS/11-serviceaccount-migracao.yaml" -f "$FS/20-configmap.yaml"
$K apply -f "$FS/25-job-fake-shop-migracao.yaml"
$K -n orion-prod wait --for=condition=complete job/orion-fake-shop-migracao --timeout=180s
$K apply -f "$FS/30-deployment-fake-shop.yaml" -f "$FS/31-service-fake-shop.yaml" -f "$FS/32-pdb-fake-shop.yaml"

# --- nyx-dev: kube-news -------------------------------------------------------
NX=$T04/workloads/nyx-dev
$K apply -f "$NX/00-namespace.yaml"
banco nyx-dev nyx-db kubedevnews kubedevnews
$K apply -f "$NX/"

$K -n orion-prod rollout status deploy/orion-fake-shop --timeout=180s
$K -n nyx-dev rollout status deploy/nyx-api --timeout=180s
