#!/usr/bin/env bash
# Reproduz em um cluster kind descartavel os achados de
# docs/revisao-do-padrao.md. Nao toca em cluster do parque.
#
#   bash lab/lab.sh          # cria o cluster (se preciso), roda e imprime
#   bash lab/lab.sh limpar   # apaga o cluster
set -uo pipefail
cd "$(dirname "$0")"
CLUSTER=metacortex-lab
IMG=nginxinc/nginx-unprivileged:1.27-alpine

if [ "${1:-}" = limpar ]; then kind delete cluster --name "$CLUSTER"; exit; fi

kind get clusters 2>/dev/null | grep -qx "$CLUSTER" || kind create cluster --name "$CLUSTER"
kubectl config use-context "kind-$CLUSTER" >/dev/null
docker pull -q "$IMG" >/dev/null && kind load docker-image "$IMG" --name "$CLUSTER" >/dev/null

titulo() { printf '\n\033[1m### %s\033[0m\n' "$1"; }

titulo "Versao do cluster"
kubectl version 2>/dev/null | grep Server

titulo "Manifests de referencia: admissao real (Pods criados sob Pod Security restricted)"
for ns in ../manifests/*/00-namespace.yaml; do kubectl apply -f "$ns" >/dev/null; done
kubectl apply -R -f ../manifests/ >/dev/null
kubectl apply -f 00-namespace.yaml >/dev/null

titulo "Achado 1 e 2 — bloco da 3.2 copiado do wiki"
kubectl apply -f 21-securitycontext-do-wiki.yaml 2>&1

titulo "Achado 3 — seletor errado: Deployment e recusado..."
kubectl apply -f 22-seletor-deployment.yaml 2>&1
titulo "...e Service/PDB sao aceitos sem reclamar"
kubectl apply -f 10-api.yaml 2>&1

titulo "Achado 4 — Pod Security barra o Pod, nao o Deployment"
kubectl apply -f 20-sem-securitycontext.yaml 2>&1

titulo "Achado 6 — nomes"
kubectl apply -f 23-nomes.yaml 2>&1

kubectl apply -f 24-crashloop.yaml -f 25-job-com-probes.yaml >/dev/null
kubectl -n lab-dev rollout status deploy/lab-api --timeout=90s >/dev/null
sleep 30

titulo "Estado dos workloads"
kubectl -n lab-dev get deploy,rs,pods
kubectl -n nyx-prod get pods

titulo "Eventos do ReplicaSet recusado (onde a mensagem do Pod Security aparece)"
kubectl -n lab-dev get events --field-selector reason=FailedCreate -o custom-columns=OBJ:.involvedObject.name,MSG:.message | head -2

titulo "Endpoints (4.6) — repare no aviso de depreciacao"
kubectl -n lab-dev get endpoints -o custom-columns='NOME:.metadata.name,IPS:.subsets[*].addresses[*].ip,PORTAS:.subsets[*].ports[*].port'

titulo "EndpointSlice — o Service de porta errada AINDA lista os IPs"
kubectl -n lab-dev get endpointslices

titulo "Trafego de verdade por cada Service"
kubectl run -n default cliente-lab --image="$IMG" --restart=Never --rm -i --quiet -- sh -c 'sleep 3
  for s in lab-api lab-api-seletor-errado lab-api-porta-errada; do
    if wget -qO /dev/null -T 3 "http://$s.lab-dev/" 2>/dev/null; then r="200 OK"; else r="falhou"; fi
    echo "$s: $r"
  done' 2>&1

titulo "PDB sem alvo"
kubectl -n lab-dev get pdb

titulo "4.1 — container em crash, Pod em fase Running"
kubectl -n lab-dev get pod lab-crashloop -o custom-columns=FASE:.status.phase,RESTARTS:.status.containerStatuses[0].restartCount,ULTIMO:.status.containerStatuses[0].lastState.terminated.reason

titulo "Achado 5 — Job com readinessProbe"
kubectl -n lab-dev get pods -l job-name=lab-job-probes -o custom-columns=NOME:.metadata.name,FASE:.status.phase,READY:.status.containerStatuses[0].ready
